package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"
)

type UpstreamRequest struct {
	RequestID  string
	Protocol   string
	Provider   string
	Model      Model
	Parameters ProviderParameters
	Payload    []byte
	Request    Request
	Headers    http.Header
}

type UpstreamResponse struct {
	ClientRequestID   string
	StreamTermination string
	Transport         string
	ToolCallIDs       []string
	ReportedEffort    ReasoningEffort
	ResponseModel     string
	ResponseID        string
	RequestID         string
	ContentType       string
	Complete          bool
	StatusCode        int
	Body              []byte
	ResponseBytes     int
	Usage             map[string]any
}

type UpstreamClient interface {
	Complete(context.Context, UpstreamRequest) (UpstreamResponse, error)
}

type PipelineResult struct {
	PreparedRequest Request `json:"-"`
	PreviousState   RouteState
	Preflight       PreflightResult
	Decision        RouteDecision
	Classification  Classification
	Audit           RouteAudit
	CacheEligible   bool
	CacheReason     string
	CacheKey        string
	CacheHit        bool
	UpstreamCalled  bool
	Upstream        UpstreamResponse
}

// Pipeline is the local phase-D seam. It models the final ordering without
// sending requests to a real provider; production authentication, cache
// storage and network clients are wired only after this seam passes review.
type Pipeline struct {
	Health      *RuntimeHealth
	Classifier  TaskClassifier
	Gateway     *AutoGateway
	Preflight   PreflightChecker
	Upstream    UpstreamClient
	CachePolicy ResponseCachePolicy
	Cache       ResponseCache
	Usage       *DailyUsageRecorder
	UsageSink   UsageEventSink
	AuditSink   AuditSink
	Meta        PipelineMeta
	StateStore  SessionStateStore
	Now         func() time.Time
	mu          sync.Mutex
	inflightMu  sync.Mutex
	inflight    map[string]*inflightUpstream
}

type inflightUpstream struct {
	done     chan struct{}
	response UpstreamResponse
	err      error
}

// Plan performs the fixed preflight and turn-boundary route without invoking
// an upstream. Streaming adapters use it to select a model before opening a
// long-lived SSE/WebSocket transport.
func (pipeline *Pipeline) Plan(ctx context.Context, protocol, provider, requestedModel string, request Request, turn int, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool, meta PipelineMeta) (PipelineResult, error) {
	meta = withRequestID(meta)
	if pipeline.Gateway == nil {
		return PipelineResult{}, errors.New("gateway_unavailable")
	}
	if err := pipeline.Gateway.ValidatePublicModel(requestedModel); err != nil {
		return PipelineResult{}, err
	}
	preflight, err := evaluatePreflight(ctx, pipeline.Preflight, request, meta)
	result := PipelineResult{Preflight: preflight}
	if err != nil || preflight.Decision == PreflightUnavailable {
		result.Preflight.Decision = PreflightUnavailable
		pipeline.writePreflightAudit(meta, requestedModel, request, result.Preflight, "preflight_unavailable")
		return result, errors.New("preflight_unavailable")
	}
	if preflight.Decision == PreflightBlock {
		pipeline.writePreflightAudit(meta, requestedModel, request, preflight, "preflight_blocked")
		return result, nil
	}
	if preflight.Decision != PreflightAllow {
		result.Preflight = PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"invalid_preflight_decision"}}
		pipeline.writePreflightAudit(meta, requestedModel, request, result.Preflight, "preflight_unavailable")
		return result, errors.New("preflight_unavailable")
	}
	if preflight.SanitizedRequest != nil {
		request = *preflight.SanitizedRequest
	}
	result.PreparedRequest = request
	classification, classErr := pipeline.classify(ctx, protocol, request, meta)
	if classErr != nil {
		pipeline.writeClassifierFailure(meta)
		return result, ErrClassifierUnavailable
	}
	if classification.Assessment != nil {
		newTaskEpoch = newTaskEpoch || classification.Assessment.NewTask
	}
	if pipeline.Classifier != nil {
		toolLoop = requestToolContinuation(request)
	}
	now := time.Now()
	if pipeline.Now != nil {
		now = pipeline.Now()
	}
	decision, previousState, routeErr := pipeline.decideWithState(request, protocol, meta, &classification, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive)
	if routeErr != nil {
		pipeline.writeRoutingFailure(meta, requestedModel, routeErr.Error())
		return result, routeErr
	}
	result.Decision, result.Classification, result.PreviousState = decision, classification, previousState
	if strings.TrimSpace(provider) == "" && decision.SelectedModel != nil {
		provider = decision.SelectedModel.Provider
	}
	result.Audit = BuildRouteAudit(now, requestedModel, provider, protocol, request, decision, classification)
	result.Audit.RequestID = meta.RequestID
	result.Audit.Region = meta.Region
	result.Audit.APIKeyID = meta.APIKeyID
	result.Audit.SessionHash = hashIdentifier(meta.SessionID)
	result.Audit.Stage = "route_decided"
	result.Audit.ClassifierVersion = classification.Source
	result.Audit.PreflightDecision = preflight.Decision
	result.Audit.PreflightReasonCodes = append([]string(nil), preflight.ReasonCodes...)
	if pipeline.AuditSink != nil {
		if auditErr := pipeline.AuditSink.WriteRouteAudit(result.Audit); auditErr != nil {
			return result, errors.New("audit_unavailable")
		}
	}
	if err != nil || decision.SelectedModel == nil {
		if decision.Reason != "" {
			return result, errors.New(decision.Reason)
		}
		return result, errors.New("no_capable_model")
	}
	return result, nil
}

