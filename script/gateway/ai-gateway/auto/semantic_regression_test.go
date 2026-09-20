package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

func TestRawProtocolPreservesDevelopmentFieldsAndIgnoresClientEffort(t *testing.T) {
	body := `{"model":"auto","reasoning_effort":"xhigh","reasoning":{"effort":"xhigh"},"temperature":0.4,"max_tokens":123,"response_format":{"type":"json_object"},"messages":[{"role":"user","content":"检查代码"},{"role":"assistant","content":null,"tool_calls":[{"id":"c1","type":"function","function":{"name":"read","arguments":"{}"}}]},{"role":"tool","tool_call_id":"c1","content":"ok"}],"tools":[{"type":"function","function":{"name":"read","description":"读取文件","parameters":{"type":"object"}}}]}`
	r, err := NormalizeProtocolRequest("chat", []byte(body))
	if err != nil {
		t.Fatal(err)
	}
	out, err := BuildProviderPayload("chat", r, BuildProviderParameters("openai", "chat", DefaultCatalog[1], ReasoningLow, false))
	if err != nil {
		t.Fatal(err)
	}
	var p map[string]any
	json.Unmarshal(out, &p)
	if p["reasoning_effort"] != "low" || p["reasoning"] != nil || p["max_tokens"] != float64(123) || p["response_format"] == nil {
		t.Fatal(string(out))
	}
	m := p["messages"].([]any)
	if m[1].(map[string]any)["tool_calls"] == nil || m[2].(map[string]any)["tool_call_id"] != "c1" || r.Tools[0].Description != "读取文件" {
		t.Fatal("tool context dropped")
	}
	r2, _ := NormalizeProtocolRequest("chat", []byte(strings.ReplaceAll(body, "xhigh", "none")))
	if CanonicalRequestDigest(r) != CanonicalRequestDigest(r2) {
		t.Fatal("client effort affects cache")
	}
	r3, _ := NormalizeProtocolRequest("chat", []byte(strings.Replace(body, "123", "124", 1)))
	if CanonicalRequestDigest(r) == CanonicalRequestDigest(r3) {
		t.Fatal("output limit missing from cache")
	}
}
func TestSemanticRejectsUnreadableImageAndProviderStoredHistory(t *testing.T) {
	r, _ := NormalizeProtocolRequest("chat", []byte(`{"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"https://example.invalid/a.png"}}]}]}`))
	if _, err := splitSemanticInput(r); err == nil {
		t.Fatal("unreadable image silently accepted")
	}
	if _, err := NormalizeProtocolRequest("responses", []byte(`{"previous_response_id":"r1","input":"继续"}`)); err == nil {
		t.Fatal("hidden history accepted")
	}
	r, err := NormalizeProtocolRequest("responses", []byte(`{"instructions":"system context","input":[{"role":"user","content":"fix"},{"type":"function_call_output","call_id":"c1","output":"failed"}]}`))
	if err != nil || r.Messages[0].Role != "system" || r.Messages[len(r.Messages)-1].Role != "tool" {
		t.Fatalf("%+v %v", r, err)
	}
}
func TestPilotIdentityRunsBeforeGuardAndRejectsForgedKeyID(t *testing.T) {
	authCalls, guardCalls := 0, 0
	status := 200
	auth := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { authCalls++; w.WriteHeader(status) }))
	defer auth.Close()
	p := &Pipeline{Gateway: NewAutoGateway(), Preflight: preflightFunc(func(context.Context, Request) (PreflightResult, error) {
		guardCalls++
		return PreflightResult{Decision: PreflightBlock}, nil
	})}
	server := &HTTPServer{Gateway: p.Gateway, Pipeline: p, Identity: &PilotIdentityResolver{Token: "synthetic-token", APIKeyID: "141", CheckURL: auth.URL}}
	for _, item := range []struct {
		token    string
		status   int
		expected int
	}{{"invalid", 200, 401}, {"synthetic-token", 200, 403}, {"synthetic-token", 401, 401}, {"synthetic-token", 503, 503}} {
		status = item.status
		r := httptest.NewRequest("POST", "/v1/chat/completions", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"hello"}]}`))
		r.Header.Set("Authorization", "Bearer "+item.token)
		r.Header.Set("X-Gateway-API-Key-ID", "141")
		w := httptest.NewRecorder()
		server.ServeHTTP(w, r)
		if w.Code != item.expected {
			t.Fatalf("%d %s", w.Code, w.Body.String())
		}
	}
	if authCalls != 3 || guardCalls != 1 {
		t.Fatalf("auth=%d guard=%d", authCalls, guardCalls)
	}
	a := PipelineMeta{Region: "tokyo", APIKeyID: "a", SessionID: "same"}
	b := a
	b.APIKeyID = "b"
	if sessionStoreKey(a) == sessionStoreKey(b) {
		t.Fatal("cross-key state collision")
	}
}

type preflightFunc func(context.Context, Request) (PreflightResult, error)

func (f preflightFunc) Evaluate(c context.Context, r Request) (PreflightResult, error) {
	return f(c, r)
}
func TestObservedStreamCompletionUsageAndFailure(t *testing.T) {
	for _, item := range []struct {
		body     string
		complete bool
		tokens   int
	}{
		{"data: {\"id\":\"r1\",\"model\":\"judge\",\"usage\":{\"prompt_tokens\":4}}\n\ndata: [DONE]", true, 4},
		{"data: {\"id\":\"r1\",\"model\":\"judge\"}\n\n", false, 0},
		{"data: {\"type\":\"error\"}\n\ndata: [DONE]\n\n", false, 0},
		{"data: {\"type\":\"message_start\",\"message\":{\"id\":\"r1\",\"model\":\"judge\",\"usage\":{\"input_tokens\":4,\"cache_read_input_tokens\":6}}}\n\ndata: {\"type\":\"message_delta\",\"usage\":{\"output_tokens\":3}}\n\ndata: {\"type\":\"message_stop\"}\n\n", true, 10},
	} {
		b := &observedSSEBody{ReadCloser: io.NopCloser(strings.NewReader(item.body))}
		io.Copy(io.Discard, b)
		if b.Complete != item.complete || NormalizeUsage(b.Usage).PromptTokens != item.tokens {
			t.Fatalf("%+v", b)
		}
	}
}
func TestResultAuditRecordsActualResponseAndFailedAttempt(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Request-ID", "provider-id")
		w.Write([]byte(`{"id":"reply-id","model":"actual-model","choices":[{"finish_reason":"stop","message":{"content":"ok"}}],"usage":{"prompt_tokens":11,"completion_tokens":7}}`))
	}))
	defer upstream.Close()
	path := t.TempDir() + "/audit"
	sink, _ := NewJSONLAuditSink(path)
	p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, AuditSink: sink, Upstream: &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Protocol: "chat", URL: upstream.URL}}}, Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
		return classificationFromAssessment(r, assessment("coding", "bounded")), nil
	})}
	r, err := p.ExecuteWithMeta(context.Background(), "chat", "", "auto", Request{Messages: []Message{{Role: "user", Content: "secret task text"}}}, 0, false, false, false, false, PipelineMeta{RequestID: "known", Region: "tokyo", APIKeyID: "141", SessionID: "s"})
	if err != nil || !r.Upstream.Complete {
		t.Fatalf("%+v %v", r, err)
	}
	raw, _ := os.ReadFile(path)
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	if len(lines) != 3 {
		t.Fatal(string(raw))
	}
	var last RouteAudit
	json.Unmarshal([]byte(lines[2]), &last)
	if last.UpstreamTransport != "buffered_json" || last.Stage != "upstream_completed" || last.ResponseModel != "actual-model" || last.UpstreamRequestID != "provider-id" || last.Usage.PromptTokens != 11 || last.RequestID != "known" || strings.Contains(string(raw), "secret task text") {
		t.Fatal(string(raw))
	}
}
func TestClassifierUnavailableIsHTTP503(t *testing.T) {
	p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, Classifier: taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) {
		return Classification{}, ErrClassifierUnavailable
	})}
	s := &HTTPServer{Gateway: p.Gateway, Pipeline: p}
	r := httptest.NewRequest("POST", "/v1/chat/completions", strings.NewReader(`{"messages":[{"role":"user","content":"hello"}]}`))
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 503 {
		t.Fatalf("%d", w.Code)
	}
}
func TestAuditFailureDoesNotLeaveCoalescedCallPending(t *testing.T) {
	p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, AuditSink: failStartedAudit{}, Cache: NewMemoryResponseCache(), CachePolicy: DefaultResponseCachePolicy(), Upstream: &HTTPUpstreamClient{}, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "k", ModelRevision: "v1", CacheSecret: "s"}}
	for i := 0; i < 2; i++ {
		ctx, cancel := context.WithTimeout(context.Background(), time.Second)
		_, err := p.Execute(ctx, "chat", "deepseek", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 0, false, false, false, false)
		cancel()
		if err == nil || errors.Is(err, context.DeadlineExceeded) {
			t.Fatal(err)
		}
	}
}

type failStartedAudit struct{}

func (failStartedAudit) WriteRouteAudit(a RouteAudit) error {
	if a.Stage == "upstream_started" {
		return errors.New("disk full")
	}
	return nil
}

func TestAstraEffortMappingUsesVerifiedSupport(t *testing.T) {
	astra := ModelByName("gpt-6-astra", DefaultCatalog)
	for _, target := range []ReasoningEffort{ReasoningNone, ReasoningMinimal, ReasoningLow, ReasoningMedium, ReasoningHigh, ReasoningXHigh, ReasoningMax} {
		mapped := BuildProviderParameters("openai", "chat", *astra, target, false)
		expected := target
		if target == ReasoningNone || target == ReasoningMinimal {
			expected = ReasoningLow
		}
		if mapped.Reasoning.Applied != expected || mapped.ReasoningParameter["reasoning_effort"] != string(expected) {
			t.Fatalf("%s %+v", target, mapped)
		}
	}
	if classifierEffort("gpt-6-astra", "gpt-6-astra") != "low" {
		t.Fatal("invalid Astra primary effort")
	}
	if classifierEffort("gpt-5.6-sol", "gpt-5.6-sol") != "none" {
		t.Fatal("valid Sol effort lost")
	}
}
