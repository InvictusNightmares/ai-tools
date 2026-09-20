package gocheck

import (
	"context"
	"time"
)

type SafetyDecision string

const (
	SafetyAllow       SafetyDecision = "allow"
	SafetyBlock       SafetyDecision = "block"
	SafetyUnavailable SafetyDecision = "unavailable"
)

type RiskLevel string

const (
	RiskLow     RiskLevel = "low"
	RiskMedium  RiskLevel = "medium"
	RiskHigh    RiskLevel = "high"
	RiskUnknown RiskLevel = "unknown"
)

type SafetyMessage struct {
	Role    string `json:"role"`
	Content string `json:"content,omitempty"`
}

type SafetyTool struct {
	Name   string `json:"name,omitempty"`
	Schema string `json:"schema,omitempty"`
}

type SafetyAttachment struct {
	Type   string `json:"type,omitempty"`
	Bytes  int64  `json:"bytes,omitempty"`
	Source string `json:"source,omitempty"`
}

// SafetyInput is protocol-neutral. RawBody is retained only by the audit sink
// when a request produces a non-allow decision.
type SafetyInput struct {
	RequestID       string             `json:"request_id,omitempty"`
	Protocol        string             `json:"protocol"`
	Provider        string             `json:"provider"`
	Model           string             `json:"model"`
	Region          string             `json:"region"`
	SessionHash     string             `json:"session_hash,omitempty"`
	AccountID       string             `json:"account_id,omitempty"`
	Messages        []SafetyMessage    `json:"messages"`
	Tools           []SafetyTool       `json:"tools,omitempty"`
	Attachments     []SafetyAttachment `json:"attachments,omitempty"`
	Metadata        map[string]string  `json:"metadata,omitempty"`
	ProviderPayload string             `json:"provider_payload,omitempty"`
	RawBody         []byte             `json:"-"`
}

type ModelVerdict struct {
	Decision    SafetyDecision `json:"decision"`
	RiskLevel   RiskLevel      `json:"risk_level"`
	Categories  []string       `json:"categories,omitempty"`
	Confidence  float64        `json:"confidence"`
	ReasonCodes []string       `json:"reason_codes,omitempty"`
}

type SafetyClassifier interface {
	Classify(context.Context, SafetyInput) (ModelVerdict, error)
}

type PreflightConfig struct {
	Strict                bool
	FailClosed            bool
	RuleVersion           string
	ModelVersion          string
	MaxBodyBytes          int64
	MaxMessages           int
	MaxTools              int
	MaxAttachments        int
	SessionBlockTTL       time.Duration
	AccountQuarantineTTL  time.Duration
	AccountCyberThreshold int
	DecisionCacheTTL      time.Duration
	HistoryCacheTTL       time.Duration
	HistoryCacheCapacity  int
}

func DefaultPreflightConfig() PreflightConfig {
	return PreflightConfig{
		Strict:                true,
		FailClosed:            true,
		RuleVersion:           "preflight-r19",
		ModelVersion:          "unconfigured",
		MaxBodyBytes:          8 << 20,
		MaxMessages:           128,
		MaxTools:              32,
		MaxAttachments:        16,
		SessionBlockTTL:       24 * time.Hour,
		AccountQuarantineTTL:  24 * time.Hour,
		AccountCyberThreshold: 2,
		DecisionCacheTTL:      5 * time.Minute,
		HistoryCacheTTL:       5 * time.Minute,
		HistoryCacheCapacity:  4096,
	}
}

type PreflightAudit struct {
	RequestID    string         `json:"request_id,omitempty"`
	RecordedAt   time.Time      `json:"recorded_at"`
	Decision     SafetyDecision `json:"decision"`
	RiskLevel    RiskLevel      `json:"risk_level"`
	Categories   []string       `json:"categories,omitempty"`
	ReasonCodes  []string       `json:"reason_codes,omitempty"`
	Confidence   float64        `json:"confidence"`
	RuleVersion  string         `json:"rule_version"`
	ModelVersion string         `json:"model_version"`
	Protocol     string         `json:"protocol"`
	Provider     string         `json:"provider"`
	Model        string         `json:"model"`
	Region       string         `json:"region"`
	SessionHash  string         `json:"session_hash,omitempty"`
	AccountID    string         `json:"account_id,omitempty"`
	BodySHA256   string         `json:"body_sha256,omitempty"`
	RawBody      []byte         `json:"raw_body,omitempty"`
}

type AuditSink interface {
	WritePreflightAudit(context.Context, PreflightAudit) error
}

type SafetyDecisionResult struct {
	HistoryTotalMessages  int
	HistoryReusedMessages int
	SanitizedPayload      string
	InputSHA256           string
	RedactionVersion      string
	Decision              SafetyDecision
	RiskLevel             RiskLevel
	Categories            []string
	Confidence            float64
	ReasonCodes           []string
	Latency               time.Duration
}