func (pipeline *Pipeline) Execute(ctx context.Context, protocol, provider, requestedModel string, request Request, turn int, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool) (PipelineResult, error) {
	return pipeline.ExecuteWithMeta(ctx, protocol, provider, requestedModel, request, turn, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive, pipeline.Meta)
}

func (pipeline *Pipeline) ExecuteWithMeta(ctx context.Context, protocol, provider, requestedModel string, request Request, turn int, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive bool, meta PipelineMeta) (result PipelineResult, resultErr error) {
	meta = withRequestID(meta)
	defer func() { pipeline.finishAudit(meta, result, resultErr) }()
	if pipeline.Gateway == nil {
		return PipelineResult{}, errors.New("gateway_unavailable")
	}
	if err := pipeline.Gateway.ValidatePublicModel(requestedModel); err != nil {
		return PipelineResult{}, err
	}
	preflight, err := evaluatePreflight(ctx, pipeline.Preflight, request, meta)
	result = PipelineResult{Preflight: preflight}
	if err != nil || preflight.Decision == PreflightUnavailable {
		result.Preflight.Decision = PreflightUnavailable
		pipeline.writePreflightAudit(meta, requestedModel, request, result.Preflight, "preflight_unavailable")
		return result, errors.New("preflight_unavailable")
	}
	if preflight.Decision == PreflightBlock {
		pipeline.writePreflightAudit(meta, requestedModel, request, preflight, "preflight_blocked")
		return result, nil
	}
	if preflight.Decision != PreflightAllow {
		result.Preflight = PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"invalid_preflight_decision"}}
		pipeline.writePreflightAudit(meta, requestedModel, request, result.Preflight, "preflight_unavailable")
		return result, errors.New("preflight_unavailable")
	}
	if preflight.SanitizedRequest != nil {
		request = *preflight.SanitizedRequest
	}
	result.PreparedRequest = request
	classification, classErr := pipeline.classify(ctx, protocol, request, meta)
	if classErr != nil {
		pipeline.writeClassifierFailure(meta)
		return result, ErrClassifierUnavailable
	}
	if classification.Assessment != nil {
		newTaskEpoch = newTaskEpoch || classification.Assessment.NewTask
	}
	if pipeline.Classifier != nil {
		toolLoop = requestToolContinuation(request)
	}
	now := time.Now()
	if pipeline.Now != nil {
		now = pipeline.Now()
	}
	decision, previousState, routeErr := pipeline.decideWithState(request, protocol, meta, &classification, turn, now, newTaskEpoch, toolLoop, hardCapabilityFailure, streamActive)
	if routeErr != nil {
		pipeline.writeRoutingFailure(meta, requestedModel, routeErr.Error())
		return result, routeErr
	}
	result.Decision, result.Classification, result.PreviousState = decision, classification, previousState
	if strings.TrimSpace(provider) == "" && decision.SelectedModel != nil {
		provider = decision.SelectedModel.Provider
	}
	result.Audit = BuildRouteAudit(now, requestedModel, provider, protocol, request, decision, classification)
	result.Audit.RequestID = meta.RequestID
	result.Audit.Region = meta.Region
	result.Audit.APIKeyID = meta.APIKeyID
	result.Audit.SessionHash = hashIdentifier(meta.SessionID)
	result.Audit.Stage = "route_decided"
	result.Audit.ClassifierVersion = classification.Source
	result.Audit.PreflightDecision = preflight.Decision
	result.Audit.PreflightReasonCodes = append([]string(nil), preflight.ReasonCodes...)
	if pipeline.AuditSink != nil {
		if auditErr := pipeline.AuditSink.WriteRouteAudit(result.Audit); auditErr != nil {
			return result, errors.New("audit_unavailable")
		}
	}
	if decision.SelectedModel == nil {
		if decision.Reason != "" {
			return result, errors.New(decision.Reason)
		}
		return result, errors.New("no_capable_model")
	}
	result.CacheEligible, result.CacheReason = pipeline.CachePolicy.Eligible(request, preflight.Decision, 0)
	if result.CacheEligible && pipeline.Cache != nil {
		key, keyErr := BuildPipelineCacheKey(meta, provider, protocol, *decision.SelectedModel, decision.ReasoningEffort, request)
		if keyErr == nil {
			result.CacheKey = key
			if cached, hit := pipeline.Cache.Get(key, now); hit {
				result.CacheHit, result.Upstream = true, cached
				pipeline.recordUsage(now, meta, decision, previousState, nil, false, true, true, result.Upstream)
				return result, nil
			}
		} else {
			result.CacheEligible, result.CacheReason = false, keyErr.Error()
		}
	}
	if pipeline.Upstream == nil {
		return result, nil
	}
	// Coalescing is limited to the non-failover path: a waiter must not inherit
	// the original model identity after its leader changes provider. Regional
	// mode disables response caching entirely.
	// Coalesce concurrent misses for the same complete cache key. This keeps a
	// burst of identical requests from multiplying provider calls while still
	// allowing each caller to receive its own usage/audit accounting.
	var call *inflightUpstream
	leader := false
	if result.CacheKey != "" && result.CacheEligible && pipeline.Cache != nil && pipeline.Health == nil {
		pipeline.inflightMu.Lock()
		if pipeline.inflight == nil {
			pipeline.inflight = make(map[string]*inflightUpstream)
		}
		call = pipeline.inflight[result.CacheKey]
		if call == nil {
			call = &inflightUpstream{done: make(chan struct{})}
			pipeline.inflight[result.CacheKey] = call
			leader = true
		}
		pipeline.inflightMu.Unlock()
		if !leader {
			select {
			case <-call.done:
				result.Upstream = call.response
				result.UpstreamCalled = false
				pipeline.recordUsage(now, meta, decision, previousState, result.Upstream.Usage, false, call.err == nil && result.Upstream.StatusCode >= 200 && result.Upstream.StatusCode < 300, false)
				return result, call.err
			case <-ctx.Done():
				return result, ctx.Err()
			}
		}
	}
	if call != nil && leader {
		defer func() {
			call.response, call.err = result.Upstream, resultErr
			pipeline.inflightMu.Lock()
			delete(pipeline.inflight, result.CacheKey)
			close(call.done)
			pipeline.inflightMu.Unlock()
		}()
	}
	upstream, err := pipeline.callWithFailover(ctx, protocol, requestedModel, meta, &result, false, func(call UpstreamRequest) (UpstreamResponse, error) { return pipeline.Upstream.Complete(ctx, call) })
	if err == nil && upstream.StatusCode >= 200 && upstream.StatusCode < 300 && meta.compactResponse {
		upstream.Body, err = compactResponseBody(result.PreparedRequest, upstream)
		if err != nil {
			upstream.Complete = false
		}
	}
	result.Upstream = upstream
	decision, previousState = result.Decision, result.PreviousState
	parameters := BuildProviderParameters(decision.SelectedModel.Provider, protocol, *decision.SelectedModel, decision.ReasoningEffort, request.Stream)
	success := err == nil && upstream.StatusCode >= 200 && upstream.StatusCode < 300
	if success && upstream.Complete {
		if bindingErr := pipeline.saveToolRound(protocol, meta, result); bindingErr != nil {
			err, success = bindingErr, false
		}
	}
	if success {
		if len(upstream.ToolCallIDs) > 0 || len(responseToolCallIDs(protocol, upstream.Body)) > 0 {
			result.CacheEligible, result.CacheReason = false, "provider_tool_call_response"
		}
		responseBytes := upstream.ResponseBytes
		if len(upstream.Body) > responseBytes {
			responseBytes = len(upstream.Body)
		}
		if result.CacheEligible {
			result.CacheEligible, result.CacheReason = pipeline.CachePolicy.Eligible(request, preflight.Decision, responseBytes)
		}
		if upstream.ReportedEffort != "" && upstream.ReportedEffort != parameters.Reasoning.Applied {
			result.CacheEligible, result.CacheReason = false, "upstream_effort_mismatch"
		}
		if result.CacheEligible && pipeline.Cache != nil && result.CacheKey != "" {
			completedAt := time.Now()
			if pipeline.Now != nil {
				completedAt = pipeline.Now()
			}
			pipeline.Cache.Set(result.CacheKey, upstream, completedAt.Add(pipeline.CachePolicy.TTL))
		}
	} else {
		result.CacheEligible, result.CacheReason = false, "upstream_unsuccessful"
		if err == nil {
			err = errors.New("upstream_http_error")
		}
	}
	pipeline.recordUsage(now, meta, decision, previousState, upstream.Usage, result.UpstreamCalled, success, false, upstream)
	return result, err
}

