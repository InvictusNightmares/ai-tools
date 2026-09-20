package autogateway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestBufferedUpstreamRequestsOneStream(t *testing.T) {
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		if body["stream"] != true {
			w.WriteHeader(504)
			return
		}
		if body["stream_options"].(map[string]any)["include_usage"] != true {
			t.Error("usage chunk not requested")
		}
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte("data: {\"id\":\"c\",\"model\":\"gpt-5.6-sol\",\"choices\":[{\"index\":0,\"delta\":{\"role\":\"assistant\",\"content\":\"Hello\"},\"finish_reason\":null}]}\n\ndata: {\"id\":\"c\",\"model\":\"gpt-5.6-sol\",\"choices\":[{\"index\":0,\"delta\":{\"content\":\" world\"},\"finish_reason\":\"stop\"}]}\n\ndata: {\"id\":\"c\",\"model\":\"gpt-5.6-sol\",\"choices\":[],\"usage\":{\"prompt_tokens\":7,\"completion_tokens\":2}}\n\ndata: [DONE]\n\n"))
	}))
	defer server.Close()
	client := &HTTPUpstreamClient{BufferedSSE: true, Endpoints: []ProviderEndpoint{{Protocol: "chat", URL: server.URL}}}
	result, err := client.Complete(context.Background(), UpstreamRequest{Protocol: "chat", Payload: []byte(`{"model":"gpt-5.6-sol","stream":false}`)})
	if err != nil || !result.Complete || calls != 1 || !strings.Contains(string(result.Body), "Hello world") || !strings.Contains(result.ContentType, "application/json") || result.Usage["prompt_tokens"] != float64(7) {
		t.Fatalf("stream aggregation failed: err=%v calls=%d result=%+v", err, calls, result)
	}
}

func TestBufferedSSEPreservesToolsReasoningAndUsage(t *testing.T) {
	for _, tc := range []struct {
		name, protocol, stream string
		contains               []string
	}{
		{"parallel_chat_tools", "chat", `data: {"id":"c","model":"gpt-5.6-sol","choices":[{"index":0,"delta":{"role":"assistant","reasoning_content":"private state","tool_calls":[{"index":0,"id":"call-a","type":"function","function":{"name":"Read","arguments":"{\"path\":"}},{"index":1,"id":"call-b","type":"function","function":{"name":"Read","arguments":"{\"path\":"}}]},"finish_reason":null}]}

data: {"id":"c","model":"gpt-5.6-sol","choices":[{"index":0,"delta":{"tool_calls":[{"index":1,"function":{"arguments":"\"b.go\"}"}},{"index":0,"function":{"arguments":"\"a.go\"}"}}]},"finish_reason":"tool_calls"}]}

data: {"id":"c","model":"gpt-5.6-sol","choices":[],"usage":{"prompt_tokens":11,"completion_tokens":8}}

data: [DONE]

`, []string{"call-a", "call-b", "a.go", "b.go", "private state", "prompt_tokens"}},
		{"responses_complete", "responses", `event: response.created
data: {"type":"response.created","response":{"id":"r","model":"gpt-6-astra","status":"in_progress"}}

event: response.completed
data: {"type":"response.completed","response":{"id":"r","model":"gpt-6-astra","status":"completed","reasoning":{"effort":"high"},"output":[{"type":"reasoning","id":"rs","encrypted_content":"opaque-signature"},{"type":"function_call","call_id":"call-r","name":"Read","arguments":"{}"}],"usage":{"input_tokens":12,"output_tokens":6}}}

`, []string{"opaque-signature", "call-r", "high", "input_tokens"}},
		{"messages_signed_tools", "anthropic", `event: message_start
data: {"type":"message_start","message":{"type":"message","id":"m","model":"gpt-5.6-sol","role":"assistant","content":[],"usage":{"input_tokens":13,"output_tokens":1}}}

data: {"type":"content_block_start","index":0,"content_block":{"type":"thinking","thinking":""}}

data: {"type":"content_block_delta","index":0,"delta":{"type":"thinking_delta","thinking":"private state"}}

data: {"type":"content_block_delta","index":0,"delta":{"type":"signature_delta","signature":"opaque-signature"}}

data: {"type":"content_block_stop","index":0}

data: {"type":"content_block_start","index":1,"content_block":{"type":"tool_use","id":"call-m","name":"Read","input":{}}}

data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"{\"large_number\":"}}

data: {"type":"content_block_delta","index":1,"delta":{"type":"input_json_delta","partial_json":"9007199254740993}"}}

data: {"type":"content_block_stop","index":1}

data: {"type":"message_delta","delta":{"stop_reason":"tool_use","stop_sequence":null},"usage":{"output_tokens":9}}

data: {"type":"message_stop"}

`, []string{"opaque-signature", "call-m", "9007199254740993", `"output_tokens":9`, `"input_tokens":13`}},
	} {
		t.Run(tc.name, func(t *testing.T) {
			raw, err := aggregateSSE(context.Background(), tc.protocol, strings.NewReader(tc.stream), 1<<20)
			if err != nil {
				t.Fatal(err)
			}
			for _, want := range tc.contains {
				if !strings.Contains(string(raw), want) {
					t.Fatalf("missing field %q", want)
				}
			}
			// CRLF and split data lines must parse identically.
			crlf, err := aggregateSSE(context.Background(), tc.protocol, strings.NewReader(strings.ReplaceAll(tc.stream, "\n", "\r\n")), 1<<20)
			if err != nil || string(raw) != string(crlf) {
				t.Fatal("CRLF changed result")
			}
		})
	}
}

