package autogateway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type fixedPreflight struct{ result PreflightResult }

func (f fixedPreflight) Evaluate(context.Context, Request) (PreflightResult, error) {
	return f.result, nil
}

func TestHTTPModelsExposeAutoOnly(t *testing.T) {
	server := httptest.NewServer(&HTTPServer{Gateway: NewAutoGateway()})
	defer server.Close()
	response, err := http.Get(server.URL + "/v1/models")
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var payload struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusOK || len(payload.Data) != 2 || payload.Data[0].ID != "auto" || payload.Data[1].ID != ActionReviewModel {
		t.Fatalf("status=%d payload=%+v", response.StatusCode, payload)
	}
}

func TestHTTPRouteNormalizesProtocolAndIgnoresClientEffort(t *testing.T) {
	server := httptest.NewServer(&HTTPServer{Gateway: NewAutoGateway()})
	defer server.Close()
	body := `{"protocol":"responses","provider":"openai","model":"auto","body":{"model":"auto","reasoning":{"effort":"xhigh"},"input":"hello"}}`
	response, err := http.Post(server.URL+"/v1/route", "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var payload routeHTTPOutput
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusOK || payload.EffectiveModel != "deepseek-flash" || payload.EffectiveReasoningEffort != ReasoningNone || payload.UpstreamCalled {
		t.Fatalf("status=%d payload=%+v", response.StatusCode, payload)
	}
}

func TestHTTPRouteRejectsUnknownModel(t *testing.T) {
	server := httptest.NewServer(&HTTPServer{Gateway: NewAutoGateway()})
	defer server.Close()
	body := `{"protocol":"chat","model":"gpt-unknown","body":{"messages":[{"role":"user","content":"hello"}]}}`
	response, err := http.Post(server.URL+"/v1/route", "application/json", strings.NewReader(body))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusNotFound {
		t.Fatalf("status=%d", response.StatusCode)
	}
}

func TestHTTPUnsupportedModelReturns404WithoutGuardOrUpstream(t *testing.T) {
	for _, path := range []string{"/v1/chat/completions", "/v1/responses", "/v1/messages"} {
		for _, stream := range []bool{false, true} {
			body, _ := json.Marshal(map[string]any{"model": "deepseek-v4-pro", "stream": stream, "messages": []any{map[string]any{"role": "user", "content": "你好"}}, "input": "你好"})
			calls := 0
			auditPath := filepath.Join(t.TempDir(), "audit.jsonl")
			sink, err := NewJSONLAuditSink(auditPath)
			if err != nil {
				t.Fatal(err)
			}
			upstream := &recordingUpstream{}
			p := &Pipeline{Gateway: NewAutoGateway(), AuditSink: sink, Upstream: upstream, Preflight: preflightFunc(func(context.Context, Request) (PreflightResult, error) {
				calls++
				return PreflightResult{Decision: PreflightAllow}, nil
			})}
			s := &HTTPServer{Gateway: p.Gateway, Pipeline: p, StreamClient: &HTTPUpstreamClient{}}
			w := httptest.NewRecorder()
			s.ServeHTTP(w, httptest.NewRequest(http.MethodPost, path, strings.NewReader(string(body))))
			if w.Code != http.StatusNotFound || calls != 0 || !strings.Contains(w.Body.String(), "model_not_found") || w.Header().Get("X-Gateway-Request-ID") == "" {
				t.Fatalf("path=%s stream=%v status=%d guard_calls=%d", path, stream, w.Code, calls)
			}
			var payload struct {
				Error struct{ Code, Type, Message string }
			}
			if json.Unmarshal(w.Body.Bytes(), &payload) != nil || payload.Error.Code != "model_not_found" || payload.Error.Message == "" {
				t.Fatal("SDK error envelope missing")
			}
			audit, err := os.ReadFile(auditPath)
			var row RouteAudit
			if err != nil || json.Unmarshal(audit, &row) != nil || row.Stage != "request_rejected" || row.HTTPStatus != 404 || row.RequestID != w.Header().Get("X-Gateway-Request-ID") || row.UpstreamCalled || upstream.calls != 0 || strings.Contains(string(audit), "你好") {
				t.Fatal("missing rejection audit or unexpected generation")
			}
		}
	}
}

func TestHTTPRouteHonorsPreflightBlockAndUnavailable(t *testing.T) {
	for _, test := range []struct {
		name      string
		result    PreflightResult
		status    int
		errorCode string
	}{
		{name: "block", result: PreflightResult{Decision: PreflightBlock, ReasonCodes: []string{"secret_input_not_allowed"}}, status: http.StatusForbidden, errorCode: "preflight_blocked"},
		{name: "unavailable", result: PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"classifier_error"}}, status: http.StatusServiceUnavailable, errorCode: "preflight_unavailable"},
	} {
		t.Run(test.name, func(t *testing.T) {
			server := httptest.NewServer(&HTTPServer{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: test.result}})
			defer server.Close()
			body := `{"protocol":"chat","model":"auto","body":{"messages":[{"role":"user","content":"hello"}]}}`
			response, err := http.Post(server.URL+"/v1/route", "application/json", strings.NewReader(body))
			if err != nil {
				t.Fatal(err)
			}
			defer response.Body.Close()
			var payload struct {
				Error    string            `json:"error"`
				Decision PreflightDecision `json:"decision"`
			}
			if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
				t.Fatal(err)
			}
			if response.StatusCode != test.status || payload.Error != test.errorCode {
				t.Fatalf("status=%d payload=%+v", response.StatusCode, payload)
			}
		})
	}
}

