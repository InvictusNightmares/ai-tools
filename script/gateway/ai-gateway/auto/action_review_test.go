package autogateway

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type reviewMustNotClassify struct{}

func (reviewMustNotClassify) Classify(context.Context, Request, PipelineMeta) (Classification, error) {
	panic("action review must not be auto-classified")
}

func TestActionReviewPreservesNativeSchemaAndModel(t *testing.T) {
	body := `{"model":"codex-auto-review","instructions":"Review this exact action","reasoning":{"effort":"low"},"input":"List local files","text":{"format":{"type":"json_schema","name":"guardian","schema":{"type":"object","properties":{"outcome":{"enum":["allow","deny"]}},"required":["outcome"]}}}}`
	seen := ""
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		seen = string(raw)
		if r.Header.Get("User-Agent") != "codex-native-test" {
			t.Error("native UA lost")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"r1","model":"codex-auto-review","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"{\"outcome\":\"allow\"}"}]}],"usage":{"input_tokens":3,"output_tokens":5}}`))
	}))
	defer upstream.Close()
	client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "default", Protocol: "responses", URL: upstream.URL}}}
	for _, decision := range []PreflightDecision{PreflightAllow, PreflightBlock, PreflightUnavailable} {
		seen = ""
		gateway := NewAutoGateway()
		p := &Pipeline{Gateway: gateway, Classifier: reviewMustNotClassify{}, Preflight: fixedPreflight{PreflightResult{Decision: decision}}, Upstream: client, Usage: NewDailyUsageRecorder()}
		s := &HTTPServer{Gateway: gateway, Pipeline: p, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "key"}}
		r := httptest.NewRequest("POST", "/v1/responses", strings.NewReader(body))
		r.Header.Set("User-Agent", "codex-native-test")
		w := httptest.NewRecorder()
		s.ServeHTTP(w, r)
		if decision == PreflightAllow {
			if w.Code != 200 || seen != body {
				t.Fatalf("contract changed: %d %s", w.Code, seen)
			}
			if events := p.Usage.Snapshot(); len(events) != 1 || events[0].Key.Purpose != "action_review" || events[0].Key.ReasoningEffort != ReasoningLow {
				t.Fatal("usage not separated")
			}
		} else if seen != "" || w.Code == 200 {
			t.Fatal("review bypassed Guard")
		}
	}
}

func TestNativeReviewEffortDoesNotRewriteOrInvent(t *testing.T) {
	for _, value := range []string{"none", "minimal", "low", "medium", "high", "xhigh", "max", "", "private-unrecognized-string"} {
		t.Run(value, func(t *testing.T) {
			raw := []byte(`{"reasoning":{"effort":"` + value + `"}}`)
			got := nativeActionReviewEffort(raw)
			if value == "" || value == "private-unrecognized-string" {
				if got != (EffortMapping{}) {
					t.Fatal("invented or logged unrecognized effort", got)
				}
			} else if string(got.Applied) != value || got.Requested != got.Applied || got.Status != EffortApplied {
				t.Fatal(got)
			}
		})
	}
}

func TestNativeReviewEffortAuditKeepsUnknownSeparateFromMismatch(t *testing.T) {
	for _, scenario := range []struct {
		name              string
		applied, reported ReasoningEffort
		mismatch          bool
	}{
		{"provider_default", "", ReasoningLow, false},
		{"provider_omitted", ReasoningLow, "", false},
		{"same", ReasoningLow, ReasoningLow, false},
		{"different", ReasoningLow, ReasoningHigh, true},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			path := t.TempDir() + "/audit.jsonl"
			sink, err := NewJSONLAuditSink(path)
			if err != nil {
				t.Fatal(err)
			}
			pipeline := &Pipeline{AuditSink: sink}
			result := PipelineResult{UpstreamCalled: true, Audit: RouteAudit{Action: "action_review", EffortApplied: scenario.applied}, Upstream: UpstreamResponse{StatusCode: 200, Complete: true, ReportedEffort: scenario.reported}, Decision: RouteDecision{SelectedModel: &Model{Name: ActionReviewModel}}}
			pipeline.finishAudit(PipelineMeta{RequestID: "native-review-effort"}, result, nil)
			audit := lastAudit(t, path)
			if audit.EffortMismatch != scenario.mismatch || audit.EffortApplied != scenario.applied || audit.ReportedEffort != scenario.reported || audit.Stage != "upstream_completed" {
				t.Fatalf("incorrect effort evidence: %+v", audit)
			}
		})
	}
}
