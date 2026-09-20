package autogateway

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type compactEndpointUpstream struct {
	calls int
	valid bool
	last  UpstreamRequest
}

func (u *compactEndpointUpstream) Complete(_ context.Context, request UpstreamRequest) (UpstreamResponse, error) {
	u.calls++
	u.last = request
	output := `[{"type":"message","role":"assistant","content":[]}]`
	if u.valid {
		output = `[{"id":"cmp_fixture","type":"compaction","encrypted_content":"opaque-original"}]`
	}
	return UpstreamResponse{StatusCode: 200, Complete: true, Body: []byte(`{"id":"resp_fixture","model":"gpt-5.6-luna","created_at":123,"output":` + output + `,"usage":{"input_tokens":10,"output_tokens":2}}`), Usage: map[string]any{"input_tokens": 10, "output_tokens": 2}}, nil
}

func TestLegacyCompactUsesRealNativeStateAndCheckedHistory(t *testing.T) {
	for _, decision := range []PreflightDecision{PreflightAllow, PreflightBlock, PreflightUnavailable} {
		for _, valid := range []bool{true, false} {
			u := &compactEndpointUpstream{valid: valid}
			gateway := NewAutoGateway()
			server := &HTTPServer{Gateway: gateway, Pipeline: &Pipeline{Gateway: gateway, Preflight: fixedPreflight{result: PreflightResult{Decision: decision}}, Upstream: u}}
			w := httptest.NewRecorder()
			raw := `{"model":"auto","stream":true,"input":[{"role":"developer","content":"preserve instructions"},{"role":"user","content":"remember marker"},{"role":"assistant","content":"marker is APRICOT"}]}`
			server.ServeHTTP(w, httptest.NewRequest("POST", "/v1/responses/compact", strings.NewReader(raw)))
			if decision != PreflightAllow {
				want := 503
				if decision == PreflightBlock {
					want = 403
				}
				if w.Code != want || u.calls != 0 {
					t.Fatalf("Guard order lost: %d calls=%d", w.Code, u.calls)
				}
				continue
			}
			if u.calls != 1 || u.last.Protocol != "responses" || u.last.Request.Stream || !strings.Contains(string(u.last.Payload), `"compaction_trigger"`) {
				t.Fatal("compact transport was not native unary", u.last)
			}
			if !valid {
				if w.Code != 502 {
					t.Fatalf("ordinary answer counted as compact: %d", w.Code)
				}
				continue
			}
			var body map[string]any
			if json.Unmarshal(w.Body.Bytes(), &body) != nil || w.Code != 200 || body["object"] != "response.compaction" {
				t.Fatal("bad compact response", w.Body.String())
			}
			items := body["output"].([]any)
			if len(items) != 3 || items[2].(map[string]any)["encrypted_content"] != "opaque-original" || strings.Contains(w.Body.String(), "marker is APRICOT") {
				t.Fatal("native state or retained messages changed")
			}
		}
	}
}

func TestLegacyCompactRejectsInvalidInputAndRetainsCheckedText(t *testing.T) {
	for _, raw := range []string{`{}`, `{"input":[]}`, `{"input":[1]}`, `{"input":[{"type":"compaction_trigger"}]}`} {
		if _, err := prepareCompactRequest([]byte(raw)); err == nil {
			t.Fatal("invalid input accepted", raw)
		}
	}
	prepared, err := prepareCompactRequest([]byte(`{"input":"checked text"}`))
	if err != nil {
		t.Fatal(err)
	}
	request, _ := NormalizeProtocolRequest("responses", prepared)
	upstream := &compactEndpointUpstream{valid: true}
	response, _ := upstream.Complete(context.Background(), UpstreamRequest{})
	body, err := compactResponseBody(request, response)
	if err != nil || !strings.Contains(string(body), "checked text") {
		t.Fatal("checked text lost", err)
	}
}

func TestNativeCompactionRequiresSupportedModelAfterGuard(t *testing.T) {
	raw := []byte(`{"input":[{"role":"user","content":"remember the fixture"},{"type":"compaction_trigger"}]}`)
	request, err := NormalizeProtocolRequest("responses", raw)
	if err != nil || !request.CompactionTrigger {
		t.Fatal("native operation lost", err)
	}
	for _, allow := range []bool{true, false} {
		decision := PreflightUnavailable
		if allow {
			decision = PreflightAllow
		}
		pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: decision}}, Classifier: taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) {
			t.Error("protocol operation sent to task classifier")
			return Classification{}, nil
		})}
		result, err := pipeline.Plan(context.Background(), "responses", "", "auto", request, 0, false, false, false, false, PipelineMeta{Region: "tokyo", APIKeyID: "fixture", SessionID: "fixture"})
		if !allow {
			if err == nil || result.Decision.SelectedModel != nil {
				t.Fatal("Guard did not fail closed")
			}
			continue
		}
		if err != nil || result.Decision.SelectedModel == nil || result.Decision.SelectedModel.Provider != "openai" || result.Decision.ReasoningEffort != ReasoningLow {
			t.Fatalf("native operation routed incorrectly: %+v %v", result.Decision, err)
		}
		if ok, _ := DefaultResponseCachePolicy().Eligible(request, PreflightAllow, 10); ok {
			t.Fatal("opaque compaction response cached")
		}
	}
}

