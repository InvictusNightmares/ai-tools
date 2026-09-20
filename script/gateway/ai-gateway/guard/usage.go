package gocheck

import "time"

// ModelUsage contains counters only, one record per actual Qwen chunk attempt.
// It never includes the text or the safety model's response body.
type ModelUsage struct {
	Decision        string    `json:"decision,omitempty"`
	QueueWaitMS     int64     `json:"queue_wait_ms,omitempty"`
	LatencyMS       int64     `json:"latency_ms,omitempty"`
	RuleVersion     string    `json:"rule_version,omitempty"`
	ModelVersion    string    `json:"model_version,omitempty"`
	At              time.Time `json:"at"`
	Purpose         string    `json:"purpose"`
	RequestID       string    `json:"request_id"`
	Region          string    `json:"region"`
	APIKeyID        string    `json:"api_key_id"`
	EffectiveModel  string    `json:"effective_model"`
	UsageReported   bool      `json:"usage_reported"`
	Attempt         bool      `json:"attempt"`
	Success         bool      `json:"success"`
	HTTPStatus      int       `json:"http_status"`
	InputTokens     int       `json:"input_tokens"`
	OutputTokens    int       `json:"output_tokens"`
	CacheHitTokens  int       `json:"cache_hit_tokens"`
	CacheMissTokens int       `json:"cache_miss_tokens"`
	ErrorType       string    `json:"error_type,omitempty"`
}
