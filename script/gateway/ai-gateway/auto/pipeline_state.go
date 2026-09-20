package autogateway

import (
	"errors"
	"time"
)

func (p *Pipeline) decideWithState(request Request, protocol string, meta PipelineMeta, classification *Classification, turn int, now time.Time, newTask, toolLoop, hardFailure, streamActive bool) (RouteDecision, RouteState, error) {
	p.mu.Lock()
	defer p.mu.Unlock()
	previous := p.Gateway.State
	var decision RouteDecision
	err := withStateTransaction(p.StateStore, now, func(store SessionStateStore) error {
		if store != nil && meta.SessionID != "" {
			var err error
			previous, err = loadSessionState(store, sessionStoreKey(meta), now)
			if err != nil {
				return errors.New("session_state_unavailable")
			}
		}
		if p.Classifier != nil {
			bound, err := toolRoundState(store, request, protocol, meta, now)
			if err != nil {
				return err
			}
			if bound != nil {
				previous = *bound
			} else if clientLocalToolPair(request, meta) {
				toolLoop = false
				if canonicalProtocol(protocol) == "responses" {
					// A user-invoked local call has no provider reasoning to replay.
					// DeepSeek currently rejects this Responses shape, even at none.
					// Keep the native history intact and select a compatible model.
					// Clone first: the classifier may have returned cached slices.
					classification.RequiredCapabilities = append(append([]Capability(nil), classification.RequiredCapabilities...), CapabilityLocalToolHistory)
				}
			}
			if !toolLoop {
				previous = EndToolLoop(previous)
			}
		}
		decision = DecideRouteAtTurnBoundary(previous, *classification, p.Gateway.Catalog, p.routingHealth(meta, protocol), turn, now, newTask, toolLoop, hardFailure, streamActive)
		if store != nil && meta.SessionID != "" {
			if err := store.Save(sessionStoreKey(meta), decision.State, now); err != nil {
				return errors.New("session_state_unavailable")
			}
		} else {
			p.Gateway.State = decision.State
		}
		return nil
	})
	if err != nil && err.Error() != "tool_context_unavailable" && err.Error() != "tool_round_mismatch" {
		err = errors.New("session_state_unavailable")
	}
	return decision, previous, err
}
