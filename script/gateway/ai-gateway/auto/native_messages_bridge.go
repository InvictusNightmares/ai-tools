package autogateway

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"strings"
)

// Sub2API's Messages adapter drops document blocks. Use its verified Chat
// file transport and translate incremental results back to Messages. This
// bridge runs only after Guard and does not extract attachment contents.
func needsNativeMessagesBridge(r UpstreamRequest) bool {
	return canonicalProtocol(r.Protocol) == "anthropic" && r.Request.Native != nil && r.Request.Native.Files > 0
}

func nativeMessagesChatPayload(raw []byte) ([]byte, error) {
	v, err := nativeDecode(raw)
	if err != nil {
		return nil, err
	}
	in, ok := v.(map[string]any)
	if !ok {
		return nil, errors.New("invalid_messages_payload")
	}
	out := map[string]any{"model": in["model"], "stream": true, "stream_options": map[string]any{"include_usage": true}}
	for _, key := range []string{"max_tokens", "temperature", "top_p", "metadata"} {
		if v, ok := in[key]; ok {
			out[key] = v
		}
	}
	if s, ok := in["stop_sequences"]; ok {
		out["stop"] = s
	}
	if config, ok := in["output_config"].(map[string]any); ok {
		if e, ok := config["effort"]; ok {
			out["reasoning_effort"] = e
		}
		if f, ok := config["format"]; ok {
			out["response_format"] = f
		}
	}
	messages := []any{}
	if system, ok := in["system"]; ok {
		parts, e := nativeMessagesChatParts(system)
		if e != nil {
			return nil, e
		}
		messages = append(messages, map[string]any{"role": "system", "content": parts})
	}
	items, ok := in["messages"].([]any)
	if !ok {
		return nil, errors.New("invalid_messages_payload")
	}
	for _, item := range items {
		m, ok := item.(map[string]any)
		if !ok {
			return nil, errors.New("invalid_message")
		}
		if content, ok := m["content"].(string); ok {
			messages = append(messages, map[string]any{"role": m["role"], "content": content})
			continue
		}
		parts, ok := m["content"].([]any)
		if !ok {
			return nil, errors.New("invalid_message_content")
		}
		ordinary := []any{}
		calls := []any{}
		flush := func() error {
			if len(ordinary) == 0 && len(calls) == 0 {
				return nil
			}
			converted, e := nativeMessagesChatParts(ordinary)
			if e != nil {
				return e
			}
			message := map[string]any{"role": m["role"], "content": converted}
			if len(calls) > 0 {
				message["tool_calls"] = calls
			}
			messages = append(messages, message)
			ordinary = []any{}
			calls = []any{}
			return nil
		}
		for _, value := range parts {
			p, ok := value.(map[string]any)
			if !ok {
				return nil, errors.New("invalid_content_part")
			}
			switch p["type"] {
			case "tool_use":
				args, e := json.Marshal(p["input"])
				if e != nil {
					return nil, e
				}
				calls = append(calls, map[string]any{"id": p["id"], "type": "function", "function": map[string]any{"name": p["name"], "arguments": string(args)}})
			case "tool_result":
				if e := flush(); e != nil {
					return nil, e
				}
				content, e := nativeMessagesChatParts(p["content"])
				if e != nil {
					return nil, e
				}
				// is_error is model-visible without changing the tool call identity.
				if p["is_error"] == true {
					if s, ok := content.(string); ok {
						content = "Tool returned an error:\n" + s
					} else {
						content = append([]any{map[string]any{"type": "text", "text": "Tool returned an error:"}}, content.([]any)...)
					}
				}
				messages = append(messages, map[string]any{"role": "tool", "tool_call_id": p["tool_use_id"], "content": content})
			case "thinking", "redacted_thinking":
				// Active provider-private state cannot be silently discarded by a bridge.
				return nil, errors.New("native_file_private_history_not_portable")
			default:
				ordinary = append(ordinary, p)
			}
		}
		if e := flush(); e != nil {
			return nil, e
		}
	}
	out["messages"] = messages
	if ts, ok := in["tools"].([]any); ok {
		tools := []any{}
		for _, v := range ts {
			t, ok := v.(map[string]any)
			if !ok {
				return nil, errors.New("invalid_tool")
			}
			if typ := textField(t, "type"); typ != "" && typ != "custom" {
				return nil, errors.New("native_file_tool_type_unsupported")
			}
			f := map[string]any{"name": t["name"], "parameters": t["input_schema"]}
			if d, ok := t["description"]; ok {
				f["description"] = d
			}
			tools = append(tools, map[string]any{"type": "function", "function": f})
		}
		out["tools"] = tools
	}
	if t, ok := in["tool_choice"].(map[string]any); ok {
		switch t["type"] {
		case "auto", "none":
			out["tool_choice"] = t["type"]
		case "any":
			out["tool_choice"] = "required"
		case "tool":
			out["tool_choice"] = map[string]any{"type": "function", "function": map[string]any{"name": t["name"]}}
		default:
			return nil, errors.New("invalid_tool_choice")
		}
		if d, ok := t["disable_parallel_tool_use"].(bool); ok {
			out["parallel_tool_calls"] = !d
		}
	}
	return json.Marshal(out)
}

