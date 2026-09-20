package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

type terminalThenCancel struct {
	body   io.Reader
	cancel context.CancelFunc
}

func (r *terminalThenCancel) Read(p []byte) (int, error) {
	n, e := r.body.Read(p)
	if n > 0 {
		r.cancel()
	}
	return n, e
}
func (r *terminalThenCancel) Close() error { return nil }

type failedTerminalWriter struct{ *httptest.ResponseRecorder }

func (failedTerminalWriter) Write([]byte) (int, error) { return 0, context.Canceled }

func TestSSETerminalCancelDistinguishesDeliveredFromFailedWrite(t *testing.T) {
	for _, failWrite := range []bool{false, true} {
		ctx, cancel := context.WithCancel(context.Background())
		body := &observedSSEBody{ReadCloser: &terminalThenCancel{body: strings.NewReader("data: {\"type\":\"response.completed\",\"response\":{\"id\":\"r\",\"model\":\"m\"}}\n\n"), cancel: cancel}}
		var writer http.ResponseWriter = httptest.NewRecorder()
		if failWrite {
			writer = failedTerminalWriter{httptest.NewRecorder()}
		}
		err := RelaySSE(ctx, writer, &http.Response{StatusCode: 200, Body: body})
		reason, normalized := streamTermination(err, body.Complete)
		cancel()
		if failWrite && (normalized == nil || reason != "client_write:context_canceled") {
			t.Fatalf("failed write hidden: %s %v", reason, normalized)
		}
		if !failWrite && (normalized != nil || reason != "client_closed_after_complete") {
			t.Fatalf("normal terminal close: %s %v", reason, normalized)
		}
	}
}

func TestSSEIncompleteAndUnknownTailFailureRemainErrors(t *testing.T) {
	for _, item := range []struct {
		err      error
		complete bool
	}{
		{newSSETransportError("canceled", context.Canceled, false), false},
		{newSSETransportError("upstream_read", io.ErrUnexpectedEOF, true), true},
		{newSSETransportError("upstream_read", errors.New("unknown"), true), true},
	} {
		if _, err := streamTermination(item.err, item.complete); err == nil {
			t.Fatal("failure was hidden")
		}
	}
}

func TestClientDeliveryFailureDoesNotOpenProviderCircuit(t *testing.T) {
	for _, phase := range []string{"client_write", "upstream_read"} {
		t.Run(phase, func(t *testing.T) {
			h := &RuntimeHealth{}
			meta := PipelineMeta{Region: "tokyo", APIKeyID: "fixture"}
			err := newSSETransportError(phase, io.ErrClosedPipe, false)
			for i := 0; i < 3; i++ {
				h.Observe(meta, "responses", "gpt-5.6-terra", UpstreamResponse{StatusCode: 200, Complete: true}, err, time.Second)
			}
			if got := h.Acquire(meta, "responses", "gpt-5.6-terra"); got != (phase == "client_write") {
				t.Fatalf("%s: next request admitted=%v", phase, got)
			}
			path := t.TempDir() + "/audit.jsonl"
			sink, err := NewJSONLAuditSink(path)
			if err != nil {
				t.Fatal(err)
			}
			pipeline := &Pipeline{AuditSink: sink}
			result := PipelineResult{UpstreamCalled: true, Upstream: UpstreamResponse{StatusCode: 200, Complete: true, StreamTermination: phase + ":transport_error"}}
			result.Decision.SelectedModel = ModelByName("gpt-5.6-terra", DefaultCatalog)
			pipeline.finishAudit(meta, result, newSSETransportError(phase, io.ErrClosedPipe, false))
			raw, err := os.ReadFile(path)
			if err != nil {
				t.Fatal(err)
			}
			var audit RouteAudit
			if err := json.Unmarshal(raw, &audit); err != nil {
				t.Fatal(err)
			}
			stage := "upstream_failed"
			if phase == "client_write" {
				stage = "client_delivery_failed"
			}
			if audit.Stage != stage || audit.ErrorType != phase+":transport_error" || !audit.ResponseComplete {
				t.Fatalf("wrong failure attribution: %+v", audit)
			}
		})
	}
}
