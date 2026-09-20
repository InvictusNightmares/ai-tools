package autogateway

import (
	"bytes"
	"testing"
)

func TestCompletedReasoningIsPortableButPendingToolReasoningIsPreserved(t *testing.T) {
	cases := []struct{ protocol, body string }{
		{"responses", `{"input":[{"role":"user","content":"old task"},{"type":"reasoning","id":"old-private-id","encrypted_content":"old-private-state","content":[{"type":"reasoning_text","text":"hidden"}]},{"type":"message","role":"assistant","id":"old-answer-id","content":[{"type":"output_text","text":"visible answer"}]},{"role":"user","content":"new task"},{"type":"reasoning","id":"pending-private-id","encrypted_content":"pending-private-state"},{"type":"function_call","id":"pending-call-item","call_id":"call-1","name":"Read","arguments":"{}"},{"type":"function_call_output","call_id":"call-1","output":"result"}]}`},
		{"anthropic", `{"messages":[{"role":"user","content":"old task"},{"role":"assistant","content":[{"type":"thinking","thinking":"hidden","signature":"old-private-state"},{"type":"text","text":"visible answer"}]},{"role":"user","content":"new task"},{"role":"assistant","content":[{"type":"thinking","thinking":"hidden","signature":"pending-private-state"},{"type":"tool_use","id":"call-1","name":"Read","input":{}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":"call-1","content":"result"},{"type":"text","text":"user correction within tool round"}]}]}`},
		{"chat", `{"messages":[{"role":"user","content":"old task"},{"role":"assistant","content":"visible answer","reasoning_content":"old-private-state"},{"role":"user","content":"new task"},{"role":"assistant","content":null,"reasoning_content":"pending-private-state","tool_calls":[{"id":"call-1","type":"function","function":{"name":"Read","arguments":"{}"}}]},{"role":"tool","tool_call_id":"call-1","content":"result"}]}`},
	}
	for _, c := range cases {
		t.Run(c.protocol, func(t *testing.T) {
			request, err := NormalizeProtocolRequest(c.protocol, []byte(c.body))
			if err != nil {
				t.Fatal(err)
			}
			before := append([]byte(nil), request.RawPayload...)
			if _, err = splitSemanticInput(request); err != nil {
				t.Fatalf("reasoning history blocked classification: %v", err)
			}
			result, err := BuildProviderPayload(c.protocol, request, BuildProviderParameters("openai", c.protocol, DefaultCatalog[3], ReasoningHigh, false))
			if err != nil {
				t.Fatal(err)
			}
			if bytes.Contains(result, []byte("old-private")) || bytes.Contains(result, []byte("old-answer-id")) {
				t.Fatal("completed provider-private state crossed turn boundary")
			}
			for _, want := range []string{"visible answer", "pending-private-state", "call-1", "result", "new task"} {
				if !bytes.Contains(result, []byte(want)) {
					t.Fatalf("required history lost: %s", want)
				}
			}
			if !bytes.Equal(request.RawPayload, before) {
				t.Fatal("original payload mutated before Guard/audit")
			}
		})
	}
}

func TestUserReasoningPartDoesNotMasqueradeAsAssistantHistory(t *testing.T) {
	request, err := NormalizeProtocolRequest("responses", []byte(`{"input":[{"role":"user","content":[{"type":"reasoning_text","text":"unsupported user input"}]}]}`))
	if err != nil {
		t.Fatal(err)
	}
	if _, err = splitSemanticInput(request); err == nil {
		t.Fatal("unsupported user modality accepted")
	}
}
