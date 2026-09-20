package autogateway

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/gorilla/websocket"
	"io"
	"net/http"
	"strings"
	"sync"
	"time"
)

// HTTPServer exposes the local route preview and the buffered completion seam.
// Production authentication, regional wiring and streaming handler ownership
// remain outside this module until the phase-D adapter is approved.
type HTTPServer struct {
	NativeAPI         *NativeAPI
	Files             *NativeFileStore
	Identity          IdentityResolver
	AllowRoutePreview bool
	Gateway           *AutoGateway
	Preflight         PreflightChecker
	Pipeline          *Pipeline
	StreamClient      StreamUpstreamClient
	TokenCounter      TokenCounter
	Meta              PipelineMeta
	Now               func() time.Time
	mu                sync.Mutex
}

type routeHTTPInput struct {
	Protocol              string          `json:"protocol"`
	Provider              string          `json:"provider"`
	Model                 string          `json:"model"`
	Body                  json.RawMessage `json:"body"`
	Request               *Request        `json:"request"`
	Turn                  int             `json:"turn"`
	NewTaskEpoch          bool            `json:"new_task_epoch"`
	ToolLoop              bool            `json:"tool_loop"`
	HardCapabilityFailure bool            `json:"hard_capability_failure"`
	StreamActive          bool            `json:"stream_active"`
	SessionID             string          `json:"session_id"`
	ReasoningEffort       string          `json:"reasoning_effort"`
}

type routeHTTPOutput struct {
	Object                   string            `json:"object"`
	RequestedModel           string            `json:"requested_model"`
	EffectiveModel           string            `json:"effective_model"`
	EffectiveReasoningEffort ReasoningEffort   `json:"effective_reasoning_effort"`
	Action                   string            `json:"action"`
	Switched                 bool              `json:"switched"`
	Reason                   string            `json:"reason"`
	Classification           Classification    `json:"classification"`
	UpstreamCalled           bool              `json:"upstream_called"`
	PreflightDecision        PreflightDecision `json:"preflight_decision"`
	PreflightReasonCodes     []string          `json:"preflight_reason_codes,omitempty"`
}

func (s *HTTPServer) ServeHTTP(response http.ResponseWriter, request *http.Request) {
	if s.Gateway == nil {
		writeJSON(response, http.StatusServiceUnavailable, map[string]string{"error": "gateway_unavailable"})
		return
	}
	if s.Identity != nil && request.URL.Path != "/healthz" {
		key, err := s.Identity.Resolve(request)
		if err != nil {
			status, code := 503, "identity_check_unavailable"
			if errors.Is(err, ErrUnauthorized) {
				status, code = 401, "unauthorized"
			}
			var failure *identityError
			if errors.As(err, &failure) {
				status, code = failure.status, failure.code
			}
			meta := withRequestID(PipelineMeta{Region: s.Meta.Region})
			response.Header().Set("X-Gateway-Request-ID", meta.RequestID)
			if s.Pipeline != nil {
				s.Pipeline.persistAudit(RouteAudit{At: time.Now(), RequestID: meta.RequestID, Region: meta.Region, Stage: "identity_rejected", HTTPStatus: status, ErrorType: code})
			}
			writeJSON(response, status, map[string]string{"error": code})
			return
		}
		// Replace all identity claims from the client, including a forged Key ID.
		request = request.Clone(request.Context())
		request.Header = request.Header.Clone()
		request.Header.Set("X-Gateway-API-Key-ID", key)
	}
	switch {
	case request.Method == http.MethodGet && request.URL.Path == "/healthz":
		writeJSON(response, http.StatusOK, map[string]string{"status": "ok"})
	case request.Method == http.MethodGet && request.URL.Path == "/v1/responses" && websocket.IsWebSocketUpgrade(request):
		s.handleResponsesWebSocket(response, request)
	case request.Method == http.MethodGet && request.URL.Path == "/v1/models":
		s.handleModels(response)
	case request.Method == http.MethodGet && request.URL.Path == "/metrics":
		s.handleMetrics(response)
	case request.Method == http.MethodPost && request.URL.Path == "/v1/route":
		if s.Identity != nil && !s.AllowRoutePreview {
			writeJSON(response, 404, map[string]string{"error": "not_found"})
			return
		}
		s.handleRoute(response, request)
	case request.Method == http.MethodPost && request.URL.Path == "/v1/messages/count_tokens":
		s.handleTokenCount(response, request)
	case isNativeAPIPath(request.URL.Path):
		if nativeFilePath.MatchString(request.URL.Path) && s.Files != nil {
			s.handleNativeFiles(response, request)
		} else {
			s.handleNativeAPI(response, request)
		}
	case request.Method == http.MethodPost && (request.URL.Path == "/v1/chat/completions" || request.URL.Path == "/v1/responses" || request.URL.Path == "/v1/responses/compact" || request.URL.Path == "/v1/messages"):
		s.handleCompletion(response, request)
	default:
		writeJSON(response, http.StatusNotFound, map[string]string{"error": "not_found"})
	}
}

