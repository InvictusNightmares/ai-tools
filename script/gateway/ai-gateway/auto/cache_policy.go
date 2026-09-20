package autogateway

import "time"

// ResponseCachePolicy controls business response-cache writes. Prompt-cache
// and routing-decision caches have separate lifecycles and must not reuse this
// policy or namespace.
type ResponseCachePolicy struct {
	TTL           time.Duration
	MaxEntryBytes int
}

func DefaultResponseCachePolicy() ResponseCachePolicy {
	return ResponseCachePolicy{TTL: 24 * time.Hour, MaxEntryBytes: 4 << 20}
}

func (policy ResponseCachePolicy) Eligible(request Request, preflight PreflightDecision, responseBytes int) (bool, string) {
	if preflight != PreflightAllow {
		return false, "preflight_not_allowed"
	}
	if request.CompactionTrigger || request.CompactionState {
		return false, "native_compaction_state"
	}
	if request.Stream {
		return false, "streaming_response"
	}
	if len(request.Tools) > 0 {
		return false, "tool_call_response"
	}
	for _, message := range request.Messages {
		if message.Role == "tool" || len(message.ToolCalls) > 0 || message.ToolCallID != "" {
			return false, "tool_history"
		}
		for _, part := range message.Parts {
			if part.Type == "tool_use" || part.Type == "tool_result" {
				return false, "tool_history"
			}
			if part.Type == "image_url" || part.Type == "input_image" {
				return false, "image_input"
			}
		}
	}
	if policy.TTL <= 0 {
		return false, "cache_disabled"
	}
	if policy.MaxEntryBytes > 0 && responseBytes > policy.MaxEntryBytes {
		return false, "response_too_large"
	}
	return true, "eligible"
}
