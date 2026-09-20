package autogateway

import (
	"encoding/json"
	"errors"
	"fmt"
)

// NormalizeProtocolRequest converts the supported provider envelopes into the
// protocol-neutral Request consumed by the classifier. Provider fields that
// affect routing, including reasoning_effort, are deliberately ignored.
func NormalizeProtocolRequest(protocol string, body []byte) (Request, error) {
	request, err := normalizeProtocolRequest(protocol, body)
	if err != nil {
		return request, err
	}
	var raw map[string]json.RawMessage
	if json.Unmarshal(body, &raw) != nil || raw == nil {
		return request, errors.New("invalid_request")
	}
	request.OutputFormat = requestOutputFormat(protocol, raw)
	request.ResponseFormat = request.OutputFormat != "text"
	// The specialized reviewer owns its exact model, effort and schema. It
	// never enters Auto classification; stripping these fields changes approvals.
	var model string
	_ = json.Unmarshal(raw["model"], &model)
	if canonicalProtocol(protocol) == "responses" && model == ActionReviewModel {
		for _, name := range []string{"previous_response_id", "conversation"} {
			if value := raw[name]; len(value) > 0 && string(value) != "null" {
				return request, errors.New("full_conversation_required")
			}
		}
		request.RawPayload = append([]byte(nil), body...)
		request.Protocol = "responses"
		return request, nil
	}
	for _, name := range []string{"model", "reasoning_effort", "reasoning", "thinking"} {
		delete(raw, name)
	}
	if canonicalProtocol(protocol) == "responses" {
		var tools []map[string]json.RawMessage
		if len(raw["tools"]) > 0 && string(raw["tools"]) != "null" {
			if json.Unmarshal(raw["tools"], &tools) != nil {
				return request, errors.New("invalid_tools")
			}
			for _, tool := range tools {
				var typ, model string
				_ = json.Unmarshal(tool["type"], &typ)
				if typ != "image_generation" {
					continue
				}
				_ = json.Unmarshal(tool["model"], &model)
				if model == "" || model == "auto" {
					model = ImageFlare
					tool["model"], _ = json.Marshal(model)
				}
				if model != ImageFlare && model != ImageSunburst {
					return request, errors.New("image_model_not_supported")
				}
				delete(tool, "reasoning_effort")
				delete(tool, "reasoning")
			}
			raw["tools"], _ = json.Marshal(tools)
		}
	}
	if value := raw["output_config"]; len(value) > 0 && string(value) != "null" {
		var config map[string]json.RawMessage
		if json.Unmarshal(value, &config) != nil || config == nil {
			return request, errors.New("invalid_output_config")
		}
		delete(config, "effort")
		if len(config) == 0 {
			delete(raw, "output_config")
		} else {
			raw["output_config"], _ = json.Marshal(config)
		}
	}
	// Server-stored history cannot be reviewed or ported across providers.
	for _, name := range []string{"previous_response_id", "conversation"} {
		if v := raw[name]; len(v) > 0 && string(v) != "null" {
			return request, errors.New("full_conversation_required")
		}
	}
	request.RawPayload, _ = json.Marshal(raw)
	request.Protocol = canonicalProtocol(protocol)
	return request, nil
}

func normalizeProtocolRequest(protocol string, body []byte) (Request, error) {
	switch protocol {
	case "chat", "chat.completions", "openai-chat":
		return decodeChatCompletions(body)
	case "responses", "openai-responses":
		return decodeResponses(body)
	case "anthropic", "messages", "anthropic-messages":
		return decodeAnthropicMessages(body)
	default:
		return Request{}, fmt.Errorf("unsupported protocol %q", protocol)
	}
}

type wireMessage struct {
	Role       string          `json:"role"`
	Content    json.RawMessage `json:"content"`
	ToolCalls  json.RawMessage `json:"tool_calls"`
	ToolCallID string          `json:"tool_call_id"`
	CallID     string          `json:"call_id"`
	Type       string          `json:"type"`
	Name       string          `json:"name"`
	Arguments  string          `json:"arguments"`
	Output     json.RawMessage `json:"output"`
}

type wirePart struct {
	Type string `json:"type"`
	Text string `json:"text"`
}

type wireTool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	Parameters  json.RawMessage `json:"parameters"`
	InputSchema json.RawMessage `json:"input_schema"`
	Function    *wireTool       `json:"function"`
}

