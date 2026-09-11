package service

import (
	"bytes"
	"io"
	"net/http"
	"strings"
	"sync"

	"github.com/Wei-Shaw/sub2api/internal/requestcontent"
	"github.com/gin-gonic/gin"
	"github.com/tidwall/gjson"
)

// These observations only retain evidence. They never change forwarding,
// billing, routing, or the existing cyber-policy enforcement path.
const openAIPolicyObservationKey = "openai_policy_request_observation"
const maxPolicyObservationBytes = 8 << 20

type OpenAIPolicyObservation struct {
	Code               string
	ErrorType          string
	SignalPath         string
	Reason             string // fixed description; never a raw upstream message
	AccountID          int64
	UpstreamStatus     int
	UpstreamRequestID  string
	UpstreamResponseID string
}

func GetOpenAIPolicyObservation(c *gin.Context) *OpenAIPolicyObservation {
	if c == nil {
		return nil
	}
	v, _ := c.Get(openAIPolicyObservationKey)
	m, _ := v.(*OpenAIPolicyObservation)
	return m
}

func ClearOpenAIPolicyObservation(c *gin.Context) {
	if c != nil {
		c.Set(openAIPolicyObservationKey, (*OpenAIPolicyObservation)(nil))
	}
}

// ObserveOpenAIPolicyPayload accepts only upstream payloads, never request data.
// First evidence wins within one upstream attempt/WS turn.
func ObserveOpenAIPolicyPayload(c *gin.Context, account *Account, payload []byte, status int, upstreamRequestID string) {
	if c == nil || account == nil || account.Platform != PlatformOpenAI || GetOpenAIPolicyObservation(c) != nil {
		return
	}
	m := detectOpenAIPolicyObservation(payload)
	if m == nil {
		return
	}
	m.Code = clonePolicyMetadata(m.Code, 64)
	m.ErrorType = clonePolicyMetadata(m.ErrorType, 128)
	m.UpstreamResponseID = clonePolicyMetadata(m.UpstreamResponseID, 256)
	m.AccountID, m.UpstreamStatus, m.UpstreamRequestID = account.ID, status, clonePolicyMetadata(upstreamRequestID, 256)
	c.Set(openAIPolicyObservationKey, m)
}

func detectOpenAIPolicyObservation(payload []byte) *OpenAIPolicyObservation {
	if !gjson.ValidBytes(payload) {
		return nil
	}
	root := gjson.ParseBytes(payload)
	m := &OpenAIPolicyObservation{}
	m.UpstreamResponseID = root.Get("response.id").String()
	if m.UpstreamResponseID == "" {
		m.UpstreamResponseID = root.Get("response_id").String()
	}
	if m.UpstreamResponseID == "" && root.Get("object").String() == "response" {
		m.UpstreamResponseID = root.Get("id").String()
	}
	for _, path := range []string{"error", "response.error"} {
		e := root.Get(path)
		if !e.IsObject() {
			continue
		}
		m.ErrorType = e.Get("type").String()
		for _, field := range []string{"code", "type"} {
			code := strings.ToLower(strings.TrimSpace(e.Get(field).String()))
			switch code {
			case "cyber_policy", "content_policy", "content_policy_violation", "content_filter":
				m.Code, m.SignalPath, m.Reason = code, path+"."+field, "explicit_upstream_policy_error"
				return m
			case "invalid_prompt":
				message := strings.ToLower(e.Get("message").String())
				if strings.Contains(message, "flagged") && strings.Contains(message, "violating our usage policy") {
					m.Code, m.SignalPath, m.Reason = code, path+"."+field+"+message", "prompt_flagged_for_usage_policy"
					return m
				}
			}
		}
	}
	for _, path := range []string{"incomplete_details.reason", "response.incomplete_details.reason"} {
		if root.Get(path).String() == "content_filter" {
			m.Code, m.SignalPath, m.Reason = "content_filter", path, "upstream_content_filter"
			return m
		}
	}
	refusal := func(path string) *OpenAIPolicyObservation {
		m.Code, m.SignalPath, m.Reason = "structured_refusal", path, "explicit_upstream_refusal"
		return m
	}
	for _, choice := range root.Get("choices").Array() {
		if choice.Get("finish_reason").String() == "content_filter" {
			m.Code, m.SignalPath, m.Reason = "content_filter", "choices.finish_reason", "upstream_content_filter"
			return m
		}
		for _, path := range []string{"message.refusal", "delta.refusal"} {
			v := choice.Get(path)
			if v.Type == gjson.String && strings.TrimSpace(v.String()) != "" {
				return refusal("choices." + path)
			}
		}
	}
	partRefuses := func(part gjson.Result) bool {
		v := part.Get("refusal")
		return part.Get("type").String() == "refusal" && v.Type == gjson.String && strings.TrimSpace(v.String()) != ""
	}
	itemRefuses := func(item gjson.Result) bool {
		if item.Get("type").String() != "message" || item.Get("role").String() != "assistant" {
			return false
		}
		for _, part := range item.Get("content").Array() {
			if partRefuses(part) {
				return true
			}
		}
		return false
	}
	for _, path := range []string{"output", "response.output"} {
		for _, item := range root.Get(path).Array() {
			if itemRefuses(item) {
				return refusal(path + ".content.refusal")
			}
		}
	}
	switch root.Get("type").String() {
	case "response.refusal.delta":
		v := root.Get("delta")
		if v.Type == gjson.String && strings.TrimSpace(v.String()) != "" {
			return refusal("response.refusal.delta")
		}
	case "response.refusal.done":
		v := root.Get("refusal")
		if v.Type == gjson.String && strings.TrimSpace(v.String()) != "" {
			return refusal("response.refusal.done")
		}
	case "response.content_part.added", "response.content_part.done":
		if partRefuses(root.Get("part")) {
			return refusal("part.refusal")
		}
	case "response.output_item.added", "response.output_item.done":
		if itemRefuses(root.Get("item")) {
			return refusal("item.content.refusal")
		}
	}
	return nil
}

