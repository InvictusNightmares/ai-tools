package autogateway

import (
	"bytes"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"strings"
)

const NativeGuardScope = "text_and_attachment_metadata_only"
const NativeStateGuardScope = "text_and_attachment_and_opaque_state_metadata_only"
const MaxNativeRequestBytes = 64 << 20

// The user explicitly excludes attachment contents from the text Guard. Keep
// an exact, digest-bound native part for transport; never claim it was scanned.
type NativeMedia struct {
	ClassifierHistory []any    `json:"-"`
	Compactions       int      `json:"compactions,omitempty"`
	ClassifierParts   []any    `json:"-"`
	Images            int      `json:"images"`
	Files             int      `json:"files"`
	Audio             int      `json:"audio"`
	Bytes             int      `json:"bytes"`
	Digest            string   `json:"digest"`
	Semantic          *Request `json:"-"`
}

func nativeGuardScope(media *NativeMedia) string {
	if media != nil && media.Compactions > 0 {
		return NativeStateGuardScope
	}
	return NativeGuardScope
}

type nativePart struct {
	path     []any
	original any
	view     any
}

type nativeInspection struct {
	parts []nativePart
	media NativeMedia
	body  any
}

func nativeDecode(raw []byte) (any, error) {
	var value any
	d := json.NewDecoder(bytes.NewReader(raw))
	d.UseNumber()
	err := d.Decode(&value)
	return value, err
}

func inspectNativeMedia(request Request) (*nativeInspection, Request, error) {
	x := &nativeInspection{}
	if len(request.RawPayload) == 0 {
		return x, request, nil
	}
	var err error
	x.body, err = nativeDecode(request.RawPayload)
	if err != nil {
		return nil, request, errors.New("invalid_native_payload")
	}
	root, ok := x.body.(map[string]any)
	if !ok {
		return nil, request, errors.New("invalid_native_payload")
	}
	// Only provider content arrays are attachment positions. Arbitrary tool
	// arguments, metadata and strings containing JSON must still be scanned.
	for _, key := range []string{"messages", "input"} {
		if list, ok := root[key].([]any); ok {
			for i, value := range list {
				if message, ok := value.(map[string]any); ok {
					if key == "input" && (message["type"] == "compaction" || message["type"] == "compaction_summary") {
						encrypted, ok := message["encrypted_content"].(string)
						if !ok || encrypted == "" || len(x.parts) >= 32 {
							return nil, request, errors.New("invalid_compaction_state")
						}
						metadata := map[string]any{}
						for name, value := range message {
							if name != "encrypted_content" {
								metadata[name] = value
							}
						}
						digest := sha256.Sum256([]byte(encrypted))
						view := map[string]any{"role": "assistant", "content": fmt.Sprintf("[Opaque provider compaction state; semantic contents unavailable to text Guard; sha256=%x; encoded_bytes=%d]", digest, len(encrypted)), "native_metadata": metadata}
						x.parts = append(x.parts, nativePart{[]any{key, i}, message, view})
						list[i] = view
						x.media.Compactions++
						x.media.Bytes += len(encrypted)
						continue
					}
					if message["type"] == "image_generation_call" {
						if result, ok := message["result"].(string); ok && result != "" {
							if len(x.parts) >= 32 {
								return nil, request, errors.New("attachment_count_limit")
							}
							raw, _ := json.Marshal(message)
							digest := sha256.Sum256(raw)
							view := map[string]any{"role": "assistant", "content": fmt.Sprintf("[Generated image attachment; contents excluded from text Guard; sha256=%x; encoded_bytes=%d]", digest, len(raw))}
							x.parts = append(x.parts, nativePart{[]any{key, i}, message, view})
							list[i] = view
							x.media.Images++
							x.media.Bytes += len(raw)
							continue
						}
					}
					for _, field := range []string{"content", "output"} {
						if content, ok := message[field].([]any); ok {
							if err := x.walkContent(content, []any{key, i, field}); err != nil {
								return nil, request, err
							}
						}
					}
				}
			}
		}
	}
	if len(x.parts) == 0 {
		return x, request, nil
	}
	raw, _ := json.Marshal(x.body)
	view, err := NormalizeProtocolRequest(request.Protocol, raw)
	if err != nil {
		return nil, request, errors.New("native_inspection_invalid")
	}
	digest := sha256.Sum256(request.RawPayload)
	x.media.Digest = hex.EncodeToString(digest[:])
	return x, view, nil
}

