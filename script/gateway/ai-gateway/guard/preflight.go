package gocheck

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"strconv"
	"sync"
	"time"
)

type accountRisk struct {
	CyberCount      int
	QuarantineUntil time.Time
}

type sessionRisk struct {
	BlockedUntil time.Time
}

type decisionCacheEntry struct {
	Result    SafetyDecisionResult
	ExpiresAt time.Time
}

type PreflightGate struct {
	Config     PreflightConfig
	Classifier SafetyClassifier
	Audit      AuditSink
	Now        func() time.Time

	mu       sync.Mutex
	accounts map[string]accountRisk
	sessions map[string]sessionRisk
	cache    map[string]decisionCacheEntry
	history  map[string]historyEntry
}

func NewPreflightGate(config PreflightConfig, classifier SafetyClassifier, audit AuditSink) *PreflightGate {
	return &PreflightGate{
		Config: config, Classifier: classifier, Audit: audit,
		Now: time.Now, accounts: make(map[string]accountRisk), sessions: make(map[string]sessionRisk),
		cache: make(map[string]decisionCacheEntry),
	}
}

// Evaluate binds the allowed, sanitized body to this exact request. Cached
// verdicts never contain payloads or request digests.
func (g *PreflightGate) Evaluate(ctx context.Context, input SafetyInput) SafetyDecisionResult {
	if input.ProviderPayload != "" && !json.Valid([]byte(input.ProviderPayload)) {
		return g.Unavailable(ctx, input, "invalid_provider_payload")
	}
	result := g.evaluate(ctx, input)
	if result.Decision == SafetyAllow && input.ProviderPayload != "" {
		digest := sha256.Sum256([]byte(input.ProviderPayload))
		result.InputSHA256 = hex.EncodeToString(digest[:])
		result.RedactionVersion = RedactionVersion
		result.SanitizedPayload = redactSecretText(input.ProviderPayload)
		if result.SanitizedPayload != input.ProviderPayload {
			result.ReasonCodes = appendUnique(append([]string(nil), result.ReasonCodes...), "input_credentials_redacted")
		}
	}
	return result
}

