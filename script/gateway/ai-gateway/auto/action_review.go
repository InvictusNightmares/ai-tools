package autogateway

import (
	"encoding/json"
	"errors"
	"net/http"
	"time"
)

const ActionReviewModel = "codex-auto-review"

// Codex owns the action-review policy, transcript, tool permissions and output
// schema. This specialized request must retain that contract and exact model;
// routing it to a general chat model would silently change the approval agent.
func (s *HTTPServer) handleActionReview(w http.ResponseWriter, r *http.Request, request Request, meta PipelineMeta) {
	preflight, err := evaluatePreflight(r.Context(), s.Pipeline.Preflight, request, meta)
	if err != nil || preflight.Decision != PreflightAllow {
		status, code := 503, "preflight_unavailable"
		if preflight.Decision == PreflightBlock {
			status, code = 403, "preflight_blocked"
		}
		s.Pipeline.writePreflightAudit(meta, ActionReviewModel, request, preflight, code)
		writeJSON(w, status, map[string]string{"error": code})
		return
	}
	if preflight.SanitizedRequest != nil {
		request = *preflight.SanitizedRequest
	}
	effort := nativeActionReviewEffort(request.RawPayload)
	model := Model{Name: ActionReviewModel, Provider: "openai"}
	result := PipelineResult{Preflight: preflight, Decision: RouteDecision{SelectedModel: &model}, Audit: RouteAudit{
		At: time.Now(), RequestID: meta.RequestID, Region: meta.Region, APIKeyID: meta.APIKeyID,
		SessionHash: hashIdentifier(meta.SessionID), RequestedModel: ActionReviewModel, EffectiveModel: ActionReviewModel,
		Action: "action_review", Reason: "native_action_review_contract", PreflightDecision: PreflightAllow,
		EffectiveReasoning: effort.Applied, EffortRequested: effort.Requested, EffortApplied: effort.Applied, EffortStatus: effort.Status, EffortParameter: effort.Parameter,
		Stream: request.Stream, Stage: "route_decided",
	}}
	if err = s.Pipeline.startAudit(meta, result); err != nil {
		writeJSON(w, 503, map[string]string{"error": "audit_unavailable"})
		return
	}
	upstream := UpstreamRequest{RequestID: meta.RequestID, Protocol: "responses", Provider: "openai", Model: model,
		Parameters: ProviderParameters{Model: ActionReviewModel, Stream: request.Stream, Reasoning: effort}, Payload: request.RawPayload, Request: request, Headers: meta.ClientHeaders}
	result.UpstreamCalled = true
	defer func() {
		s.Pipeline.finishAudit(meta, result, err)
		u := NormalizeUsage(result.Upstream.Usage)
		event := UsageEvent{UsageReported: u.HasPromptTokens, At: time.Now(), Purpose: "action_review", Region: meta.Region, APIKeyID: meta.APIKeyID, RequestID: meta.RequestID,
			EffectiveModel: ActionReviewModel, ReasoningEffort: effort.Applied, RequestedEffort: effort.Requested, EffortStatus: effort.Status, ReportedEffort: result.Upstream.ReportedEffort, EffortMismatch: effort.Applied != "" && result.Upstream.ReportedEffort != "" && effort.Applied != result.Upstream.ReportedEffort, ResponseModel: result.Upstream.ResponseModel, ResponseID: result.Upstream.ResponseID,
			UpstreamRequestID: result.Upstream.RequestID, UpstreamClientRequestID: result.Upstream.ClientRequestID, Attempt: true, Success: err == nil && result.Upstream.Complete,
			HTTPStatus: result.Upstream.StatusCode, InputTokens: u.PromptTokens, OutputTokens: u.CompletionTokens, CacheHitTokens: u.CacheHitTokens, CacheMissTokens: u.CacheMissTokens}
		if s.Pipeline.Usage != nil {
			s.Pipeline.Usage.Record(event)
		}
		if s.Pipeline.UsageSink != nil {
			if e := s.Pipeline.UsageSink.WriteUsageEvent(event); e != nil {
				s.Pipeline.persistAudit(RouteAudit{At: time.Now(), RequestID: meta.RequestID, Stage: "usage_persist_failed", ErrorType: "usage_persist_failed", Region: meta.Region, APIKeyID: meta.APIKeyID})
			}
		}
	}()
	if request.Stream {
		if s.StreamClient == nil {
			err = errors.New("upstream_stream_unavailable")
			writeJSON(w, 503, map[string]string{"error": err.Error()})
			return
		}
		var response *http.Response
		response, err = s.StreamClient.OpenStream(r.Context(), upstream)
		if err != nil {
			writeJSON(w, 502, map[string]string{"error": "upstream_stream_unavailable"})
			return
		}
		result.Upstream = UpstreamResponse{Transport: "sse_relay", StatusCode: response.StatusCode, RequestID: response.Header.Get("X-Request-ID"), ClientRequestID: response.Header.Get("X-Client-Request-ID"), ContentType: response.Header.Get("Content-Type")}
		if response.StatusCode < 200 || response.StatusCode >= 300 {
			response.Body.Close()
			err = errors.New("action_review_upstream_error")
			writeJSON(w, response.StatusCode, map[string]string{"error": err.Error()})
			return
		}
		observed := &observedSSEBody{ReadCloser: response.Body}
		response.Body = observed
		err = RelaySSE(r.Context(), w, response)
		result.Upstream = UpstreamResponse{Transport: "sse_relay", StatusCode: response.StatusCode, RequestID: response.Header.Get("X-Request-ID"), ClientRequestID: response.Header.Get("X-Client-Request-ID"), ResponseID: observed.ID, ResponseModel: observed.Model, ReportedEffort: observed.ReportedEffort, Complete: observed.Complete && !observed.Invalid, Usage: observed.Usage}
		result.Upstream.StreamTermination, err = streamTermination(err, result.Upstream.Complete)
		if err == nil && !result.Upstream.Complete {
			err = errors.New("upstream_stream_incomplete")
		}
		return
	}
	if s.Pipeline.Upstream == nil {
		err = errors.New("upstream_unconfigured")
		writeJSON(w, 503, map[string]string{"error": err.Error()})
		return
	}
	result.Upstream, err = s.Pipeline.Upstream.Complete(r.Context(), upstream)
	if err != nil && result.Upstream.StatusCode < 400 {
		writeJSON(w, 502, map[string]string{"error": "action_review_upstream_error"})
		return
	}
	status := result.Upstream.StatusCode
	if status == 0 {
		status = 502
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, writeErr := w.Write(result.Upstream.Body)
	if writeErr != nil {
		err = writeErr
	}
}

// The native reviewer owns its effort contract; record its known value without
// routing, mapping, rewriting, or logging arbitrary client-provided strings.
func nativeActionReviewEffort(raw json.RawMessage) EffortMapping {
	var body struct {
		Reasoning struct {
			Effort ReasoningEffort `json:"effort"`
		} `json:"reasoning"`
	}
	if json.Unmarshal(raw, &body) != nil {
		return EffortMapping{}
	}
	switch body.Reasoning.Effort {
	case ReasoningNone, ReasoningMinimal, ReasoningLow, ReasoningMedium, ReasoningHigh, ReasoningXHigh, ReasoningMax:
		return EffortMapping{Requested: body.Reasoning.Effort, Applied: body.Reasoning.Effort, Status: EffortApplied, Parameter: "reasoning.effort"}
	default:
		return EffortMapping{}
	}
}
