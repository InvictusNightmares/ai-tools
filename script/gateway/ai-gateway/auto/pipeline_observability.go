package autogateway

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"log"
	"time"
)

func withRequestID(meta PipelineMeta) PipelineMeta {
	if meta.RequestID == "" {
		var id [16]byte
		if _, err := rand.Read(id[:]); err != nil {
			panic("request_id_entropy_unavailable")
		}
		meta.RequestID = hex.EncodeToString(id[:])
	}
	return meta
}
func (p *Pipeline) currentTime() time.Time {
	if p.Now != nil {
		return p.Now()
	}
	return time.Now()
}

func (p *Pipeline) classify(ctx context.Context, protocol string, r Request, meta PipelineMeta) (Classification, error) {
	if r.CompactionTrigger {
		c := classificationFromAssessment(r, TaskAssessment{TaskType: "quick_qa", TaskLabels: []string{"quick_qa"}, Stage: "continue", Complexity: "simple", Scope: "local", Uncertainty: "low", Verification: "none", Continuation: true, Confidence: 1})
		c.EffectiveReasoningEffort = ReasoningLow
		c.ReasonCodes = append(c.ReasonCodes, "native_compaction_operation")
		return c, nil
	}
	if p.Classifier == nil {
		c := ExtractFeatures(r)
		c.Source = "legacy-preview"
		return c, nil
	}
	if c, ok := p.boundToolClassification(protocol, r, meta); ok {
		return c, nil
	}
	return p.Classifier.Classify(ctx, r, meta)
}
func (p *Pipeline) writeClassifierFailure(meta PipelineMeta) {
	if p.AuditSink != nil {
		p.persistAudit(RouteAudit{At: time.Now(), RequestID: meta.RequestID, Stage: "classification_failed", ErrorType: "classifier_unavailable", Region: meta.Region, APIKeyID: meta.APIKeyID, SessionHash: hashIdentifier(meta.SessionID), PreflightDecision: PreflightAllow})
	}
}

func (p *Pipeline) writeRoutingFailure(meta PipelineMeta, requestedModel, reason string) {
	p.persistAudit(RouteAudit{At: time.Now(), RequestID: meta.RequestID, Stage: "routing_unavailable", ErrorType: reason, RequestedModel: requestedModel, Region: meta.Region, APIKeyID: meta.APIKeyID, SessionHash: hashIdentifier(meta.SessionID), PreflightDecision: PreflightAllow, HTTPStatus: 503})
}
func (p *Pipeline) startAudit(meta PipelineMeta, r PipelineResult) error {
	if p.AuditSink == nil {
		return nil
	}
	a := r.Audit
	a.At = time.Now()
	a.Stage = "upstream_started"
	a.RequestID = meta.RequestID
	a.UpstreamCalled = true
	if p.AuditSink.WriteRouteAudit(a) != nil {
		return errors.New("audit_unavailable")
	}
	return nil
}
func (p *Pipeline) finishAudit(meta PipelineMeta, r PipelineResult, err error) {
	if p.AuditSink == nil || r.Decision.SelectedModel == nil {
		return
	}
	a := r.Audit
	a.RequestID = meta.RequestID
	a.At = time.Now()
	a.UpstreamTransport = r.Upstream.Transport
	a.HTTPStatus = r.Upstream.StatusCode
	a.ResponseModel = r.Upstream.ResponseModel
	a.ReportedEffort = r.Upstream.ReportedEffort
	a.EffortMismatch = a.EffortApplied != "" && a.ReportedEffort != "" && a.ReportedEffort != a.EffortApplied
	a.ResponseID = r.Upstream.ResponseID
	a.UpstreamRequestID = r.Upstream.RequestID
	a.UpstreamClientRequestID = r.Upstream.ClientRequestID
	a.UpstreamCalled = r.UpstreamCalled
	a.ResponseComplete = r.Upstream.Complete
	a.StreamTermination = r.Upstream.StreamTermination
	a.Usage = NormalizedUsage{}
	if r.UpstreamCalled {
		a.Usage = NormalizeUsage(r.Upstream.Usage)
	}
	switch {
	case err != nil:
		a.Stage = failureAuditStage(err)
		a.ErrorType = "upstream_failed"
		if errors.Is(err, context.Canceled) {
			a.ErrorType = "context_canceled"
		}
		if a.StreamTermination != "" {
			a.ErrorType = a.StreamTermination
		}
		if !r.UpstreamCalled {
			a.ErrorType = "request_failed"
		}
	case r.CacheHit:
		a.Stage = "response_cache_hit"
	case !r.UpstreamCalled:
		a.Stage = "request_completed_without_upstream"
	default:
		a.Stage = "upstream_completed"
	}
	p.persistAudit(a)
}

func failureAuditStage(err error) string {
	if isClientDeliveryFailure(err) {
		return "client_delivery_failed"
	}
	if errors.Is(err, context.Canceled) {
		return "request_canceled"
	}
	return "upstream_failed"
}

// The process log is a second, metadata-only evidence channel when the spool fails.
func (p *Pipeline) persistAudit(a RouteAudit) {
	if p.AuditSink == nil {
		return
	}
	if err := p.AuditSink.WriteRouteAudit(a); err != nil {
		raw, _ := json.Marshal(a)
		log.Printf("audit_sink_failed event=%s", raw)
	}
}