func (s *HTTPServer) handleMetrics(response http.ResponseWriter) {
	response.Header().Set("Content-Type", "text/plain; version=0.0.4")
	if s.Pipeline == nil || s.Pipeline.Usage == nil {
		_, _ = response.Write([]byte("# HELP auto_gateway_usage_entries Number of usage buckets currently held.\n# TYPE auto_gateway_usage_entries gauge\nauto_gateway_usage_entries 0\n"))
		return
	}
	entries := s.Pipeline.Usage.Snapshot()
	requests, attempts, cacheHits, successes, failures := 0, 0, 0, 0, 0
	for _, entry := range entries {
		requests += entry.Requests
		attempts += entry.Attempts
		cacheHits += entry.ResponseCacheHits
		successes += entry.Successes
		failures += entry.Failures
	}
	response.WriteHeader(http.StatusOK)
	_, _ = fmt.Fprintf(response, "# TYPE auto_gateway_requests_total counter\nauto_gateway_requests_total %d\n# TYPE auto_gateway_attempts_total counter\nauto_gateway_attempts_total %d\n# TYPE auto_gateway_response_cache_hits_total counter\nauto_gateway_response_cache_hits_total %d\n# TYPE auto_gateway_successes_total counter\nauto_gateway_successes_total %d\n# TYPE auto_gateway_failures_total counter\nauto_gateway_failures_total %d\n", requests, attempts, cacheHits, successes, failures)
}

