package autogateway

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
	"time"
)

func TestHistoricalProjectCheckpoints(t *testing.T) {
	data, err := os.ReadFile("testdata/history-cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Cases []struct {
			ID               string                     `json:"id"`
			Protocol         string                     `json:"protocol"`
			ToolContinuation bool                       `json:"expected_tool_continuation"`
			Current          map[string]string          `json:"expected_current"`
			Variants         map[string]json.RawMessage `json:"variants"`
		} `json:"cases"`
	}
	if json.Unmarshal(data, &fixture) != nil || len(fixture.Cases) != 16 {
		t.Fatal("invalid frozen history fixture")
	}
	for _, c := range fixture.Cases {
		for _, lang := range []string{"zh", "en", "mixed"} {
			t.Run(c.ID+"/"+lang, func(t *testing.T) {
				r, err := NormalizeProtocolRequest(c.Protocol, c.Variants[lang])
				if err != nil {
					t.Fatal(err)
				}
				input, err := splitSemanticInput(r)
				if err != nil || !strings.Contains(input.Current.Content, c.Current[lang]) || requestToolContinuation(r) != c.ToolContinuation {
					t.Fatalf("wrong current task/tool boundary: %v", err)
				}
				wire, err := BuildProviderPayload(c.Protocol, r, BuildProviderParameters("openai", c.Protocol, DefaultCatalog[3], ReasoningHigh, false))
				if err != nil || !json.Valid(wire) {
					t.Fatalf("invalid payload: %v", err)
				}
				var source, output map[string]json.RawMessage
				json.Unmarshal(c.Variants[lang], &source)
				json.Unmarshal(wire, &output)
				for _, field := range []string{"messages", "input", "system", "instructions", "tools"} {
					if src, ok := source[field]; ok {
						var a, b any
						json.Unmarshal(src, &a)
						json.Unmarshal(output[field], &b)
						aBytes, _ := json.Marshal(a)
						bBytes, _ := json.Marshal(b)
						if string(aBytes) != string(bBytes) {
							t.Fatalf("history/transport field lost: %s", field)
						}
					}
				}
			})
		}
	}
}

func TestToolResultWithUserCorrectionIsCurrentTask(t *testing.T) {
	for _, correction := range []string{"改用 deviceName，不再取 stationName", "Use deviceName instead of stationName", "改用 deviceName; preserve the divider"} {
		r := Request{Messages: []Message{
			{Role: "user", Content: "修复提醒列表字段"},
			{Role: "assistant", Parts: []ContentPart{{Type: "tool_use", Raw: []byte(`{"type":"tool_use","id":"c1","name":"Read","input":{}}`)}}},
			{Role: "user", Parts: []ContentPart{{Type: "tool_result", Raw: []byte(`{"type":"tool_result","tool_use_id":"c1","content":"stationName is absent"}`)}, {Type: "text", Text: correction}}},
		}}
		input, err := splitSemanticInput(r)
		if err != nil || !requestToolContinuation(r) || !strings.Contains(input.Current.Content, correction) {
			t.Fatalf("user correction lost or pending transport unlocked: %q %v", input.Current.Content, err)
		}
	}
}

func TestToolRoundCannotResetOrFailover(t *testing.T) {
	now := time.Now()
	state := NewRouteState()
	state.HasCurrent, state.CurrentModel, state.CurrentTier = true, DefaultCatalog[1].Name, DefaultCatalog[1].Tier
	state.CurrentReasoningEffort, state.LastActivityAt, state.ToolLoopLocked = ReasoningLow, now.Add(-2*time.Hour), true
	classification := classificationFromAssessment(Request{}, assessment("debugging", "exceptional"))
	decision := DecideRoute(state, classification, DefaultCatalog, nil, 0, now, true, true, false)
	if decision.SelectedModel == nil || decision.SelectedModel.Name != state.CurrentModel || decision.State.RouteEpoch != state.RouteEpoch || decision.Reason != "tool_loop_locked" {
		t.Fatalf("pending tool round reset or switched: %+v", decision)
	}
	decision = DecideRoute(state, classification, DefaultCatalog, nil, 0, now, true, true, true)
	if decision.SelectedModel != nil || decision.Reason != "tool_provider_unavailable" {
		t.Fatalf("pending provider tool round silently failed over: %+v", decision)
	}
}

func TestNestedToolResultImageIsNotSilentlyClassifiedAsText(t *testing.T) {
	r, err := NormalizeProtocolRequest("anthropic", []byte(`{"messages":[{"role":"user","content":"排查页面白屏"},{"role":"user","content":[{"type":"tool_result","tool_use_id":"c1","content":[{"type":"text","text":"截图"},{"type":"image","source":{"type":"base64","media_type":"image/png","data":"synthetic"}}]}]}]}`))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := splitSemanticInput(r); err == nil {
		t.Fatal("nested image accepted without visual analysis")
	}
}

func TestToolHistoryWithoutCatalogCannotUseResponseCache(t *testing.T) {
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		r := toolResultFixture(protocol, "call-one")
		if len(r.Tools) != 0 {
			t.Fatal("fixture unexpectedly includes tool catalog")
		}
		if allowed, _ := DefaultResponseCachePolicy().Eligible(r, PreflightAllow, 100); allowed {
			t.Fatalf("%s tool history eligible for replay cache", protocol)
		}
	}
}
