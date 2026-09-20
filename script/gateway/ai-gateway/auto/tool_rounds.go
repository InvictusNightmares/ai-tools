package autogateway

import (
	"encoding/json"
	"errors"
	"time"
)

func pendingToolResultIDs(r Request) []string {
	var ids []string
	for i := len(r.Messages) - 1; i >= 0; i-- {
		m := r.Messages[i]
		if m.Role == "assistant" {
			break
		}
		if m.Role == "tool" && m.ToolCallID != "" {
			ids = append(ids, m.ToolCallID)
		}
		for _, p := range m.Parts {
			if p.Type != "tool_result" {
				continue
			}
			var result struct {
				ID string `json:"tool_use_id"`
			}
			if json.Unmarshal(p.Raw, &result) == nil && result.ID != "" {
				ids = append(ids, result.ID)
			}
		}
	}
	return ids
}

func responseToolCallIDs(protocol string, body []byte) []string {
	var out struct {
		Content []struct {
			Type string `json:"type"`
			ID   string `json:"id"`
		} `json:"content"`
		Output []struct {
			Type string `json:"type"`
			ID   string `json:"call_id"`
		} `json:"output"`
		Choices []struct {
			Message struct {
				Calls []struct {
					ID string `json:"id"`
				} `json:"tool_calls"`
			} `json:"message"`
		} `json:"choices"`
	}
	if json.Unmarshal(body, &out) != nil {
		return nil
	}
	var ids []string
	switch canonicalProtocol(protocol) {
	case "chat":
		for _, c := range out.Choices {
			for _, t := range c.Message.Calls {
				if t.ID != "" {
					ids = append(ids, t.ID)
				}
			}
		}
	case "responses":
		for _, t := range out.Output {
			if t.Type == "function_call" && t.ID != "" {
				ids = append(ids, t.ID)
			}
		}
	case "anthropic":
		for _, t := range out.Content {
			if t.Type == "tool_use" && t.ID != "" {
				ids = append(ids, t.ID)
			}
		}
	}
	return ids
}

func toolBindingKey(meta PipelineMeta, protocol, id string) string {
	raw, _ := json.Marshal([]string{"tool-round-v1", meta.Region, meta.APIKeyID, canonicalProtocol(protocol), id})
	return "tool:" + RequestDigest(raw)
}

// Call IDs bind a result to the provider response, independently of optional
// client session headers. This also prevents parent/child agents overwriting
// each other's model when they share a parent session ID.
func (p *Pipeline) toolRoundState(request Request, protocol string, meta PipelineMeta, now time.Time) (*RouteState, error) {
	return toolRoundState(p.StateStore, request, protocol, meta, now)
}
func toolRoundState(store SessionStateStore, request Request, protocol string, meta PipelineMeta, now time.Time) (*RouteState, error) {
	ids := pendingToolResultIDs(request)
	if !requestToolContinuation(request) {
		return nil, nil
	}
	if len(ids) == 0 || store == nil || meta.Region == "" || meta.APIKeyID == "" {
		return nil, errors.New("tool_context_unavailable")
	}
	var first *RouteState
	for _, id := range ids {
		state, err := loadSessionState(store, toolBindingKey(meta, protocol, id), now)
		if err != nil {
			return nil, errors.New("session_state_unavailable")
		}
		if !state.HasCurrent || state.ToolRoundID == "" {
			if len(ids) == 1 && clientLocalToolPair(request, meta) {
				return nil, nil
			}
			return nil, errors.New("tool_context_unavailable")
		}
		if first != nil && (first.ToolRoundID != state.ToolRoundID || first.CurrentModel != state.CurrentModel) {
			return nil, errors.New("tool_round_mismatch")
		}
		copyState := state
		first = &copyState
	}
	return first, nil
}

func (p *Pipeline) saveToolRound(protocol string, meta PipelineMeta, result PipelineResult) error {
	if !result.Upstream.Complete || result.Decision.SelectedModel == nil {
		return nil
	}
	ids := result.Upstream.ToolCallIDs
	if len(ids) == 0 {
		ids = responseToolCallIDs(protocol, result.Upstream.Body)
	}
	if len(ids) == 0 {
		return nil
	}
	if p.StateStore == nil || meta.Region == "" || meta.APIKeyID == "" {
		return errors.New("tool_state_unavailable")
	}
	now := time.Now()
	if p.Now != nil {
		now = p.Now()
	}
	p.mu.Lock()
	defer p.mu.Unlock()
	return withStateTransaction(p.StateStore, now, func(store SessionStateStore) error {
		state := result.Decision.State
		state.ToolLoopLocked = true
		state.ToolRoundID = meta.RequestID
		state.ToolTaskDigest = ""
		state.ToolAssessment = nil
		state.ToolClassifierPolicy = ""
		if result.Classification.Source == semanticPolicyVersion && result.Classification.Assessment != nil {
			digest := taskGoalDigest(result.PreparedRequest)
			if digest != "" {
				a := *result.Classification.Assessment
				a.TaskLabels = append([]string(nil), a.TaskLabels...)
				state.ToolTaskDigest, state.ToolAssessment, state.ToolClassifierPolicy = digest, &a, semanticPolicyVersion
			}
		}
		for _, id := range ids {
			previous, err := loadSessionState(store, toolBindingKey(meta, protocol, id), now)
			if err != nil {
				return errors.New("session_state_unavailable")
			}
			if previous.HasCurrent && previous.ToolRoundID != "" && previous.ToolRoundID != meta.RequestID {
				return errors.New("tool_call_id_collision")
			}
		}
		for _, id := range ids {
			if err := store.Save(toolBindingKey(meta, protocol, id), state, now); err != nil {
				return err
			}
		}
		return nil
	})
}
