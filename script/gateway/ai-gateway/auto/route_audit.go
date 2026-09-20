package autogateway

import "time"

type RouteAudit struct {
	OutputFormat            string            `json:"output_format,omitempty"`
	Protocol                string            `json:"protocol,omitempty"`
	RequestOperation        string            `json:"request_operation,omitempty"`
	RequestedModelHash      string            `json:"requested_model_hash,omitempty"`
	TaskAssessment          *TaskAssessment   `json:"task_assessment,omitempty"`
	TaskType                string            `json:"task_type,omitempty"`
	SelectionPolicy         string            `json:"selection_policy,omitempty"`
	TargetModelTier         *int              `json:"target_model_tier,omitempty"`
	UpstreamClientRequestID string            `json:"upstream_client_request_id,omitempty"`
	StreamTermination       string            `json:"stream_termination,omitempty"`
	GuardScope              string            `json:"guard_scope,omitempty"`
	ContextBudget           ContextBudget     `json:"context_budget"`
	UpstreamTransport       string            `json:"upstream_transport,omitempty"`
	TokenCountMethod        string            `json:"token_count_method,omitempty"`
	CountedInputTokens      int               `json:"counted_input_tokens,omitempty"`
	UpstreamHTTPStatus      int               `json:"upstream_http_status,omitempty"`
	Region                  string            `json:"region,omitempty"`
	APIKeyID                string            `json:"api_key_id,omitempty"`
	SessionHash             string            `json:"session_hash,omitempty"`
	Usage                   NormalizedUsage   `json:"usage"`
	RequestID               string            `json:"request_id,omitempty"`
	Stage                   string            `json:"stage,omitempty"`
	ClassifierVersion       string            `json:"classifier_version,omitempty"`
	ClassifierTrace         ClassifierTrace   `json:"classifier_trace"`
	TaskComplexity          string            `json:"task_complexity,omitempty"`
	HTTPStatus              int               `json:"http_status,omitempty"`
	ResponseModel           string            `json:"response_model,omitempty"`
	ResponseID              string            `json:"response_id,omitempty"`
	UpstreamRequestID       string            `json:"upstream_request_id,omitempty"`
	ResponseComplete        bool              `json:"response_complete"`
	UpstreamCalled          bool              `json:"upstream_called"`
	ErrorType               string            `json:"error_type,omitempty"`
	At                      time.Time         `json:"at"`
	RequestedModel          string            `json:"requested_model"`
	EffectiveModel          string            `json:"effective_model"`
	EffectiveReasoning      ReasoningEffort   `json:"effective_reasoning_effort"`
	EffortRequested         ReasoningEffort   `json:"effort_requested"`
	ReportedEffort          ReasoningEffort   `json:"upstream_reported_effort,omitempty"`
	EffortMismatch          bool              `json:"effort_mismatch,omitempty"`
	EffortApplied           ReasoningEffort   `json:"effort_applied"`
	EffortStatus            EffortStatus      `json:"effort_status"`
	EffortParameter         string            `json:"effort_parameter"`
	Action                  string            `json:"action"`
	Reason                  string            `json:"reason"`
	Score                   int               `json:"score"`
	Confidence              float64           `json:"confidence"`
	RequiredCapabilities    []Capability      `json:"required_capabilities"`
	Stream                  bool              `json:"stream"`
	PreflightDecision       PreflightDecision `json:"preflight_decision"`
	PreflightReasonCodes    []string          `json:"preflight_reason_codes,omitempty"`
}

func BuildRouteAudit(at time.Time, requestedModel, provider, protocol string, request Request, decision RouteDecision, classification Classification) RouteAudit {
	audit := RouteAudit{
		OutputFormat: request.OutputFormat,
		Protocol:     canonicalProtocol(protocol), RequestOperation: requestOperation(request),
		ContextBudget: classification.ContextBudget,
		At:            at, RequestedModel: requestedModel, EffectiveReasoning: decision.ReasoningEffort,
		Action: decision.Action, Reason: decision.Reason, Score: classification.Score,
		Confidence: classification.Confidence, RequiredCapabilities: append([]Capability(nil), classification.RequiredCapabilities...), Stream: request.Stream,
	}
	audit.ClassifierTrace = classification.Trace
	if request.Native != nil {
		audit.GuardScope = nativeGuardScope(request.Native)
	}
	if classification.Assessment != nil {
		assessment := *classification.Assessment
		assessment.TaskLabels = append([]string(nil), assessment.TaskLabels...)
		audit.TaskAssessment = &assessment
		audit.TaskType = classification.Assessment.TaskType
		if classification.Source == semanticPolicyVersion {
			audit.SelectionPolicy = taskRoutingPolicy
			floor := taskModelFloor(classification)
			audit.TargetModelTier = &floor
		}
		audit.TaskComplexity = classification.Assessment.Complexity
	}
	if decision.SelectedModel == nil {
		return audit
	}
	audit.EffectiveModel = decision.SelectedModel.Name
	mapping := BuildProviderParameters(provider, protocol, *decision.SelectedModel, decision.ReasoningEffort, request.Stream)
	audit.EffortApplied, audit.EffortStatus, audit.EffortParameter = mapping.Reasoning.Applied, mapping.Reasoning.Status, mapping.Reasoning.Parameter
	audit.EffortRequested, audit.EffectiveReasoning = mapping.Reasoning.Requested, mapping.Reasoning.Applied
	return audit
}

func requestOperation(request Request) string {
	if request.CompactionTrigger {
		return "compaction"
	}
	return "completion"
}
