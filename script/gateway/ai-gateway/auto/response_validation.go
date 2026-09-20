package autogateway

import "encoding/json"

// Completeness is a protocol terminal condition, not merely HTTP 200 or valid JSON.
func completeJSONResponse(protocol string, body []byte) bool {
	var r struct {
		ID      string `json:"id"`
		Model   string `json:"model"`
		Status  string `json:"status"`
		Stop    string `json:"stop_reason"`
		Choices []struct {
			Finish  *string         `json:"finish_reason"`
			Message json.RawMessage `json:"message"`
		} `json:"choices"`
		Content json.RawMessage `json:"content"`
		Output  json.RawMessage `json:"output"`
	}
	if json.Unmarshal(body, &r) != nil || r.ID == "" || r.Model == "" {
		return false
	}
	switch canonicalProtocol(protocol) {
	case "chat":
		if len(r.Choices) == 0 {
			return false
		}
		for _, choice := range r.Choices {
			if choice.Finish == nil || *choice.Finish == "" || len(choice.Message) == 0 {
				return false
			}
		}
		return true
	case "responses":
		return r.Status == "completed" && len(r.Output) > 0
	case "anthropic":
		return r.Stop != "" && len(r.Content) > 0
	}
	return false
}
