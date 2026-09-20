package autogateway

import (
	"sync"
	"time"
)

type UsageEvent struct {
	UpstreamClientRequestID string          `json:"upstream_client_request_id,omitempty"`
	UsageReported           bool            `json:"usage_reported"`
	ClassificationCacheHit  bool            `json:"classification_cache_hit,omitempty"`
	ResponseModel           string          `json:"response_model,omitempty"`
	ResponseID              string          `json:"response_id,omitempty"`
	UpstreamRequestID       string          `json:"upstream_request_id,omitempty"`
	ErrorType               string          `json:"error_type,omitempty"`
	RequestID               string          `json:"request_id,omitempty"`
	Purpose                 string          `json:"purpose,omitempty"`
	HTTPStatus              int             `json:"http_status,omitempty"`
	At                      time.Time       `json:"at"`
	Region                  string          `json:"region"`
	EffectiveModel          string          `json:"effective_model"`
	ReasoningEffort         ReasoningEffort `json:"effective_reasoning_effort"`
	RequestedEffort         ReasoningEffort `json:"effort_requested,omitempty"`
	EffortStatus            EffortStatus    `json:"effort_status,omitempty"`
	ReportedEffort          ReasoningEffort `json:"upstream_reported_effort,omitempty"`
	EffortMismatch          bool            `json:"effort_mismatch,omitempty"`
	APIKeyID                string          `json:"api_key_id"`
	Attempt                 bool            `json:"attempt"`
	ResponseCacheHit        bool            `json:"response_cache_hit"`
	InputTokens             int             `json:"input_tokens"`
	CacheHitTokens          int             `json:"cache_hit_tokens"`
	CacheMissTokens         int             `json:"cache_miss_tokens"`
	OutputTokens            int             `json:"output_tokens"`
	Success                 bool            `json:"success"`
	Upgrade                 bool            `json:"upgrade"`
	Downgrade               bool            `json:"downgrade"`
}

type DailyUsageKey struct {
	Purpose         string
	Date            string
	Region          string
	EffectiveModel  string
	ReasoningEffort ReasoningEffort
	APIKeyID        string
}

type DailyUsage struct {
	ClassificationCacheHits int           `json:"classification_cache_hits"`
	Key                     DailyUsageKey `json:"key"`
	Requests                int           `json:"requests"`
	Attempts                int           `json:"attempts"`
	ResponseCacheHits       int           `json:"response_cache_hits"`
	InputTokens             int           `json:"input_tokens"`
	CacheHitTokens          int           `json:"cache_hit_tokens"`
	CacheMissTokens         int           `json:"cache_miss_tokens"`
	OutputTokens            int           `json:"output_tokens"`
	Successes               int           `json:"successes"`
	Failures                int           `json:"failures"`
	Upgrades                int           `json:"upgrades"`
	Downgrades              int           `json:"downgrades"`
}

type DailyUsageRecorder struct {
	mu      sync.Mutex
	entries map[DailyUsageKey]DailyUsage
}

func NewDailyUsageRecorder() *DailyUsageRecorder {
	return &DailyUsageRecorder{entries: make(map[DailyUsageKey]DailyUsage)}
}

func (recorder *DailyUsageRecorder) Record(event UsageEvent) DailyUsage {
	date := event.At.UTC().Format("2006-01-02")
	purpose := event.Purpose
	if purpose == "" {
		purpose = "business"
	}
	key := DailyUsageKey{Purpose: purpose, Date: date, Region: event.Region, EffectiveModel: event.EffectiveModel, ReasoningEffort: event.ReasoningEffort, APIKeyID: event.APIKeyID}
	recorder.mu.Lock()
	defer recorder.mu.Unlock()
	entry := recorder.entries[key]
	entry.Key = key
	entry.Requests++
	if event.ClassificationCacheHit {
		entry.ClassificationCacheHits++
	}
	if event.Attempt {
		entry.Attempts++
	}
	if event.ResponseCacheHit {
		entry.ResponseCacheHits++
	}
	entry.InputTokens += event.InputTokens
	entry.CacheHitTokens += event.CacheHitTokens
	entry.CacheMissTokens += event.CacheMissTokens
	entry.OutputTokens += event.OutputTokens
	if event.Success {
		entry.Successes++
	} else {
		entry.Failures++
	}
	if event.Upgrade {
		entry.Upgrades++
	}
	if event.Downgrade {
		entry.Downgrades++
	}
	recorder.entries[key] = entry
	return entry
}

func (recorder *DailyUsageRecorder) Snapshot() []DailyUsage {
	recorder.mu.Lock()
	defer recorder.mu.Unlock()
	result := make([]DailyUsage, 0, len(recorder.entries))
	for _, entry := range recorder.entries {
		result = append(result, entry)
	}
	return result
}
