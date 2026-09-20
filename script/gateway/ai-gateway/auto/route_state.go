package autogateway

import "time"

type Health struct {
	Score       float64
	Unavailable bool
}

type RouteState struct {
	SessionTTL             time.Duration
	UpgradeCooldownTurns   int
	DowngradeMargin        float64
	RouteEpoch             int
	Turn                   int
	CurrentModel           string
	CurrentTier            int
	CurrentReasoningEffort ReasoningEffort
	HasCurrent             bool
	LastSwitchTurn         int
	LastActivityAt         time.Time
	ToolLoopLocked         bool
	ToolRoundID            string
	ToolTaskDigest         string          `json:",omitempty"`
	ToolAssessment         *TaskAssessment `json:",omitempty"`
	ToolClassifierPolicy   string          `json:",omitempty"`
}

type RouteDecision struct {
	State           RouteState
	SelectedModel   *Model
	Action          string
	Switched        bool
	Reason          string
	ReasoningEffort ReasoningEffort
}

func NewRouteState() RouteState {
	return RouteState{SessionTTL: time.Hour, UpgradeCooldownTurns: 3, DowngradeMargin: 0.2, LastSwitchTurn: -1}
}

func bestModel(classification Classification, catalog []Model, health map[string]Health) *Model {
	capable := FilterCapableModels(classification, healthyCatalog(catalog, health))
	if len(capable) == 0 {
		return nil
	}
	healthScores := make(map[string]float64, len(health))
	for name, item := range health {
		healthScores[name] = item.Score
	}
	ranked := RankModels(classification, capable, healthScores)
	if len(ranked) == 0 {
		return nil
	}
	return &ranked[0]
}

