package autogateway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestTokenCountAuditsToolBindingFailureAndCompletion(t *testing.T) {
	for _, missingBinding := range []bool{true, false} {
		t.Run(map[bool]string{true: "missing_tool_binding", false: "completed"}[missingBinding], func(t *testing.T) {
			path := t.TempDir() + "/audit.jsonl"
			sink, err := NewJSONLAuditSink(path)
			if err != nil {
				t.Fatal(err)
			}
			g := NewAutoGateway()
			p := &Pipeline{Gateway: g, AuditSink: sink, Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}},
				StateStore: NewMemorySessionStateStore(), Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
					return classificationFromAssessment(r, assessment("coding", "bounded")), nil
				})}
			calls := 0
			s := &HTTPServer{Gateway: g, Pipeline: p, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "141"},
				TokenCounter: countFunc(func(context.Context, []byte, http.Header, string) (int, error) {
					calls++
					return 42, nil
				})}
			body := `{"model":"auto","messages":[{"role":"user","content":"private fixture"}]}`
			if missingBinding {
				body = `{"model":"auto","messages":[{"role":"user","content":"private fixture"},{"role":"assistant","content":[{"type":"tool_use","id":"unknown-call","name":"Read","input":{}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":"unknown-call","content":"private result"}]}]}`
			}
			w := httptest.NewRecorder()
			s.ServeHTTP(w, httptest.NewRequest("POST", "/v1/messages/count_tokens", strings.NewReader(body)))
			raw, err := os.ReadFile(path)
			if err != nil || len(strings.TrimSpace(string(raw))) == 0 {
				t.Fatalf("missing token-count outcome audit: %v", err)
			}
			lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
			var audit RouteAudit
			if json.Unmarshal([]byte(lines[len(lines)-1]), &audit) != nil {
				t.Fatal("invalid audit")
			}
			if audit.RequestID != w.Header().Get("X-Gateway-Request-ID") || audit.PreflightDecision != PreflightAllow || strings.Contains(string(raw), "private") {
				t.Fatalf("missing correlation/safety result or content leak: %+v", audit)
			}
			if missingBinding {
				if w.Code != 503 || calls != 0 || audit.Stage != "routing_unavailable" || audit.UpstreamCalled {
					t.Fatalf("unlogged tool rejection or upstream call: status=%d calls=%d audit=%+v", w.Code, calls, audit)
				}
			} else if w.Code != 200 || calls != 1 || audit.Stage != "token_count_completed" || !audit.ResponseComplete || audit.HTTPStatus != 200 || audit.ClassifierVersion != SemanticPolicyVersion {
				t.Fatalf("incomplete success audit: status=%d calls=%d audit=%+v", w.Code, calls, audit)
			}
		})
	}
}

type countFunc func(context.Context, []byte, http.Header, string) (int, error)

func (f countFunc) Count(c context.Context, b []byte, h http.Header, id string) (int, error) {
	return f(c, b, h, id)
}

func TestTokenCountGuardAndStateBoundary(t *testing.T) {
	for _, verdict := range []PreflightDecision{PreflightBlock, PreflightUnavailable, PreflightAllow} {
		t.Run(string(verdict), func(t *testing.T) {
			g := NewAutoGateway()
			calls, classCalls := 0, 0
			p := &Pipeline{Gateway: g, Preflight: fixedPreflight{result: PreflightResult{Decision: verdict}}, Classifier: taskClassifierFunc(func(_ context.Context, r Request, meta PipelineMeta) (Classification, error) {
				classCalls++
				if meta.ClientHeaders.Get("X-API-Key") != "synthetic" {
					t.Error("token count classifier authentication missing")
				}
				return classificationFromAssessment(r, assessment("coding", "bounded")), nil
			})}
			s := &HTTPServer{Gateway: g, Pipeline: p, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "141"}, TokenCounter: countFunc(func(_ context.Context, b []byte, _ http.Header, id string) (int, error) {
				calls++
				var payload map[string]any
				json.Unmarshal(b, &payload)
				if payload["model"] == "claude-opus-5" || id == "" {
					t.Fatal("missing Auto selection or ID")
				}
				return 42, nil
			})}
			req := httptest.NewRequest("POST", "/v1/messages/count_tokens", strings.NewReader(`{"model":"claude-opus-5","messages":[{"role":"user","content":"实现本地校验 / implement validation"}]}`))
			req.Header.Set("X-API-Key", "synthetic")
			w := httptest.NewRecorder()
			s.ServeHTTP(w, req)
			want := 503
			if verdict == PreflightBlock {
				want = 403
			}
			if verdict == PreflightAllow {
				want = 200
			}
			if w.Code != want || (verdict != PreflightAllow && (calls != 0 || classCalls != 0)) || (verdict == PreflightAllow && (calls != 1 || classCalls != 1)) || g.State.Turn != 0 || g.State.HasCurrent {
				t.Fatalf("status=%d count=%d classifier=%d state=%+v", w.Code, calls, classCalls, g.State)
			}
		})
	}
}