func (s *HTTPServer) handleCompletion(response http.ResponseWriter, request *http.Request) {
	if s.Pipeline == nil {
		writeJSON(response, http.StatusNotImplemented, map[string]string{"error": "pipeline_unconfigured"})
		return
	}
	body, err := io.ReadAll(http.MaxBytesReader(response, request.Body, MaxNativeRequestBytes))
	if err != nil {
		writeJSON(response, http.StatusRequestEntityTooLarge, map[string]string{"error": "request_too_large"})
		return
	}
	var envelope struct {
		Model string `json:"model"`
	}
	if err := json.Unmarshal(body, &envelope); err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": "invalid_json"})
		return
	}
	if envelope.Model == "" {
		envelope.Model = s.Gateway.PublicModel
	}
	protocol := "chat"
	compactEndpoint := request.URL.Path == "/v1/responses/compact"
	if request.URL.Path == "/v1/responses" || compactEndpoint {
		protocol = "responses"
	} else if request.URL.Path == "/v1/messages" {
		protocol = "anthropic"
	}
	if compactEndpoint {
		body, err = prepareCompactRequest(body)
		if err != nil {
			writeJSON(response, 400, map[string]string{"error": "invalid_compaction_request"})
			return
		}
	}
	body, err = s.Files.Expand(request.Header.Get("X-Gateway-API-Key-ID"), body)
	if err != nil {
		status, code := nativeFileError(err)
		writeJSON(response, status, map[string]string{"error": code})
		return
	}
	protocolRequest, err := NormalizeProtocolRequest(protocol, body)
	if err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": "invalid_request", "message": err.Error()})
		return
	}
	media, _, mediaErr := inspectNativeMedia(protocolRequest)
	if mediaErr != nil {
		writeJSON(response, 400, map[string]string{"error": mediaErr.Error()})
		return
	}
	if media.media.Audio > 0 {
		writeJSON(response, 400, map[string]any{"error": map[string]string{"type": "invalid_request_error", "code": "audio_not_supported", "message": "Audio input is not supported by this gateway."}})
		return
	}
	if len(media.parts) > 0 {
		response.Header().Set("X-Gateway-Guard-Scope", nativeGuardScope(&media.media))
	}
	meta := withRequestID(s.Meta)
	meta.compactResponse = compactEndpoint
	if meta.SessionID == "" {
		meta.SessionID, _ = clientSessionID(request.Header, protocol, body)
	}
	if meta.Region == "" {
		meta.Region = s.Pipeline.Meta.Region
	}
	if s.Identity != nil || meta.APIKeyID == "" {
		meta.APIKeyID = request.Header.Get("X-Gateway-API-Key-ID")
	}
	if meta.SessionID == "" {
		meta.SessionID = meta.RequestID
	}
	meta.ClientHeaders = request.Header
	response.Header().Set("X-Gateway-Request-ID", meta.RequestID)
	if warmup, _ := request.Context().Value(websocketWarmupKey{}).(bool); warmup && envelope.Model == ActionReviewModel && protocol == "responses" {
		s.handleWebSocketWarmup(response, request, protocolRequest, meta)
		return
	}
	if envelope.Model == ActionReviewModel && protocol == "responses" {
		s.handleActionReview(response, request, protocolRequest, meta)
		return
	}
	if err := s.Gateway.ValidatePublicModel(envelope.Model); err != nil {
		// Reject before Guard/classification and never reflect arbitrary model
		// input into logs or SDK errors; it may contain private request data.
		s.Pipeline.persistAudit(RouteAudit{At: time.Now(), RequestID: meta.RequestID,
			Region: meta.Region, APIKeyID: meta.APIKeyID, Stage: "request_rejected",
			Protocol: protocol, RequestOperation: requestOperation(protocolRequest), Stream: protocolRequest.Stream,
			SessionHash: hashIdentifier(meta.SessionID), RequestedModelHash: hashIdentifier(envelope.Model),
			HTTPStatus: http.StatusNotFound, ErrorType: "model_not_found"})
		errorType := "invalid_request_error"
		if protocol == "anthropic" {
			errorType = "not_found_error"
		}
		writeJSON(response, http.StatusNotFound, map[string]any{"type": "error", "error": map[string]string{
			"type": errorType, "code": "model_not_found", "param": "model",
			"message": "The requested model is not available. Use auto.",
		}})
		return
	}
	if warmup, _ := request.Context().Value(websocketWarmupKey{}).(bool); warmup {
		s.handleWebSocketWarmup(response, request, protocolRequest, meta)
		return
	}
	if protocolRequest.Stream && s.StreamClient != nil {
		result, planErr := s.Pipeline.Plan(request.Context(), protocol, "", envelope.Model, protocolRequest, 0, false, false, false, false, meta)
		if result.Preflight.Decision == PreflightBlock {
			writeJSON(response, http.StatusForbidden, map[string]any{"error": "preflight_blocked", "decision": "block", "reason_codes": result.Preflight.ReasonCodes})
			return
		}
		if planErr != nil {
			status := http.StatusBadGateway
			if planErr.Error() == "preflight_unavailable" || errors.Is(planErr, ErrClassifierUnavailable) || isRoutingUnavailable(planErr) {
				status = http.StatusServiceUnavailable
			}
			writeJSON(response, status, map[string]string{"error": planErr.Error()})
			return
		}
		protocolRequest = result.PreparedRequest
		var streamResponse *http.Response
		started := time.Now()
		_, streamErr := s.Pipeline.callWithFailover(request.Context(), protocol, envelope.Model, meta, &result, true, func(call UpstreamRequest) (UpstreamResponse, error) {
			var openErr error
			streamResponse, openErr = s.StreamClient.OpenStream(request.Context(), call)
			if openErr != nil {
				return UpstreamResponse{}, openErr
			}
			snapshot := UpstreamResponse{Transport: "sse_relay", StatusCode: streamResponse.StatusCode, RequestID: streamResponse.Header.Get("X-Request-ID"), ClientRequestID: streamResponse.Header.Get("X-Client-Request-ID"), ContentType: streamResponse.Header.Get("Content-Type")}
			if snapshot.StatusCode < 200 || snapshot.StatusCode >= 300 {
				streamResponse.Body.Close()
				return snapshot, errors.New("upstream_stream_invalid_response")
			}
			return snapshot, nil
		})
		if streamErr != nil {
			s.Pipeline.finishAudit(meta, result, streamErr)
			s.Pipeline.recordUsage(time.Now(), meta, result.Decision, result.PreviousState, nil, result.UpstreamCalled, false, false, result.Upstream)
			status := result.Upstream.StatusCode
			if status < 400 {
				status = 502
			}
			if isRoutingUnavailable(streamErr) {
				status = 503
			}
			writeJSON(response, status, map[string]string{"error": "upstream_stream_unavailable"})
			return
		}
		result.Upstream = UpstreamResponse{Transport: "sse_relay", StatusCode: streamResponse.StatusCode, RequestID: streamResponse.Header.Get("X-Request-ID"), ClientRequestID: streamResponse.Header.Get("X-Client-Request-ID"), ContentType: streamResponse.Header.Get("Content-Type")}
		if streamResponse.StatusCode < 200 || streamResponse.StatusCode >= 300 || !strings.Contains(strings.ToLower(streamResponse.Header.Get("Content-Type")), "text/event-stream") {
			streamResponse.Body.Close()
			failure := errors.New("upstream_stream_invalid_response")
			s.Pipeline.Health.Observe(meta, protocol, result.Decision.SelectedModel.Name, result.Upstream, failure, time.Since(started))
			s.Pipeline.finishAudit(meta, result, failure)
			s.Pipeline.recordUsage(time.Now(), meta, result.Decision, result.PreviousState, nil, true, false, false, result.Upstream)
			status := streamResponse.StatusCode
			if status >= 200 && status < 300 {
				status = 502
			}
			writeJSON(response, status, map[string]string{"error": "upstream_stream_invalid_response"})
			return
		}
		observed := &observedSSEBody{ReadCloser: streamResponse.Body}
		if nativeImageTool(protocolRequest) {
			observed.MaxEventBytes = 128 << 20
		}
		observed.BeforeComplete = func() error {
			if observed.ID == "" || observed.Model == "" {
				return errors.New("upstream_stream_incomplete")
			}
			completed := result
			completed.Upstream = UpstreamResponse{Complete: true, ToolCallIDs: observed.ToolCallIDs}
			return s.Pipeline.saveToolRound(protocol, meta, completed)
		}
		streamResponse.Body = observed
		relayErr := RelaySSE(request.Context(), response, streamResponse)
		result.Upstream = UpstreamResponse{Transport: "sse_relay", StatusCode: streamResponse.StatusCode, RequestID: streamResponse.Header.Get("X-Request-ID"), ClientRequestID: streamResponse.Header.Get("X-Client-Request-ID"), ResponseModel: observed.Model, ResponseID: observed.ID, Complete: observed.Complete && observed.ID != "" && observed.Model != "", Usage: observed.Usage}
		result.Upstream.ReportedEffort = observed.ReportedEffort
		result.Upstream.ToolCallIDs = observed.ToolCallIDs
		result.Upstream.StreamTermination, relayErr = streamTermination(relayErr, result.Upstream.Complete)
		if relayErr == nil && (streamResponse.StatusCode < 200 || streamResponse.StatusCode >= 300 || !result.Upstream.Complete) {
			relayErr = errors.New("upstream_stream_incomplete")
		}
		s.Pipeline.Health.Observe(meta, protocol, result.Decision.SelectedModel.Name, result.Upstream, relayErr, time.Since(started))
		s.Pipeline.finishAudit(meta, result, relayErr)
		s.Pipeline.recordUsage(time.Now(), meta, result.Decision, result.PreviousState, observed.Usage, true, relayErr == nil, false, result.Upstream)
		return
	}
	result, executeErr := s.Pipeline.ExecuteWithMeta(request.Context(), protocol, "", envelope.Model, protocolRequest, 0, false, false, false, protocolRequest.Stream, meta)
	if result.Preflight.Decision == PreflightBlock {
		writeJSON(response, http.StatusForbidden, map[string]any{"error": "preflight_blocked", "decision": "block", "reason_codes": result.Preflight.ReasonCodes})
		return
	}
	if executeErr != nil && (result.Upstream.StatusCode == 0 || result.Upstream.StatusCode >= 200 && result.Upstream.StatusCode < 300) {
		status := http.StatusBadGateway
		if executeErr.Error() == "preflight_unavailable" || errors.Is(executeErr, ErrClassifierUnavailable) || isRoutingUnavailable(executeErr) {
			status = http.StatusServiceUnavailable
		}
		writeJSON(response, status, map[string]string{"error": publicPipelineError(executeErr)})
		return
	}
	if result.Upstream.StatusCode > 0 {
		response.Header().Set("Content-Type", "application/json")
		response.WriteHeader(result.Upstream.StatusCode)
		_, _ = io.Copy(response, bytes.NewReader(result.Upstream.Body))
		return
	}
	writeJSON(response, http.StatusBadGateway, map[string]string{"error": "upstream_unconfigured"})
}

