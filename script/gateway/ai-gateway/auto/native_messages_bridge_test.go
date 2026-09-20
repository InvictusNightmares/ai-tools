package autogateway

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestNativeMessagesFileBridgePreservesFileToolsAndOptions(t *testing.T) {
	raw := []byte(`{"model":"gpt-5.6-luna","system":[{"type":"text","text":"system instruction"}],"max_tokens":256,"stop_sequences":["END"],"output_config":{"effort":"none"},"tools":[{"name":"read","description":"read file","input_schema":{"type":"object"}}],"tool_choice":{"type":"auto","disable_parallel_tool_use":true},"messages":[{"role":"assistant","content":[{"type":"tool_use","id":"call-A","name":"read","input":{"n":9007199254740993}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":"call-A","is_error":true,"content":[{"type":"text","text":"partial result"},{"type":"document","source":{"type":"base64","media_type":"application/pdf","data":"YWJj"}}]}]}]}`)
	b, err := nativeMessagesChatPayload(raw)
	if err != nil {
		t.Fatal(err)
	}
	for _, want := range []string{"9007199254740993", "call-A", "data:application/pdf;base64,YWJj", "Tool returned an error:", "system instruction", `"parallel_tool_calls":false`, `"reasoning_effort":"none"`} {
		if !bytes.Contains(b, []byte(want)) {
			t.Fatalf("missing %s", want)
		}
	}
	for _, body := range []string{`{"messages":[{"role":"assistant","content":[{"type":"thinking","thinking":"private"}]}]}`, `{"messages":[{"role":"user","content":[{"type":"document","citations":{"enabled":true},"source":{"type":"base64","data":"YWJj"}}]}]}`} {
		if _, err := nativeMessagesChatPayload([]byte(body)); err == nil {
			t.Fatal("silently discarded unsupported semantics")
		}
	}
}
func bridgeFixture(events ...string) string {
	return "data: " + strings.Join(events, "\n\ndata: ") + "\n\n"
}

var bridgeText = bridgeFixture(`{"id":"chat-1","model":"gpt-5.6-luna","choices":[{"index":0,"delta":{"role":"assistant","content":"COBALT"},"finish_reason":null}]}`, `{"id":"chat-1","model":"gpt-5.6-luna","choices":[{"index":0,"delta":{"content":"-47"},"finish_reason":"stop"}]}`, `{"id":"chat-1","model":"gpt-5.6-luna","choices":[],"usage":{"prompt_tokens":12,"completion_tokens":4}}`, `[DONE]`)

