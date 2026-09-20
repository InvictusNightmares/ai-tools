package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

type imageAuditTransport func(*http.Request) (*http.Response, error)

func (f imageAuditTransport) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func lastAudit(t *testing.T, path string) RouteAudit {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	var audit RouteAudit
	if json.Unmarshal([]byte(lines[len(lines)-1]), &audit) != nil {
		t.Fatal("invalid audit")
	}
	return audit
}

func TestNativeClientCancellationIsNotAttributedToProviderFailure(t *testing.T) {
	for _, err := range []error{context.Canceled, fmt.Errorf("upstream_transport: %w", context.Canceled), newSSETransportError("upstream_read", context.Canceled, false), context.DeadlineExceeded, io.ErrUnexpectedEOF} {
		path := t.TempDir() + "/audit.jsonl"
		sink, _ := NewJSONLAuditSink(path)
		p := &Pipeline{AuditSink: sink}
		result := PipelineResult{UpstreamCalled: true, Upstream: UpstreamResponse{StatusCode: 200}}
		result.Decision.SelectedModel = ModelByName("gpt-5.6-luna", DefaultCatalog)
		p.finishAudit(PipelineMeta{RequestID: "cancellation-fixture"}, result, err)
		audit := lastAudit(t, path)
		want := "upstream_failed"
		if errors.Is(err, context.Canceled) {
			want = "request_canceled"
		}
		if audit.Stage != want || audit.ResponseComplete {
			t.Fatalf("wrong cancellation/timeout attribution: %+v", audit)
		}
	}
}

func TestNativeImageCompletionAndClientDeliveryAreSeparate(t *testing.T) {
	for _, mode := range []string{"json", "json_write_failed", "sse_terminal_cancel", "sse_terminal_write_failed", "sse_partial_cancel", "transport_canceled"} {
		t.Run(mode, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			path := t.TempDir() + "/audit.jsonl"
			sink, _ := NewJSONLAuditSink(path)
			usagePath := t.TempDir() + "/usage.jsonl"
			usageSink, _ := NewJSONLUsageSink(usagePath)
			g := NewAutoGateway()
			p := &Pipeline{Gateway: g, Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, AuditSink: sink, UsageSink: usageSink}
			transport := imageAuditTransport(func(*http.Request) (*http.Response, error) {
				if mode == "transport_canceled" {
					return nil, context.Canceled
				}
				kind := "application/json"
				body := `{"data":[{"b64_json":"synthetic"}],"usage":{"input_tokens":2,"output_tokens":3}}`
				if strings.HasPrefix(mode, "sse") {
					kind = "text/event-stream"
					body = "data: {\"type\":\"image_generation.completed\",\"usage\":{\"input_tokens\":2,\"output_tokens\":3}}\n\n"
					if mode == "sse_partial_cancel" {
						body = "data: {\"type\":\"image_generation.partial_image\"}\n\n"
					}
				}
				var reader io.ReadCloser = io.NopCloser(strings.NewReader(body))
				if strings.HasPrefix(mode, "sse") {
					reader = &terminalThenCancel{body: strings.NewReader(body), cancel: cancel}
				}
				return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": {kind}, "X-Client-Request-Id": {"image-billing-fixture"}}, Body: reader}, nil
			})
			server := &HTTPServer{Gateway: g, Pipeline: p, NativeAPI: &NativeAPI{BaseURL: "http://fixture.invalid", Client: &http.Client{Transport: transport}}}
			r := httptest.NewRequest(http.MethodPost, "/v1/images/generations", strings.NewReader(`{"model":"auto","prompt":"a plain blue square"}`)).WithContext(ctx)
			r.Header.Set("Authorization", "Bearer fixture")
			r.Header.Set("Content-Type", "application/json")
			var w http.ResponseWriter = httptest.NewRecorder()
			if strings.Contains(mode, "write_failed") {
				w = failedTerminalWriter{httptest.NewRecorder()}
			}
			server.ServeHTTP(w, r)
			audit := lastAudit(t, path)
			stage, complete, success := "upstream_completed", true, true
			if strings.Contains(mode, "write_failed") {
				stage, success = "client_delivery_failed", false
			}
			if mode == "sse_partial_cancel" || mode == "transport_canceled" {
				stage, complete, success = "request_canceled", false, false
			}
			if audit.Stage != stage || audit.ResponseComplete != complete {
				t.Fatalf("image transport facts conflated: %+v", audit)
			}
			raw, err := os.ReadFile(usagePath)
			var usage UsageEvent
			if err != nil || json.Unmarshal(raw, &usage) != nil || !usage.Attempt || usage.Success != success {
				t.Fatal("image attempt accounting lost", err)
			}
			if complete && (usage.InputTokens != 2 || usage.OutputTokens != 3 || usage.UpstreamClientRequestID != "image-billing-fixture") {
				t.Fatal("completed image usage lost on client close")
			}
		})
	}
}
