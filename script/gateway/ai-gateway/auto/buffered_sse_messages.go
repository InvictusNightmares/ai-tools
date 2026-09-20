package autogateway

import (
	"encoding/json"
	"errors"
	"strings"
)

func (b *streamAssembly) messageEvent(e map[string]any, eventKind string) error {
	kind := textField(e, "type")
	if kind == "" {
		kind = eventKind
	}
	if kind == "ping" {
		return nil
	}
	if kind == "message_start" {
		if b.started {
			return errors.New("upstream_stream_duplicate_start")
		}
		msg, ok := e["message"].(map[string]any)
		if !ok {
			return errors.New("upstream_stream_invalid_message")
		}
		b.response = msg
		b.started = true
		return nil
	}
	if !b.started {
		return errors.New("upstream_stream_missing_start")
	}
	switch kind {
	case "content_block_start", "content_block_delta", "content_block_stop":
		i, err := eventIndex(e)
		if err != nil {
			return err
		}
		if kind == "content_block_start" {
			if b.blocks[i] != nil {
				return errors.New("upstream_stream_duplicate_block")
			}
			block, ok := e["content_block"].(map[string]any)
			if !ok {
				return errors.New("upstream_stream_invalid_block")
			}
			b.blocks[i] = block
			return nil
		}
		block := b.blocks[i]
		if block == nil || b.closed[i] {
			return errors.New("upstream_stream_invalid_block_order")
		}
		if kind == "content_block_stop" {
			if partial, ok := b.partialJSON[i]; ok {
				decoder := json.NewDecoder(strings.NewReader(partial))
				decoder.UseNumber()
				var input map[string]any
				if !json.Valid([]byte(partial)) || decoder.Decode(&input) != nil || input == nil {
					return errors.New("upstream_stream_invalid_tool_json")
				}
				block["input"] = input
			}
			b.closed[i] = true
			return nil
		}
		delta, ok := e["delta"].(map[string]any)
		if !ok {
			return errors.New("upstream_stream_invalid_delta")
		}
		switch textField(delta, "type") {
		case "input_json_delta":
			fragment, ok := delta["partial_json"].(string)
			if !ok || textField(block, "type") != "tool_use" {
				return errors.New("upstream_stream_invalid_tool_json")
			}
			b.partialJSON[i] += fragment
		case "text_delta", "thinking_delta", "signature_delta":
			delete(delta, "type")
			return mergeStreamDelta(block, delta)
		case "citations_delta":
			citation, ok := delta["citation"].(map[string]any)
			if !ok {
				return errors.New("upstream_stream_invalid_citation")
			}
			return mergeStreamDelta(block, map[string]any{"citations": []any{citation}})
		default:
			return errors.New("upstream_stream_unsupported_delta")
		}
	case "message_delta":
		delta, ok := e["delta"].(map[string]any)
		if !ok {
			return errors.New("upstream_stream_invalid_delta")
		}
		for k, v := range delta {
			b.response[k] = v
		}
		if usage, ok := e["usage"].(map[string]any); ok {
			old, ok := b.response["usage"].(map[string]any)
			if !ok {
				old = map[string]any{}
				b.response["usage"] = old
			}
			for k, v := range usage {
				old[k] = v
			}
		}
	case "message_stop":
		b.terminal = true
	default:
		return errors.New("upstream_stream_unsupported_event")
	}
	return nil
}
