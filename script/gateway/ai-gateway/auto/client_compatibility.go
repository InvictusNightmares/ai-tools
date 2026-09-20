package autogateway

import "strings"

// Client aliases enter Auto routing. They do not force a business model or
// inherit the regional Sub2API's former fixed alias-to-model mapping.
func isClaudeCodeAlias(model string) bool {
	switch model {
	case "claude-opus-5", "claude-sonnet-5", "claude-haiku-4", "claude-haiku-4-5-20251001":
		return true
	}
	return false
}

// Anthropic tool results have role=user but are not a fresh user goal.
func isToolResultMessage(message Message) bool {
	if message.Role == "tool" {
		return true
	}
	hasResult := false
	for _, part := range message.Parts {
		if (part.Type == "text" || part.Type == "input_text") && strings.TrimSpace(part.Text) != "" {
			return false
		}
		if part.Type == "tool_result" {
			hasResult = true
		}
	}
	return hasResult
}