func (g *PreflightGate) evaluate(ctx context.Context, input SafetyInput) SafetyDecisionResult {
	started := g.Now()
	originalBodyBytes := int64(len(input.RawBody))
	secretPresent := containsSecret(input)
	secretUse := secretUseMarker.MatchString(normalizedSafetyText(input))
	input = SanitizeInputForModel(input)
	if originalBodyBytes > g.Config.MaxBodyBytes {
		return g.finish(ctx, input, SafetyDecisionResult{Decision: SafetyBlock, RiskLevel: RiskHigh, ReasonCodes: []string{"body_too_large"}}, started)
	}
	if len(input.Messages) > g.Config.MaxMessages || len(input.Tools) > g.Config.MaxTools || len(input.Attachments) > g.Config.MaxAttachments {
		return g.finish(ctx, input, SafetyDecisionResult{Decision: SafetyBlock, RiskLevel: RiskHigh, ReasonCodes: []string{"request_shape_limit"}}, started)
	}
	if blocked, reason := g.isStateBlocked(input); blocked {
		return g.finish(ctx, input, SafetyDecisionResult{Decision: SafetyBlock, RiskLevel: RiskHigh, ReasonCodes: []string{reason}}, started)
	}
	rule := evaluateSafetyRules(input, secretPresent, secretUse)
	if rule.Decision == SafetyBlock {
		g.blockSession(input.SessionHash)
		return g.finish(ctx, input, rule, started)
	}
	cacheKey := decisionCacheKey(input, g.Config.RuleVersion, g.Config.ModelVersion)
	if cached, ok := g.cacheGet(cacheKey); ok {
		cached.Latency = g.Now().Sub(started)
		return cached
	}
	if g.Classifier == nil {
		if g.Config.FailClosed {
			return g.finishAndCache(ctx, input, cacheKey, SafetyDecisionResult{Decision: SafetyUnavailable, RiskLevel: RiskUnknown, ReasonCodes: []string{"classifier_unavailable"}}, started)
		}
		return g.finish(ctx, input, rule, started)
	}

	inspection := g.historyInspection(input)
	verdict, err := g.Classifier.Classify(ctx, inspection.input)
	if err != nil {
		if g.Config.FailClosed {
			return g.finishAndCache(ctx, input, cacheKey, SafetyDecisionResult{Decision: SafetyUnavailable, RiskLevel: RiskUnknown, ReasonCodes: []string{"classifier_error"}}, started)
		}
		return g.finish(ctx, input, rule, started)
	}
	if verdict.Decision == "" || verdict.RiskLevel == "" {
		if g.Config.FailClosed {
			return g.finishAndCache(ctx, input, cacheKey, SafetyDecisionResult{Decision: SafetyUnavailable, RiskLevel: RiskUnknown, ReasonCodes: []string{"invalid_classifier_verdict"}}, started)
		}
		return g.finish(ctx, input, rule, started)
	}
	result := SafetyDecisionResult{
		HistoryTotalMessages: inspection.total, HistoryReusedMessages: inspection.reused,
		Decision: verdict.Decision, RiskLevel: verdict.RiskLevel,
		Categories: verdict.Categories, Confidence: verdict.Confidence,
		ReasonCodes: append(rule.ReasonCodes, verdict.ReasonCodes...),
	}
	result.RiskLevel = maxRisk(rule.RiskLevel, result.RiskLevel)
	result.Categories = appendUnique(append([]string(nil), rule.Categories...), result.Categories...)
	if rule.Decision == SafetyBlock || verdict.Decision == SafetyBlock {
		result.Decision = SafetyBlock
	}
	if g.Config.Strict && (result.RiskLevel == RiskMedium || result.RiskLevel == RiskHigh) {
		result.Decision = SafetyBlock
	}
	if result.Decision == SafetyBlock {
		g.blockSession(input.SessionHash)
	}
	result = g.finishAndCache(ctx, input, cacheKey, result, started)
	if result.Decision == SafetyAllow {
		g.rememberHistory(inspection)
	}
	return result
}

// Unavailable records a fail-closed decision for requests rejected before
// classifier execution, such as queue saturation.
func (g *PreflightGate) Unavailable(ctx context.Context, input SafetyInput, reason string) SafetyDecisionResult {
	started := g.Now()
	input = SanitizeInputForModel(input)
	if reason == "" {
		reason = "preflight_unavailable"
	}
	return g.finish(ctx, input, SafetyDecisionResult{
		Decision: SafetyUnavailable, RiskLevel: RiskUnknown,
		ReasonCodes: []string{reason},
	}, started)
}

func (g *PreflightGate) finish(ctx context.Context, input SafetyInput, result SafetyDecisionResult, started time.Time) SafetyDecisionResult {
	result.Latency = g.Now().Sub(started)
	if g.Audit != nil && result.Decision != SafetyAllow {
		bodyHash := ""
		if len(input.RawBody) > 0 {
			h := sha256.Sum256(input.RawBody)
			bodyHash = hex.EncodeToString(h[:])
		}
		err := g.Audit.WritePreflightAudit(ctx, PreflightAudit{
			RequestID:  input.RequestID,
			RecordedAt: g.Now(), Decision: result.Decision, RiskLevel: result.RiskLevel,
			Categories: result.Categories, ReasonCodes: result.ReasonCodes,
			Confidence: result.Confidence, RuleVersion: g.Config.RuleVersion,
			ModelVersion: g.Config.ModelVersion, Protocol: input.Protocol,
			Provider: input.Provider, Model: input.Model, Region: input.Region,
			SessionHash: input.SessionHash, AccountID: input.AccountID,
			BodySHA256: bodyHash, RawBody: append([]byte(nil), input.RawBody...),
		})
		if err != nil {
			return SafetyDecisionResult{
				Decision: SafetyUnavailable, RiskLevel: RiskUnknown,
				ReasonCodes: appendUnique(append([]string(nil), result.ReasonCodes...), "audit_write_failed"),
				Latency:     g.Now().Sub(started),
			}
		}
	}
	return result
}

