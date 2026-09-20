package autogateway

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestClientBoilerplateDoesNotExcludeSmallModels(t *testing.T) {
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		t.Run(protocol, func(t *testing.T) {
			body := map[string]any{"model": "auto", "stream": true, "max_tokens": 256}
			instructions := strings.Repeat("Available tools are optional. ", 2000)
			switch protocol {
			case "chat":
				body["messages"] = []any{map[string]any{"role": "system", "content": instructions}, map[string]any{"role": "user", "content": "你好"}}
				body["tools"] = []any{map[string]any{"type": "function", "function": map[string]any{"name": "read", "parameters": map[string]any{"type": "object"}}}}
			case "responses":
				delete(body, "max_tokens")
				body["max_output_tokens"], body["instructions"], body["input"] = 256, instructions, "你好"
				body["tools"] = []any{map[string]any{"type": "function", "name": "read", "parameters": map[string]any{"type": "object"}}}
			case "anthropic":
				body["system"] = instructions
				body["messages"] = []any{map[string]any{"role": "user", "content": "你好"}}
				body["tools"] = []any{map[string]any{"name": "read", "input_schema": map[string]any{"type": "object"}}}
			}
			raw, _ := json.Marshal(body)
			r, err := NormalizeProtocolRequest(protocol, raw)
			if err != nil {
				t.Fatal(err)
			}
			c := classificationFromAssessment(r, assessment("quick_qa", "simple"))
			d := DecideRoute(NewRouteState(), c, DefaultCatalog, nil, 1, time.Unix(1, 0), false, false, false)
			if d.SelectedModel == nil || d.SelectedModel.Name != "deepseek-flash" || c.Score != 5 {
				t.Fatalf("simple task with normal client context over-routed: model=%v score=%d capabilities=%v", d.SelectedModel, c.Score, c.RequiredCapabilities)
			}
		})
	}
}

func TestNumericContextBudgetBoundaries(t *testing.T) {
	model := Model{Name: "fixture", ContextWindowTokens: 10000, MaxInputTokens: 9000, MaxOutputTokens: 2000}
	for _, tc := range []struct {
		name          string
		input, output int
		invalid, want bool
	}{
		{"exact_total", 9000, 1000, false, true},
		{"input_too_large", 9001, 1, false, false},
		{"output_too_large", 1, 2001, false, false},
		{"total_too_large", 9000, 1001, false, false},
		{"default_reserves_max_output", 8000, 0, false, true},
		{"default_output_overflow", 8001, 0, false, false},
		{"invalid_limit", 1, 1, true, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			c := Classification{ContextBudget: ContextBudget{InputEstimateTokens: tc.input, OutputLimitTokens: tc.output, Invalid: tc.invalid, Method: "fixture"}}
			if got := modelFitsContext(c, model); got != tc.want {
				t.Fatalf("fits=%v want=%v", got, tc.want)
			}
		})
	}
}

func TestContextBudgetIncludesToolsAndRejectsInvalidOutput(t *testing.T) {
	r := Request{Messages: []Message{{Role: "user", Content: "你好"}}, Tools: []Tool{{Name: "read", Description: strings.Repeat("工具", 5000), Schema: `{}`}}}
	b := requestContextBudget(r)
	if b.Invalid || b.InputEstimateTokens < 30000 {
		t.Fatalf("tool descriptions omitted: %+v", b)
	}
	for _, value := range []string{`-1`, `0`, `1.5`, `"128"`, `9223372036854775808`} {
		r.RawPayload = json.RawMessage(`{"max_output_tokens":` + value + `}`)
		if !requestContextBudget(r).Invalid {
			t.Fatalf("accepted invalid limit %s", value)
		}
	}
	r.RawPayload = json.RawMessage(`{"max_tokens":200,"max_completion_tokens":300,"max_output_tokens":400}`)
	if got := requestContextBudget(r).OutputLimitTokens; got != 400 {
		t.Fatal(got)
	}
}

func TestCapacityCannotBeOverriddenByStickyOrToolState(t *testing.T) {
	c := classificationFromAssessment(Request{Messages: []Message{{Role: "user", Content: "continue"}}}, assessment("quick_qa", "simple"))
	c.ContextBudget.InputEstimateTokens = 950000
	c.ContextBudget.OutputLimitTokens = 1000
	state := NewRouteState()
	state.HasCurrent, state.CurrentModel, state.CurrentTier = true, "gpt-5.6-terra", 2
	d := DecideRoute(state, c, DefaultCatalog, nil, 1, time.Unix(1, 0), false, false, false)
	if d.SelectedModel == nil || d.SelectedModel.Name != "deepseek-flash" || d.Reason != "context_capacity_switch" {
		t.Fatalf("oversized sticky model retained: %+v", d)
	}
	d = DecideRoute(state, c, DefaultCatalog, nil, 1, time.Unix(1, 0), false, true, false)
	if d.SelectedModel != nil || d.Reason != "tool_context_capacity_exceeded" {
		t.Fatalf("switched active tool provider: %+v", d)
	}
	c.ContextBudget.InputEstimateTokens = 1100000
	if len(FilterCapableModels(c, DefaultCatalog)) != 0 {
		t.Fatal("oversized input accepted")
	}
}

func TestComplexTaskStillSelectsStrongModelWithNormalContext(t *testing.T) {
	c := classificationFromAssessment(Request{Messages: []Message{{Role: "user", Content: "Analyze interacting failures"}}}, assessment("architecture", "exceptional"))
	d := DecideRoute(NewRouteState(), c, DefaultCatalog, nil, 1, time.Unix(1, 0), false, false, false)
	if d.SelectedModel == nil || d.SelectedModel.Name != "gpt-6-astra" {
		t.Fatalf("complex task downgraded: %+v", d)
	}
}
