package autogateway

// portableCompletedHistory removes provider-private reasoning from completed
// turns after Guard has checked the full input. Public text, phase, tools and
// results remain. The active tool round is retained verbatim: its reasoning
// and call IDs belong to the model pinned by the tool binding.
//
// This pilot deliberately uses current-turn reasoning continuity. Cross-turn
// opaque state needs verified model/account provenance before it can be reused
// safely across this multi-provider endpoint.
func portableCompletedHistory(payload map[string]any, protocol string) {
	field := "messages"
	if protocol == "responses" {
		field = "input"
	}
	items, ok := payload[field].([]any)
	if !ok {
		return
	}
	boundary := -1
	for i, item := range items {
		message, ok := item.(map[string]any)
		if !ok || message["role"] != "user" {
			continue
		}
		// A tool_result accompanied by a user correction is still inside the
		// pinned round. It must not discard that round's signed reasoning.
		hasToolResult := false
		parts, _ := message["content"].([]any)
		for _, part := range parts {
			if p, ok := part.(map[string]any); ok && p["type"] == "tool_result" {
				hasToolResult = true
			}
		}
		if !hasToolResult {
			boundary = i
		}
	}
	if boundary < 0 {
		return
	}
	result := make([]any, 0, len(items))
	for i, item := range items {
		message, ok := item.(map[string]any)
		if !ok || i >= boundary {
			result = append(result, item)
			continue
		}
		if protocol == "responses" && message["type"] == "reasoning" {
			continue
		}
		if protocol == "responses" && (message["role"] == "assistant" || message["type"] == "function_call" || message["type"] == "function_call_output") {
			// Keep call_id for tool pairing, remove only server-local item IDs.
			delete(message, "id")
		}
		if message["role"] == "assistant" {
			delete(message, "reasoning_content")
			delete(message, "reasoning")
			parts, isArray := message["content"].([]any)
			if isArray && protocol == "anthropic" {
				kept := make([]any, 0, len(parts))
				for _, part := range parts {
					p, ok := part.(map[string]any)
					if ok && (p["type"] == "thinking" || p["type"] == "redacted_thinking") {
						continue
					}
					kept = append(kept, part)
				}
				if len(kept) == 0 {
					continue
				}
				message["content"] = kept
			}
		}
		result = append(result, message)
	}
	payload[field] = result
}