func (pipeline *Pipeline) recordUsage(now time.Time, meta PipelineMeta, decision RouteDecision, previous RouteState, usage map[string]any, attempt, success, responseCacheHit bool, responses ...UpstreamResponse) {
	if decision.SelectedModel == nil {
		return
	}
	// Cached response metadata belongs to the original attempt. A replay adds
	// a request and a response-cache hit, never provider tokens or attempts.
	normalized := NormalizedUsage{}
	if attempt {
		normalized = NormalizeUsage(usage)
	}
	model := decision.SelectedModel
	switched := decision.Switched && previous.HasCurrent
	event := UsageEvent{UsageReported: normalized.HasPromptTokens, Purpose: "business", RequestID: meta.RequestID, At: now, Region: meta.Region, EffectiveModel: model.Name, ReasoningEffort: decision.ReasoningEffort, APIKeyID: meta.APIKeyID, Attempt: attempt, ResponseCacheHit: responseCacheHit, InputTokens: normalized.PromptTokens, CacheHitTokens: normalized.CacheHitTokens, CacheMissTokens: normalized.CacheMissTokens, OutputTokens: normalized.CompletionTokens, Success: success, Upgrade: switched && model.Tier > previous.CurrentTier, Downgrade: switched && model.Tier < previous.CurrentTier}
	mapping := MapReasoningEffort(model.Provider, "chat", decision.ReasoningEffort, model.ReasoningEfforts)
	event.RequestedEffort, event.ReasoningEffort, event.EffortStatus = mapping.Requested, mapping.Applied, mapping.Status
	if len(responses) > 0 {
		r := responses[0]
		event.ReportedEffort = r.ReportedEffort
		event.EffortMismatch = r.ReportedEffort != "" && r.ReportedEffort != event.ReasoningEffort
		event.HTTPStatus = r.StatusCode
		event.ResponseModel = r.ResponseModel
		event.ResponseID = r.ResponseID
		event.UpstreamRequestID = r.RequestID
		event.UpstreamClientRequestID = r.ClientRequestID
	}
	if pipeline.Usage != nil {
		pipeline.Usage.Record(event)
	}
	if pipeline.UsageSink != nil {
		if err := pipeline.UsageSink.WriteUsageEvent(event); err != nil {
			raw, _ := json.Marshal(event)
			log.Printf("usage_sink_failed event=%s", raw)
		}
	}
}

func (pipeline *Pipeline) writePreflightAudit(meta PipelineMeta, requestedModel string, request Request, preflight PreflightResult, action string) {
	if pipeline.AuditSink == nil {
		return
	}
	now := time.Now()
	if pipeline.Now != nil {
		now = pipeline.Now()
	}
	pipeline.persistAudit(RouteAudit{RequestID: meta.RequestID, Stage: action, Region: meta.Region, APIKeyID: meta.APIKeyID, SessionHash: hashIdentifier(meta.SessionID),
		At: now, RequestedModel: requestedModel, Action: action,
		Reason: strings.Join(preflight.ReasonCodes, ","), Stream: request.Stream,
		PreflightDecision:    preflight.Decision,
		PreflightReasonCodes: append([]string(nil), preflight.ReasonCodes...),
	})
}
