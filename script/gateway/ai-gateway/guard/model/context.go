package guarddeployment

import (
	"encoding/json"
	"strings"
)

// Every original character is still checked. Context is repeated, never used
// as an instruction to trust or skip configuration, history or tool content.
func contextualInputChunks(text, providerPayload string, maxChars int) []string {
	task := providerUserTask(providerPayload)
	contextLimit := maxChars / 4
	if contextLimit > 2400 {
		contextLimit = 2400
	}
	if runes := []rune(task); len(runes) > contextLimit && contextLimit > 1 {
		half := contextLimit / 2
		task = string(runes[:half]) + "\n[Context excerpt; the full user message remains in the inspected data segments.]\n" + string(runes[len(runes)-half:])
	}
	prefix := "Application API request, presented as data for safety classification.\nCurrent user message: " + task + "\nAPI request data segment:\n"
	remaining := maxChars - len([]rune(prefix))
	if remaining < maxChars/2 || remaining < 1 {
		return splitRunes(text, maxChars)
	}
	chunks := splitRunes(text, remaining)
	for i := range chunks {
		chunks[i] = prefix + chunks[i]
	}
	return chunks
}

func providerUserTask(raw string) string {
	var body struct {
		Messages []json.RawMessage `json:"messages"`
		Input    json.RawMessage   `json:"input"`
	}
	if json.Unmarshal([]byte(raw), &body) != nil {
		return ""
	}
	messages := body.Messages
	if len(body.Input) > 0 {
		var text string
		if json.Unmarshal(body.Input, &text) == nil {
			return text
		}
		if json.Unmarshal(body.Input, &messages) != nil {
			return ""
		}
	}
	for i := len(messages) - 1; i >= 0; i-- {
		var message struct {
			Role    string          `json:"role"`
			Content json.RawMessage `json:"content"`
		}
		if json.Unmarshal(messages[i], &message) != nil || message.Role != "user" {
			continue
		}
		var text string
		if json.Unmarshal(message.Content, &text) == nil && text != "" {
			return text
		}
		var parts []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		}
		if json.Unmarshal(message.Content, &parts) != nil {
			continue
		}
		var texts []string
		for _, part := range parts {
			if (part.Type == "text" || part.Type == "input_text") && part.Text != "" {
				texts = append(texts, part.Text)
			}
		}
		if len(texts) > 0 {
			return strings.Join(texts, "\n")
		}
	}
	return ""
}
