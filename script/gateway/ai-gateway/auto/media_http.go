package autogateway

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"log"
	"mime"
	"mime/multipart"
	"net/http"
	"net/textproto"
	"net/url"
	"regexp"
	"strings"
	"time"
)

const ImageFlare = "gpt-image-2.5-flare"
const ImageSunburst = "gpt-image-2.5-sunburst"

type NativeAPI struct {
	BaseURL string
	Client  *http.Client
}

var nativeFilePath = regexp.MustCompile(`^/v1/files(?:/[A-Za-z0-9_-]+(?:/content)?)?$`)

func isNativeAPIPath(path string) bool {
	return nativeFilePath.MatchString(path) || path == "/v1/images/generations" || path == "/v1/images/edits" || path == "/v1/audio/transcriptions" || path == "/v1/audio/translations" || path == "/v1/audio/speech"
}

type nativeUpload struct {
	header textproto.MIMEHeader
	data   []byte
}

func (s *HTTPServer) handleNativeAPI(w http.ResponseWriter, r *http.Request) {
	fail := func(status int, code string) {
		writeJSON(w, status, map[string]any{"error": map[string]string{"type": "invalid_request_error", "message": code, "code": code}})
	}
	if strings.HasPrefix(r.URL.Path, "/v1/audio/") {
		fail(400, "audio_not_supported")
		return
	}
	if s.NativeAPI == nil || s.Pipeline == nil || s.NativeAPI.BaseURL == "" {
		fail(503, "native_api_unavailable")
		return
	}
	isFiles := nativeFilePath.MatchString(r.URL.Path)
	if r.Method != "POST" && !(isFiles && (r.Method == "GET" || r.Method == "DELETE")) {
		fail(405, "method_not_allowed")
		return
	}
	meta := withRequestID(s.Meta)
	meta.ClientHeaders = r.Header
	meta.APIKeyID = r.Header.Get("X-Gateway-API-Key-ID")
	if meta.APIKeyID == "" {
		meta.APIKeyID = s.Meta.APIKeyID
	}
	w.Header().Set("X-Gateway-Request-ID", meta.RequestID)
	w.Header().Set("X-Gateway-Guard-Scope", NativeGuardScope)
	raw, err := io.ReadAll(http.MaxBytesReader(w, r.Body, MaxNativeRequestBytes))
	if err != nil {
		fail(413, "request_too_large")
		return
	}
	params := map[string]any{}
	var uploads []nativeUpload
	var opaque = map[string]any{}
	kind, contentParams, _ := mime.ParseMediaType(r.Header.Get("Content-Type"))
	if r.Method == "POST" {
		if kind == "multipart/form-data" {
			reader := multipart.NewReader(bytes.NewReader(raw), contentParams["boundary"])
			for {
				part, partErr := reader.NextPart()
				if partErr == io.EOF {
					break
				}
				if partErr != nil {
					fail(400, "invalid_multipart")
					return
				}
				data, readErr := io.ReadAll(io.LimitReader(part, (50<<20)+1))
				part.Close()
				if readErr != nil || len(data) > 50<<20 {
					fail(413, "attachment_size_limit")
					return
				}
				name := part.FormName()
				if name == "" {
					fail(400, "multipart_name_required")
					return
				}
				if part.FileName() != "" {
					if len(uploads) >= 32 {
						fail(400, "attachment_count_limit")
						return
					}
					uploads = append(uploads, nativeUpload{part.Header, data})
				} else {
					if _, duplicate := params[name]; duplicate {
						fail(400, "duplicate_form_field")
						return
					}
					params[name] = string(data)
				}
			}
		} else if kind == "application/json" || kind == "" {
			raw, err = s.Files.Expand(meta.APIKeyID, raw)
			if err != nil {
				fail(nativeFileError(err))
				return
			}
			decoded, decodeErr := nativeDecode(raw)
			if decodeErr != nil {
				fail(400, "invalid_json")
				return
			}
			var ok bool
			params, ok = decoded.(map[string]any)
			if !ok {
				fail(400, "invalid_json")
				return
			}
			// Image edit JSON references are opaque native attachment content.
			for _, key := range []string{"images", "image", "mask"} {
				if value, ok := params[key]; ok {
					opaque[key] = value
					delete(params, key)
				}
			}
		} else {
			fail(415, "unsupported_media_type")
			return
		}
	}
	if strings.HasPrefix(r.URL.Path, "/v1/images/") {
		model, _ := params["model"].(string)
		if model == "" || model == "auto" {
			model = ImageFlare
			if r.URL.Path == "/v1/images/edits" {
				model = ImageSunburst
			}
			params["model"] = model
		}
		if model != ImageFlare && model != ImageSunburst {
			fail(400, "image_model_not_supported")
			return
		}
		for _, key := range []string{"reasoning", "reasoning_effort", "thinking"} {
			delete(params, key)
		}
	}
	// No model receives raw attachment bytes during this text-only preflight.
	metadata := map[string]any{"path": r.URL.Path, "method": r.Method, "parameters": params, "attachment_contents_not_inspected": true}
	fileMetadata := []map[string]any{}
	for _, upload := range uploads {
		fileMetadata = append(fileMetadata, map[string]any{"headers": upload.header, "bytes": len(upload.data)})
	}
	metadata["uploads"] = fileMetadata
	for key, value := range opaque {
		b, _ := json.Marshal(value)
		metadata[key+"_encoded_bytes"] = len(b)
	}
	guardText, _ := json.Marshal(metadata)
	guardBody, _ := json.Marshal(map[string]any{"messages": []any{map[string]any{"role": "user", "content": string(guardText)}}})
	request, _ := NormalizeProtocolRequest("chat", guardBody)
	preflight, guardErr := evaluatePreflight(r.Context(), s.Pipeline.Preflight, request, meta)
	if guardErr != nil || preflight.Decision != PreflightAllow {
		status, code := 503, "preflight_unavailable"
		if preflight.Decision == PreflightBlock {
			status, code = 403, "preflight_blocked"
		}
		s.Pipeline.writePreflightAudit(meta, "native", request, preflight, code)
		fail(status, code)
		return
	}
	if preflight.SanitizedRequest != nil {
		messages := preflight.SanitizedRequest.Messages
		if len(messages) != 1 {
			fail(503, "guard_payload_contract_invalid")
			return
		}
		clean, cleanErr := nativeDecode([]byte(messages[0].Content))
		if cleanErr != nil {
			fail(503, "guard_payload_contract_invalid")
			return
		}
		cleanMap, ok := clean.(map[string]any)
		if !ok {
			fail(503, "guard_payload_contract_invalid")
			return
		}
		params, ok = cleanMap["parameters"].(map[string]any)
		if !ok {
			fail(503, "guard_payload_contract_invalid")
			return
		}
		before, _ := json.Marshal(metadata["uploads"])
		after, _ := json.Marshal(cleanMap["uploads"])
		if !bytes.Equal(before, after) {
			fail(403, "attachment_metadata_rejected")
			return
		}
	}
	contentType := "application/json"
	if r.Method == "POST" {
		if kind == "multipart/form-data" {
			var body bytes.Buffer
			writer := multipart.NewWriter(&body)
			for key, value := range params {
				str, ok := value.(string)
				if !ok {
					fail(503, "guard_payload_contract_invalid")
					return
				}
				if writer.WriteField(key, str) != nil {
					fail(500, "multipart_encoding_failed")
					return
				}
			}
			for _, upload := range uploads {
				p, e := writer.CreatePart(upload.header)
				if e != nil {
					fail(400, "invalid_multipart")
					return
				}
				_, _ = p.Write(upload.data)
			}
			_ = writer.Close()
			raw = body.Bytes()
			contentType = writer.FormDataContentType()
		} else {
			for key, value := range opaque {
				params[key] = value
			}
			raw, _ = json.Marshal(params)
		}
	}
	target, err := url.Parse(strings.TrimRight(s.NativeAPI.BaseURL, "/") + r.URL.Path)
	if err != nil || target.Host == "" {
		fail(503, "native_api_unavailable")
		return
	}
	target.RawQuery = r.URL.RawQuery
	upstream, err := http.NewRequestWithContext(r.Context(), r.Method, target.String(), bytes.NewReader(raw))
	if err != nil {
		fail(503, "native_api_unavailable")
		return
	}
	copyAuthHeaders(upstream.Header, r.Header)
	copyClientUserAgent(upstream.Header, r.Header)
	upstream.Header.Set("Content-Type", contentType)
	upstream.Header.Set("X-Request-ID", meta.RequestID)
	for _, name := range []string{"OpenAI-Beta", "anthropic-beta", "Accept"} {
		if value := r.Header.Get(name); value != "" {
			upstream.Header.Set(name, value)
		}
	}
	model, _ := params["model"].(string)
	audit := RouteAudit{At: time.Now(), RequestID: meta.RequestID, Region: meta.Region, APIKeyID: meta.APIKeyID, Stage: "upstream_started", EffectiveModel: model, GuardScope: NativeGuardScope, PreflightDecision: PreflightAllow, UpstreamCalled: true, Action: "native_api"}
	if s.Pipeline.AuditSink != nil && s.Pipeline.AuditSink.WriteRouteAudit(audit) != nil {
		fail(503, "audit_unavailable")
		return
	}
	client := s.NativeAPI.Client
	if client == nil {
		client = &http.Client{Timeout: time.Hour, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	}
	result, callErr := client.Do(upstream)
	var usage map[string]any
	success := false
	complete := false
	finishErr := callErr
	defer func() {
		audit.At = time.Now()
		audit.Stage = failureAuditStage(finishErr)
		if success {
			audit.Stage = "upstream_completed"
		} else if audit.StreamTermination != "" {
			audit.ErrorType = audit.StreamTermination
		} else if isClientDeliveryFailure(finishErr) {
			audit.ErrorType = finishErr.Error()
		} else if errors.Is(finishErr, context.Canceled) {
			audit.ErrorType = "context_canceled"
		} else {
			audit.ErrorType = "native_upstream_failed"
		}
		audit.ResponseComplete = complete
		audit.Usage = NormalizeUsage(usage)
		s.Pipeline.persistAudit(audit)
		if model != "" {
			u := NormalizeUsage(usage)
			event := UsageEvent{UsageReported: u.HasPromptTokens, At: time.Now(), Region: meta.Region, APIKeyID: meta.APIKeyID, RequestID: meta.RequestID, UpstreamRequestID: audit.UpstreamRequestID, UpstreamClientRequestID: audit.UpstreamClientRequestID, EffectiveModel: model, Purpose: "business", Attempt: true, Success: success, HTTPStatus: audit.HTTPStatus, InputTokens: u.PromptTokens, OutputTokens: u.CompletionTokens, CacheHitTokens: u.CacheHitTokens, CacheMissTokens: u.CacheMissTokens}
			if s.Pipeline.Usage != nil {
				s.Pipeline.Usage.Record(event)
			}
			if s.Pipeline.UsageSink != nil {
				if err := s.Pipeline.UsageSink.WriteUsageEvent(event); err != nil {
					// The response may already be streamed; retain metadata for
					// recovery without replaying a billable image generation.
					raw, _ := json.Marshal(event)
					log.Printf("usage_sink_failed event=%s", raw)
				}
			}
		}
	}()
	if callErr != nil {
		fail(502, "native_upstream_unavailable")
		return
	}
	defer result.Body.Close()
	audit.HTTPStatus = result.StatusCode
	audit.UpstreamRequestID = result.Header.Get("X-Request-ID")
	audit.UpstreamClientRequestID = result.Header.Get("X-Client-Request-ID")
	for _, name := range []string{"Content-Type", "Content-Disposition", "X-Request-ID", "OpenAI-Processing-Ms", "Retry-After"} {
		if v := result.Header.Get(name); v != "" {
			w.Header().Set(name, v)
		}
	}
	if strings.Contains(result.Header.Get("Content-Type"), "text/event-stream") {
		observer := &nativeImageStream{ReadCloser: result.Body}
		result.Body = observer
		err = RelaySSE(r.Context(), w, result)
		usage = observer.usage
		complete = observer.complete && result.StatusCode >= 200 && result.StatusCode < 300
		audit.StreamTermination, finishErr = streamTermination(err, complete)
		success = finishErr == nil && complete
		if !success && finishErr == nil {
			finishErr = errors.New("native_stream_incomplete")
			audit.StreamTermination = "native_stream_incomplete"
		}
		return
	}
	responseBody, readErr := io.ReadAll(io.LimitReader(result.Body, (128<<20)+1))
	if readErr != nil || len(responseBody) > 128<<20 {
		finishErr = readErr
		fail(502, "native_response_too_large_or_incomplete")
		return
	}
	usage = extractUsage(responseBody)
	success = result.StatusCode >= 200 && result.StatusCode < 300
	complete = success
	w.WriteHeader(result.StatusCode)
	written, err := w.Write(responseBody)
	if err == nil && written != len(responseBody) {
		err = io.ErrShortWrite
	}
	if err != nil {
		success = false
		finishErr = newSSETransportError("client_write", err, false)
		audit.ErrorType = finishErr.Error()
	}
}

type nativeImageStream struct {
	io.ReadCloser
	pending  []byte
	usage    map[string]any
	complete bool
}

func (s *nativeImageStream) streamComplete() bool { return s.complete }

func (s *nativeImageStream) Read(p []byte) (int, error) {
	n, err := s.ReadCloser.Read(p)
	s.pending = append(s.pending, p[:n]...)
	for {
		at := bytes.IndexByte(s.pending, '\n')
		if at < 0 {
			break
		}
		line := bytes.TrimSpace(s.pending[:at])
		s.pending = s.pending[at+1:]
		if !bytes.HasPrefix(line, []byte("data:")) {
			continue
		}
		var event map[string]any
		if json.Unmarshal(bytes.TrimSpace(line[5:]), &event) != nil {
			continue
		}
		if u, ok := event["usage"].(map[string]any); ok {
			s.usage = u
		}
		typ, _ := event["type"].(string)
		if typ == "image_generation.completed" || typ == "image_edit.completed" {
			s.complete = true
		}
	}
	if len(s.pending) > 128<<20 {
		return n, errors.New("image_stream_event_too_large")
	}
	return n, err
}
