package autogateway

import (
	"context"
	"errors"
	"time"
)

// A request gets at most two provider attempts. All payloads come from the
// already checked, sanitized request; classification and Guard are not skipped
// or rewritten on failover. Each actual attempt has separate usage and audit.
func (p *Pipeline) callWithFailover(ctx context.Context, protocol, requestedModel string, meta PipelineMeta, result *PipelineResult, stream bool, call func(UpstreamRequest) (UpstreamResponse, error)) (UpstreamResponse, error) {
	for attempt := 0; attempt < 2; attempt++ {
		if ctx.Err() != nil {
			return UpstreamResponse{}, ctx.Err()
		}
		model := result.Decision.SelectedModel
		if !p.Health.Acquire(meta, protocol, model.Name) {
			if attempt == 0 {
				if err := p.failover(meta, protocol, requestedModel, result); err == nil {
					continue
				}
			}
			return UpstreamResponse{}, errors.New("no_healthy_model")
		}
		parameters := BuildProviderParameters(model.Provider, protocol, *model, result.Decision.ReasoningEffort, stream)
		payload, err := BuildProviderPayload(protocol, result.PreparedRequest, parameters)
		if err != nil {
			p.Health.Release(meta, protocol, model.Name)
			return UpstreamResponse{}, errors.New("provider_payload_invalid")
		}
		if err = p.startAudit(meta, *result); err != nil {
			p.Health.Release(meta, protocol, model.Name)
			return UpstreamResponse{}, err
		}
		result.UpstreamCalled = true
		started := time.Now()
		response, err := call(UpstreamRequest{RequestID: meta.RequestID, Protocol: protocol, Provider: model.Provider, Model: *model, Parameters: parameters, Payload: payload, Request: result.PreparedRequest, Headers: meta.ClientHeaders})
		if !stream || err != nil || response.StatusCode < 200 || response.StatusCode >= 300 {
			p.Health.Observe(meta, protocol, model.Name, response, err, time.Since(started))
		}
		result.Upstream = response
		if attempt == 0 && ctx.Err() == nil && p.mayFailover(result.PreparedRequest, response, err) {
			previous := *result
			if switchErr := p.failover(meta, protocol, requestedModel, result); switchErr == nil {
				p.finishAudit(meta, previous, err)
				p.recordUsage(time.Now(), meta, previous.Decision, previous.PreviousState, response.Usage, true, false, false, response)
				result.Upstream = UpstreamResponse{}
				result.UpstreamCalled = false
				continue
			}
		}
		return response, err
	}
	return UpstreamResponse{}, errors.New("no_healthy_model")
}
