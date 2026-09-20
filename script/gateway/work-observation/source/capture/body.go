package capture

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"mime/multipart"
	"strings"
	"unicode/utf8"
)

func ProjectBody(raw []byte, contentType, encoding, path string, limit int64) (json.RawMessage, []string) {
	if len(raw) == 0 {
		return nil, nil
	}
	var missing []string
	if encoding != "" && encoding != "identity" {
		if encoding != "gzip" {
			b, _ := json.Marshal(omitted(string(raw), "unsupported_content_encoding"))
			return b, []string{"unsupported_content_encoding"}
		}
		reader, err := gzip.NewReader(bytes.NewReader(raw))
		if err != nil {
			return nil, []string{"invalid_gzip"}
		}
		decoded, err := io.ReadAll(io.LimitReader(reader, limit+1))
		reader.Close()
		if err != nil || int64(len(decoded)) > limit {
			return nil, []string{"gzip_decode_incomplete"}
		}
		raw = decoded
	}
	media, params, err := mime.ParseMediaType(contentType)
	if err != nil {
		media = ""
	}
	var out json.RawMessage
	switch {
	case media == "application/json" || strings.HasSuffix(media, "+json") || media == "" && json.Valid(raw):
		out, err = ProjectJSONForPath(raw, path)
	case media == "text/event-stream":
		// A canceled stream can retain all complete preceding events.
		var parseErr error
		out, parseErr = ProjectSSE(raw)
		if parseErr != nil {
			missing = append(missing, "incomplete_sse_event")
		}
	case strings.HasPrefix(media, "multipart/"):
		out, err = projectMultipart(raw, params["boundary"])
	case strings.HasPrefix(media, "text/") && utf8.Valid(raw):
		out, err = json.Marshal(string(raw))
	default:
		out, err = json.Marshal(map[string]any{"omitted": "binary_or_unknown_media", "content_type": media, "bytes": len(raw), "sha256": digest(raw)})
	}
	if err != nil {
		out = nil
		missing = append(missing, "body_projection_failed")
	}
	return out, missing
}
func projectMultipart(raw []byte, boundary string) (json.RawMessage, error) {
	if boundary == "" {
		return nil, errors.New("missing_boundary")
	}
	reader := multipart.NewReader(bytes.NewReader(raw), boundary)
	parts := []any{}
	for {
		part, err := reader.NextPart()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		b, err := io.ReadAll(part)
		part.Close()
		if err != nil {
			return nil, err
		}
		item := map[string]any{"name": part.FormName(), "bytes": len(b)}
		if part.FileName() != "" {
			item["filename"] = part.FileName()
			item["sha256"] = digest(b)
			item["content_type"] = part.Header.Get("Content-Type")
			item["omitted"] = "attachment"
		} else if utf8.Valid(b) {
			item["text"] = string(b)
		} else {
			item["omitted"] = "binary_part"
			item["sha256"] = digest(b)
		}
		parts = append(parts, item)
	}
	return json.Marshal(map[string]any{"multipart": parts})
}
