package autogateway

import (
	"encoding/json"
	"errors"
)

// The legacy unary API uses the provider's actual native compaction operation.
// It never creates or interprets encrypted state locally.
func prepareCompactRequest(raw []byte) ([]byte, error) {
	decoded, err := nativeDecode(raw)
	if err != nil {
		return nil, err
	}
	root, ok := decoded.(map[string]any)
	if !ok {
		return nil, errors.New("invalid_compaction_input")
	}
	var input []any
	switch value := root["input"].(type) {
	case string:
		input = []any{map[string]any{"role": "user", "content": value}}
	case []any:
		input = value
	default:
		return nil, errors.New("invalid_compaction_input")
	}
	if len(input) == 0 {
		return nil, errors.New("empty_compaction_input")
	}
	for _, value := range input {
		item, ok := value.(map[string]any)
		if !ok || item["type"] == "compaction_trigger" {
			return nil, errors.New("invalid_compaction_input")
		}
	}
	root["input"] = append(input, map[string]any{"type": "compaction_trigger"})
	root["stream"] = false
	return json.Marshal(root)
}

func compactResponseBody(request Request, response UpstreamResponse) ([]byte, error) {
	decoded, err := nativeDecode(request.RawPayload)
	if err != nil {
		return nil, err
	}
	input, ok := decoded.(map[string]any)
	if !ok {
		return nil, errors.New("invalid_compaction_input")
	}
	decoded, err = nativeDecode(response.Body)
	if err != nil || !response.Complete {
		return nil, errors.New("upstream_compaction_incomplete")
	}
	root, ok := decoded.(map[string]any)
	if !ok {
		return nil, errors.New("upstream_compaction_invalid")
	}
	items, _ := root["output"].([]any)
	var state any
	for _, value := range items {
		item, ok := value.(map[string]any)
		if !ok || item["type"] != "compaction" || state != nil {
			return nil, errors.New("upstream_compaction_invalid")
		}
		encrypted, _ := item["encrypted_content"].(string)
		if encrypted == "" {
			return nil, errors.New("upstream_compaction_invalid")
		}
		state = item
	}
	if state == nil {
		return nil, errors.New("upstream_compaction_missing")
	}
	retained := []any{}
	// Guard's prepared input contains the checked text and original attachments.
	// Preserve user and instruction messages; assistant/tool history is carried
	// by the provider's opaque state, as in the native Codex v2 path.
	history, _ := input["input"].([]any)
	for _, value := range history {
		item, ok := value.(map[string]any)
		if !ok {
			continue
		}
		role, _ := item["role"].(string)
		if role == "user" || role == "developer" || role == "system" {
			retained = append(retained, item)
		}
	}
	retained = append(retained, state)
	return json.Marshal(map[string]any{"id": root["id"], "object": "response.compaction", "created_at": root["created_at"], "output": retained, "usage": root["usage"]})
}