func decodeChatCompletions(body []byte) (Request, error) {
	var payload struct {
		Messages       []wireMessage   `json:"messages"`
		Tools          []wireTool      `json:"tools"`
		ResponseFormat json.RawMessage `json:"response_format"`
		Stream         bool            `json:"stream"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return Request{}, err
	}
	request, err := normalizeMessages(payload.Messages)
	if err != nil {
		return Request{}, err
	}
	request.Tools = normalizeTools(payload.Tools)
	request.Stream = payload.Stream
	return request, nil
}

func decodeResponses(body []byte) (Request, error) {
	var payload struct {
		Input          json.RawMessage `json:"input"`
		Instructions   string          `json:"instructions"`
		Tools          []wireTool      `json:"tools"`
		Text           json.RawMessage `json:"text"`
		Reasoning      json.RawMessage `json:"reasoning"`
		ResponseFormat json.RawMessage `json:"response_format"`
		Stream         bool            `json:"stream"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return Request{}, err
	}
	var messages []wireMessage
	if len(payload.Input) > 0 && string(payload.Input) != "null" {
		if err := json.Unmarshal(payload.Input, &messages); err != nil {
			var text string
			if err := json.Unmarshal(payload.Input, &text); err != nil {
				return Request{}, errors.New("responses input must be a string or message array")
			}
			messages = []wireMessage{{Role: "user", Content: json.RawMessage(mustJSON(text))}}
		}
	}
	if payload.Instructions != "" {
		messages = append([]wireMessage{{Role: "system", Content: mustJSON(payload.Instructions)}}, messages...)
	}
	request, err := normalizeMessages(messages)
	if err != nil {
		return Request{}, err
	}
	request.Tools = normalizeTools(payload.Tools)
	for _, message := range messages {
		if message.Type == "compaction_trigger" {
			request.CompactionTrigger = true
		}
		if message.Type == "compaction" || message.Type == "compaction_summary" {
			request.CompactionState = true
		}
	}
	request.Stream = payload.Stream
	return request, nil
}

func decodeAnthropicMessages(body []byte) (Request, error) {
	var payload struct {
		System   json.RawMessage `json:"system"`
		Messages []wireMessage   `json:"messages"`
		Tools    []wireTool      `json:"tools"`
		Stream   bool            `json:"stream"`
	}
	if err := json.Unmarshal(body, &payload); err != nil {
		return Request{}, err
	}
	messages := append([]wireMessage(nil), payload.Messages...)
	if len(payload.System) > 0 && string(payload.System) != "null" {
		messages = append([]wireMessage{{Role: "system", Content: payload.System}}, messages...)
	}
	request, err := normalizeMessages(messages)
	if err != nil {
		return Request{}, err
	}
	request.Tools = normalizeTools(payload.Tools)
	request.Stream = payload.Stream
	return request, nil
}

func normalizeMessages(messages []wireMessage) (Request, error) {
	request := Request{Messages: make([]Message, 0, len(messages))}
	for _, item := range messages {
		if item.Type == "configuration_update" {
			return Request{}, errors.New("client_configuration_update_not_allowed")
		}
		message := Message{Role: item.Role, ToolCalls: item.ToolCalls, ToolCallID: item.ToolCallID}
		if item.Type == "reasoning" {
			// Provider-private reasoning is transport state, not a user task.
			// RawPayload still retains it for Guard and the active tool round.
			request.Messages = append(request.Messages, Message{Role: "assistant", Content: "[assistant reasoning block retained for transport]"})
			continue
		}
		if item.Type == "function_call" {
			message.Role = "assistant"
			message.Content = item.Name + "\n" + item.Arguments
			request.Messages = append(request.Messages, message)
			continue
		}
		if item.Type == "function_call_output" {
			message.Role = "tool"
			message.ToolCallID = item.CallID
			message.Content = string(item.Output)
			request.Messages = append(request.Messages, message)
			continue
		}
		if len(item.Content) == 0 || string(item.Content) == "null" {
			request.Messages = append(request.Messages, message)
			continue
		}
		var text string
		if json.Unmarshal(item.Content, &text) == nil {
			message.Content = text
			request.Messages = append(request.Messages, message)
			continue
		}
		var parts []wirePart
		if err := json.Unmarshal(item.Content, &parts); err != nil {
			return Request{}, errors.New("message content must be a string or content-part array")
		}
		var rawParts []json.RawMessage
		if err := json.Unmarshal(item.Content, &rawParts); err != nil || len(rawParts) != len(parts) {
			return Request{}, errors.New("message content parts are malformed")
		}
		for index, part := range parts {
			message.Parts = append(message.Parts, ContentPart{Type: part.Type, Text: part.Text, Raw: append([]byte(nil), rawParts[index]...)})
			if part.Type == "text" || part.Type == "input_text" {
				message.Content += part.Text
			}
		}
		request.Messages = append(request.Messages, message)
	}
	return request, nil
}

func normalizeTools(tools []wireTool) []Tool {
	result := make([]Tool, 0, len(tools))
	for _, item := range tools {
		if item.Function != nil {
			item = *item.Function
		}
		schema := string(item.Parameters)
		if len(item.InputSchema) > 0 {
			schema = string(item.InputSchema)
		}
		result = append(result, Tool{Name: item.Name, Schema: schema, Description: item.Description})
	}
	return result
}

func mustJSON(value string) []byte { result, _ := json.Marshal(value); return result }

// A tool-result request continues the current provider tool round. An actual
// user message starts a new boundary even when earlier history contains tools.
func requestToolContinuation(r Request) bool {
	for i := len(r.Messages) - 1; i >= 0; i-- {
		m := r.Messages[i]
		if m.Role == "tool" {
			return true
		}
		for _, p := range m.Parts {
			if p.Type == "tool_result" {
				return true
			}
		}
		if m.Role == "assistant" {
			return false
		}
	}
	return false
}
