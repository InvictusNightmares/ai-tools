package autogateway

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestPhaseDOrderGuardThenAutoThenUpstream(t *testing.T) {
	upstreamCalls := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		upstreamCalls++
		writer.Header().Set("Content-Type", "application/json")
		_, _ = writer.Write([]byte(`{"id":"integration","model":"deepseek-flash","choices":[{"finish_reason":"stop","message":{"content":"ok"}}],"usage":{"prompt_tokens":5,"completion_tokens":2}}`))
	}))
	defer upstream.Close()
	guardDecision := PreflightAllow
	guard := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if guardDecision == PreflightUnavailable {
			writer.WriteHeader(http.StatusServiceUnavailable)
			_, _ = writer.Write([]byte(`{"decision":"unavailable","reason_codes":["queue_timeout"]}`))
			return
		}
		status := http.StatusOK
		if guardDecision == PreflightBlock {
			status = http.StatusOK
		}
		writer.WriteHeader(status)
		result := boundGuardResponse(t, request)
		result["decision"] = guardDecision
		_ = json.NewEncoder(writer).Encode(result)
	}))
	defer guard.Close()
	pipeline := &Pipeline{
		Gateway:     NewAutoGateway(),
		Preflight:   &HTTPPreflightChecker{Endpoint: guard.URL, Provider: "deepseek", Region: "tokyo", SessionID: "test-session"},
		Upstream:    &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "deepseek", Protocol: "chat", URL: upstream.URL}}},
		CachePolicy: ResponseCachePolicy{},
	}
	server := httptest.NewServer(&HTTPServer{Gateway: pipeline.Gateway, Pipeline: pipeline, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "test-key", ModelRevision: "rev", CacheSecret: "secret"}})
	defer server.Close()
	call := func() *http.Response {
		request, _ := http.NewRequest(http.MethodPost, server.URL+"/v1/chat/completions", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"hello"}]}`))
		return mustHTTPDo(request)
	}
	response := call()
	if response.StatusCode != http.StatusOK || upstreamCalls != 1 {
		t.Fatalf("allow status=%d upstream_calls=%d", response.StatusCode, upstreamCalls)
	}
	response.Body.Close()
	guardDecision = PreflightBlock
	response = call()
	if response.StatusCode != http.StatusForbidden || upstreamCalls != 1 {
		t.Fatalf("block status=%d upstream_calls=%d", response.StatusCode, upstreamCalls)
	}
	response.Body.Close()
	guardDecision = PreflightUnavailable
	response = call()
	if response.StatusCode != http.StatusServiceUnavailable || upstreamCalls != 1 {
		t.Fatalf("unavailable status=%d upstream_calls=%d", response.StatusCode, upstreamCalls)
	}
	response.Body.Close()
}

func mustHTTPDo(request *http.Request) *http.Response {
	response, err := http.DefaultClient.Do(request)
	if err != nil {
		panic(err)
	}
	return response
}
