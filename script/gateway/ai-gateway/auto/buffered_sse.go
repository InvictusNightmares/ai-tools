package autogateway

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"io"
	"strings"
)

// Complete through a single upstream stream. No fallback/retry is allowed: a
// timeout may already have completed and incurred usage on the provider side.
func (client *HTTPUpstreamClient) completeBufferedSSE(ctx context.Context, request UpstreamRequest) (UpstreamResponse, error) {
	var payload map[string]json.RawMessage
	if json.Unmarshal(request.Payload, &payload) != nil || payload == nil {
		return UpstreamResponse{}, errors.New("invalid_provider_payload")
	}
	payload["stream"] = json.RawMessage(`true`)
	if canonicalProtocol(request.Protocol) == "chat" {
		options := map[string]json.RawMessage{}
		if v := payload["stream_options"]; len(v) > 0 && string(v) != "null" {
			if json.Unmarshal(v, &options) != nil || options == nil {
				return UpstreamResponse{}, errors.New("invalid_stream_options")
			}
		}
		options["include_usage"] = json.RawMessage(`true`)
		payload["stream_options"], _ = json.Marshal(options)
	}
	request.Payload, _ = json.Marshal(payload)
	request.Parameters.Stream = true
	request.Request.Stream = true
	response, err := client.OpenStream(ctx, request)
	if err != nil {
		return UpstreamResponse{}, err
	}
	defer response.Body.Close()
	result := UpstreamResponse{Transport: "sse_buffered", StatusCode: response.StatusCode, RequestID: response.Header.Get("X-Request-ID"), ClientRequestID: response.Header.Get("X-Client-Request-ID"), ContentType: "application/json"}
	max := client.MaxResponseSize
	if max <= 0 {
		max = 16 << 20
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		result.Body, err = io.ReadAll(io.LimitReader(response.Body, max+1))
		result.ResponseBytes = len(result.Body)
		if err != nil || int64(len(result.Body)) > max {
			result.Body = nil
			return result, errors.New("upstream_error_body_unavailable")
		}
		return validateBufferedResponse(request.Protocol, result)
	}
	if !strings.Contains(strings.ToLower(response.Header.Get("Content-Type")), "text/event-stream") {
		return result, errors.New("upstream_stream_invalid_response")
	}
	observed := &observedSSEBody{ReadCloser: response.Body, MaxEventBytes: int(max)}
	result.Body, err = aggregateSSE(ctx, request.Protocol, observed, max)
	if err != nil {
		// A failed assembly must not publish partial output, but complete usage
		// events already received still belong to this failed provider attempt.
		result.Usage = observed.Usage
		result.ResponseModel, result.ResponseID = observed.Model, observed.ID
		result.ReportedEffort = observed.ReportedEffort
		return result, err
	}
	result.ResponseBytes = len(result.Body)
	return validateBufferedResponse(request.Protocol, result)
}

type streamAssembly struct {
	protocol    string
	response    map[string]any
	choices     map[int]map[string]any
	tools       map[int]map[int]map[string]any
	blocks      map[int]map[string]any
	partialJSON map[int]string
	closed      map[int]bool
	terminal    bool
	started     bool
}

