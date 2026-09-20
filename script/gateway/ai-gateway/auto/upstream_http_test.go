package autogateway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHTTPUpstreamClientBuildsGeneratedPayloadAndAuth(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if got := request.Header.Get("Authorization"); got != "Bearer test-secret" {
			t.Fatalf("authorization = %q", got)
		}
		var payload map[string]any
		if err := json.NewDecoder(request.Body).Decode(&payload); err != nil {
			t.Fatal(err)
		}
		if payload["model"] != "deepseek-flash" {
			t.Fatalf("payload model = %#v", payload["model"])
		}
		if value, found := payload["reasoning_effort"]; !found || value != string(ReasoningLow) {
			t.Fatalf("generated reasoning effort = %#v", value)
		}
		writer.Header().Set("Content-Type", "application/json")
		_, _ = writer.Write([]byte(`{"id":"x","model":"deepseek-flash","choices":[{"finish_reason":"stop","message":{"content":"ok"}}],"usage":{"prompt_tokens":4,"completion_tokens":2}}`))
	}))
	defer server.Close()
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	parameters := BuildProviderParameters("deepseek", "chat", DefaultCatalog[0], ReasoningLow, false)
	payload, err := BuildProviderPayload("chat", request, parameters)
	if err != nil {
		t.Fatal(err)
	}
	client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "deepseek", Protocol: "chat", URL: server.URL, Token: "test-secret"}}}
	response, err := client.Complete(context.Background(), UpstreamRequest{Provider: "deepseek", Protocol: "chat", Parameters: parameters, Payload: payload, Request: request})
	if err != nil || response.StatusCode != http.StatusOK || response.ResponseBytes == 0 || NormalizeUsage(response.Usage).PromptTokens != 4 {
		t.Fatalf("response=%+v err=%v", response, err)
	}
}

func TestHTTPUpstreamClientPropagatesStatusWithoutCachingContract(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		writer.WriteHeader(http.StatusTooManyRequests)
		_, _ = writer.Write([]byte(`{"error":"busy"}`))
	}))
	defer server.Close()
	client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "responses", URL: server.URL}}}
	response, err := client.Complete(context.Background(), UpstreamRequest{Provider: "openai", Protocol: "responses", Parameters: ProviderParameters{}, Payload: []byte(`{"input":[]}`), Request: Request{}})
	if err == nil || response.StatusCode != http.StatusTooManyRequests || !strings.Contains(err.Error(), "429") {
		t.Fatalf("response=%+v err=%v", response, err)
	}
}

func TestHTTPUpstreamClientRejectsStreamingComplete(t *testing.T) {
	client := &HTTPUpstreamClient{}
	_, err := client.Complete(context.Background(), UpstreamRequest{Parameters: ProviderParameters{Stream: true}, Request: Request{Stream: true}})
	if err == nil || err.Error() != "streaming_requires_stream_transport" {
		t.Fatalf("err=%v", err)
	}
}

func TestHTTPUpstreamClientEnforcesResponseLimit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		_, _ = writer.Write([]byte("0123456789"))
	}))
	defer server.Close()
	client := &HTTPUpstreamClient{MaxResponseSize: 5, Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "chat", URL: server.URL}}}
	response, err := client.Complete(context.Background(), UpstreamRequest{Provider: "openai", Protocol: "chat", Payload: []byte(`{}`)})
	if err == nil || err.Error() != "upstream_response_too_large" || response.ResponseBytes != 6 {
		t.Fatalf("response=%+v err=%v", response, err)
	}
}
