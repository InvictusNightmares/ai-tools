package autogateway

import (
	"strings"
	"testing"
	"time"
)

func TestClassifierAndCapabilityFilter(t *testing.T) {
	classification := ExtractFeatures(Request{Messages: []Message{{Role: "user", Content: strings.Repeat("Debug this stack trace and prepare a patch for the migration. ", 900)}}, Tools: []Tool{{Name: "run_tests"}}, ResponseFormat: true})
	if classification.Intent != "agent" {
		t.Fatalf("intent = %s", classification.Intent)
	}
	if classification.EffectiveReasoningEffort != ReasoningXHigh {
		t.Fatalf("effort = %s", classification.EffectiveReasoningEffort)
	}
	capable := FilterCapableModels(classification, DefaultCatalog)
	if len(capable) != 3 {
		t.Fatalf("capable models = %d, want 3", len(capable))
	}
}

func TestMultipleUpgradesAndTaskReset(t *testing.T) {
	state := NewRouteState()
	health := map[string]Health{}
	route := func(turn, score int, newEpoch bool) RouteDecision {
		return DecideRoute(state, Classification{Intent: "coding", RequiredCapabilities: []Capability{CapabilityText, CapabilityCode}, Score: score, Confidence: 0.9}, DefaultCatalog, health, turn, time.Unix(int64(turn), 0), newEpoch, false, false)
	}
	result := route(1, 10, false)
	state = result.State
	if result.SelectedModel.Name != "deepseek-flash" {
		t.Fatal(result.SelectedModel.Name)
	}
	result = route(2, 35, false)
	state = result.State
	if result.Action != "keep" {
		t.Fatal(result.Action)
	}
	result = route(4, 35, false)
	state = result.State
	if result.SelectedModel.Name != "gpt-5.6-luna" {
		t.Fatal(result.SelectedModel.Name)
	}
	result = route(7, 60, false)
	state = result.State
	if result.SelectedModel.Name != "gpt-5.6-terra" {
		t.Fatal(result.SelectedModel.Name)
	}
	result = route(10, 80, false)
	state = result.State
	if result.SelectedModel.Name != "gpt-5.6-sol" {
		t.Fatal(result.SelectedModel.Name)
	}
	result = route(13, 95, false)
	state = result.State
	if result.SelectedModel.Name != "gpt-6-astra" {
		t.Fatal(result.SelectedModel.Name)
	}
	result = route(14, 10, false)
	state = result.State
	if result.Reason != "sticky_quality_floor" {
		t.Fatal(result.Reason)
	}
	result = route(15, 10, true)
	if result.SelectedModel.Name != "deepseek-flash" {
		t.Fatal(result.SelectedModel.Name)
	}
}

func TestToolLoopLocksModel(t *testing.T) {
	state := NewRouteState()
	base := Classification{Intent: "coding", RequiredCapabilities: []Capability{CapabilityText, CapabilityCode}, Score: 10, Confidence: 0.9}
	result := DecideRoute(state, base, DefaultCatalog, nil, 1, time.Unix(1, 0), false, true, false)
	result = DecideRoute(result.State, Classification{Intent: "coding", RequiredCapabilities: []Capability{CapabilityText, CapabilityCode}, Score: 95, Confidence: 0.9}, DefaultCatalog, nil, 2, time.Unix(2, 0), false, true, false)
	if result.Action != "keep" || result.SelectedModel.Name != "deepseek-flash" {
		t.Fatalf("unexpected tool route: %+v", result)
	}
	result = DecideRoute(EndToolLoop(result.State), Classification{Intent: "coding", RequiredCapabilities: []Capability{CapabilityText, CapabilityCode}, Score: 95, Confidence: 0.9}, DefaultCatalog, nil, 5, time.Unix(5, 0), false, false, false)
	if result.Action != "upgrade" {
		t.Fatal(result.Action)
	}
}

func TestStreamingTurnCannotSwitchModelsMidResponse(t *testing.T) {
	state := NewRouteState()
	quick := ExtractFeatures(Request{Messages: []Message{{Role: "user", Content: "hello"}}, Stream: true})
	first := DecideRouteAtTurnBoundary(state, quick, DefaultCatalog, nil, 1, time.Unix(1, 0), false, false, false, false)
	if first.SelectedModel.Name != "deepseek-flash" {
		t.Fatalf("initial model = %s", first.SelectedModel.Name)
	}
	complex := ExtractFeatures(Request{Messages: []Message{{Role: "user", Content: strings.Repeat("Design a scalable architecture and debug this production failure with a migration plan and regression tests. ", 500)}}, Stream: true})
	active := DecideRouteAtTurnBoundary(first.State, complex, DefaultCatalog, nil, 2, time.Unix(2, 0), false, false, false, true)
	if active.Action != "keep" || active.Reason != "stream_in_flight" || active.SelectedModel.Name != "deepseek-flash" {
		t.Fatalf("stream switched mid-response: %+v", active)
	}
	completed := DecideRouteAtTurnBoundary(active.State, complex, DefaultCatalog, nil, 5, time.Unix(5, 0), false, false, false, false)
	if completed.Action != "upgrade" || completed.SelectedModel.Name != "gpt-6-astra" {
		t.Fatalf("turn-boundary upgrade = %+v", completed)
	}
}