func nativeMessagesChatParts(value any) (any, error) {
	if value == nil {
		return "", nil
	}
	if s, ok := value.(string); ok {
		return s, nil
	}
	parts, ok := value.([]any)
	if !ok {
		return nil, errors.New("invalid_content_parts")
	}
	out := []any{}
	for _, v := range parts {
		p, ok := v.(map[string]any)
		if !ok {
			return nil, errors.New("invalid_content_part")
		}
		switch p["type"] {
		case "text":
			out = append(out, map[string]any{"type": "text", "text": p["text"]})
		case "image", "document":
			if c, ok := p["citations"].(map[string]any); ok && c["enabled"] == true {
				return nil, errors.New("native_file_citations_unsupported")
			}
			native, ok := nativeClassifierPart(p)
			if !ok {
				return nil, errors.New("unsupported_native_part")
			}
			n := native.(map[string]any)
			switch n["type"] {
			case "input_text":
				out = append(out, map[string]any{"type": "text", "text": n["text"]})
			case "input_image":
				out = append(out, map[string]any{"type": "image_url", "image_url": map[string]any{"url": n["image_url"]}})
			case "input_file":
				delete(n, "type")
				out = append(out, map[string]any{"type": "file", "file": n})
			}
		default:
			return nil, errors.New("native_file_content_type_unsupported")
		}
	}
	return out, nil
}

type nativeBridgeBody struct {
	*io.PipeReader
	upstream io.Closer
}

func (b *nativeBridgeBody) Close() error {
	_ = b.upstream.Close()
	return b.PipeReader.Close()
}

