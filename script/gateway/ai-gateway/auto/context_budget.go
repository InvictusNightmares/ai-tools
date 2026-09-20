package autogateway

import "encoding/json"

// This conservative byte-based estimate includes the complete request and
// framing headroom. It is not tokenizer output or billable token usage.
type ContextBudget struct {
	InputEstimateTokens int    `json:"input_estimate_tokens"`
	OutputLimitTokens   int    `json:"output_limit_tokens"`
	Method              string `json:"method"`
	Invalid             bool   `json:"invalid,omitempty"`
}

func requestContextBudget(r Request) ContextBudget {
	if r.Native != nil && r.Native.Semantic != nil {
		b := requestContextBudget(*r.Native.Semantic)
		// Provider tokenization of files/media is opaque. Reserve headroom; this
		// is explicitly an estimate, never a guaranteed bound or billed usage.
		b.InputEstimateTokens += r.Native.Images*16384 + r.Native.Files*65536 + r.Native.Audio*32768
		b.Method = "native_media_budget_estimate_v1"
		return b
	}
	// Marshal normalized parts as well: this covers tool arguments/descriptions
	// for callers without RawPayload, without truncating any provider content.
	normalized, err := json.Marshal(struct {
		Messages []Message
		Tools    []Tool
	}{r.Messages, r.Tools})
	n := len(normalized)
	if len(r.RawPayload) > n {
		n = len(r.RawPayload)
	}
	b := ContextBudget{InputEstimateTokens: n + 1024 + 64*len(r.Messages) + 256*len(r.Tools), Method: "utf8_bytes_with_framing_v1", Invalid: err != nil}
	if len(r.RawPayload) == 0 {
		return b
	}
	var payload map[string]json.RawMessage
	if json.Unmarshal(r.RawPayload, &payload) != nil {
		b.Invalid = true
		return b
	}
	for _, key := range []string{"max_tokens", "max_completion_tokens", "max_output_tokens"} {
		value, ok := payload[key]
		if !ok || string(value) == "null" {
			continue
		}
		var limit int
		if json.Unmarshal(value, &limit) != nil || limit <= 0 {
			b.Invalid = true
			continue
		}
		if limit > b.OutputLimitTokens {
			b.OutputLimitTokens = limit
		}
	}
	return b
}

func modelFitsContext(c Classification, model Model) bool {
	b := c.ContextBudget
	if b.Method == "" {
		return true
	} // legacy preview/tests have no provider budget
	if b.Invalid || model.ContextWindowTokens <= 0 || model.MaxInputTokens <= 0 || model.MaxOutputTokens <= 0 || b.InputEstimateTokens > model.MaxInputTokens {
		return false
	}
	output := b.OutputLimitTokens
	if output == 0 {
		output = model.MaxOutputTokens
	}
	// Subtraction avoids overflow for untrusted output limits.
	return output <= model.MaxOutputTokens && output <= model.ContextWindowTokens && b.InputEstimateTokens <= model.ContextWindowTokens-output
}