func TestCompactionStatePreservesOpaqueBytesAndScansOtherMetadata(t *testing.T) {
	encrypted := "gAAAA_native_opaque_fixture"
	raw := []byte(`{"input":[{"type":"compaction","id":"cmp_fixture","encrypted_content":"` + encrypted + `","metadata":{"note":"inspect this plaintext"}},{"role":"user","content":"continue the task"}]}`)
	request, err := NormalizeProtocolRequest("responses", raw)
	if err != nil {
		t.Fatal(err)
	}
	guard := nativeTestGuard(t, func(view string) string {
		if strings.Contains(view, encrypted) || !strings.Contains(view, "inspect this plaintext") {
			t.Error("opaque state leaked or plaintext metadata skipped")
		}
		return view
	})
	defer guard.Close()
	checked, err := (&HTTPPreflightChecker{Endpoint: guard.URL}).Evaluate(context.Background(), request)
	if err != nil || checked.SanitizedRequest == nil || !bytesEqualJSON(checked.SanitizedRequest.RawPayload, request.RawPayload) {
		t.Fatal("native state changed", err)
	}
	prepared := *checked.SanitizedRequest
	if !prepared.CompactionState || len(prepared.Native.ClassifierHistory) != 1 || nativeGuardScope(prepared.Native) != NativeStateGuardScope {
		t.Fatal("native state capability or scope lost")
	}
	classification := classificationFromAssessment(prepared, assessment("coding", "bounded"))
	for _, model := range FilterCapableModels(classification, DefaultCatalog) {
		if model.Provider != "openai" {
			t.Fatal("opaque state sent to unsupported provider")
		}
	}
	tamper := nativeTestGuard(t, func(view string) string {
		return strings.ReplaceAll(view, "inspect this plaintext", "changed metadata")
	})
	defer tamper.Close()
	bad, err := (&HTTPPreflightChecker{Endpoint: tamper.URL}).Evaluate(context.Background(), request)
	if err == nil && bad.Decision == PreflightAllow {
		t.Fatal("modified metadata restored as original")
	}
}

func TestClassifierUsesNativeCompactionHistoryAndRetainsBillingCorrelation(t *testing.T) {
	guard := nativeTestGuard(t, nil)
	defer guard.Close()
	request, _ := NormalizeProtocolRequest("responses", []byte(`{"input":[{"type":"compaction","id":"cmp_fixture","encrypted_content":"opaque-fixture"},{"role":"user","content":"continue the task"}]}`))
	checked, err := (&HTTPPreflightChecker{Endpoint: guard.URL}).Evaluate(context.Background(), request)
	if err != nil {
		t.Fatal(err)
	}
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if r.URL.Path != "/responses" || !strings.Contains(string(body), `"type":"compaction"`) || !strings.Contains(string(body), "opaque-fixture") {
			t.Error("classifier lost native context")
		}
		w.Header().Set("X-Client-Request-ID", "billing-classifier-fixture")
		text, _ := json.Marshal(assessment("coding", "bounded"))
		json.NewEncoder(w).Encode(map[string]any{"id": "resp_fixture", "model": "gpt-5.6-luna", "status": "completed", "output": []any{map[string]any{"type": "message", "content": []any{map[string]any{"type": "output_text", "text": string(text)}}}}, "usage": map[string]int{"input_tokens": 12, "output_tokens": 4}})
	}))
	defer upstream.Close()
	var events []UsageEvent
	classifier := &SemanticClassifier{Endpoint: upstream.URL + "/chat/completions", Model: "gpt-5.6-luna", ReviewerModel: "gpt-5.6-sol", OnUsage: func(event UsageEvent) error {
		events = append(events, event)
		return nil
	}}
	_, err = classifier.Classify(context.Background(), *checked.SanitizedRequest, PipelineMeta{})
	if err != nil || len(events) != 2 {
		t.Fatal("native classifier failed or billing correlation missing", err)
	}
	for _, event := range events {
		if event.UpstreamClientRequestID != "billing-classifier-fixture" || !event.UsageReported || !event.Success {
			t.Fatalf("classifier attempt lost billing correlation: %+v", event)
		}
	}
}