func (s *HTTPServer) handleModels(response http.ResponseWriter) {
	models := []map[string]any{{"id": s.Gateway.PublicModel, "object": "model", "owned_by": "auto-gateway"}}
	models = append(models, map[string]any{"id": ActionReviewModel, "object": "model", "owned_by": "openai"})
	writeJSON(response, http.StatusOK, map[string]any{"object": "list", "data": models, "models": codexModelDescriptors(s.Gateway.PublicModel)})
}

func (s *HTTPServer) handleRoute(response http.ResponseWriter, request *http.Request) {
	var input routeHTTPInput
	decoder := json.NewDecoder(http.MaxBytesReader(response, request.Body, 8<<20))
	if err := decoder.Decode(&input); err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": "invalid_json"})
		return
	}
	if input.Protocol == "" {
		input.Protocol = protocolFromHeader(request.Header.Get("X-Gateway-Protocol"))
	}
	if input.Provider == "" {
		input.Provider = "openai"
	}
	if err := s.Gateway.ValidatePublicModel(input.Model); err != nil {
		writeJSON(response, http.StatusNotFound, map[string]string{"error": ErrModelNotFound.Error()})
		return
	}
	protocolRequest, err := decodeRouteRequest(input)
	if err != nil {
		writeJSON(response, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}
	if s.Pipeline != nil {
		meta := withRequestID(s.Meta)
		meta.ClientHeaders = request.Header
		if meta.SessionID == "" {
			meta.SessionID = input.SessionID
		}
		result, planErr := s.Pipeline.Plan(request.Context(), input.Protocol, input.Provider, input.Model, protocolRequest, input.Turn, input.NewTaskEpoch, input.ToolLoop, input.HardCapabilityFailure, input.StreamActive, meta)
		if result.Preflight.Decision == PreflightBlock {
			writeJSON(response, 403, map[string]string{"error": "preflight_blocked"})
			return
		}
		if planErr != nil {
			writeJSON(response, 503, map[string]string{"error": publicPipelineError(planErr)})
			return
		}
		d := result.Decision
		writeJSON(response, 200, routeHTTPOutput{Object: "auto.route", RequestedModel: s.Gateway.PublicModel, EffectiveModel: d.SelectedModel.Name, EffectiveReasoningEffort: d.ReasoningEffort, Action: d.Action, Switched: d.Switched, Reason: d.Reason, Classification: result.Classification, PreflightDecision: result.Preflight.Decision})
		return
	}
	turn := input.Turn
	if turn == 0 {
		turn = 1
	}
	preflight := PreflightResult{Decision: PreflightAllow}
	if s.Preflight != nil {
		preflight, err = s.Preflight.Evaluate(request.Context(), protocolRequest)
		if err != nil || preflight.Decision == PreflightUnavailable {
			writeJSON(response, http.StatusServiceUnavailable, map[string]any{"error": "preflight_unavailable", "decision": PreflightUnavailable, "reason_codes": preflight.ReasonCodes})
			return
		}
		if preflight.Decision == PreflightBlock {
			writeJSON(response, http.StatusForbidden, map[string]any{"error": "preflight_blocked", "decision": PreflightBlock, "reason_codes": preflight.ReasonCodes})
			return
		}
		if preflight.Decision != PreflightAllow {
			writeJSON(response, http.StatusServiceUnavailable, map[string]any{"error": "preflight_unavailable", "decision": PreflightUnavailable, "reason_codes": []string{"invalid_preflight_decision"}})
			return
		}
	}
	now := time.Now()
	if s.Now != nil {
		now = s.Now()
	}
	s.mu.Lock()
	decision, classification, routeErr := s.Gateway.RouteAtTurnBoundary(protocolRequest, turn, now, input.NewTaskEpoch, input.ToolLoop, input.HardCapabilityFailure, input.StreamActive)
	s.mu.Unlock()
	if routeErr != nil || decision.SelectedModel == nil {
		writeJSON(response, http.StatusUnprocessableEntity, map[string]string{"error": "no_capable_model"})
		return
	}
	writeJSON(response, http.StatusOK, routeHTTPOutput{Object: "auto.route", RequestedModel: s.Gateway.PublicModel, EffectiveModel: decision.SelectedModel.Name, EffectiveReasoningEffort: decision.ReasoningEffort, Action: decision.Action, Switched: decision.Switched, Reason: decision.Reason, Classification: classification, UpstreamCalled: false, PreflightDecision: preflight.Decision, PreflightReasonCodes: preflight.ReasonCodes})
}