func TestNativeMessagesFileBridgeBufferedAndStreaming(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.URL.Path != "/chat" || r.UserAgent() != "native-file-client/1" || r.Header.Get("Authorization") != "Bearer fixture" {
			t.Error("transport identity changed")
		}
		raw, _ := io.ReadAll(r.Body)
		if !bytes.Contains(raw, []byte("data:application/pdf;base64,YWJj")) {
			t.Error("file dropped")
		}
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, bridgeText)
	}))
	defer server.Close()
	client := HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "chat", URL: server.URL + "/chat"}}, ForwardClientAuth: true}
	request := UpstreamRequest{Provider: "openai", Protocol: "anthropic", Payload: []byte(`{"model":"gpt-5.6-luna","messages":[{"role":"user","content":[{"type":"document","source":{"type":"base64","media_type":"application/pdf","data":"YWJj"}}]}]}`), Headers: http.Header{"Authorization": []string{"Bearer fixture"}, "User-Agent": []string{"native-file-client/1"}}, Request: Request{Native: &NativeMedia{Files: 1}}}
	result, err := client.Complete(context.Background(), request)
	if err != nil || !result.Complete || !bytes.Contains(result.Body, []byte("COBALT-47")) {
		t.Fatalf("bad result %s %v", result.Body, err)
	}
	var response map[string]any
	_ = json.Unmarshal(result.Body, &response)
	if response["usage"].(map[string]any)["input_tokens"] != float64(12) {
		t.Fatal("usage lost")
	}
	request.Parameters.Stream = true
	responseStream, err := client.OpenStream(context.Background(), request)
	if err != nil {
		t.Fatal(err)
	}
	defer responseStream.Body.Close()
	b, err := aggregateSSE(context.Background(), "anthropic", responseStream.Body, 1<<20)
	if err != nil || !bytes.Contains(b, []byte("COBALT-47")) {
		t.Fatalf("stream %v", err)
	}
	if calls != 2 {
		t.Fatal("unexpected retry")
	}
}
func TestNativeMessagesBridgeToolFragmentsAndErrors(t *testing.T) {
	tool := bridgeFixture(`{"id":"chat-1","model":"gpt-5.6-luna","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"id":"call-A","type":"function","function":{"name":"read","arguments":"{\"path\":"}}]},"finish_reason":null}]}`, `{"id":"chat-1","model":"gpt-5.6-luna","choices":[{"index":0,"delta":{"tool_calls":[{"index":0,"function":{"arguments":"\"a\"}"}}]},"finish_reason":"tool_calls"}]}`, `[DONE]`)
	var out bytes.Buffer
	if err := relayChatToMessages(context.Background(), &out, strings.NewReader(tool)); err != nil {
		t.Fatal(err)
	}
	raw, err := aggregateSSE(context.Background(), "anthropic", &out, 1<<20)
	if err != nil || !bytes.Contains(raw, []byte(`"path":"a"`)) || !bytes.Contains(raw, []byte(`"stop_reason":"tool_use"`)) {
		t.Fatalf("tool result %s %v", raw, err)
	}
	for _, input := range []string{strings.ReplaceAll(bridgeText, "data: [DONE]\n\n", ""), bridgeFixture(`{"error":{"message":"failed"}}`), bridgeText + bridgeFixture(`{"id":"late"}`)} {
		if err := relayChatToMessages(context.Background(), io.Discard, strings.NewReader(input)); err == nil {
			t.Fatal("bad stream accepted")
		}
	}
}
func TestNativeMessagesBridgeCancellationAndIncrementalDelivery(t *testing.T) {
	exited := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer close(exited)
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, bridgeFixture(`{"id":"chat-1","model":"gpt-5.6-luna","choices":[{"index":0,"delta":{"content":"first"},"finish_reason":null}]}`))
		w.(http.Flusher).Flush()
		<-r.Context().Done()
	}))
	defer server.Close()
	client := HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "chat", URL: server.URL}}}
	request := UpstreamRequest{Provider: "openai", Protocol: "anthropic", Payload: []byte(`{"model":"gpt-5.6-luna","messages":[{"role":"user","content":"test"}]}`), Parameters: ProviderParameters{Stream: true}, Request: Request{Native: &NativeMedia{Files: 1}}}
	response, err := client.OpenStream(context.Background(), request)
	if err != nil {
		t.Fatal(err)
	}
	b := make([]byte, 4096)
	n, err := response.Body.Read(b)
	if err != nil || !bytes.Contains(b[:n], []byte("message_start")) {
		t.Fatal("not incremental")
	}
	response.Body.Close()
	select {
	case <-exited:
	case <-time.After(2 * time.Second):
		t.Fatal("cancel not propagated")
	}
}

func TestAudioUnsupportedWithoutUpstreamCall(t *testing.T) {
	server := &HTTPServer{Gateway: NewAutoGateway(), Pipeline: &Pipeline{}}
	for _, tc := range []struct{ path, body string }{
		{"/v1/audio/speech", `{"input":"test"}`},
		{"/v1/chat/completions", `{"model":"auto","messages":[{"role":"user","content":[{"type":"input_audio","input_audio":{"format":"wav","data":"YWJj"}}]}]}`},
		{"/v1/responses", `{"model":"auto","input":[{"role":"user","content":[{"type":"input_file","filename":"recording.wav","file_data":"data:audio/wav;base64,YWJj"}]}]}`},
	} {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest("POST", tc.path, strings.NewReader(tc.body))
		server.ServeHTTP(rec, req)
		if rec.Code != 400 || !strings.Contains(rec.Body.String(), "audio_not_supported") {
			t.Fatalf("%s: %d %s", tc.path, rec.Code, rec.Body.String())
		}
	}
}
