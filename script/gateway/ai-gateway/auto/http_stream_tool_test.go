package autogateway

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

type terminalStreamClient struct{ body string }

func (c terminalStreamClient) OpenStream(context.Context, UpstreamRequest) (*http.Response, error) {
	return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": {"text/event-stream"}}, Body: io.NopCloser(strings.NewReader(c.body))}, nil
}

type terminalClientWriter struct {
	*httptest.ResponseRecorder
	onWrite func()
}

func (w terminalClientWriter) Write(body []byte) (int, error) {
	w.onWrite()
	return w.ResponseRecorder.Write(body)
}

func TestHTTPToolBindingExistsBeforeClientSeesTerminalEvent(t *testing.T) {
	for _, complete := range []bool{true, false} {
		p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, StateStore: NewMemorySessionStateStore()}
		meta := PipelineMeta{RequestID: "first", Region: "tokyo", APIKeyID: "key", SessionID: "session"}
		body := "data: {\"type\":\"response.output_item.added\",\"item\":{\"type\":\"function_call\",\"call_id\":\"call-terminal\"}}\n\n"
		if complete {
			body += "data: {\"type\":\"response.completed\",\"response\":{\"id\":\"reply\",\"model\":\"gpt-5.6-terra\"}}\n\n"
		}
		s := &HTTPServer{Gateway: p.Gateway, Pipeline: p, StreamClient: terminalStreamClient{body}, Meta: meta}
		ctx, cancel := context.WithCancel(context.Background())
		defer cancel()
		boundBeforeWrite := false
		w := terminalClientWriter{ResponseRecorder: httptest.NewRecorder(), onWrite: func() {
			boundBeforeWrite = p.StateStore.Load(toolBindingKey(meta, "responses", "call-terminal"), time.Now()).HasCurrent
			// SDKs can close on response.completed and immediately send tool output.
			cancel()
		}}
		r := httptest.NewRequest(http.MethodPost, "/v1/responses", strings.NewReader(`{"model":"auto","stream":true,"input":"Read a local fixture"}`)).WithContext(ctx)
		s.ServeHTTP(w, r)
		after := p.StateStore.Load(toolBindingKey(meta, "responses", "call-terminal"), time.Now())
		if boundBeforeWrite != complete || after.HasCurrent != complete {
			t.Fatalf("complete=%v binding_before_write=%v binding_after_close=%v", complete, boundBeforeWrite, after.HasCurrent)
		}
	}
}