func TestHTTPTokenCounterValidatesResponse(t *testing.T) {
	response := `{"input_tokens":12}`
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("X-API-Key") != "synthetic" || r.Header.Get("anthropic-version") == "" {
			t.Error("headers missing")
		}
		w.Write([]byte(response))
	}))
	defer server.Close()
	c := &HTTPTokenCounter{URL: server.URL}
	headers := http.Header{"X-Api-Key": []string{"synthetic"}}
	n, err := c.Count(context.Background(), []byte(`{}`), headers, "request")
	if n != 12 || err != nil {
		t.Fatalf("%d %v", n, err)
	}
	for _, bad := range []string{`{}`, `{"input_tokens":-1}`, `{"input_tokens":1,"error":{"message":"bad"}}`} {
		response = bad
		if _, err = c.Count(context.Background(), []byte(`{}`), headers, "request"); err == nil {
			t.Fatal("invalid count accepted")
		}
	}
}

func TestTokenCountUnsupportedUsesMarkedEstimate(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("known unsupported counter must not be called")
		w.WriteHeader(404)
		w.Write([]byte(`{"type":"error","error":{"type":"not_found_error","message":"Token counting is not supported by upstream"}}`))
	}))
	defer upstream.Close()
	p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}}
	s := &HTTPServer{Gateway: p.Gateway, Pipeline: p, TokenCounter: &HTTPTokenCounter{URL: upstream.URL, EstimateModels: map[string]bool{"deepseek-flash": true}}}
	w := httptest.NewRecorder()
	s.ServeHTTP(w, httptest.NewRequest("POST", "/v1/messages/count_tokens", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"解释配置 / explain config"}]}`)))
	var out struct {
		InputTokens int `json:"input_tokens"`
	}
	json.Unmarshal(w.Body.Bytes(), &out)
	if w.Code != 200 || out.InputTokens <= 0 || w.Header().Get("X-Gateway-Count-Method") != "utf8_bytes_estimate" {
		t.Fatalf("unsupported count must expose estimate: status=%d method=%s", w.Code, w.Header().Get("X-Gateway-Count-Method"))
	}
}

func TestTokenCountRejectsCorruptSharedState(t *testing.T) {
	path := t.TempDir() + "/state.json"
	store, err := NewFileSessionStateStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(path, []byte("corrupt"), 0600); err != nil {
		t.Fatal(err)
	}
	gateway := NewAutoGateway()
	pipeline := &Pipeline{Gateway: gateway, StateStore: store, Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}}
	server := &HTTPServer{Gateway: gateway, Pipeline: pipeline, Meta: PipelineMeta{SessionID: "fixture"}, TokenCounter: countFunc(func(context.Context, []byte, http.Header, string) (int, error) {
		t.Error("corrupt state reached counter")
		return 1, nil
	})}
	recorder := httptest.NewRecorder()
	server.ServeHTTP(recorder, httptest.NewRequest("POST", "/v1/messages/count_tokens", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"hello"}]}`)))
	if recorder.Code != 503 || !strings.Contains(recorder.Body.String(), "session_state_unavailable") {
		t.Fatalf("%d %s", recorder.Code, recorder.Body.String())
	}
}