func DecideRoute(state RouteState, classification Classification, catalog []Model, health map[string]Health, turn int, now time.Time, newTaskEpoch bool, toolLoop bool, hardCapabilityFailure bool) RouteDecision {
	next := state
	if turn <= 0 {
		turn = next.Turn + 1
		if turn <= 0 {
			turn = 1
		}
	}
	next.Turn = turn
	expired := !next.LastActivityAt.IsZero() && now.Sub(next.LastActivityAt) > next.SessionTTL
	// A pending tool result belongs to the provider round that produced it.
	// Reclassification and idle TTL must not reset that provider binding.
	if !toolLoop && (newTaskEpoch || expired) {
		next.RouteEpoch++
		next.HasCurrent = false
		next.CurrentModel = ""
		next.CurrentTier = 0
		next.CurrentReasoningEffort = ""
		next.LastSwitchTurn = -1
		next.ToolLoopLocked = false
		next.ToolRoundID = ""
		next.ToolTaskDigest, next.ToolClassifierPolicy, next.ToolAssessment = "", "", nil
	}

	best := bestModel(classification, catalog, health)
	if best == nil {
		next.LastActivityAt = now
		return RouteDecision{State: next, Action: "reject", Reason: "no_capable_model"}
	}
	effort := classification.EffectiveReasoningEffort
	if effort == "" {
		effort = InferReasoningEffort(classification.Score)
	}
	if !next.HasCurrent {
		next.HasCurrent, next.CurrentModel, next.CurrentTier, next.CurrentReasoningEffort, next.LastSwitchTurn = true, best.Name, best.Tier, effort, turn
		next.LastActivityAt, next.ToolLoopLocked = now, toolLoop
		return RouteDecision{State: next, SelectedModel: best, Action: "select", Switched: true, Reason: "initial_selection", ReasoningEffort: effort}
	}

	current := ModelByName(next.CurrentModel, catalog)
	if current == nil {
		next.HasCurrent = false
		return DecideRoute(next, classification, catalog, health, turn, now, false, toolLoop, hardCapabilityFailure)
	}
	if hardCapabilityFailure || health[current.Name].Unavailable {
		if next.ToolLoopLocked || toolLoop {
			next.LastActivityAt = now
			return RouteDecision{State: next, Action: "reject", Reason: "tool_provider_unavailable"}
		}
		fallback := fallbackModel(classification, current.Name, catalog, health)
		if fallback == nil {
			next.LastActivityAt = now
			return RouteDecision{State: next, Action: "reject", Reason: "no_fallback_model"}
		}
		next.CurrentModel, next.CurrentTier, next.CurrentReasoningEffort, next.LastSwitchTurn, next.LastActivityAt = fallback.Name, fallback.Tier, effort, turn, now
		next.ToolLoopLocked = toolLoop
		return RouteDecision{State: next, SelectedModel: fallback, Action: "failover", Switched: true, Reason: "provider_failure_failover", ReasoningEffort: effort}
	}
	if next.ToolLoopLocked || toolLoop {
		if !modelFitsContext(classification, *current) {
			return RouteDecision{State: next, Action: "reject", Reason: "tool_context_capacity_exceeded"}
		}
		if len(FilterCapableModels(classification, []Model{*current})) == 0 {
			return RouteDecision{State: next, Action: "reject", Reason: "tool_model_capability_mismatch"}
		}
		next.LastActivityAt, next.ToolLoopLocked = now, true
		return RouteDecision{State: next, SelectedModel: current, Action: "keep", Reason: "tool_loop_locked", ReasoningEffort: next.CurrentReasoningEffort}
	}
	currentHealthy := true
	if item, ok := health[current.Name]; ok {
		currentHealthy = item.Score >= 0.5
	}
	currentCapable := true
	if !modelFitsContext(classification, *current) {
		// Capacity is a hard boundary, including when the fitting model is a
		// lower tier; never keep an oversized request solely due to stickiness.
		next.CurrentModel, next.CurrentTier, next.CurrentReasoningEffort = best.Name, best.Tier, effort
		next.LastSwitchTurn, next.LastActivityAt = turn, now
		return RouteDecision{State: next, SelectedModel: best, Action: "switch", Switched: true, Reason: "context_capacity_switch", ReasoningEffort: effort}
	}
	for _, required := range classification.RequiredCapabilities {
		found := false
		for _, available := range current.Capabilities {
			if required == available {
				found = true
				break
			}
		}
		if !found {
			currentCapable = false
			break
		}
	}
	cooldownElapsed := turn-next.LastSwitchTurn >= next.UpgradeCooldownTurns
	if classification.Source == semanticPolicyVersion && classification.Assessment != nil &&
		(current.Tier < taskModelFloor(classification) || !modelSupportsReasoningEffort(*current, effort)) {
		// A safety floor is not a soft preference. Apply it immediately at a
		// user boundary; pending provider tool rounds were handled above.
		cooldownElapsed = true
	}
	if classification.Source == semanticPolicyVersion && classification.Score >= 65 {
		cooldownElapsed = true
	}
	if best.Tier > current.Tier && (cooldownElapsed || hardCapabilityFailure || !currentCapable || !currentHealthy) {
		next.CurrentModel, next.CurrentTier, next.CurrentReasoningEffort, next.LastSwitchTurn, next.LastActivityAt = best.Name, best.Tier, effort, turn, now
		return RouteDecision{State: next, SelectedModel: best, Action: "upgrade", Switched: true, Reason: "quality_upgrade", ReasoningEffort: effort}
	}
	if best.Tier < current.Tier && routinePhaseDownshift(classification) {
		// A completed provider round may be followed by a simple information
		// phase of the same task. Do not carry the old task's cost and effort
		// forever. Capability, capacity and active tool/stream checks ran first.
		next.CurrentModel, next.CurrentTier, next.CurrentReasoningEffort = best.Name, best.Tier, effort
		next.LastSwitchTurn, next.LastActivityAt = turn, now
		return RouteDecision{State: next, SelectedModel: best, Action: "downgrade", Switched: true, Reason: "routine_phase_downshift", ReasoningEffort: effort}
	}
	if classification.Source == semanticPolicyVersion && classification.Assessment != nil && classification.Assessment.Continuation && effortRank(effort) < effortRank(next.CurrentReasoningEffort) {
		effort = next.CurrentReasoningEffort
	}
	next.CurrentReasoningEffort = effort
	next.LastActivityAt = now
	reason := "cooldown_or_same_tier"
	if best.Tier < current.Tier {
		reason = "sticky_quality_floor"
	}
	return RouteDecision{State: next, SelectedModel: current, Action: "keep", Reason: reason, ReasoningEffort: effort}
}

func fallbackModel(classification Classification, failedModel string, catalog []Model, health map[string]Health) *Model {
	candidates := FilterCapableModels(classification, healthyCatalog(catalog, health))
	filtered := make([]Model, 0, len(candidates))
	for _, candidate := range candidates {
		if candidate.Name != failedModel {
			filtered = append(filtered, candidate)
		}
	}
	if len(filtered) == 0 {
		return nil
	}
	healthScores := make(map[string]float64, len(health))
	for name, item := range health {
		healthScores[name] = item.Score
	}
	ranked := RankModels(classification, filtered, healthScores)
	if len(ranked) == 0 {
		return nil
	}
	return &ranked[0]
}

func EndToolLoop(state RouteState) RouteState { state.ToolLoopLocked = false; return state }

func effortRank(e ReasoningEffort) int {
	for i, v := range []ReasoningEffort{ReasoningNone, ReasoningMinimal, ReasoningLow, ReasoningMedium, ReasoningHigh, ReasoningXHigh, ReasoningMax} {
		if e == v {
			return i
		}
	}
	return 0
}

func healthyCatalog(catalog []Model, health map[string]Health) []Model {
	result := make([]Model, 0, len(catalog))
	for _, model := range catalog {
		if !health[model.Name].Unavailable {
			result = append(result, model)
		}
	}
	return result
}
