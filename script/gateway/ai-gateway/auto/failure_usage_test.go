package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strconv"
	"strings"
	"testing"
)

type failureUsageTransport func(*http.Request) (*http.Response, error)

func (f failureUsageTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

type usageThenFailure struct {
	reader *strings.Reader
	err    error
	cancel context.CancelFunc
}

func (r *usageThenFailure) Read(p []byte) (int, error) {
	if r.reader.Len() > 0 {
		return r.reader.Read(p)
	}
	if r.cancel != nil {
		r.cancel()
	}
	return 0, r.err
}
func (*usageThenFailure) Close() error { return nil }

func TestBufferedSSEFailuresKeepReceivedUsageWithoutPartialOutput(t *testing.T) {
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		for _, mode := range []string{"incomplete", "read_failure", "canceled", "unknown_usage"} {
			t.Run(protocol+"/"+mode, func(t *testing.T) {
				ctx, cancel := context.WithCancel(context.Background())
				defer cancel()
				usage := map[string]any{"input_tokens": 4, "output_tokens": 2}
				if protocol == "chat" {
					usage = map[string]any{"prompt_tokens": 4, "completion_tokens": 2}
				}
				if mode == "unknown_usage" {
					usage = nil
				}
				message := map[string]any{"id": "response-id", "model": "provider-model", "usage": usage}
				var event any = message
				switch protocol {
				case "chat":
					message["choices"] = []any{map[string]any{"index": 0, "delta": map[string]any{"content": "partial"}, "finish_reason": nil}}
				case "responses":
					message["status"], message["output"] = "in_progress", []any{}
					event = map[string]any{"type": "response.created", "response": message}
				case "anthropic":
					message["type"], message["role"], message["content"] = "message", "assistant", []any{}
					event = map[string]any{"type": "message_start", "message": message}
				}
				raw, _ := json.Marshal(event)
				body := &usageThenFailure{reader: strings.NewReader("data: " + string(raw) + "\n\n"), err: io.EOF}
				if mode == "read_failure" {
					body.err = io.ErrUnexpectedEOF
				}
				if mode == "canceled" {
					body.err, body.cancel = context.Canceled, cancel
				}
				transport := failureUsageTransport(func(*http.Request) (*http.Response, error) {
					return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": {"text/event-stream"}, "X-Request-Id": {"provider-request-id"}, "X-Client-Request-Id": {"billing-id"}}, Body: body}, nil
				})
				client := &HTTPUpstreamClient{BufferedSSE: true, Client: &http.Client{Transport: transport}, Endpoints: []ProviderEndpoint{{Provider: "default", Protocol: protocol, URL: "http://fixture.invalid"}}}
				response, err := client.Complete(ctx, UpstreamRequest{Protocol: protocol, Payload: []byte(`{}`)})
				if err == nil || response.Complete || len(response.Body) != 0 {
					t.Fatal("failed generation became a complete response")
				}
				if mode == "canceled" && !errors.Is(err, context.Canceled) {
					t.Fatalf("cancellation was attributed to provider failure: %v", err)
				}
				known := mode != "unknown_usage"
				got := NormalizeUsage(response.Usage)
				if got.HasPromptTokens != known || (known && (got.PromptTokens != 4 || got.CompletionTokens != 2)) {
					t.Fatalf("received usage lost or invented: %+v", got)
				}
				if response.ClientRequestID != "billing-id" || response.RequestID != "provider-request-id" || response.ResponseID != "response-id" || response.ResponseModel != "provider-model" {
					t.Fatalf("failed attempt metadata missing: %+v", response)
				}
			})
		}
	}
}

func TestFailedClassifierAttemptsRetainReportedUsage(t *testing.T) {
	for _, native := range []bool{false, true} {
		for _, mode := range []string{"http_failure", "read_failure", "unknown_usage"} {
			t.Run(strconv.FormatBool(native)+"/"+mode, func(t *testing.T) {
				server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
					body := `{"id":"classifier-response","model":"classifier-model","usage":{"input_tokens":4,"output_tokens":2}}`
					if mode == "unknown_usage" {
						body = "incomplete json"
					}
					w.Header().Set("X-Request-ID", "provider-request-id")
					w.Header().Set("X-Client-Request-ID", "billing-id")
					if mode == "read_failure" {
						w.Header().Set("Content-Length", strconv.Itoa(len(body)+100))
					} else {
						w.WriteHeader(429)
					}
					_, _ = io.WriteString(w, body)
				}))
				defer server.Close()
				var events []UsageEvent
				classifier := &SemanticClassifier{Endpoint: server.URL + "/chat/completions", Model: "gpt-5.6-luna", OnUsage: func(e UsageEvent) error { events = append(events, e); return nil }}
				var media *NativeMedia
				if native {
					media = &NativeMedia{ClassifierParts: []any{map[string]any{"type": "input_text", "text": "synthetic"}}}
				}
				_, err := classifier.assess(context.Background(), classifier.Model, []byte(`{}`), PipelineMeta{RequestID: "gateway-id"}, media)
				if !errors.Is(err, ErrClassifierUnavailable) || len(events) != 1 || events[0].Success || !events[0].Attempt {
					t.Fatal("failed classifier became successful")
				}
				e := events[0]
				known := mode != "unknown_usage"
				if e.UpstreamClientRequestID != "billing-id" || e.UpstreamRequestID != "provider-request-id" || e.RequestID != "gateway-id" || e.UsageReported != known || (known && (e.InputTokens != 4 || e.OutputTokens != 2)) {
					t.Fatalf("classifier billing facts lost: %+v", e)
				}
			})
		}
	}
}

func TestRejectedActionReviewRetainsProviderCorrelation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("X-Request-ID", "provider-request-id")
		w.Header().Set("X-Client-Request-ID", "review-billing-id")
		w.WriteHeader(503)
	}))
	defer server.Close()
	client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "default", Protocol: "responses", URL: server.URL}}}
	path := t.TempDir() + "/usage.jsonl"
	sink, _ := NewJSONLUsageSink(path)
	gateway := NewAutoGateway()
	pipeline := &Pipeline{Gateway: gateway, Classifier: reviewMustNotClassify{}, Preflight: fixedPreflight{PreflightResult{Decision: PreflightAllow}}, UsageSink: sink}
	handler := &HTTPServer{Gateway: gateway, Pipeline: pipeline, StreamClient: client}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("POST", "/v1/responses", strings.NewReader(`{"model":"codex-auto-review","input":"review fixture","stream":true}`)))
	raw, err := os.ReadFile(path)
	var event UsageEvent
	if err != nil || json.Unmarshal(raw, &event) != nil || w.Code != 503 || event.Success || event.UsageReported || !event.Attempt || event.Purpose != "action_review" || event.UpstreamClientRequestID != "review-billing-id" || event.UpstreamRequestID != "provider-request-id" {
		t.Fatalf("rejected review lost correlation or fabricated usage: %+v, %v", event, err)
	}
}
