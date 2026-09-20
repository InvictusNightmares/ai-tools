package autogateway

import "errors"

func (b *streamAssembly) chatEvent(e map[string]any) error {
	for _, key := range []string{"id", "model"} {
		if v := textField(e, key); v != "" {
			if old := textField(b.response, key); old != "" && old != v {
				return errors.New("upstream_stream_identity_changed")
			}
			b.response[key] = v
		}
	}
	for _, key := range []string{"created", "system_fingerprint", "service_tier", "usage", "reasoning"} {
		if e[key] != nil {
			b.response[key] = e[key]
		}
	}
	choices, ok := e["choices"].([]any)
	if !ok {
		return errors.New("upstream_stream_invalid_choices")
	}
	for _, raw := range choices {
		item, ok := raw.(map[string]any)
		if !ok {
			return errors.New("upstream_stream_invalid_choice")
		}
		i, err := eventIndex(item)
		if err != nil {
			return err
		}
		choice := b.choices[i]
		if choice == nil {
			choice = map[string]any{"index": i, "message": map[string]any{"role": "assistant", "content": nil}}
			b.choices[i] = choice
		}
		if textField(choice, "finish_reason") != "" {
			return errors.New("upstream_stream_choice_already_finished")
		}
		delta, ok := item["delta"].(map[string]any)
		if !ok {
			return errors.New("upstream_stream_invalid_delta")
		}
		message := choice["message"].(map[string]any)
		for key, value := range delta {
			if value == nil {
				continue
			}
			if key == "tool_calls" {
				calls, ok := value.([]any)
				if !ok {
					return errors.New("upstream_stream_invalid_tool")
				}
				if b.tools[i] == nil {
					b.tools[i] = map[int]map[string]any{}
				}
				for _, rawCall := range calls {
					call, ok := rawCall.(map[string]any)
					if !ok {
						return errors.New("upstream_stream_invalid_tool")
					}
					j, err := eventIndex(call)
					if err != nil {
						return err
					}
					delete(call, "index")
					if b.tools[i][j] == nil {
						b.tools[i][j] = map[string]any{}
					}
					if err := mergeStreamDelta(b.tools[i][j], call); err != nil {
						return err
					}
				}
			} else {
				if err := mergeStreamDelta(message, map[string]any{key: value}); err != nil {
					return err
				}
			}
		}
		if item["finish_reason"] != nil {
			choice["finish_reason"] = item["finish_reason"]
		}
		if logs, ok := item["logprobs"].(map[string]any); ok {
			old, ok := choice["logprobs"].(map[string]any)
			if !ok {
				old = map[string]any{}
				choice["logprobs"] = old
			}
			if err := mergeStreamDelta(old, logs); err != nil {
				return err
			}
		}
	}
	return nil
}
