package autogateway

import (
	"encoding/json"
	"strings"
)

// OpenCode also records user-invoked commands as a complete local call/result
// pair. No provider issued these IDs, so there is no provider round to resume.
// This is a transport compatibility hint, never authentication or authority to
// execute a tool. The complete payload still passes identity and Guard first;
// it cannot retrieve a response, tool state, or file belonging to another key.
func clientLocalToolPair(r Request, meta PipelineMeta) bool {
	if !strings.HasPrefix(meta.ClientHeaders.Get("User-Agent"), "opencode/") {
		return false
	}
	var body struct {
		Input    []wireMessage `json:"input"`
		Messages []wireMessage `json:"messages"`
	}
	if json.Unmarshal(r.RawPayload, &body) != nil {
		return false
	}
	items := body.Messages
	if r.Protocol == "responses" {
		items = body.Input
	}
	if len(items) < 3 {
		return false
	}
	marker, call, result := items[len(items)-3], items[len(items)-2], items[len(items)-1]
	if marker.Role != "user" {
		return false
	}
	var text string
	if json.Unmarshal(marker.Content, &text) != nil {
		var parts []wirePart
		if json.Unmarshal(marker.Content, &parts) != nil || len(parts) != 1 || (parts[0].Type != "text" && parts[0].Type != "input_text") {
			return false
		}
		text = parts[0].Text
	}
	if text != "The following tool was executed by the user" {
		return false
	}
	var id, name, resultID string
	switch r.Protocol {
	case "responses":
		if call.Type != "function_call" || result.Type != "function_call_output" || len(result.Output) == 0 || !json.Valid([]byte(call.Arguments)) {
			return false
		}
		id, name, resultID = call.CallID, call.Name, result.CallID
	case "chat":
		var calls []struct {
			ID       string `json:"id"`
			Type     string `json:"type"`
			Function struct {
				Name      string `json:"name"`
				Arguments string `json:"arguments"`
			} `json:"function"`
		}
		if call.Role != "assistant" || result.Role != "tool" || len(result.Content) == 0 || json.Unmarshal(call.ToolCalls, &calls) != nil || len(calls) != 1 || calls[0].Type != "function" || !json.Valid([]byte(calls[0].Function.Arguments)) {
			return false
		}
		id, name, resultID = calls[0].ID, calls[0].Function.Name, result.ToolCallID
	case "anthropic":
		var calls []struct {
			Type  string          `json:"type"`
			ID    string          `json:"id"`
			Name  string          `json:"name"`
			Input json.RawMessage `json:"input"`
		}
		var results []struct {
			Type    string          `json:"type"`
			ID      string          `json:"tool_use_id"`
			Content json.RawMessage `json:"content"`
		}
		if call.Role != "assistant" || result.Role != "user" || json.Unmarshal(call.Content, &calls) != nil || len(calls) != 1 || calls[0].Type != "tool_use" || !json.Valid(calls[0].Input) || json.Unmarshal(result.Content, &results) != nil || len(results) != 1 || results[0].Type != "tool_result" || len(results[0].Content) == 0 {
			return false
		}
		id, name, resultID = calls[0].ID, calls[0].Name, results[0].ID
	default:
		return false
	}
	// Native local commands use a ULID; normal provider call IDs must retain
	// their binding even if a client copies the explanatory marker.
	if len(id) != 26 || id != resultID || (name != "task" && name != "bash") {
		return false
	}
	for _, c := range id {
		if !strings.ContainsRune("0123456789ABCDEFGHJKMNPQRSTVWXYZ", c) {
			return false
		}
	}
	return true
}
