package autogateway

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestEveryModelEffortAcrossProtocols(t *testing.T) {
	targets := []ReasoningEffort{ReasoningNone, ReasoningMinimal, ReasoningLow, ReasoningMedium, ReasoningHigh, ReasoningXHigh, ReasoningMax}
	for _, model := range DefaultCatalog {
		for _, protocol := range []string{"chat", "responses"} {
			for _, target := range targets {
				t.Run(model.Name+"/"+protocol+"/"+string(target), func(t *testing.T) {
					expected := target
					if target == ReasoningMinimal || (model.Name == "gpt-6-astra" && target == ReasoningNone) {
						expected = ReasoningLow
					}
					if model.Provider == "deepseek" && (target == ReasoningMedium || target == ReasoningXHigh) {
						expected = ReasoningHigh
					}
					p := BuildProviderParameters(model.Provider, protocol, model, target, false)
					body := `{"model":"auto","reasoning_effort":"low","reasoning":{"effort":"low"},"thinking":{"type":"disabled"},"output_config":{"effort":"low"},"messages":[{"role":"user","content":"检查实现 / check implementation"}]}`
					if protocol == "responses" {
						body = `{"model":"auto","reasoning":{"effort":"low"},"input":"检查实现 / check implementation"}`
					}
					r, err := NormalizeProtocolRequest(protocol, []byte(body))
					if err != nil {
						t.Fatal(err)
					}
					wire, err := BuildProviderPayload(protocol, r, p)
					if err != nil {
						t.Fatal(err)
					}
					var payload map[string]any
					if json.Unmarshal(wire, &payload) != nil {
						t.Fatal("bad JSON")
					}
					actual := payload["reasoning_effort"]
					if protocol == "responses" {
						if v, ok := payload["reasoning"].(map[string]any); ok {
							actual = v["effort"]
						} else {
							t.Fatal("missing reasoning.effort")
						}
					}
					if p.Reasoning.Applied != expected || actual != string(expected) || payload["output_config"] != nil {
						t.Fatalf("target=%s expected=%s mapping=%+v wire=%s", target, expected, p.Reasoning, wire)
					}
				})
			}
		}
	}
}

func TestMessagesBridgeAlwaysReceivesExplicitEffort(t *testing.T) {
	// Tokyo Sub2API 0.1.161 ignores thinking.type and defaults to medium
	// without output_config.effort, including when thinking is disabled.
	for _, model := range DefaultCatalog {
		t.Run(model.Name, func(t *testing.T) {
			p := BuildProviderParameters(model.Provider, "anthropic", model, ReasoningNone, false)
			r, err := NormalizeProtocolRequest("anthropic", []byte(`{"model":"auto","max_tokens":128,"thinking":{"type":"enabled"},"output_config":{"effort":"high"},"messages":[{"role":"user","content":"Explain HTTP 304"}]}`))
			if err != nil {
				t.Fatal(err)
			}
			wire, err := BuildProviderPayload("anthropic", r, p)
			if err != nil {
				t.Fatal(err)
			}
			var body map[string]any
			json.Unmarshal(wire, &body)
			effort := "medium" // Actual bridge's fallback, not the desired result.
			if config, ok := body["output_config"].(map[string]any); ok {
				if value, ok := config["effort"].(string); ok {
					effort = value
				}
			}
			expected := "none"
			if model.Name == "gpt-6-astra" {
				expected = "low"
			}
			if effort != expected || p.Reasoning.Parameter != "output_config.effort" {
				t.Fatalf("bridge will receive %s, expected %s; parameter=%s", effort, expected, p.Reasoning.Parameter)
			}
		})
	}
}

func TestReportedDowngradeCannotPopulateHigherEffortCache(t *testing.T) {
	p, u := cacheTestPipeline()
	p.Classifier = taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
		return classificationFromAssessment(r, assessment("reasoning", "exceptional")), nil
	})
	u.response.ReportedEffort = ReasoningHigh
	for i := 0; i < 2; i++ {
		r, err := executeCacheTest(p, "responses")
		if err != nil || r.CacheEligible || r.CacheReason != "upstream_effort_mismatch" || r.Decision.ReasoningEffort != ReasoningXHigh {
			t.Fatalf("result=%+v error=%v", r, err)
		}
	}
	if u.calls != 2 {
		t.Fatal("downgraded response was reused as xhigh")
	}
}

func TestBufferedAndStreamReportedEffortPreserved(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, `{"id":"r","model":"gpt-6-astra","status":"completed","output":[],"reasoning":{"effort":"high"}}`)
	}))
	defer server.Close()
	u := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "responses", URL: server.URL}}}
	r, err := u.Complete(context.Background(), UpstreamRequest{Provider: "openai", Protocol: "responses", Payload: []byte(`{}`)})
	if err != nil || r.ReportedEffort != ReasoningHigh {
		t.Fatalf("%+v %v", r, err)
	}
	b := &observedSSEBody{ReadCloser: io.NopCloser(strings.NewReader("data: {\"type\":\"response.completed\",\"response\":{\"id\":\"r\",\"model\":\"gpt-6-astra\",\"reasoning\":{\"effort\":\"high\"}}}\n\n"))}
	_, _ = io.Copy(io.Discard, b)
	if b.ReportedEffort != ReasoningHigh || !b.Complete {
		t.Fatal("stream effort missing")
	}
}

func TestResponsesClientConfigurationCannotOverrideAutoEffort(t *testing.T) {
	_, err := NormalizeProtocolRequest("responses", []byte(`{"input":[{"role":"user","content":"继续"},{"type":"configuration_update","reasoning":{"effort":"low"}}]}`))
	if err == nil {
		t.Fatal("client input configuration_update can override generated effort")
	}
}

func TestNativeEffortMatchesUsageAuditAndCache(t *testing.T) {
	for _, name := range []string{"deepseek-flash", "gpt-6-astra"} {
		model := *ModelByName(name, DefaultCatalog)
		target, native := ReasoningXHigh, ReasoningHigh
		if name == "gpt-6-astra" {
			target, native = ReasoningNone, ReasoningLow
		}
		decision := RouteDecision{SelectedModel: &model, ReasoningEffort: target}
		usage := NewDailyUsageRecorder()
		pipeline := &Pipeline{Usage: usage}
		pipeline.recordUsage(time.Now(), PipelineMeta{Region: "tokyo", APIKeyID: "141"}, decision, NewRouteState(), nil, true, true, false)
		for key := range usage.entries {
			if key.ReasoningEffort != native {
				t.Errorf("%s usage=%s want=%s", name, key.ReasoningEffort, native)
			}
		}
		audit := BuildRouteAudit(time.Now(), "auto", model.Provider, "chat", Request{}, decision, Classification{})
		if audit.EffectiveReasoning != native || audit.EffortApplied != native {
			t.Errorf("%s audit=%+v", name, audit)
		}
		meta := PipelineMeta{Region: "tokyo", APIKeyID: "141", CacheSecret: "test-secret", ModelRevision: "test"}
		a, err := BuildPipelineCacheKey(meta, model.Provider, "chat", model, target, Request{})
		b, err2 := BuildPipelineCacheKey(meta, model.Provider, "chat", model, native, Request{})
		if err != nil || err2 != nil || a != b {
			t.Errorf("%s identical applied effort gets different cache", name)
		}
	}
}
