package autogateway

import (
	"context"
	"net/http"
	"testing"
	"time"
)

func TestLocalToolHistoryRequiresCompatibleTransport(t *testing.T) {
	for _, flow := range []string{"plan", "execute"} {
		for _, protocol := range []string{"responses", "chat", "anthropic"} {
			for _, mode := range []string{"new", "sticky", "provider-bound", "incompatible-only"} {
				t.Run(flow+"/"+protocol+"/"+mode, func(t *testing.T) {
					now := time.Now()
					backing := []Capability{CapabilityText, CapabilityTools, "cache-sentinel"}
					classification := Classification{Score: 5, Confidence: .99, EffectiveReasoningEffort: ReasoningNone, RequiredCapabilities: backing[:2]}
					store := NewMemorySessionStateStore()
					upstream := &toolRoundUpstream{}
					p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, StateStore: store, Upstream: upstream, Now: func() time.Time { return now }, Classifier: taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) { return classification, nil })}
					meta := PipelineMeta{Region: "tokyo", APIKeyID: "fixture-key", SessionID: "local-history", RequestID: "fixture-request", ClientHeaders: http.Header{"User-Agent": {"opencode/1.18.4"}}}
					r := localCommandFixture(protocol, localCommandID)
					original := string(r.RawPayload)
					state := NewRouteState()
					state.HasCurrent, state.CurrentModel, state.CurrentTier = true, "deepseek-flash", 0
					state.Turn, state.LastSwitchTurn, state.LastActivityAt = 1, 1, now
					state.CurrentReasoningEffort = ReasoningNone
					if mode == "sticky" {
						store.Save(sessionStoreKey(meta), state, now)
					}
					if mode == "provider-bound" {
						state.ToolLoopLocked, state.ToolRoundID = true, "provider-round"
						store.Save(toolBindingKey(meta, protocol, localCommandID), state, now)
					}
					if mode == "incompatible-only" {
						p.Gateway.Catalog = p.Gateway.Catalog[:1]
					}
					var result PipelineResult
					var err error
					if flow == "plan" {
						result, err = p.Plan(context.Background(), protocol, "", "auto", r, 2, false, false, false, false, meta)
					} else {
						result, err = p.ExecuteWithMeta(context.Background(), protocol, "", "auto", r, 2, false, false, false, false, meta)
					}
					constrained := protocol == "responses" && mode != "provider-bound"
					if constrained && mode == "incompatible-only" {
						if err == nil || err.Error() != "no_capable_model" || upstream.calls != 0 {
							t.Fatal("incompatible history reached provider", err)
						}
						return
					}
					want := "deepseek-flash"
					if constrained {
						want = "gpt-5.6-luna"
					}
					if err != nil || result.Decision.SelectedModel == nil || result.Decision.SelectedModel.Name != want {
						t.Fatalf("history route want %s, got %+v, err %v", want, result.Decision, err)
					}
					if string(result.PreparedRequest.RawPayload) != original || backing[2] != "cache-sentinel" {
						t.Fatal("transport constraint rewrote client history or cached classification")
					}
					if constrained {
						for _, model := range FilterCapableModels(result.Classification, p.Gateway.Catalog) {
							if model.Name == "deepseek-flash" {
								t.Fatal("transport constraint missing from resulting classification")
							}
						}
					}
				})
			}
		}
	}
}
