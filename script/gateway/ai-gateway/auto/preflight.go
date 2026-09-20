package autogateway

import (
	"context"
	"errors"
)

type PreflightDecision string

const (
	PreflightAllow       PreflightDecision = "allow"
	PreflightBlock       PreflightDecision = "block"
	PreflightUnavailable PreflightDecision = "unavailable"
)

type PreflightResult struct {
	SanitizedRequest *Request          `json:"-"`
	Decision         PreflightDecision `json:"decision"`
	ReasonCodes      []string          `json:"reason_codes,omitempty"`
}

// PreflightChecker is the narrow seam used by the local adapter. The real
// Guard client is wired only during phase D, after Auto independent tests.
type PreflightChecker interface {
	Evaluate(context.Context, Request) (PreflightResult, error)
}

type contextualPreflightChecker interface {
	EvaluateWithMeta(context.Context, Request, PipelineMeta) (PreflightResult, error)
}

func evaluatePreflight(ctx context.Context, checker PreflightChecker, request Request, meta PipelineMeta) (PreflightResult, error) {
	if checker == nil {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_unconfigured"}}, errors.New("preflight_unavailable")
	}
	if contextual, ok := checker.(contextualPreflightChecker); ok {
		return contextual.EvaluateWithMeta(ctx, request, meta)
	}
	return checker.Evaluate(ctx, request)
}
