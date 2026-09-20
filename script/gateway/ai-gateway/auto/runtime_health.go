package autogateway

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Circuits are scoped to the actual regional Key and protocol: a throttled or
// unhealthy account must not poison routing for another customer's account.
type healthKey struct{ Region, Key, Protocol, Model string }
type healthSample struct {
	Failures, Attempts, Successes int
	OpenUntil, Updated            time.Time
	Probing                       bool
	Latency                       time.Duration
}
type RuntimeHealth struct {
	mu       sync.Mutex
	entries  map[healthKey]*healthSample
	Now      func() time.Time
	Cooldown time.Duration
}

func (h *RuntimeHealth) now() time.Time {
	if h.Now != nil {
		return h.Now()
	}
	return time.Now()
}
func runtimeHealthKey(meta PipelineMeta, protocol, model string) healthKey {
	return healthKey{meta.Region, meta.APIKeyID, canonicalProtocol(protocol), model}
}
func (h *RuntimeHealth) entry(key healthKey) *healthSample {
	if h.entries == nil {
		h.entries = make(map[healthKey]*healthSample)
	}
	if e := h.entries[key]; e != nil {
		return e
	}
	if len(h.entries) >= 4096 {
		var oldest healthKey
		var at time.Time
		for k, e := range h.entries {
			if !e.Probing && (at.IsZero() || e.Updated.Before(at)) {
				oldest, at = k, e.Updated
			}
		}
		if !at.IsZero() {
			delete(h.entries, oldest)
		} else {
			return nil
		}
	}
	e := &healthSample{Updated: h.now()}
	h.entries[key] = e
	return e
}
func (h *RuntimeHealth) Snapshot(meta PipelineMeta, protocol string, base map[string]Health) map[string]Health {
	out := make(map[string]Health, len(base))
	for k, v := range base {
		out[k] = v
	}
	if h == nil {
		return out
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	now := h.now()
	for key, e := range h.entries {
		if key.Region != meta.Region || key.Key != meta.APIKeyID || key.Protocol != canonicalProtocol(protocol) {
			continue
		}
		if e.Probing || now.Before(e.OpenUntil) {
			out[key.Model] = Health{Score: 0, Unavailable: true}
		}
	}
	return out
}

// Acquire admits one real request after cooldown; no background request uses
// someone else's credentials or consumes their tokens to probe recovery.
func (h *RuntimeHealth) Acquire(meta PipelineMeta, protocol, model string) bool {
	if h == nil {
		return true
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	e := h.entry(runtimeHealthKey(meta, protocol, model))
	if e == nil || e.Probing || h.now().Before(e.OpenUntil) {
		return false
	}
	if !e.OpenUntil.IsZero() {
		e.Probing = true
	}
	e.Updated = h.now()
	return true
}
func transientProviderStatus(status int) bool {
	return status == 429 || status == 502 || status == 503 || status == 504
}
func (h *RuntimeHealth) Observe(meta PipelineMeta, protocol, model string, response UpstreamResponse, err error, elapsed time.Duration) {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	e := h.entry(runtimeHealthKey(meta, protocol, model))
	if e == nil {
		return
	}
	e.Probing = false
	e.Updated = h.now()
	// Cancellation and client write failures do not establish a supplier outage.
	// An interrupted recovery probe remains eligible for the next real request.
	if errors.Is(err, context.Canceled) || isClientDeliveryFailure(err) {
		return
	}
	e.Attempts++
	e.Latency = elapsed
	if err == nil && response.StatusCode >= 200 && response.StatusCode < 300 && response.Complete {
		e.Successes++
		e.Failures = 0
		e.OpenUntil = time.Time{}
		return
	}
	if transientProviderStatus(response.StatusCode) || response.StatusCode == 0 || (response.StatusCode >= 200 && response.StatusCode < 300 && err != nil) {
		e.Failures++
		if e.Failures >= 3 {
			cooldown := h.Cooldown
			if cooldown <= 0 {
				cooldown = 30 * time.Second
			}
			multiplier := e.Failures - 2
			if multiplier > 10 {
				multiplier = 10
			}
			e.OpenUntil = h.now().Add(time.Duration(multiplier) * cooldown)
		}
	} else {
		e.Failures = 0
		e.OpenUntil = time.Time{}
	}
}

func (p *Pipeline) routingHealth(meta PipelineMeta, protocol string) map[string]Health {
	return p.Health.Snapshot(meta, protocol, p.Gateway.Health)
}

// Only an explicit transient rejection without a successful generation is
// retried. Ambiguous transport timeouts, started streams, tool continuations,
// and authentication/permission failures are never replayed.
func (p *Pipeline) mayFailover(request Request, response UpstreamResponse, err error) bool {
	return p.Health != nil && err != nil && transientProviderStatus(response.StatusCode) && !response.Complete &&
		len(response.Usage) == 0 && len(response.ToolCallIDs) == 0 && !requestToolContinuation(request) && !nativeImageTool(request)
}

func (p *Pipeline) failover(meta PipelineMeta, protocol, requestedModel string, result *PipelineResult) error {
	if result.Decision.SelectedModel == nil || requestToolContinuation(result.PreparedRequest) {
		return errors.New("tool_provider_unavailable")
	}
	now := time.Now()
	if p.Now != nil {
		now = p.Now()
	}
	health := p.routingHealth(meta, protocol)
	health[result.Decision.SelectedModel.Name] = Health{Unavailable: true}
	decision := DecideRouteAtTurnBoundary(result.Decision.State, result.Classification, p.Gateway.Catalog, health,
		result.Decision.State.Turn, now, false, false, true, false)
	if decision.SelectedModel == nil {
		return errors.New("no_healthy_model")
	}
	p.mu.Lock()
	err := withStateTransaction(p.StateStore, now, func(store SessionStateStore) error {
		if store != nil && meta.SessionID != "" {
			current, err := loadSessionState(store, sessionStoreKey(meta), now)
			if err != nil {
				return err
			}
			if current.Turn != result.Decision.State.Turn || current.CurrentModel != result.Decision.State.CurrentModel {
				return errors.New("route_changed_during_failover")
			}
			return store.Save(sessionStoreKey(meta), decision.State, now)
		}
		p.Gateway.State = decision.State
		return nil
	})
	p.mu.Unlock()
	if err != nil {
		return errors.New("session_state_unavailable")
	}
	result.PreviousState = result.Decision.State
	result.Decision = decision
	result.CacheEligible = false
	result.CacheReason = "provider_failure_failover"
	result.CacheKey = ""
	result.Audit = BuildRouteAudit(now, requestedModel, decision.SelectedModel.Provider, protocol, result.PreparedRequest, decision, result.Classification)
	result.Audit.RequestID = meta.RequestID
	result.Audit.Region = meta.Region
	result.Audit.APIKeyID = meta.APIKeyID
	result.Audit.SessionHash = hashIdentifier(meta.SessionID)
	result.Audit.Stage = "route_decided"
	result.Audit.PreflightDecision = PreflightAllow
	if p.AuditSink != nil {
		if err := p.AuditSink.WriteRouteAudit(result.Audit); err != nil {
			return errors.New("audit_unavailable")
		}
	}
	return nil
}

func (h *RuntimeHealth) Release(meta PipelineMeta, protocol, model string) {
	if h == nil {
		return
	}
	h.mu.Lock()
	defer h.mu.Unlock()
	if e := h.entries[runtimeHealthKey(meta, protocol, model)]; e != nil {
		e.Probing = false
	}
}
