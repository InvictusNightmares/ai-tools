package autogateway

import (
	"bytes"
	"encoding/json"
	"errors"
)

// BuildProviderPayload creates the provider envelope after routing. The input
// was normalized for classification, but raw content parts are retained so
// adapters do not silently drop images or other provider fields.
func BuildProviderPayload(protocol string, request Request, parameters ProviderParameters) ([]byte, error) {
	if len(request.RawPayload) > 0 {
		if request.Protocol != canonicalProtocol(protocol) {
			return nil, errors.New("cross_protocol_payload_unsupported")
		}
		var payload map[string]any
		decoder := json.NewDecoder(bytes.NewReader(request.RawPayload))
		decoder.UseNumber()
		if decoder.Decode(&payload) != nil || payload == nil {
			return nil, errors.New("invalid_provider_payload")
		}
		portableCompletedHistory(payload, canonicalProtocol(protocol))
		for _, name := range []string{"model", "reasoning_effort", "reasoning", "thinking"} {
			delete(payload, name)
		}
		if config, ok := payload["output_config"].(map[string]any); ok {
			delete(config, "effort")
			if len(config) == 0 {
				delete(payload, "output_config")
			}
		}
		payload["model"] = parameters.Model
		payload["stream"] = parameters.Stream
		for key, value := range parameters.ReasoningParameter {
			if key == "output_config" {
				if config, ok := payload[key].(map[string]any); ok {
					for k, v := range value.(map[string]any) {
						config[k] = v
					}
					continue
				}
			}
			payload[key] = value
		}
		if canonicalProtocol(protocol) == "chat" && parameters.Stream {
			options, _ := payload["stream_options"].(map[string]any)
			if options == nil {
				options = map[string]any{}
			}
			options["include_usage"] = true
			payload["stream_options"] = options
		}
		return json.Marshal(payload)
	}
	messages := make([]map[string]any, 0, len(request.Messages))
	for _, message := range request.Messages {
		content, err := payloadContent(message)
		if err != nil {
			return nil, err
		}
		messages = append(messages, map[string]any{"role": message.Role, "content": content})
	}
	canonical := canonicalProtocol(protocol)
	if canonical == "" {
		return nil, errors.New("unsupported protocol")
	}
	payload := map[string]any{"model": parameters.Model, "stream": parameters.Stream}
	for key, value := range parameters.ReasoningParameter {
		payload[key] = value
	}
	switch canonical {
	case "chat":
		payload["messages"] = messages
	case "responses":
		payload["input"] = messages
	case "anthropic":
		payload["messages"] = messages
		for _, message := range request.Messages {
			if message.Role == "system" {
				payload["system"] = message.Content
				break
			}
		}
	}
	if len(request.Tools) > 0 {
		tools := make([]any, 0, len(request.Tools))
		for _, tool := range request.Tools {
			var schema any = map[string]any{}
			if tool.Schema != "" {
				if err := json.Unmarshal([]byte(tool.Schema), &schema); err != nil {
					return nil, errors.New("tool schema is malformed")
				}
			}
			if canonical == "chat" {
				tools = append(tools, map[string]any{"type": "function", "function": map[string]any{"name": tool.Name, "parameters": schema}})
			} else {
				tools = append(tools, map[string]any{"type": "function", "name": tool.Name, "parameters": schema})
			}
		}
		payload["tools"] = tools
	}
	return json.Marshal(payload)
}

func canonicalProtocol(protocol string) string {
	switch protocol {
	case "chat", "chat.completions", "openai-chat":
		return "chat"
	case "responses", "openai-responses":
		return "responses"
	case "anthropic", "messages", "anthropic-messages":
		return "anthropic"
	default:
		return ""
	}
}

func payloadContent(message Message) (any, error) {
	if len(message.Parts) == 0 {
		return message.Content, nil
	}
	parts := make([]json.RawMessage, 0, len(message.Parts))
	for _, part := range message.Parts {
		if len(bytes.TrimSpace(part.Raw)) > 0 {
			var raw json.RawMessage
			if err := json.Unmarshal(part.Raw, &raw); err != nil {
				return nil, errors.New("content part is malformed")
			}
			parts = append(parts, raw)
			continue
		}
		encoded, err := json.Marshal(map[string]string{"type": part.Type, "text": part.Text})
		if err != nil {
			return nil, err
		}
		parts = append(parts, encoded)
	}
	return parts, nil
}
