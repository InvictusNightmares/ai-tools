package autogateway

import "time"

// DecideRouteAtTurnBoundary is the only route entry point that a streaming
// or WebSocket adapter should use after a turn has started. While a response
// is in flight, the adapter passes streamActive=true and the current model is
// kept. A new model may be selected only after the adapter marks the turn
// complete and calls this function again with streamActive=false.
func DecideRouteAtTurnBoundary(state RouteState, classification Classification, catalog []Model, health map[string]Health, turn int, now time.Time, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool) RouteDecision {
	if streamActive && state.HasCurrent {
		current := ModelByName(state.CurrentModel, catalog)
		if current != nil {
			state.LastActivityAt = now
			return RouteDecision{
				State: state, SelectedModel: current, Action: "keep", Reason: "stream_in_flight",
				ReasoningEffort: state.CurrentReasoningEffort,
			}
		}
	}
	return DecideRoute(state, classification, catalog, health, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure)
}
