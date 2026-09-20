package capture

import (
	"bytes"
	"encoding/json"
	"errors"
	"strings"
)

func ParseSSE(data []byte) ([]json.RawMessage, error) {
	var events []json.RawMessage
	var current []string
	flush := func() error {
		if len(current) == 0 {
			return nil
		}
		text := strings.Join(current, "\n")
		current = nil
		if text == "[DONE]" {
			return nil
		}
		if !json.Valid([]byte(text)) {
			return errors.New("invalid_sse_json")
		}
		events = append(events, json.RawMessage(text))
		return nil
	}
	for _, line := range bytes.Split(data, []byte{'\n'}) {
		line = bytes.TrimSuffix(line, []byte{'\r'})
		if len(line) == 0 {
			if err := flush(); err != nil {
				return events, err
			}
			continue
		}
		if bytes.HasPrefix(line, []byte("data:")) {
			value := line[5:]
			if len(value) > 0 && value[0] == ' ' {
				value = value[1:]
			}
			current = append(current, string(value))
		}
	}
	if err := flush(); err != nil {
		return events, err
	}
	return events, nil
}

// ProjectSSE preserves transport IDs/types and terminal markers alongside each
// projected JSON event. Comments have no model text and are not retained.
func ProjectSSE(data []byte) (json.RawMessage, error) {
	var records []json.RawMessage
	var lines []string
	eventType, eventID, retry := "", "", ""
	flush := func() error {
		if len(lines) == 0 {
			eventType = ""
			retry = ""
			return nil
		}
		text := strings.Join(lines, "\n")
		lines = nil
		var payload json.RawMessage
		var err error
		if text == "[DONE]" {
			payload = json.RawMessage(`"[DONE]"`)
		} else {
			payload, err = ProjectJSON([]byte(text))
			if err != nil {
				return err
			}
		}
		row := struct {
			Transport string          `json:"_capture_transport"`
			Type      string          `json:"event"`
			ID        string          `json:"id,omitempty"`
			Retry     string          `json:"retry,omitempty"`
			Data      json.RawMessage `json:"data"`
		}{"sse", eventType, eventID, retry, payload}
		if row.Type == "" {
			row.Type = "message"
		}
		b, err := json.Marshal(row)
		if err != nil {
			return err
		}
		records = append(records, b)
		eventType = ""
		retry = ""
		return nil
	}
	for _, line := range bytes.Split(data, []byte{'\n'}) {
		line = bytes.TrimSuffix(line, []byte{'\r'})
		if len(line) == 0 {
			if err := flush(); err != nil {
				b, _ := json.Marshal(records)
				return b, err
			}
			continue
		}
		key, value, found := strings.Cut(string(line), ":")
		if !found {
			value = ""
		}
		value = strings.TrimPrefix(value, " ")
		switch key {
		case "data":
			lines = append(lines, value)
		case "event":
			eventType = value
		case "id":
			if !strings.ContainsRune(value, 0) {
				eventID = value
			}
		case "retry":
			retry = value
		}
	}
	if err := flush(); err != nil {
		b, _ := json.Marshal(records)
		return b, err
	}
	return json.Marshal(records)
}