func TestHardFailureFailsOverWithoutWaitingForHealthRefresh(t *testing.T) {
	classification := Classification{Intent: "architecture", RequiredCapabilities: []Capability{CapabilityText, CapabilityCode, CapabilityLongContext}, Score: 95, EffectiveReasoningEffort: ReasoningXHigh}
	first := DecideRoute(NewRouteState(), classification, DefaultCatalog, nil, 1, time.Unix(1, 0), false, false, false)
	if first.SelectedModel.Name != "gpt-6-astra" {
		t.Fatalf("initial model = %s", first.SelectedModel.Name)
	}
	failover := DecideRoute(first.State, classification, DefaultCatalog, nil, 2, time.Unix(2, 0), false, false, true)
	if failover.Action != "failover" || failover.SelectedModel == nil || failover.SelectedModel.Name == "gpt-6-astra" || failover.Reason != "provider_failure_failover" {
		t.Fatalf("failure route = %+v", failover)
	}
}

func TestCacheNamespaceIsolation(t *testing.T) {
	args := []string{"local-secret", "tokyo", "sub2api", "deepseek-flash", "r1", "key-1", "workspace-a"}
	first, err := CacheNamespace(args[0], args[1], args[2], args[3], args[4], args[5], args[6])
	if err != nil {
		t.Fatal(err)
	}
	same, _ := CacheNamespace(args[0], args[1], args[2], args[3], args[4], args[5], args[6])
	other, _ := CacheNamespace(args[0], args[1], args[2], args[3], args[4], "key-2", args[6])
	if first != same || first == other {
		t.Fatal("namespace isolation failed")
	}
	withLow, _ := CacheNamespaceWithReasoningEffort(args[0], args[1], args[2], args[3], ReasoningLow, args[4], args[5], args[6])
	withHigh, _ := CacheNamespaceWithReasoningEffort(args[0], args[1], args[2], args[3], ReasoningHigh, args[4], args[5], args[6])
	if withLow == withHigh {
		t.Fatal("reasoning effort must isolate cache namespace")
	}
}

func TestReasoningEffortIsGeneratedFromFeatures(t *testing.T) {
	quick := ExtractFeatures(Request{Messages: []Message{{Role: "user", Content: "translate hello"}}})
	complex := ExtractFeatures(Request{Messages: []Message{{Role: "user", Content: strings.Repeat("Design a scalable architecture and debug this production failure. ", 500)}}, Tools: []Tool{{Name: "run_tests"}}})
	if quick.EffectiveReasoningEffort != ReasoningLow {
		t.Fatalf("quick effort = %s", quick.EffectiveReasoningEffort)
	}
	if complex.EffectiveReasoningEffort != ReasoningXHigh {
		t.Fatalf("complex effort = %s", complex.EffectiveReasoningEffort)
	}
}

func TestProviderReasoningMapping(t *testing.T) {
	mapped := MapReasoningEffort("openai", "responses", ReasoningXHigh, []ReasoningEffort{ReasoningHigh})
	if mapped.Status != EffortMapped || mapped.Applied != ReasoningHigh || mapped.Parameter != "reasoning.effort" {
		t.Fatalf("mapping = %+v", mapped)
	}
	defaulted := MapReasoningEffort("deepseek", "chat", ReasoningXHigh, nil)
	if defaulted.Status != EffortDefaulted || defaulted.Parameter != "reasoning_effort" {
		t.Fatalf("default = %+v", defaulted)
	}
	minimal := MapReasoningEffort("provider", "chat", ReasoningMinimal, []ReasoningEffort{ReasoningNone})
	if minimal.Status != EffortMapped || minimal.Applied != ReasoningNone {
		t.Fatalf("minimal mapping = %+v", minimal)
	}
}

func TestProviderParametersNeverForwardClientEffort(t *testing.T) {
	model := *ModelByName("gpt-6-astra", DefaultCatalog)
	responses := BuildProviderParameters("openai", "responses", model, ReasoningHigh, true)
	if responses.Model != model.Name || !responses.Stream || responses.ReasoningParameter["reasoning"] == nil {
		t.Fatalf("responses parameters = %+v", responses)
	}
	deepseek := *ModelByName("deepseek-flash", DefaultCatalog)
	chat := BuildProviderParameters("deepseek", "chat", deepseek, ReasoningXHigh, false)
	if chat.Reasoning.Status != EffortMapped || chat.ReasoningParameter["reasoning_effort"] != string(ReasoningHigh) {
		t.Fatalf("deepseek parameters = %+v", chat)
	}
	unsupported := Model{Name: "limited", Provider: "provider", ReasoningEfforts: []ReasoningEffort{ReasoningNone}}
	defaulted := BuildProviderParameters("provider", "chat", unsupported, ReasoningHigh, false)
	if defaulted.Reasoning.Status != EffortMapped || defaulted.ReasoningParameter["reasoning_effort"] != string(ReasoningNone) {
		t.Fatalf("fallback parameters = %+v", defaulted)
	}
}

func TestUsageNormalization(t *testing.T) {
	usage := map[string]any{"prompt_tokens": 10000, "prompt_tokens_details": map[string]any{"cached_tokens": 8000}, "completion_tokens": 500}
	normalized := NormalizeUsage(usage)
	if normalized.CacheHitTokens != 8000 || normalized.CacheMissTokens != 2000 || normalized.CacheStatus != "hit" {
		t.Fatalf("unexpected usage: %+v", normalized)
	}
	_, cost, status := EstimateCost(map[string]any{"prompt_tokens": 10000, "completion_tokens": 500}, Pricing{InputMiss: 1, InputHit: 0.1, Output: 2})
	if status != "conservative" || cost != 0.011 {
		t.Fatalf("cost=%v status=%s", cost, status)
	}
}

func TestPublicModelIsAutoOnly(t *testing.T) {
	gateway := NewAutoGateway()
	if err := gateway.ValidatePublicModel(""); err != nil {
		t.Fatal(err)
	}
	if err := gateway.ValidatePublicModel("auto"); err != nil {
		t.Fatal(err)
	}
	if err := gateway.ValidatePublicModel("gpt-unknown"); err != ErrModelNotFound {
		t.Fatalf("error = %v", err)
	}
}