func decodeRouteRequest(input routeHTTPInput) (Request, error) {
	if len(input.Body) > 0 && string(input.Body) != "null" {
		if input.Protocol == "" {
			return Request{}, errors.New("protocol is required when body is provided")
		}
		return NormalizeProtocolRequest(input.Protocol, input.Body)
	}
	if input.Request == nil {
		return Request{}, errors.New("request or body is required")
	}
	return *input.Request, nil
}

func protocolFromHeader(value string) string {
	value = strings.TrimSpace(strings.ToLower(value))
	if value == "" {
		return ""
	}
	return value
}

func writeJSON(response http.ResponseWriter, status int, value any) {
	response.Header().Set("Content-Type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(value)
}

func publicPipelineError(err error) string {
	if isRoutingUnavailable(err) {
		return err.Error()
	}
	if errors.Is(err, ErrClassifierUnavailable) {
		return "classifier_unavailable"
	}
	if err != nil && err.Error() == "preflight_unavailable" {
		return "preflight_unavailable"
	}
	return "upstream_request_failed"
}

func isRoutingUnavailable(err error) bool {
	if err == nil {
		return false
	}
	switch err.Error() {
	case "no_healthy_model", "tool_provider_unavailable", "no_fallback_model", "no_capable_model", "tool_context_unavailable", "tool_state_unavailable", "tool_round_mismatch", "tool_call_id_collision", "session_state_unavailable", "session_state_write_failed":
		return true
	}
	return false
}