func TestHTTPRouteKeepsModelWhenStreamIsActive(t *testing.T) {
	server := httptest.NewServer(&HTTPServer{Gateway: NewAutoGateway()})
	defer server.Close()
	quick := `{"protocol":"chat","model":"auto","turn":1,"body":{"stream":true,"messages":[{"role":"user","content":"hello"}]}}`
	response, err := http.Post(server.URL+"/v1/route", "application/json", strings.NewReader(quick))
	if err != nil {
		t.Fatal(err)
	}
	response.Body.Close()
	complex := `{"protocol":"chat","model":"auto","turn":2,"stream_active":true,"body":{"stream":true,"messages":[{"role":"user","content":"Design a scalable architecture and debug this production failure."}]}}`
	response, err = http.Post(server.URL+"/v1/route", "application/json", strings.NewReader(complex))
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	var payload routeHTTPOutput
	if err := json.NewDecoder(response.Body).Decode(&payload); err != nil {
		t.Fatal(err)
	}
	if response.StatusCode != http.StatusOK || payload.Action != "keep" || payload.Reason != "stream_in_flight" || payload.EffectiveModel != "deepseek-flash" {
		t.Fatalf("stream route = %+v", payload)
	}
}

func TestHTTPCompletionForwardsBufferedResponse(t *testing.T) {
	upstream := &recordingUpstream{}
	pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, Upstream: upstream, CachePolicy: ResponseCachePolicy{}}
	server := httptest.NewServer(&HTTPServer{Gateway: pipeline.Gateway, Pipeline: pipeline, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "key", ModelRevision: "v1", CacheSecret: "secret"}})
	defer server.Close()
	request, err := http.NewRequest(http.MethodPost, server.URL+"/v1/chat/completions", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"hello"}]}`))
	if err != nil {
		t.Fatal(err)
	}
	request.Header.Set("X-Gateway-Provider", "openai")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("status=%d", response.StatusCode)
	}
}

func TestHTTPCompletionForwardsAllowlistedAuthOnStream(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if got := request.Header.Get("Authorization"); got != "Bearer stream-test-token" {
			t.Errorf("authorization = %q", got)
		}
		writer.Header().Set("Content-Type", "text/event-stream")
		_, _ = writer.Write([]byte("data: [DONE]\n\n"))
	}))
	defer upstream.Close()
	client := &HTTPUpstreamClient{ForwardClientAuth: true, Endpoints: []ProviderEndpoint{{Provider: "default", Protocol: "chat", URL: upstream.URL}}}
	pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, CachePolicy: ResponseCachePolicy{}}
	server := httptest.NewServer(&HTTPServer{Gateway: pipeline.Gateway, Pipeline: pipeline, StreamClient: client, Meta: PipelineMeta{Region: "tokyo", ModelRevision: "v1", CacheSecret: "secret"}})
	defer server.Close()
	request, err := http.NewRequest(http.MethodPost, server.URL+"/v1/chat/completions", strings.NewReader(`{"model":"auto","stream":true,"messages":[{"role":"user","content":"hello"}]}`))
	if err != nil {
		t.Fatal(err)
	}
	request.Header.Set("Authorization", "Bearer stream-test-token")
	request.Header.Set("X-Gateway-Provider", "openai")
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		t.Fatal(err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		t.Fatalf("status=%d", response.StatusCode)
	}
}
