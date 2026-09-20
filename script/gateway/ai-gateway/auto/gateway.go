package autogateway

import (
	"errors"
	"strings"
	"time"
)

var ErrModelNotFound = errors.New("model_not_found")

type AutoGateway struct {
	PublicModel string
	Catalog     []Model
	Health      map[string]Health
	State       RouteState
}

func NewAutoGateway() *AutoGateway {
	return &AutoGateway{PublicModel: "auto", Catalog: append([]Model(nil), DefaultCatalog...), Health: map[string]Health{}, State: NewRouteState()}
}

func (gateway *AutoGateway) ValidatePublicModel(model string) error {
	model = strings.TrimSpace(model)
	// Migrated clients can retain a concrete model on existing threads,
	// compaction and child agents. These are aliases into Auto, never pins.
	if model == "" || model == gateway.PublicModel || isClaudeCodeAlias(model) || ModelByName(model, gateway.Catalog) != nil {
		return nil
	}
	return ErrModelNotFound
}

func (gateway *AutoGateway) Route(request Request, turn int, now time.Time, newTaskEpoch, toolLoop, hardCapabilityFailure bool) (RouteDecision, Classification, error) {
	return gateway.route(request, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure, false)
}

func (gateway *AutoGateway) RouteAtTurnBoundary(request Request, turn int, now time.Time, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool) (RouteDecision, Classification, error) {
	return gateway.route(request, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive)
}

func (gateway *AutoGateway) RouteWithState(state RouteState, request Request, turn int, now time.Time, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool) (RouteDecision, Classification, error) {
	classification := ExtractFeatures(request)
	decision := DecideRouteAtTurnBoundary(state, classification, gateway.Catalog, gateway.Health, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive)
	return decision, classification, nil
}

func (gateway *AutoGateway) route(request Request, turn int, now time.Time, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool) (RouteDecision, Classification, error) {
	decision, classification, err := gateway.RouteWithState(gateway.State, request, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive)
	gateway.State = decision.State
	return decision, classification, err
}