func TestBufferedSSERejectsMalformedOrIncompleteStreams(t *testing.T) {
	complete := `data: {"id":"c","model":"gpt-5.6-sol","choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}` + "\n\n"
	for name, stream := range map[string]string{
		"no_terminal":        complete,
		"no_finish":          strings.ReplaceAll(complete, `"stop"`, `null`) + "data: [DONE]\n\n",
		"broken_json":        "data: {broken}\n\n" + complete + "data: [DONE]\n\n",
		"error_after_finish": complete + "event: error\ndata: {\"message\":\"synthetic error\"}\n\ndata: [DONE]\n\n",
		"duplicate_terminal": complete + "data: [DONE]\n\ndata: [DONE]\n\n",
		"identity_change":    strings.ReplaceAll(complete, `"stop"`, `null`) + strings.ReplaceAll(complete, `"gpt-5.6-sol"`, `"gpt-6-astra"`) + "data: [DONE]\n\n",
		"missing_index":      strings.ReplaceAll(complete, `"index":0,`, "") + "data: [DONE]\n\n",
	} {
		t.Run(name, func(t *testing.T) {
			if _, err := aggregateSSE(context.Background(), "chat", strings.NewReader(stream), 1<<20); err == nil {
				t.Fatal("malformed stream marked complete")
			}
		})
	}
	if _, err := aggregateSSE(context.Background(), "chat", strings.NewReader(complete+"data: [DONE]\n\n"), 32); err == nil {
		t.Fatal("buffer limit ignored")
	}
}

func TestBufferedSSECancellationDoesNotRetry(t *testing.T) {
	started := make(chan struct{})
	ended := make(chan struct{})
	calls := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Header().Set("Content-Type", "text/event-stream")
		w.Write([]byte(": waiting\n\n"))
		w.(http.Flusher).Flush()
		close(started)
		<-r.Context().Done()
		close(ended)
	}))
	defer server.Close()
	client := &HTTPUpstreamClient{BufferedSSE: true, Endpoints: []ProviderEndpoint{{Protocol: "chat", URL: server.URL}}}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	result := make(chan error, 1)
	go func() {
		_, err := client.Complete(ctx, UpstreamRequest{Protocol: "chat", Payload: []byte(`{"model":"gpt-5.6-sol"}`)})
		result <- err
	}()
	<-started
	cancel()
	if err := <-result; err == nil {
		t.Fatal("cancelled stream accepted")
	}
	<-ended
	if calls != 1 {
		t.Fatal("cancelled generation was retried")
	}
}
