package autogateway

import "encoding/json"

// Fingerprint the goal and its preceding context, not the growing tool output.
// Only a digest and validated assessment are stored; no prompt text is retained.
func taskGoalDigest(r Request) string {
	if r.CompactionTrigger || r.CompactionState || (r.Native != nil && (r.Native.Images > 0 || r.Native.Files > 0 || r.Native.Audio > 0)) {
		return ""
	}
	in, err := splitSemanticInput(r)
	if err != nil {
		return ""
	}
	in.After, in.Tools = nil, nil
	data, err := json.Marshal(in)
	if err != nil {
		return ""
	}
	return RequestDigest(data)
}

// A new user instruction mixed with a result must still be classified. This
// check is deliberately narrower than the transport's tool-continuation test.
func onlyPendingToolResults(r Request) bool {
	if !requestToolContinuation(r) {
		return false
	}
	seen := false
	for i := len(r.Messages) - 1; i >= 0; i-- {
		m := r.Messages[i]
		if m.Role == "assistant" {
			return seen
		}
		if m.Role == "tool" && m.ToolCallID != "" {
			seen = true
			continue
		}
		if m.Role != "user" || len(m.Parts) == 0 {
			return false
		}
		for _, part := range m.Parts {
			if part.Type != "tool_result" {
				return false
			}
			seen = true
		}
	}
	return false
}

func (p *Pipeline) boundToolClassification(protocol string, r Request, meta PipelineMeta) (Classification, bool) {
	if !onlyPendingToolResults(r) {
		return Classification{}, false
	}
	digest := taskGoalDigest(r)
	if digest == "" {
		return Classification{}, false
	}
	now := p.currentTime()
	p.mu.Lock()
	defer p.mu.Unlock()
	var bound *RouteState
	err := withStateTransaction(p.StateStore, now, func(store SessionStateStore) error {
		var err error
		bound, err = toolRoundState(store, r, protocol, meta, now)
		return err
	})
	if err != nil || bound == nil || bound.ToolTaskDigest != digest || bound.ToolClassifierPolicy != semanticPolicyVersion || bound.ToolAssessment == nil || !validAssessment(*bound.ToolAssessment) {
		// Existing routing validation remains authoritative for absent, expired,
		// cross-key or legacy bindings. Never invent a low-cost assessment.
		return Classification{}, false
	}
	a := *bound.ToolAssessment
	a.TaskLabels = append([]string(nil), a.TaskLabels...)
	a.Continuation, a.NewTask = true, false
	c := classificationFromAssessment(r, a)
	c.EffectiveReasoningEffort = bound.CurrentReasoningEffort
	c.Trace.ToolBindingReused = true
	c.ReasonCodes = append(c.ReasonCodes, "bound_tool_assessment_reused")
	return c, true
}
