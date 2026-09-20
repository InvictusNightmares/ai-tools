package autogateway

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// This is a contract stub, not a credential detector. Actual detector/API
// integration is exercised by the cross-module isolated smoke script.
func boundGuardResponse(t *testing.T, r *http.Request) map[string]any {
	t.Helper()
	var body struct {
		ProviderPayload string `json:"provider_payload"`
	}
	if json.NewDecoder(r.Body).Decode(&body) != nil {
		t.Error("invalid Guard input")
	}
	digest := sha256.Sum256([]byte(body.ProviderPayload))
	return map[string]any{"decision": "allow", "input_sha256": hex.EncodeToString(digest[:]), "redaction_version": "credential-redaction-v1", "sanitized_payload": strings.ReplaceAll(body.ProviderPayload, "fixtureplain", "<REDACTED:secret>")}
}

func TestRedactedInputReachesEveryEgressPath(t *testing.T) {
	for _, tc := range []struct {
		name, path, body, response string
		stream, count              bool
	}{
		{"chat", "/v1/chat/completions", `{"model":"auto","messages":[{"role":"user","content":"Explain password=fixtureplain"}]}`, `{"id":"c","model":"deepseek-flash","choices":[{"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}]}`, false, false},
		{"responses", "/v1/responses", `{"model":"auto","input":"Explain password=fixtureplain"}`, `{"id":"r","model":"deepseek-flash","status":"completed","output":[]}`, false, false},
		{"messages", "/v1/messages", `{"model":"auto","messages":[{"role":"user","content":"Explain password=fixtureplain"}]}`, `{"id":"m","model":"deepseek-flash","type":"message","role":"assistant","stop_reason":"end_turn","content":[{"type":"text","text":"ok"}]}`, false, false},
		{"chat_stream", "/v1/chat/completions", `{"model":"auto","stream":true,"messages":[{"role":"user","content":"Explain password=fixtureplain"}]}`, "data: {\"id\":\"c\",\"model\":\"deepseek-flash\",\"choices\":[{\"delta\":{\"content\":\"ok\"},\"finish_reason\":\"stop\"}]}\n\ndata: [DONE]\n\n", true, false},
		{"responses_stream", "/v1/responses", `{"model":"auto","stream":true,"input":"Explain password=fixtureplain"}`, "data: {\"type\":\"response.completed\",\"response\":{\"id\":\"r\",\"model\":\"deepseek-flash\",\"status\":\"completed\",\"output\":[]}}\n\n", true, false},
		{"messages_stream", "/v1/messages", `{"model":"auto","stream":true,"messages":[{"role":"user","content":"Explain password=fixtureplain"}]}`, "data: {\"type\":\"message_start\",\"message\":{\"id\":\"m\",\"model\":\"deepseek-flash\"}}\n\ndata: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"end_turn\"}}\n\ndata: {\"type\":\"message_stop\"}\n\n", true, false},
		{"count", "/v1/messages/count_tokens", `{"model":"claude-opus-5","messages":[{"role":"user","content":"Explain password=fixtureplain"}]}`, `{"input_tokens":12}`, false, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			guardCalls, classCalls, upstreamCalls := 0, 0, 0
			guard := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				guardCalls++
				json.NewEncoder(w).Encode(boundGuardResponse(t, r))
			}))
			defer guard.Close()
			assertSafe := func(b []byte) {
				t.Helper()
				if strings.Contains(string(b), "fixtureplain") || !strings.Contains(string(b), "REDACTED") {
					t.Error("egress did not use redacted payload")
				}
			}
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				upstreamCalls++
				b, _ := io.ReadAll(r.Body)
				assertSafe(b)
				if tc.stream {
					w.Header().Set("Content-Type", "text/event-stream")
				} else {
					w.Header().Set("Content-Type", "application/json")
				}
				w.Write([]byte(tc.response))
			}))
			defer upstream.Close()
			client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Protocol: "chat", URL: upstream.URL}, {Protocol: "responses", URL: upstream.URL}, {Protocol: "anthropic", URL: upstream.URL}}}
			p := &Pipeline{Gateway: NewAutoGateway(), Preflight: &HTTPPreflightChecker{Endpoint: guard.URL}, Upstream: client, Cache: NewMemoryResponseCache(), CachePolicy: DefaultResponseCachePolicy(), Meta: PipelineMeta{Region: "tokyo", APIKeyID: "test", ModelRevision: "r3", CacheSecret: "synthetic"}, Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
				classCalls++
				assertSafe(r.RawPayload)
				for _, m := range r.Messages {
					if strings.Contains(m.Content, "fixtureplain") {
						t.Error("semantic view leaked")
					}
				}
				return classificationFromAssessment(r, assessment("general_qa", "trivial")), nil
			})}
			s := &HTTPServer{Gateway: p.Gateway, Pipeline: p, StreamClient: client, TokenCounter: &HTTPTokenCounter{URL: upstream.URL}, Meta: p.Meta}
			repeat := 1
			if !tc.stream && !tc.count {
				repeat = 2
			}
			for i := 0; i < repeat; i++ {
				w := httptest.NewRecorder()
				s.ServeHTTP(w, httptest.NewRequest("POST", tc.path, strings.NewReader(tc.body)))
				if w.Code != 200 {
					t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
				}
			}
			if guardCalls != repeat || classCalls != repeat || upstreamCalls != 1 {
				t.Fatalf("Guard=%d classifier=%d upstream=%d", guardCalls, classCalls, upstreamCalls)
			}
		})
	}
}

func TestGuardPayloadContractRejectsStaleAndMalformedResults(t *testing.T) {
	for _, field := range []string{"input_sha256", "redaction_version", "sanitized_payload", "stream"} {
		t.Run(field, func(t *testing.T) {
			guard := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				v := boundGuardResponse(t, r)
				if field == "stream" {
					v["sanitized_payload"] = `{"stream":true,"messages":[]}`
				} else {
					v[field] = "invalid"
				}
				json.NewEncoder(w).Encode(v)
			}))
			defer guard.Close()
			cache := &observedResponseCache{}
			calls := 0
			p := &Pipeline{Gateway: NewAutoGateway(), Preflight: &HTTPPreflightChecker{Endpoint: guard.URL}, Cache: cache, Classifier: taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) {
				calls++
				return Classification{}, nil
			})}
			request, _ := NormalizeProtocolRequest("chat", []byte(`{"messages":[{"role":"user","content":"password=fixtureplain"}]}`))
			result, err := p.Execute(context.Background(), "chat", "", "auto", request, 1, false, false, false, false)
			if err == nil || result.Preflight.Decision != PreflightUnavailable || calls != 0 || cache.gets != 0 || result.UpstreamCalled {
				t.Fatal("invalid sanitized result crossed safety boundary")
			}
		})
	}
}