func (g *PreflightGate) finishAndCache(ctx context.Context, input SafetyInput, key string, result SafetyDecisionResult, started time.Time) SafetyDecisionResult {
	result = g.finish(ctx, input, result, started)
	if result.Decision != SafetyUnavailable && g.Config.DecisionCacheTTL > 0 {
		g.mu.Lock()
		g.cache[key] = decisionCacheEntry{Result: result, ExpiresAt: g.Now().Add(g.Config.DecisionCacheTTL)}
		g.mu.Unlock()
	}
	return result
}

func (g *PreflightGate) cacheGet(key string) (SafetyDecisionResult, bool) {
	if g.Config.DecisionCacheTTL <= 0 {
		return SafetyDecisionResult{}, false
	}
	now := g.Now()
	g.mu.Lock()
	defer g.mu.Unlock()
	entry, ok := g.cache[key]
	if !ok {
		return SafetyDecisionResult{}, false
	}
	if !now.Before(entry.ExpiresAt) {
		delete(g.cache, key)
		return SafetyDecisionResult{}, false
	}
	return entry.Result, true
}

func decisionCacheKey(input SafetyInput, ruleVersion, modelVersion string) string {
	input = SanitizeInputForModel(input)
	h := sha256.New()
	h.Write([]byte(ruleVersion))
	h.Write([]byte{'\x00'})
	h.Write([]byte(modelVersion))
	h.Write([]byte{'\x00'})
	h.Write([]byte(input.Protocol))
	h.Write([]byte{'\x00'})
	h.Write([]byte(input.Provider))
	h.Write([]byte{'\x00'})
	h.Write([]byte(input.Model))
	h.Write([]byte{'\x00'})
	h.Write([]byte(input.Region))
	h.Write([]byte{'\x00'})
	h.Write([]byte(input.SessionHash))
	h.Write([]byte{'\x00'})
	h.Write([]byte(input.AccountID))
	h.Write([]byte{'\x00'})
	h.Write([]byte(normalizedSafetyText(input)))
	for _, tool := range input.Tools {
		h.Write([]byte(tool.Name))
		h.Write([]byte(tool.Schema))
	}
	for _, attachment := range input.Attachments {
		h.Write([]byte(attachment.Type))
		h.Write([]byte(strconv.FormatInt(attachment.Bytes, 10)))
	}
	return hex.EncodeToString(h.Sum(nil))
}

func (g *PreflightGate) isStateBlocked(input SafetyInput) (bool, string) {
	now := g.Now()
	g.mu.Lock()
	defer g.mu.Unlock()
	if input.SessionHash != "" {
		if state, ok := g.sessions[input.SessionHash]; ok && now.Before(state.BlockedUntil) {
			return true, "session_quarantined"
		}
	}
	if input.AccountID != "" {
		if state, ok := g.accounts[input.AccountID]; ok && now.Before(state.QuarantineUntil) {
			return true, "account_quarantined"
		}
	}
	return false, ""
}

func (g *PreflightGate) blockSession(sessionHash string) {
	if sessionHash == "" {
		return
	}
	g.mu.Lock()
	defer g.mu.Unlock()
	g.sessions[sessionHash] = sessionRisk{BlockedUntil: g.Now().Add(g.Config.SessionBlockTTL)}
}

// ObserveUpstreamCyber is called only after a confirmed upstream cyber_policy.
// It never causes the original request to be retried or sent to another account.
func (g *PreflightGate) ObserveUpstreamCyber(accountID, sessionHash string) {
	if sessionHash != "" {
		g.blockSession(sessionHash)
	}
	if accountID == "" {
		return
	}
	g.mu.Lock()
	defer g.mu.Unlock()
	state := g.accounts[accountID]
	state.CyberCount++
	if state.CyberCount >= g.Config.AccountCyberThreshold {
		state.QuarantineUntil = g.Now().Add(g.Config.AccountQuarantineTTL)
	}
	g.accounts[accountID] = state
}

func (g *PreflightGate) ReleaseAccount(accountID string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	delete(g.accounts, accountID)
}
