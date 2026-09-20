package autogateway

import "encoding/json"

// These bounded enum values are safe for routing diagnostics. Never log a
// user-supplied format name or schema, which can contain private task data.
func requestOutputFormat(protocol string, raw map[string]json.RawMessage) string {
	formats := []json.RawMessage{raw["response_format"]}
	container := ""
	switch canonicalProtocol(protocol) {
	case "responses":
		container = "text"
	case "anthropic":
		container = "output_config"
	}
	if value := raw[container]; len(value) > 0 && string(value) != "null" {
		var config map[string]json.RawMessage
		if json.Unmarshal(value, &config) != nil || config == nil {
			return "unknown"
		}
		// Verbosity and reasoning effort are not output schemas.
		formats = append(formats, config["format"])
	}
	kind := "text"
	for _, value := range formats {
		if len(value) == 0 || string(value) == "null" {
			continue
		}
		var format struct {
			Type string `json:"type"`
		}
		if json.Unmarshal(value, &format) != nil {
			return "unknown"
		}
		switch format.Type {
		case "text":
		case "json_schema":
			kind = "json_schema"
		case "json_object":
			if kind == "text" {
				kind = "json_object"
			}
		default:
			// Unknown/future formats retain the conservative capability gate.
			return "unknown"
		}
	}
	return kind
}
