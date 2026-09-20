package autogateway

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"time"
)

type TokenCounter interface {
	Count(context.Context, []byte, http.Header, string) (int, error)
}
type TokenCountResult struct {
	InputTokens    int
	Method         string
	UpstreamCalled bool
	UpstreamStatus int
}
type detailedTokenCounter interface {
	CountDetailed(context.Context, []byte, http.Header, string) (TokenCountResult, error)
}
type HTTPTokenCounter struct {
	// Explicit per-model policy; never infer support from arbitrary HTTP failures.
	EstimateModels map[string]bool
	URL            string
	Client         *http.Client
}

func (c *HTTPTokenCounter) Count(ctx context.Context, payload []byte, headers http.Header, id string) (int, error) {
	result, err := c.CountDetailed(ctx, payload, headers, id)
	return result.InputTokens, err
}

func (c *HTTPTokenCounter) CountDetailed(ctx context.Context, payload []byte, headers http.Header, id string) (TokenCountResult, error) {
	result := TokenCountResult{Method: "upstream_reported"}
	var envelope struct {
		Model string `json:"model"`
	}
	if json.Unmarshal(payload, &envelope) != nil {
		return result, errors.New("token_counter_invalid_payload")
	}
	if c.EstimateModels[envelope.Model] {
		// This is a conservative client-budget heuristic, NOT a tokenizer result
		// or a guaranteed bound on provider-internal framing. Never bill it as usage.
		return TokenCountResult{InputTokens: len(payload), Method: "utf8_bytes_estimate"}, nil
	}
	if c.URL == "" {
		return result, errors.New("token_counter_unconfigured")
	}
	r, err := http.NewRequestWithContext(ctx, "POST", c.URL, bytes.NewReader(payload))
	if err != nil {
		return result, errors.New("token_counter_unconfigured")
	}
	copyAuthHeaders(r.Header, headers)
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("X-Request-ID", id)
	if r.Header.Get("anthropic-version") == "" {
		r.Header.Set("anthropic-version", "2023-06-01")
	}
	client := c.Client
	if client == nil {
		client = &http.Client{Timeout: 15 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	}
	result.UpstreamCalled = true
	resp, err := client.Do(r)
	if err != nil {
		return result, errors.New("token_counter_unavailable")
	}
	defer resp.Body.Close()
	result.UpstreamStatus = resp.StatusCode
	if resp.StatusCode != 200 {
		return result, errors.New("token_counter_unavailable")
	}
	b, err := io.ReadAll(io.LimitReader(resp.Body, (1<<20)+1))
	if err != nil || len(b) > 1<<20 {
		return result, errors.New("token_counter_invalid_response")
	}
	var out struct {
		InputTokens *int            `json:"input_tokens"`
		Error       json.RawMessage `json:"error"`
	}
	if json.Unmarshal(b, &out) != nil || out.InputTokens == nil || *out.InputTokens < 0 || (len(out.Error) > 0 && string(out.Error) != "null") {
		return result, errors.New("token_counter_invalid_response")
	}
	result.InputTokens = *out.InputTokens
	return result, nil
}

// Count for the model selected from this exact task and current route state,
// without advancing the conversation, starting a generation, or caching an answer.
func (s *HTTPServer) handleTokenCount(w http.ResponseWriter, r *http.Request) {
	fail := func(status int, code string) {
		writeJSON(w, status, map[string]any{"type": "error", "error": map[string]string{"type": "api_error", "message": code}})
	}
	if s.Pipeline == nil || s.TokenCounter == nil || s.Pipeline.Preflight == nil {
		fail(503, "token_counter_unavailable")
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(w, r.Body, MaxNativeRequestBytes))
	if err != nil {
		fail(413, "request_too_large")
		return
	}
	var envelope struct {
		Model string `json:"model"`
	}
	if json.Unmarshal(body, &envelope) != nil || s.Gateway.ValidatePublicModel(envelope.Model) != nil {
		fail(400, "invalid_model_or_json")
		return
	}
	body, err = s.Files.Expand(r.Header.Get("X-Gateway-API-Key-ID"), body)
	if err != nil {
		fail(400, err.Error())
		return
	}
	request, err := NormalizeProtocolRequest("anthropic", body)
	if err != nil {
		fail(400, "invalid_request")
		return
	}
	meta := withRequestID(s.Meta)
	meta.ClientHeaders = r.Header
	if meta.Region == "" {
		meta.Region = s.Pipeline.Meta.Region
	}
	meta.APIKeyID = r.Header.Get("X-Gateway-API-Key-ID")
	if meta.APIKeyID == "" {
		meta.APIKeyID = s.Meta.APIKeyID
	}
	if meta.SessionID == "" {
		meta.SessionID, _ = clientSessionID(r.Header, "anthropic", body)
	}
	w.Header().Set("X-Gateway-Request-ID", meta.RequestID)
	preflight, err := evaluatePreflight(r.Context(), s.Pipeline.Preflight, request, meta)
	if err != nil || preflight.Decision != PreflightAllow {
		stage, status := "preflight_unavailable", 503
		if err == nil && preflight.Decision == PreflightBlock {
			stage, status = "preflight_blocked", 403
		}
		s.Pipeline.writePreflightAudit(meta, envelope.Model, request, preflight, stage)
		fail(status, stage)
		return
	}
	if preflight.SanitizedRequest != nil {
		request = *preflight.SanitizedRequest
	}
	classification, err := s.Pipeline.classify(r.Context(), "anthropic", request, meta)
	if err != nil {
		s.Pipeline.writeClassifierFailure(meta)
		fail(503, "classifier_unavailable")
		return
	}
	s.Pipeline.mu.Lock()
	state := s.Gateway.State
	if s.Pipeline.StateStore != nil && meta.SessionID != "" {
		state, err = loadSessionState(s.Pipeline.StateStore, sessionStoreKey(meta), time.Now())
	} else if meta.SessionID == "" {
		state = NewRouteState()
	}
	s.Pipeline.mu.Unlock()
	if err != nil {
		s.Pipeline.writeRoutingFailure(meta, envelope.Model, "session_state_unavailable")
		fail(503, "session_state_unavailable")
		return
	}
	if s.Pipeline.Classifier != nil {
		binding, bindingErr := s.Pipeline.toolRoundState(request, "anthropic", meta, time.Now())
		if bindingErr != nil {
			s.Pipeline.writeRoutingFailure(meta, envelope.Model, bindingErr.Error())
			fail(503, "tool_context_unavailable")
			return
		}
		if binding != nil {
			state = *binding
		}
	}
	newTask := classification.Assessment != nil && classification.Assessment.NewTask
	if !requestToolContinuation(request) {
		state = EndToolLoop(state)
	}
	decision := DecideRouteAtTurnBoundary(state, classification, s.Gateway.Catalog, s.Pipeline.routingHealth(meta, "anthropic"), 0, time.Now(), newTask, requestToolContinuation(request), false, false)
	if decision.SelectedModel == nil {
		s.Pipeline.writeRoutingFailure(meta, envelope.Model, decision.Reason)
		fail(503, "no_capable_model")
		return
	}
	parameters := BuildProviderParameters(decision.SelectedModel.Provider, "anthropic", *decision.SelectedModel, decision.ReasoningEffort, false)
	payload, err := BuildProviderPayload("anthropic", request, parameters)
	if err != nil {
		fail(400, "invalid_provider_payload")
		return
	}
	audit := BuildRouteAudit(time.Now(), envelope.Model, decision.SelectedModel.Provider, "anthropic", request, decision, classification)
	audit.RequestID, audit.Region, audit.APIKeyID, audit.SessionHash, audit.Stage = meta.RequestID, meta.Region, meta.APIKeyID, hashIdentifier(meta.SessionID), "token_count_started"
	audit.ClassifierVersion = classification.Source
	audit.PreflightDecision = preflight.Decision
	audit.PreflightReasonCodes = append([]string(nil), preflight.ReasonCodes...)
	if s.Pipeline.AuditSink != nil && s.Pipeline.AuditSink.WriteRouteAudit(audit) != nil {
		fail(503, "audit_unavailable")
		return
	}
	countResult := TokenCountResult{Method: "upstream_reported", UpstreamCalled: true}
	if counter, ok := s.TokenCounter.(detailedTokenCounter); ok {
		countResult, err = counter.CountDetailed(r.Context(), payload, r.Header, meta.RequestID)
	} else {
		countResult.InputTokens, err = s.TokenCounter.Count(r.Context(), payload, r.Header, meta.RequestID)
	}
	count := countResult.InputTokens
	audit.TokenCountMethod, audit.CountedInputTokens = countResult.Method, count
	audit.UpstreamHTTPStatus = countResult.UpstreamStatus
	audit.At = time.Now()
	audit.UpstreamCalled = countResult.UpstreamCalled
	audit.Stage = "token_count_completed"
	if err != nil {
		audit.Stage = "token_count_failed"
		audit.ErrorType = "token_counter_unavailable"
	} else {
		// Count method distinguishes upstream reporting from the explicit local estimate.
		audit.HTTPStatus = http.StatusOK
		audit.ResponseComplete = true
	}
	s.Pipeline.persistAudit(audit)
	if err != nil {
		fail(503, "token_counter_unavailable")
		return
	}
	w.Header().Set("X-Gateway-Count-Model", decision.SelectedModel.Name)
	w.Header().Set("X-Gateway-Count-Method", countResult.Method)
	writeJSON(w, 200, map[string]int{"input_tokens": count})
}
