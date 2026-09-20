package autogateway

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"testing"
	"time"
)

type toolRoundUpstream struct {
	calls  int
	models []string
}

func (u *toolRoundUpstream) Complete(_ context.Context, r UpstreamRequest) (UpstreamResponse, error) {
	u.calls++
	u.models = append(u.models, r.Model.Name)
	callID := fmt.Sprintf("call-%d", u.calls)
	var response map[string]any
	switch r.Protocol {
	case "anthropic":
		response = map[string]any{"id": "reply", "model": r.Model.Name, "stop_reason": "tool_use", "content": []any{map[string]any{"type": "tool_use", "id": callID, "name": "Read", "input": map[string]any{"path": "fixture.txt"}}}}
	case "responses":
		response = map[string]any{"id": "reply", "model": r.Model.Name, "status": "completed", "output": []any{map[string]any{"type": "function_call", "call_id": callID, "name": "Read", "arguments": "{}"}}}
	default:
		response = map[string]any{"id": "reply", "model": r.Model.Name, "choices": []any{map[string]any{"finish_reason": "tool_calls", "message": map[string]any{"tool_calls": []any{map[string]any{"id": callID, "type": "function", "function": map[string]any{"name": "Read", "arguments": "{}"}}}}}}}
	}
	body, _ := json.Marshal(response)
	return UpstreamResponse{StatusCode: 200, Complete: true, Body: body, ResponseModel: r.Model.Name, ResponseID: "reply"}, nil
}

func toolResultFixture(protocol, id string) Request {
	var body string
	switch protocol {
	case "anthropic":
		body = fmt.Sprintf(`{"messages":[{"role":"user","content":"fix startup"},{"role":"assistant","content":[{"type":"tool_use","id":%q,"name":"Read","input":{}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":%q,"content":"two callbacks navigate twice"}]}]}`, id, id)
	case "responses":
		body = fmt.Sprintf(`{"input":[{"role":"user","content":"fix startup"},{"type":"function_call","call_id":%q,"name":"Read","arguments":"{}"},{"type":"function_call_output","call_id":%q,"output":"two callbacks navigate twice"}]}`, id, id)
	default:
		body = fmt.Sprintf(`{"messages":[{"role":"user","content":"fix startup"},{"role":"assistant","tool_calls":[{"id":%q,"type":"function","function":{"name":"Read","arguments":"{}"}}]},{"role":"tool","tool_call_id":%q,"content":"two callbacks navigate twice"}]}`, id, id)
	}
	r, err := NormalizeProtocolRequest(protocol, []byte(body))
	if err != nil {
		panic(err)
	}
	return r
}

func TestInterleavedAgentsResumeTheirOwnToolProvider(t *testing.T) {
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		t.Run(protocol, func(t *testing.T) {
			now := time.Now()
			complexity := "bounded"
			upstream := &toolRoundUpstream{}
			p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, StateStore: NewMemorySessionStateStore(), Upstream: upstream, Now: func() time.Time { return now }, Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
				a := assessment("debugging", complexity)
				a.NewTask = true
				return classificationFromAssessment(r, a), nil
			})}
			meta := PipelineMeta{RequestID: "first", Region: "tokyo", APIKeyID: "a", SessionID: "shared-parent"}
			first, err := p.ExecuteWithMeta(context.Background(), protocol, "", "auto", Request{Messages: []Message{{Role: "user", Content: "fix startup"}}}, 0, false, false, false, false, meta)
			if err != nil {
				t.Fatal(err)
			}
			complexity = "exceptional"
			meta.RequestID = "second"
			second, err := p.ExecuteWithMeta(context.Background(), protocol, "", "auto", Request{Messages: []Message{{Role: "user", Content: "system redesign"}}}, 0, false, false, false, false, meta)
			if err != nil || first.Decision.SelectedModel.Name == second.Decision.SelectedModel.Name {
				t.Fatalf("setup did not produce distinct providers: %v", err)
			}
			meta.RequestID = "third"
			meta.SessionID = "request-without-parent-id"
			third, err := p.ExecuteWithMeta(context.Background(), protocol, "", "auto", toolResultFixture(protocol, "call-1"), 0, false, false, false, false, meta)
			if err != nil || third.Decision.SelectedModel.Name != first.Decision.SelectedModel.Name || third.Decision.Reason != "tool_loop_locked" {
				t.Fatalf("tool result followed sibling routing: %+v %v", third.Decision, err)
			}
			meta.APIKeyID = "other-key"
			_, err = p.ExecuteWithMeta(context.Background(), protocol, "", "auto", toolResultFixture(protocol, "call-1"), 0, false, false, false, false, meta)
			if err == nil || err.Error() != "tool_context_unavailable" || upstream.calls != 3 {
				t.Fatal("cross-key tool result reached provider")
			}
			meta.APIKeyID = "a"
			now = now.Add(2 * time.Hour)
			_, err = p.ExecuteWithMeta(context.Background(), protocol, "", "auto", toolResultFixture(protocol, "call-1"), 0, false, false, false, false, meta)
			if err == nil || upstream.calls != 3 {
				t.Fatal("expired tool binding silently selected a new provider")
			}
		})
	}
}

func TestStreamToolCallIDsAcrossProtocols(t *testing.T) {
	for _, body := range []string{
		`{"choices":[{"delta":{"tool_calls":[{"id":"call-1"}]}}]}`,
		`{"type":"response.output_item.added","item":{"type":"function_call","call_id":"call-1"}}`,
		`{"type":"content_block_start","content_block":{"type":"tool_use","id":"call-1"}}`,
	} {
		observed := &observedSSEBody{ReadCloser: io.NopCloser(strings.NewReader("data: " + body + "\n\ndata: " + body + "\n\n"))}
		io.Copy(io.Discard, observed)
		if len(observed.ToolCallIDs) != 1 || observed.ToolCallIDs[0] != "call-1" {
			t.Fatal("stream tool ID lost or duplicated")
		}
	}
}

func TestMalformedStreamCannotBecomeSuccessfulAfterDone(t *testing.T) {
	body := "data: {\"id\":\"reply\",\"model\":\"gpt-5.6-sol\"}\n\ndata: {malformed payload}\n\ndata: [DONE]\n\n"
	observed := &observedSSEBody{ReadCloser: io.NopCloser(strings.NewReader(body))}
	io.Copy(io.Discard, observed)
	if observed.Complete || !observed.Invalid {
		t.Fatal("malformed SSE was recorded as a complete response")
	}
}

func TestSSEMultilineDataAndCRLF(t *testing.T) {
	body := "event: message\r\ndata: {\"id\":\"reply\",\r\ndata: \"model\":\"gpt-5.6-sol\"}\r\n\r\ndata: [DONE]\r\n\r\n"
	observed := &observedSSEBody{ReadCloser: io.NopCloser(strings.NewReader(body))}
	io.Copy(io.Discard, observed)
	if !observed.Complete || observed.Invalid || observed.Model != "gpt-5.6-sol" {
		t.Fatal("valid multiline SSE rejected")
	}
}