func (x *nativeInspection) walkContent(list []any, path []any) error {
	for i, value := range list {
		part, ok := value.(map[string]any)
		if !ok {
			continue
		}
		typ, _ := part["type"].(string)
		if typ == "tool_result" {
			if nested, ok := part["content"].([]any); ok {
				if err := x.walkContent(nested, appendPath(path, i, "content")); err != nil {
					return err
				}
			}
			continue
		}
		kind := ""
		switch typ {
		case "image", "image_url", "input_image":
			kind = "image"
		case "document", "file", "input_file":
			kind = "file"
			if nativeAudioFile(part) {
				kind = "audio"
			}
		case "input_audio", "audio":
			kind = "audio"
		default:
			continue
		}
		if len(x.parts) >= 32 {
			return errors.New("attachment_count_limit")
		}
		if err := validateNativePart(part, kind); err != nil {
			return err
		}
		raw, _ := json.Marshal(part)
		digest := sha256.Sum256(raw)
		label, _ := part["filename"].(string)
		if label == "" {
			for _, key := range []string{"file", "source"} {
				if source, ok := part[key].(map[string]any); ok {
					label = textField(source, "filename")
					if label != "" {
						break
					}
				}
			}
		}
		if label == "" {
			label, _ = part["title"].(string)
		}
		view := map[string]any{"type": "text", "text": fmt.Sprintf("[Native %s attachment; contents excluded from text Guard; sha256=%x; encoded_bytes=%d; filename=%s]", kind, digest, len(raw), label)}
		x.parts = append(x.parts, nativePart{appendPath(path, i), part, view})
		list[i] = view
		x.media.Bytes += len(raw)
		switch kind {
		case "image":
			x.media.Images++
		case "file":
			x.media.Files++
		case "audio":
			x.media.Audio++
		}
	}
	return nil
}

func appendPath(path []any, values ...any) []any {
	return append(append([]any(nil), path...), values...)
}

func validateNativePart(part map[string]any, kind string) error {
	// Validate transport fields without interpreting, extracting, or logging contents.
	var source map[string]any
	if s, ok := part["source"].(map[string]any); ok {
		source = s
	}
	if f, ok := part["file"].(map[string]any); ok {
		source = f
	}
	if a, ok := part["input_audio"].(map[string]any); ok {
		source = a
	}
	if source == nil {
		source = part
	}
	for _, key := range []string{"file_id", "id"} {
		if value, ok := source[key].(string); ok && value != "" {
			return nil
		}
	}
	if source["type"] == "text" {
		if _, ok := source["text"].(string); ok {
			return nil
		}
	}
	for _, key := range []string{"data", "file_data", "image_url", "file_url", "url"} {
		value := source[key]
		if m, ok := value.(map[string]any); ok {
			value = m["url"]
		}
		s, ok := value.(string)
		if !ok || s == "" {
			continue
		}
		if key == "data" || key == "file_data" || strings.HasPrefix(s, "data:") {
			if strings.HasPrefix(s, "data:") {
				at := strings.Index(s, ";base64,")
				if at < 0 {
					return errors.New("attachment_encoding_invalid")
				}
				s = s[at+8:]
			}
			if len(s) > MaxNativeRequestBytes || base64.StdEncoding.DecodedLen(len(s)) > 50<<20 {
				return errors.New("attachment_size_limit")
			}
			decoded, err := base64.StdEncoding.DecodeString(s)
			if err != nil || len(decoded) == 0 {
				return errors.New("attachment_encoding_invalid")
			}
			if part["type"] == "input_audio" && source["format"] != "wav" && source["format"] != "mp3" {
				return errors.New("audio_format_unsupported")
			}
			return nil
		}
		u, err := url.Parse(s)
		if err != nil || (u.Scheme != "https" && u.Scheme != "http") || u.Host == "" || u.User != nil {
			return errors.New("attachment_url_invalid")
		}
		return nil
	}
	return errors.New("attachment_source_missing")
}

