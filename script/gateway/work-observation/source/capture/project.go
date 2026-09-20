// Package capture processes observation copies; it never edits forwarded bytes.
package capture

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"unicode/utf8"
)

func digest(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func omitted(value any, kind string) map[string]any {
	data, _ := json.Marshal(value)
	return map[string]any{"omitted": kind, "encoded_bytes": len(data), "sha256": digest(data)}
}

func decodeJSON(data []byte) (any, error) {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	var value any
	if err := dec.Decode(&value); err != nil {
		return nil, err
	}
	var extra any
	if err := dec.Decode(&extra); err != io.EOF {
		return nil, errors.New("multiple_json_values")
	}
	return value, nil
}

// projectPart recognizes protocol attachment containers, never arbitrary words,
// URLs, JSON keys or serialized JSON inside ordinary tool arguments/results.
func projectPart(value any) any {
	switch v := value.(type) {
	case []any:
		for i := range v {
			v[i] = projectPart(v[i])
		}
	case map[string]any:
		kind, _ := v["type"].(string)
		switch kind {
		case "input_image", "image_url", "image", "input_file", "file", "document", "input_audio", "audio", "output_audio":
			out := omitted(v, "attachment")
			for _, key := range []string{"type", "file_id", "filename", "detail", "format", "media_type", "mime_type", "id", "transcript"} {
				if field, ok := v[key]; ok {
					out[key] = field
				}
			}
			if source, ok := v["source"].(map[string]any); ok {
				for _, key := range []string{"media_type", "type", "file_id"} {
					if field, ok := source[key]; ok {
						out["source_"+key] = field
					}
				}
			}
			if file, ok := v["file"].(map[string]any); ok {
				for _, key := range []string{"filename", "file_id"} {
					if value, ok := file[key]; ok {
						out[key] = value
					}
				}
			}
			return out
		case "tool_use", "function_call", "function":
			return v // Tool code and arguments are literal evidence, not API media.
		case "image_generation_call":
			if result, ok := v["result"]; ok {
				v["result"] = omitted(result, "image")
			}
			return v
		case "tool_result":
			if content, ok := v["content"]; ok {
				v["content"] = projectPart(content)
			}
			return v
		}
		if content, ok := v["content"]; ok {
			v["content"] = projectPart(content)
		}
		// Chat Completions audio includes a transcript plus a binary data field.
		if audio, ok := v["audio"].(map[string]any); ok {
			if data, ok := audio["data"]; ok {
				audio["data"] = omitted(data, "audio")
			}
		}
	}
	return value
}

func projectEnvelope(value any) any {
	v, ok := value.(map[string]any)
	if !ok {
		return value
	}
	for _, key := range []string{"messages", "input", "output"} {
		if field, ok := v[key]; ok {
			v[key] = projectPart(field)
		}
	}
	if response, ok := v["response"]; ok {
		v["response"] = projectEnvelope(response)
	}
	if choices, ok := v["choices"].([]any); ok {
		for _, choice := range choices {
			if choice, ok := choice.(map[string]any); ok {
				for _, key := range []string{"message", "delta"} {
					if field, ok := choice[key]; ok {
						choice[key] = projectPart(field)
					}
				}
			}
		}
	}
	// Responses/Anthropic envelopes hold protocol content at known positions.
	for _, key := range []string{"item", "part", "content_block", "message"} {
		if field, ok := v[key]; ok {
			v[key] = projectPart(field)
		}
	}
	if content, ok := v["content"]; ok {
		v["content"] = projectPart(content)
	}
	kind, _ := v["type"].(string)
	switch kind {
	case "response.audio.delta", "response.output_audio.delta":
		if delta, ok := v["delta"]; ok {
			v["delta"] = omitted(delta, "audio_delta")
		}
	case "response.image_generation_call.partial_image":
		if data, ok := v["partial_image_b64"]; ok {
			v["partial_image_b64"] = omitted(data, "image")
		}
	}
	// Native Responses image generation output. The result is image bytes.
	if kind == "image_generation_call" {
		if result, ok := v["result"]; ok {
			v["result"] = omitted(result, "image")
		}
	}
	return v
}

// ProjectJSON preserves text, tool parameters, signatures and opaque native
// context. It does NOT redact or encrypt. Attachments alone become metadata.
// Invalid JSON is returned as an error, not guessed to be attachment-free text.
func ProjectJSON(data []byte) (json.RawMessage, error) {
	return ProjectJSONForPath(data, "")
}

// The endpoint is server-observed, not read from an untrusted JSON field.
func ProjectJSONForPath(data []byte, path string) (json.RawMessage, error) {
	if literalJSON(data, path) {
		// Borrow the worker-owned bytes until the synchronous sink has encoded
		// the event. Avoid decoding and re-encoding attachment-free JSON.
		return json.RawMessage(data), nil
	}
	value, err := decodeJSON(data)
	if err != nil {
		return nil, errors.New("invalid_json")
	}
	if path == "/v1/images/generations" || path == "/v1/images/edits" || path == "/v1/images/variations" {
		if obj, ok := value.(map[string]any); ok {
			if items, ok := obj["data"].([]any); ok {
				for _, item := range items {
					if image, ok := item.(map[string]any); ok {
						for _, key := range []string{"b64_json", "url"} {
							if data, ok := image[key]; ok {
								image[key] = omitted(data, "image")
							}
						}
					}
				}
			}
		}
	}
	return json.Marshal(projectEnvelope(value))
}

// Conservative fast path. Any JSON escape or attachment discriminator takes
// the existing structural projection path. A mere text mention is allowed to
// cause a slow-path false positive; a hidden attachment must never pass here.
func literalJSON(data []byte, path string) bool {
	if path == "/v1/images/generations" || path == "/v1/images/edits" || path == "/v1/images/variations" ||
		bytes.IndexByte(data, '\\') >= 0 || !utf8.Valid(data) || !json.Valid(data) {
		return false
	}
	for _, word := range []string{
		`"input_image"`, `"image_url"`, `"image"`, `"input_file"`, `"file"`, `"document"`,
		`"input_audio"`, `"audio"`, `"output_audio"`, `"image_generation_call"`,
		`"response.audio.delta"`, `"response.output_audio.delta"`, `"response.image_generation_call.partial_image"`,
	} {
		if bytes.Contains(data, []byte(word)) {
			return false
		}
	}
	return true
}

func ProjectSequence(events []json.RawMessage) (json.RawMessage, error) {
	out := make([]json.RawMessage, 0, len(events))
	for _, event := range events {
		projected, err := ProjectJSON(event)
		if err != nil {
			return nil, errors.New("invalid_stream_event")
		}
		out = append(out, projected)
	}
	return json.Marshal(out)
}
