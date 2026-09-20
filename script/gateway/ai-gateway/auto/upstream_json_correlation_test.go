package autogateway

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"
)

// A provider billing ID is independent of both the gateway ID and response ID.
// Keep it even when a JSON attempt fails after its response headers arrive.
func TestJSONUpstreamRetainsBillingMetadataOnEveryOutcome(t *testing.T) {
	bodies := map[string]string{
		"chat":      `{"id":"response-id","model":"provider-model","choices":[{"finish_reason":"stop","message":{"content":"ok"}}],"usage":{"prompt_tokens":4,"completion_tokens":2}}`,
		"responses": `{"id":"response-id","model":"provider-model","status":"completed","output":[],"usage":{"input_tokens":4,"output_tokens":2}}`,
		"anthropic": `{"id":"response-id","model":"provider-model","stop_reason":"end_turn","content":[],"usage":{"input_tokens":4,"output_tokens":2}}`,
	}
	for protocol, complete := range bodies {
		for _, outcome := range []string{"complete", "http_failure", "invalid_json", "too_large", "read_failure", "complete_json_read_failure"} {
			t.Run(protocol+"/"+outcome, func(t *testing.T) {
				status, body := http.StatusOK, complete
				switch outcome {
				case "http_failure":
					status, body = http.StatusTooManyRequests, `{"error":"busy"}`
				case "invalid_json", "read_failure":
					body = "incomplete json"
				}
				server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
					if r.Header.Get("X-Request-ID") != "gateway-id" {
						t.Error("gateway correlation changed")
					}
					w.Header().Set("Content-Type", "application/json")
					w.Header().Set("X-Request-ID", "provider-request-id")
					w.Header().Set("X-Client-Request-ID", "provider-billing-id")
					if strings.Contains(outcome, "read_failure") {
						w.Header().Set("Content-Length", strconv.Itoa(len(body)+100))
					}
					w.WriteHeader(status)
					_, _ = io.WriteString(w, body)
				}))
				defer server.Close()
				client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: protocol, URL: server.URL}}}
				if outcome == "too_large" {
					client.MaxResponseSize = 5
				}
				response, err := client.Complete(context.Background(), UpstreamRequest{RequestID: "gateway-id", Provider: "openai", Protocol: protocol, Payload: []byte(`{}`)})
				if (err == nil) != (outcome == "complete") {
					t.Fatalf("unexpected result: %v", err)
				}
				if response.ClientRequestID != "provider-billing-id" || response.RequestID != "provider-request-id" || response.StatusCode != status || response.Transport != "buffered_json" || response.ContentType != "application/json" {
					t.Fatalf("billing metadata lost: %+v", response)
				}
				if outcome == "read_failure" || outcome == "complete_json_read_failure" || outcome == "too_large" {
					if response.Complete || len(response.Body) != 0 || response.ResponseBytes == 0 {
						t.Fatal("partial transport data was published as a complete response")
					}
				}
				usage := NormalizeUsage(response.Usage)
				known := outcome == "complete" || outcome == "complete_json_read_failure"
				if usage.HasPromptTokens != known || (known && (usage.PromptTokens != 4 || usage.CompletionTokens != 2)) {
					t.Fatalf("known and unknown usage were conflated: %+v", usage)
				}
			})
		}
	}
}