// Observe bytes as consumers read them, preserving read sizes, errors, timing,
// and the exact response. Only an in-memory bounded response fragment is kept.
func observeOpenAIPolicyResponse(c *gin.Context, account *Account, resp *http.Response) {
	if c == nil || account == nil || account.Platform != PlatformOpenAI || resp == nil || resp.Body == nil {
		return
	}
	resp.Body = &openAIPolicyResponseBody{
		ReadCloser: resp.Body, c: c, account: account, status: resp.StatusCode,
		requestID: resp.Header.Get("X-Request-Id"),
		sse:       strings.Contains(strings.ToLower(resp.Header.Get("Content-Type")), "text/event-stream"),
	}
}

type openAIPolicyResponseBody struct {
	io.ReadCloser
	mu                                    sync.Mutex
	c                                     *gin.Context
	account                               *Account
	status                                int
	requestID                             string
	sse, decided, stopped, discardingLine bool
	buffer, event                         []byte
}

func (b *openAIPolicyResponseBody) observe(payload []byte) {
	ObserveOpenAIPolicyPayload(b.c, b.account, payload, b.status, b.requestID)
	if GetOpenAIPolicyObservation(b.c) != nil {
		b.stopped = true
		b.buffer = nil
		b.event = nil
	}
}

func (b *openAIPolicyResponseBody) Read(p []byte) (int, error) {
	n, err := b.ReadCloser.Read(p)
	b.mu.Lock()
	defer b.mu.Unlock()
	if n > 0 {
		b.feed(p[:n])
	}
	if err != nil {
		b.finish()
	}
	return n, err
}

func (b *openAIPolicyResponseBody) Close() error {
	b.mu.Lock()
	b.finish()
	b.mu.Unlock()
	return b.ReadCloser.Close()
}

func (b *openAIPolicyResponseBody) feed(p []byte) {
	if b.stopped {
		return
	}
	if !b.decided {
		trimmed := bytes.TrimSpace(p)
		if len(trimmed) == 0 {
			return
		}
		// OpenAI-compatible endpoints occasionally omit the event-stream header.
		b.sse = b.sse || (trimmed[0] != '{' && trimmed[0] != '[')
		b.decided = true
	}
	if !b.sse {
		if len(b.buffer)+len(p) > maxPolicyObservationBytes {
			b.stopped = true
			b.buffer = nil
			return
		}
		b.buffer = append(b.buffer, p...)
		return
	}
	for len(p) > 0 && !b.stopped {
		i := bytes.IndexByte(p, '\n')
		part := p
		if i >= 0 {
			part = p[:i]
		}
		if !b.discardingLine {
			if len(b.buffer)+len(part) > maxPolicyObservationBytes {
				b.discardingLine = true
				b.buffer = nil
				b.event = nil
			} else {
				b.buffer = append(b.buffer, part...)
			}
		}
		if i < 0 {
			break
		}
		if !b.discardingLine {
			b.line(b.buffer)
		}
		b.buffer = nil
		b.discardingLine = false
		p = p[i+1:]
	}
}

func (b *openAIPolicyResponseBody) line(line []byte) {
	line = bytes.TrimSuffix(line, []byte{'\r'})
	if len(line) == 0 {
		if len(b.event) > 0 {
			b.observe(b.event)
			b.event = nil
		}
		return
	}
	if !bytes.HasPrefix(line, []byte("data:")) {
		return
	}
	data := bytes.TrimPrefix(line[5:], []byte{' '})
	if len(b.event)+len(data)+1 > maxPolicyObservationBytes {
		b.event = nil
		return
	}
	if len(b.event) > 0 {
		b.event = append(b.event, '\n')
	}
	b.event = append(b.event, data...)
	// A complete JSON data line can be classified immediately, before a client
	// disconnect or a forwarder returning at a terminal event without EOF.
	if gjson.ValidBytes(b.event) {
		b.observe(b.event)
		b.event = nil
	}
}

func (b *openAIPolicyResponseBody) finish() {
	if b.stopped {
		return
	}
	if b.sse {
		if len(b.buffer) > 0 && !b.discardingLine {
			b.line(b.buffer)
		}
		if !b.stopped && len(b.event) > 0 {
			b.observe(b.event)
		}
	} else if len(b.buffer) > 0 {
		b.observe(b.buffer)
	}
	b.stopped = true
	b.buffer = nil
	b.event = nil
}

// Detach metadata from GJSON payload backing strings before it enters the queue.
func clonePolicyMetadata(value string, limit int) string {
	if len(value) > limit {
		value = value[:limit]
	}
	return strings.Clone(value)
}

func (s *OpenAIGatewayService) policyObservationAvailable() bool {
	if s.policyObservationEnabled != nil {
		return s.policyObservationEnabled()
	}
	return requestcontent.Enabled()
}