func (client *HTTPUpstreamClient) openNativeMessagesStream(ctx context.Context, r UpstreamRequest) (*http.Response, error) {
	payload, err := nativeMessagesChatPayload(r.Payload)
	if err != nil {
		return nil, err
	}
	r.Protocol = "chat"
	r.Payload = payload
	response, err := client.OpenStream(ctx, r)
	if err != nil {
		return nil, err
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 {
		return response, nil
	}
	if !strings.Contains(response.Header.Get("Content-Type"), "text/event-stream") {
		response.Body.Close()
		return nil, errors.New("native_bridge_requires_sse")
	}
	original := response.Body
	reader, writer := io.Pipe()
	response.Body = &nativeBridgeBody{reader, original}
	response.ContentLength = -1
	response.Header.Del("Content-Length")
	go func() {
		defer original.Close()
		err := relayChatToMessages(ctx, writer, original)
		_ = writer.CloseWithError(err)
	}()
	return response, nil
}

func relayChatToMessages(ctx context.Context, w io.Writer, r io.Reader) error {
	emit := func(kind string, v map[string]any) error {
		v["type"] = kind
		b, e := json.Marshal(v)
		if e != nil {
			return e
		}
		_, e = w.Write(append(append([]byte("event: "+kind+"\ndata: "), b...), []byte("\n\n")...))
		return e
	}
	assembly := streamAssembly{protocol: "chat", response: map[string]any{}, choices: map[int]map[string]any{}, tools: map[int]map[int]map[string]any{}}
	started := false
	next := 0
	textIndex := -1
	toolBlocks := map[int]int{}
	toolSent := map[int]int{}
	reason := ""
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 4096), 16<<20)
	var data []string
	flush := func() error {
		if len(data) == 0 {
			return nil
		}
		raw := strings.Join(data, "\n")
		data = nil
		if err := assembly.event("", raw); err != nil {
			return err
		}
		if assembly.terminal {
			if !started || reason == "" {
				return errors.New("native_bridge_incomplete")
			}
			for i := 0; i < next; i++ {
				if e := emit("content_block_stop", map[string]any{"index": i}); e != nil {
					return e
				}
			}
			usage := map[string]any{"input_tokens": 0, "output_tokens": 0}
			if u, ok := assembly.response["usage"].(map[string]any); ok {
				usage["input_tokens"] = u["prompt_tokens"]
				usage["output_tokens"] = u["completion_tokens"]
				if d, ok := u["prompt_tokens_details"].(map[string]any); ok {
					usage["cache_read_input_tokens"] = d["cached_tokens"]
				}
			}
			stop := "end_turn"
			switch reason {
			case "tool_calls":
				stop = "tool_use"
			case "length":
				stop = "max_tokens"
			case "stop":
			default:
				return errors.New("native_bridge_finish_unsupported")
			}
			if e := emit("message_delta", map[string]any{"delta": map[string]any{"stop_reason": stop, "stop_sequence": nil}, "usage": usage}); e != nil {
				return e
			}
			return emit("message_stop", map[string]any{})
		}
		if !started {
			if textField(assembly.response, "id") == "" {
				return errors.New("native_bridge_missing_id")
			}
			started = true
			if e := emit("message_start", map[string]any{"message": map[string]any{"id": assembly.response["id"], "type": "message", "role": "assistant", "model": assembly.response["model"], "content": []any{}, "stop_reason": nil, "stop_sequence": nil, "usage": map[string]any{"input_tokens": 0, "output_tokens": 0}}}); e != nil {
				return e
			}
		}
		decoded, _ := nativeDecode([]byte(raw))
		event := decoded.(map[string]any)
		choices, _ := event["choices"].([]any)
		for _, v := range choices {
			c := v.(map[string]any)
			i, e := eventIndex(c)
			if e != nil || i != 0 {
				return errors.New("native_bridge_multiple_choices")
			}
			d := c["delta"].(map[string]any)
			if s := textField(d, "content"); s != "" {
				if textIndex < 0 {
					textIndex = next
					next++
					if e := emit("content_block_start", map[string]any{"index": textIndex, "content_block": map[string]any{"type": "text", "text": ""}}); e != nil {
						return e
					}
				}
				if e := emit("content_block_delta", map[string]any{"index": textIndex, "delta": map[string]any{"type": "text_delta", "text": s}}); e != nil {
					return e
				}
			}
			for j, call := range assembly.tools[0] {
				f, _ := call["function"].(map[string]any)
				id, name := textField(call, "id"), textField(f, "name")
				if id == "" || name == "" {
					continue
				}
				index, ok := toolBlocks[j]
				if !ok {
					index = next
					next++
					toolBlocks[j] = index
					if e := emit("content_block_start", map[string]any{"index": index, "content_block": map[string]any{"type": "tool_use", "id": id, "name": name, "input": map[string]any{}}}); e != nil {
						return e
					}
				}
				args := textField(f, "arguments")
				if len(args) > toolSent[j] {
					if e := emit("content_block_delta", map[string]any{"index": index, "delta": map[string]any{"type": "input_json_delta", "partial_json": args[toolSent[j]:]}}); e != nil {
						return e
					}
					toolSent[j] = len(args)
				}
			}
			if s := textField(c, "finish_reason"); s != "" {
				reason = s
			}
		}
		return nil
	}
	for scanner.Scan() {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		line := strings.TrimSuffix(scanner.Text(), "\r")
		if line == "" {
			if e := flush(); e != nil {
				return e
			}
		} else if strings.HasPrefix(line, "data:") {
			data = append(data, strings.TrimPrefix(line[5:], " "))
		}
	}
	if scanner.Err() != nil {
		return scanner.Err()
	}
	if e := flush(); e != nil {
		return e
	}
	if !assembly.terminal {
		return errors.New("native_bridge_incomplete")
	}
	return nil
}
