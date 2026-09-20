package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"testing"
	"time"
)

const localCommandID = "01M2NHT0PYXNH4V0N8Y57Q074P"

type checkedFailureStateStore struct{ MemorySessionStateStore }

func (*checkedFailureStateStore) LoadChecked(string, time.Time) (RouteState, error) {
	return RouteState{}, errors.New("unreadable state")
}

func localCommandFixture(protocol, id string) Request {
	marker := "The following tool was executed by the user"
	var raw string
	switch protocol {
	case "responses":
		raw = fmt.Sprintf(`{"input":[{"role":"user","content":[{"type":"input_text","text":%q}]},{"type":"function_call","call_id":%q,"name":"task","arguments":"{}"},{"type":"function_call_output","call_id":%q,"output":"Local task completed"}]}`, marker, id, id)
	case "chat":
		raw = fmt.Sprintf(`{"messages":[{"role":"user","content":%q},{"role":"assistant","tool_calls":[{"id":%q,"type":"function","function":{"name":"bash","arguments":"{}"}}]},{"role":"tool","tool_call_id":%q,"content":"Local command completed"}]}`, marker, id, id)
	default:
		raw = fmt.Sprintf(`{"messages":[{"role":"user","content":[{"type":"text","text":%q}]},{"role":"assistant","content":[{"type":"tool_use","id":%q,"name":"task","input":{}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":%q,"content":"Local task completed"}]}]}`, marker, id, id)
	}
	r, err := NormalizeProtocolRequest(protocol, []byte(raw))
	if err != nil {
		panic(err)
	}
	return r
}

func TestOpenCodeLocalCommandCompatibilityIsNarrow(t *testing.T) {
	meta := PipelineMeta{ClientHeaders: http.Header{"User-Agent": {"opencode/1.18.4"}}}
	for _, protocol := range []string{"responses", "chat", "anthropic"} {
		t.Run(protocol, func(t *testing.T) {
			r := localCommandFixture(protocol, localCommandID)
			if !clientLocalToolPair(r, meta) {
				t.Fatal("native complete local command pair rejected")
			}
			if clientLocalToolPair(r, PipelineMeta{}) || clientLocalToolPair(localCommandFixture(protocol, "call-provider-id"), meta) {
				t.Fatal("unrelated client or provider round adopted as local command")
			}
			for _, mutate := range []func(string) string{
				func(s string) string { return strings.ReplaceAll(s, "executed by the user", "executed by someone") },
				func(s string) string { return strings.Replace(s, localCommandID, "01M2NHT0PYXNH4V0N8Y57Q074X", 1) },
				func(s string) string {
					return strings.ReplaceAll(strings.ReplaceAll(s, `"task"`, `"Read"`), `"bash"`, `"Read"`)
				},
				func(s string) string { return strings.ReplaceAll(s, localCommandID, "abcdefghijklmnopqrstuvwxyz") },
			} {
				bad := r
				bad.RawPayload = []byte(mutate(string(r.RawPayload)))
				if !json.Valid(bad.RawPayload) || clientLocalToolPair(bad, meta) {
					t.Fatal("incomplete or unrelated pair accepted")
				}
			}
		})
	}
}

func TestOpenCodeLocalToolsKeepGuardAndExistingProviderBindings(t *testing.T) {
	for _, protocol := range []string{"responses", "chat", "anthropic"} {
		for _, mode := range []string{"local", "bound", "blocked", "foreign-provider-result", "corrupt-store"} {
			t.Run(protocol+"/"+mode, func(t *testing.T) {
				now := time.Now()
				upstream := &toolRoundUpstream{}
				preflight := PreflightAllow
				if mode == "blocked" {
					preflight = PreflightBlock
				}
				store := NewMemorySessionStateStore()
				p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: preflight}}, StateStore: store, Upstream: upstream, Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
					a := assessment("coding", "exceptional")
					a.NewTask = true
					return classificationFromAssessment(r, a), nil
				})}
				meta := PipelineMeta{Region: "tokyo", APIKeyID: "key-a", SessionID: "parent", RequestID: "new-turn", ClientHeaders: http.Header{"User-Agent": {"opencode/1.18.4"}}}
				r := localCommandFixture(protocol, localCommandID)
				id := localCommandID
				if mode == "foreign-provider-result" {
					id = "provider-call-1"
					r = toolResultFixture(protocol, id)
				}
				boundMeta := meta
				if mode == "foreign-provider-result" {
					boundMeta.APIKeyID = "key-b"
				}
				state := NewRouteState()
				state.HasCurrent, state.CurrentModel, state.CurrentTier, state.ToolLoopLocked, state.ToolRoundID, state.LastActivityAt = true, DefaultCatalog[1].Name, 1, true, "old-round", now
				state.CurrentReasoningEffort = ReasoningLow
				if mode == "bound" || mode == "foreign-provider-result" {
					store.Save(toolBindingKey(boundMeta, protocol, id), state, now)
				}
				if mode == "corrupt-store" {
					// A broken persistence contract must fail before a local hint
					// can discard the missing provider binding.
					p.StateStore = &checkedFailureStateStore{}
				}
				result, err := p.ExecuteWithMeta(context.Background(), protocol, "", "auto", r, 0, false, false, false, false, meta)
				switch mode {
				case "blocked":
					if err != nil || result.Preflight.Decision != PreflightBlock || upstream.calls != 0 {
						t.Fatal("local command bypassed Guard")
					}
				case "foreign-provider-result", "corrupt-store":
					if err == nil || upstream.calls != 0 {
						t.Fatal("invalid provider state reached business model")
					}
				case "bound":
					if err != nil || result.Decision.SelectedModel.Name != DefaultCatalog[1].Name || result.Decision.Reason != "tool_loop_locked" {
						t.Fatal("local hint displaced an existing provider binding", err)
					}
				default:
					if err != nil || upstream.calls != 1 || result.Decision.SelectedModel == nil || result.Decision.Reason == "tool_loop_locked" {
						t.Fatal("local user command still requires a provider binding", err)
					}
				}
			})
		}
	}
}
