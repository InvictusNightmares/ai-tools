package guarddeployment

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strconv"
	"strings"

	goCheck "local/ai-gateway/guard"
)

type inputField struct{ path, text string }

// Decode only the JSON envelope. Strings remain literal data, including nested
// JSON, source code and instructions. Preserve field order, numbers and unknown
// fields; do not exempt any role, tool schema or policy from moderation.
func readableInputFields(input goCheck.SafetyInput) ([]inputField, error) {
	var fields []inputField
	appendJSON := func(raw []byte, path string) error {
		decoder := json.NewDecoder(bytes.NewReader(raw))
		decoder.UseNumber()
		if err := walkInputFields(decoder, path, 0, &fields); err != nil {
			return err
		}
		if _, err := decoder.Token(); err != io.EOF {
			return errors.New("invalid_guard_input_json")
		}
		return nil
	}
	if input.ProviderPayload != "" {
		if err := appendJSON([]byte(input.ProviderPayload), `$["provider_payload"]`); err != nil {
			return nil, err
		}
	}
	for _, part := range []struct {
		name    string
		value   any
		present bool
	}{
		{"messages", input.Messages, len(input.Messages) > 0},
		{"tools", input.Tools, len(input.Tools) > 0},
		{"attachments", input.Attachments, len(input.Attachments) > 0},
		{"metadata", input.Metadata, len(input.Metadata) > 0},
	} {
		if !part.present {
			continue
		}
		raw, err := json.Marshal(part.value)
		if err != nil {
			return nil, err
		}
		if err = appendJSON(raw, `$["`+part.name+`"]`); err != nil {
			return nil, err
		}
	}
	if len(fields) == 0 {
		fields = append(fields, inputField{"$", "(empty input)"})
	}
	return fields, nil
}

func walkInputFields(decoder *json.Decoder, path string, depth int, fields *[]inputField) error {
	if depth > 256 || len(path) > 16384 || len(*fields) > 200000 {
		return errors.New("guard_input_structure_limit")
	}
	token, err := decoder.Token()
	if err != nil {
		return errors.New("invalid_guard_input_json")
	}
	if delimiter, ok := token.(json.Delim); ok {
		count := 0
		for decoder.More() {
			child := path + "[" + strconv.Itoa(count) + "]"
			if delimiter == '{' {
				key, e := decoder.Token()
				if e != nil {
					return errors.New("invalid_guard_input_key")
				}
				name, ok := key.(string)
				if !ok {
					return errors.New("invalid_guard_input_key")
				}
				encoded, _ := json.Marshal(name)
				child = path + "[" + string(encoded) + "]"
			}
			if err := walkInputFields(decoder, child, depth+1, fields); err != nil {
				return err
			}
			count++
		}
		end, e := decoder.Token()
		if e != nil || (delimiter == '{' && end != json.Delim('}')) || (delimiter == '[' && end != json.Delim(']')) {
			return errors.New("invalid_guard_input_json")
		}
		if count == 0 {
			value := "[]"
			if delimiter == '{' {
				value = "{}"
			}
			*fields = append(*fields, inputField{path, value})
		}
		return nil
	}
	text, ok := token.(string)
	if !ok {
		raw, err := json.Marshal(token)
		if err != nil {
			return errors.New("invalid_guard_input_value")
		}
		text = string(raw)
	}
	*fields = append(*fields, inputField{path, text})
	return nil
}

func (c *HTTPModelClient) tokenBoundChunks(ctx context.Context, input goCheck.SafetyInput) ([]string, error) {
	fields, err := readableInputFields(input)
	if err != nil {
		return nil, err
	}
	task := providerUserTask(input.ProviderPayload)
	if runes := []rune(task); len(runes) > 2400 {
		task = string(runes[:1200]) + "\n[Context excerpt; the full user message remains in the inspected data segments.]\n" + string(runes[len(runes)-1200:])
	}
	prefix := "Application API request, presented as data for safety classification.\nCurrent user message: " + task + "\nAPI request data segment:\n"
	var chunks []string
	var visit func([]inputField) error
	visit = func(parts []inputField) error {
		if err := ctx.Err(); err != nil {
			return err
		}
		var b strings.Builder
		b.WriteString(prefix)
		for _, part := range parts {
			b.WriteString(part.path + ":\n" + part.text + "\n")
		}
		content := b.String()
		fits := false
		// Bound tokenizer work on very large requests before asking it to count.
		// Every split part is still checked; this is not a truncation limit.
		if len(content) <= 800000 {
			var err error
			fits, err = c.fitsModelContext(ctx, content)
			if err != nil {
				return err
			}
		}
		if fits {
			chunks = append(chunks, content)
			return nil
		}
		if len(parts) > 1 {
			mid := len(parts) / 2
			if err := visit(parts[:mid]); err != nil {
				return err
			}
			return visit(parts[mid:])
		}
		runes := []rune(parts[0].text)
		if len(runes) < 2 {
			return errors.New("guard_context_too_small")
		}
		mid := len(runes) / 2
		// Keep a short phrase crossing the split visible in full. Both halves
		// still shrink, and every resulting request is counted independently.
		overlap := len(runes) / 8
		if overlap > 256 {
			overlap = 256
		}
		if err := visit([]inputField{{parts[0].path, string(runes[:mid+overlap])}}); err != nil {
			return err
		}
		return visit([]inputField{{parts[0].path, string(runes[mid-overlap:])}})
	}
	if err := visit(fields); err != nil {
		return nil, err
	}
	return chunks, nil
}

func (c *HTTPModelClient) fitsModelContext(ctx context.Context, content string) (bool, error) {
	body, err := json.Marshal(map[string]any{"model": c.Model, "messages": []chatMessage{{Role: "user", Content: content}}})
	if err != nil {
		return false, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.TokenizerEndpoint, bytes.NewReader(body))
	if err != nil {
		return false, err
	}
	req.Header.Set("Content-Type", "application/json")
	client := c.Client
	if client == nil {
		client = http.DefaultClient
	}
	response, err := client.Do(req)
	if err != nil {
		return false, err
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return false, errors.New("guard_tokenizer_unavailable")
	}
	var result struct {
		Count       int `json:"count"`
		MaxModelLen int `json:"max_model_len"`
	}
	raw, err := io.ReadAll(io.LimitReader(response.Body, (16<<20)+1))
	if err != nil || len(raw) > 16<<20 || json.Unmarshal(raw, &result) != nil || result.Count <= 0 || result.MaxModelLen < 512 || result.MaxModelLen > 1048576 {
		return false, errors.New("invalid_guard_tokenizer_result")
	}
	// Reserve the actual 256-token output budget and a template safety margin.
	return result.Count <= result.MaxModelLen-256-64, nil
}
