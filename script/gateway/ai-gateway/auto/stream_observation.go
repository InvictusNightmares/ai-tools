package autogateway

import (
	"bytes"
	"encoding/json"
	"io"
	"strings"
)

// Observe metadata only; never persist provider text or buffer the entire stream.
type observedSSEBody struct {
	MaxEventBytes int
	io.ReadCloser
	pending        []byte
	frame          []string
	frameBytes     int
	Complete       bool
	Model, ID      string
	Usage          map[string]any
	Invalid        bool
	ReportedEffort ReasoningEffort
	ToolCallIDs    []string
	// Commit continuation state before a terminal event is returned to the
	// relay. Clients may close and send the next request immediately afterward.
	BeforeComplete      func() error
	completionCommitted bool
}

func (b *observedSSEBody) Read(p []byte) (int, error) {
	n, e := b.ReadCloser.Read(p)
	if n > 0 {
		b.pending = append(b.pending, p[:n]...)
		for {
			idx := bytes.IndexByte(b.pending, '\n')
			if idx < 0 {
				break
			}
			line := string(b.pending[:idx])
			b.pending = b.pending[idx+1:]
			b.observe(line)
		}
		if len(b.pending) > b.eventLimit() {
			b.pending = nil
			b.Invalid = true
			b.Complete = false
		}
	}
	if e == io.EOF && len(b.pending) > 0 {
		b.observe(string(b.pending))
		b.pending = nil
	}
	if e == io.EOF {
		b.observe("")
	}
	if b.Complete && !b.Invalid && !b.completionCommitted && b.BeforeComplete != nil {
		if err := b.BeforeComplete(); err != nil {
			// Do not deliver the terminal batch if its continuation state failed.
			b.Invalid, b.Complete = true, false
			return 0, err
		}
		b.completionCommitted = true
	}
	return n, e
}
func (b *observedSSEBody) observe(line string) {
	line = strings.TrimSuffix(line, "\r")
	if line == "" {
		if len(b.frame) > 0 {
			b.observeData(strings.Join(b.frame, "\n"))
		}
		b.frame, b.frameBytes = nil, 0
		return
	}
	if !strings.HasPrefix(line, "data:") {
		return
	}
	data := strings.TrimPrefix(strings.TrimPrefix(line, "data:"), " ")
	b.frameBytes += len(data) + 1
	if b.frameBytes > b.eventLimit() {
		b.Invalid = true
		b.Complete = false
		b.frame = nil
		return
	}
	b.frame = append(b.frame, data)
}

func (b *observedSSEBody) eventLimit() int {
	if b.MaxEventBytes > 0 && b.MaxEventBytes <= 128<<20 {
		return b.MaxEventBytes
	}
	return 1 << 20
}

func (b *observedSSEBody) observeData(data string) {
	if b.Invalid {
		return
	}
	data = strings.TrimSpace(data)
	if data == "[DONE]" {
		b.Complete = true
		return
	}
	var event struct {
		ID      string         `json:"id"`
		Model   string         `json:"model"`
		Type    string         `json:"type"`
		Usage   map[string]any `json:"usage"`
		Message *struct {
			ID    string         `json:"id"`
			Model string         `json:"model"`
			Usage map[string]any `json:"usage"`
		} `json:"message"`
		Error    json.RawMessage `json:"error"`
		Response *struct {
			ID        string         `json:"id"`
			Model     string         `json:"model"`
			Usage     map[string]any `json:"usage"`
			Reasoning struct {
				Effort ReasoningEffort `json:"effort"`
			} `json:"reasoning"`
		} `json:"response"`
	}
	if json.Unmarshal([]byte(data), &event) != nil {
		b.Invalid, b.Complete = true, false
		return
	}
	for _, id := range streamToolCallIDs([]byte(data)) {
		found := false
		for _, old := range b.ToolCallIDs {
			if old == id {
				found = true
				break
			}
		}
		if !found {
			b.ToolCallIDs = append(b.ToolCallIDs, id)
		}
	}
	if event.ID != "" {
		b.ID = event.ID
	}
	if event.Model != "" {
		b.Model = event.Model
	}
	if event.Usage != nil {
		b.mergeUsage(event.Usage)
	}
	if event.Response != nil {
		b.ID = event.Response.ID
		b.Model = event.Response.Model
		if event.Response.Reasoning.Effort != "" {
			b.ReportedEffort = event.Response.Reasoning.Effort
		}
		if event.Response.Usage != nil {
			b.mergeUsage(event.Response.Usage)
		}
	}
	if event.Message != nil {
		b.ID = event.Message.ID
		b.Model = event.Message.Model
		b.mergeUsage(event.Message.Usage)
	}
	if event.Type == "response.completed" || event.Type == "message_stop" {
		b.Complete = true
	}
	if event.Type == "response.failed" || event.Type == "response.incomplete" || event.Type == "error" || (len(event.Error) > 0 && string(event.Error) != "null") {
		b.Invalid = true
		b.Complete = false
	}
}

func streamToolCallIDs(data []byte) []string {
	var event struct {
		Block struct {
			Type string `json:"type"`
			ID   string `json:"id"`
		} `json:"content_block"`
		Item struct {
			Type string `json:"type"`
			ID   string `json:"call_id"`
		} `json:"item"`
		Response json.RawMessage `json:"response"`
		Choices  []struct {
			Delta struct {
				Calls []struct {
					ID string `json:"id"`
				} `json:"tool_calls"`
			} `json:"delta"`
		} `json:"choices"`
	}
	if json.Unmarshal(data, &event) != nil {
		return nil
	}
	var ids []string
	if event.Block.Type == "tool_use" && event.Block.ID != "" {
		ids = append(ids, event.Block.ID)
	}
	if event.Item.Type == "function_call" && event.Item.ID != "" {
		ids = append(ids, event.Item.ID)
	}
	for _, c := range event.Choices {
		for _, t := range c.Delta.Calls {
			if t.ID != "" {
				ids = append(ids, t.ID)
			}
		}
	}
	ids = append(ids, responseToolCallIDs("responses", event.Response)...)
	return ids
}

func (b *observedSSEBody) mergeUsage(u map[string]any) {
	if b.Usage == nil {
		b.Usage = map[string]any{}
	}
	for k, v := range u {
		b.Usage[k] = v
	}
}
