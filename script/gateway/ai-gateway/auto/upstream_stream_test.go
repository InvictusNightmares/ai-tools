package autogateway

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHTTPUpstreamClientOpensAndRelaysSSE(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.Header.Get("Accept") != "text/event-stream" {
			t.Fatalf("accept = %q", request.Header.Get("Accept"))
		}
		writer.Header().Set("Content-Type", "text/event-stream")
		_, _ = writer.Write([]byte("data: one\n\ndata: [DONE]\n\n"))
	}))
	defer server.Close()
	client := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "chat", URL: server.URL}}}
	response, err := client.OpenStream(context.Background(), UpstreamRequest{Provider: "openai", Protocol: "chat", Parameters: ProviderParameters{Stream: true}, Request: Request{Stream: true}, Payload: []byte(`{"stream":true}`)})
	if err != nil {
		t.Fatal(err)
	}
	recorder := httptest.NewRecorder()
	if err := RelaySSE(context.Background(), recorder, response); err != nil {
		t.Fatal(err)
	}
	if recorder.Code != http.StatusOK || !strings.Contains(recorder.Body.String(), "data: [DONE]") {
		t.Fatalf("status=%d body=%q", recorder.Code, recorder.Body.String())
	}
}