func (x *nativeInspection) restore(sanitized Request) (Request, error) {
	if len(x.parts) == 0 {
		return sanitized, nil
	}
	body, err := nativeDecode(sanitized.RawPayload)
	if err != nil {
		return Request{}, errors.New("native_contract_invalid")
	}
	for _, part := range x.parts {
		parent := body
		for _, step := range part.path[:len(part.path)-1] {
			switch key := step.(type) {
			case string:
				m, ok := parent.(map[string]any)
				if !ok {
					return Request{}, errors.New("native_contract_invalid")
				}
				parent = m[key]
			case int:
				a, ok := parent.([]any)
				if !ok || key >= len(a) {
					return Request{}, errors.New("native_contract_invalid")
				}
				parent = a[key]
			}
		}
		index := part.path[len(part.path)-1].(int)
		list, ok := parent.([]any)
		if !ok || index >= len(list) {
			return Request{}, errors.New("native_contract_invalid")
		}
		got, _ := json.Marshal(list[index])
		want, _ := json.Marshal(part.view)
		if !bytes.Equal(got, want) {
			return Request{}, errors.New("attachment_metadata_rejected")
		}
		list[index] = part.original
	}
	raw, _ := json.Marshal(body)
	result, err := NormalizeProtocolRequest(sanitized.Protocol, raw)
	if err != nil {
		return Request{}, err
	}
	x.media.Semantic = &sanitized
	for _, part := range x.parts {
		if original, ok := part.original.(map[string]any); ok && (original["type"] == "compaction" || original["type"] == "compaction_summary") {
			x.media.ClassifierHistory = append(x.media.ClassifierHistory, part.original)
			continue
		}
		if p, ok := nativeClassifierPart(part.original); ok {
			x.media.ClassifierParts = append(x.media.ClassifierParts, p)
		}
	}
	result.Native = &x.media
	return result, nil
}

// Mainline classifiers use native Responses attachments after text Guard.
// This does not make classification a safety review of attachment contents.
func nativeClassifierPart(value any) (any, bool) {
	p, ok := value.(map[string]any)
	if !ok {
		return nil, false
	}
	typ, _ := p["type"].(string)
	if typ == "input_image" || typ == "input_file" {
		return p, true
	}
	if typ == "image_url" {
		u := p["image_url"]
		if m, ok := u.(map[string]any); ok {
			u = m["url"]
		}
		return map[string]any{"type": "input_image", "image_url": u}, true
	}
	if typ == "file" {
		f, ok := p["file"].(map[string]any)
		if !ok {
			return nil, false
		}
		out := map[string]any{"type": "input_file"}
		for k, v := range f {
			out[k] = v
		}
		return out, true
	}
	source, ok := p["source"].(map[string]any)
	if !ok {
		return nil, false
	}
	if typ == "image" {
		out := map[string]any{"type": "input_image"}
		switch source["type"] {
		case "base64":
			out["image_url"] = fmt.Sprint("data:", source["media_type"], ";base64,", source["data"])
		case "url":
			out["image_url"] = source["url"]
		case "file":
			out["file_id"] = source["file_id"]
		default:
			return nil, false
		}
		return out, true
	}
	if typ == "document" {
		out := map[string]any{"type": "input_file"}
		switch source["type"] {
		case "base64":
			out["file_data"] = fmt.Sprint("data:", source["media_type"], ";base64,", source["data"])
			out["filename"] = nativeDocumentFilename(source)
		case "url":
			out["file_url"] = source["url"]
		case "file":
			out["file_id"] = source["file_id"]
		case "text":
			return map[string]any{"type": "input_text", "text": source["text"]}, true
		default:
			return nil, false
		}
		return out, true
	}
	return nil, false
}

func nativeImageTool(request Request) bool {
	var body struct {
		Tools []struct {
			Type string `json:"type"`
		} `json:"tools"`
	}
	_ = json.Unmarshal(request.RawPayload, &body)
	for _, tool := range body.Tools {
		if tool.Type == "image_generation" {
			return true
		}
	}
	return false
}

// Audio is not enabled on the verified regional upstream account types. Detect
// both explicit audio blocks and audio files without decoding their contents.
func nativeAudioFile(p map[string]any) bool {
	source := p
	if f, ok := p["file"].(map[string]any); ok {
		source = f
	}
	if f, ok := p["source"].(map[string]any); ok {
		source = f
	}
	if strings.HasPrefix(strings.ToLower(textField(source, "media_type")), "audio/") || strings.HasPrefix(strings.ToLower(textField(source, "file_data")), "data:audio/") {
		return true
	}
	name := strings.ToLower(textField(source, "filename"))
	if name == "" {
		name = strings.ToLower(textField(p, "filename"))
	}
	for _, ext := range []string{".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".aiff", ".aif", ".opus"} {
		if strings.HasSuffix(name, ext) {
			return true
		}
	}
	return false
}