func aggregateSSE(ctx context.Context, protocol string, reader io.Reader, max int64) ([]byte, error) {
	// SSE events may repeat the final response and add framing. Both wire bytes
	// and the returned JSON are bounded; neither body is written to audit logs.
	if max <= 0 || max > 128<<20 {
		return nil, errors.New("invalid_stream_buffer_limit")
	}
	limited := &io.LimitedReader{R: reader, N: max*8 + 1}
	scanner := bufio.NewScanner(limited)
	scanner.Buffer(make([]byte, 4096), int(max)+1)
	b := streamAssembly{protocol: canonicalProtocol(protocol), response: map[string]any{}, choices: map[int]map[string]any{}, tools: map[int]map[int]map[string]any{}, blocks: map[int]map[string]any{}, partialJSON: map[int]string{}, closed: map[int]bool{}}
	var data []string
	size := 0
	kind := ""
	flush := func() error {
		if len(data) == 0 {
			kind = ""
			return nil
		}
		value := strings.Join(data, "\n")
		data = nil
		size = 0
		eventKind := kind
		kind = ""
		return b.event(eventKind, value)
	}
	for scanner.Scan() {
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		line := strings.TrimSuffix(scanner.Text(), "\r")
		if line == "" {
			if err := flush(); err != nil {
				return nil, err
			}
			continue
		}
		if strings.HasPrefix(line, "event:") {
			kind = strings.TrimSpace(line[6:])
		}
		if strings.HasPrefix(line, "data:") {
			part := strings.TrimPrefix(line[5:], " ")
			size += len(part) + 1
			if int64(size) > max {
				return nil, errors.New("upstream_stream_event_too_large")
			}
			data = append(data, part)
		}
	}
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	if scanner.Err() != nil {
		return nil, errors.New("upstream_stream_read_error")
	}
	if limited.N <= 0 {
		return nil, errors.New("upstream_stream_too_large")
	}
	if err := flush(); err != nil {
		return nil, err
	}
	if ctx.Err() != nil {
		return nil, ctx.Err()
	}
	if !b.terminal {
		return nil, errors.New("upstream_stream_incomplete")
	}
	if b.protocol == "chat" {
		choices := []any{}
		for _, i := range sortedIndexes(b.choices) {
			choice := b.choices[i]
			message := choice["message"].(map[string]any)
			if len(b.tools[i]) > 0 {
				calls := []any{}
				for _, j := range sortedIndexes(b.tools[i]) {
					tool := b.tools[i][j]
					if textField(tool, "id") == "" {
						return nil, errors.New("upstream_stream_invalid_tool")
					}
					calls = append(calls, tool)
				}
				message["tool_calls"] = calls
			}
			choices = append(choices, choice)
		}
		b.response["choices"] = choices
		b.response["object"] = "chat.completion"
	}
	if b.protocol == "anthropic" {
		content := []any{}
		for _, i := range sortedIndexes(b.blocks) {
			if !b.closed[i] {
				return nil, errors.New("upstream_stream_incomplete_block")
			}
			content = append(content, b.blocks[i])
		}
		b.response["content"] = content
	}
	raw, err := json.Marshal(b.response)
	if err != nil || int64(len(raw)) > max {
		return nil, errors.New("upstream_response_too_large")
	}
	if !completeJSONResponse(protocol, raw) {
		return nil, errors.New("upstream_stream_incomplete")
	}
	return raw, nil
}

func (b *streamAssembly) event(eventKind, data string) error {
	if b.terminal {
		return errors.New("upstream_stream_after_terminal")
	}
	if strings.TrimSpace(data) == "[DONE]" {
		if b.protocol != "chat" {
			return errors.New("upstream_stream_wrong_terminal")
		}
		b.terminal = true
		return nil
	}
	decoder := json.NewDecoder(strings.NewReader(data))
	decoder.UseNumber()
	var e map[string]any
	if !json.Valid([]byte(data)) || decoder.Decode(&e) != nil || e == nil {
		return errors.New("upstream_stream_invalid_json")
	}
	if e["error"] != nil || eventKind == "error" || textField(e, "type") == "error" || textField(e, "type") == "response.failed" || textField(e, "type") == "response.incomplete" {
		return errors.New("upstream_stream_error_event")
	}
	switch b.protocol {
	case "responses":
		if textField(e, "type") == "response.completed" {
			r, ok := e["response"].(map[string]any)
			if !ok {
				return errors.New("upstream_stream_invalid_response")
			}
			b.response = r
			b.terminal = true
		}
		return nil
	case "chat":
		return b.chatEvent(e)
	case "anthropic":
		return b.messageEvent(e, eventKind)
	}
	return errors.New("unsupported_stream_protocol")
}
