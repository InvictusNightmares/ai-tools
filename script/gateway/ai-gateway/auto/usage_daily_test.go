package autogateway

import (
	"testing"
	"time"
)

func TestDailyUsageSeparatesModelReasoningRegionAndKey(t *testing.T) {
	recorder := NewDailyUsageRecorder()
	at := time.Date(2026, 9, 15, 0, 0, 0, 0, time.UTC)
	recorder.Record(UsageEvent{At: at, Region: "tokyo", EffectiveModel: "deepseek-flash", ReasoningEffort: ReasoningNone, APIKeyID: "key-1", Attempt: true, InputTokens: 100, CacheHitTokens: 80, CacheMissTokens: 20, OutputTokens: 10, Success: true})
	recorder.Record(UsageEvent{At: at, Region: "tokyo", EffectiveModel: "gpt-6-astra", ReasoningEffort: ReasoningXHigh, APIKeyID: "key-1", Attempt: true, InputTokens: 200, OutputTokens: 30, Success: false, Upgrade: true})
	recorder.Record(UsageEvent{At: at.Add(24 * time.Hour), Region: "tokyo", EffectiveModel: "deepseek-flash", ReasoningEffort: ReasoningNone, APIKeyID: "key-1", Success: true})
	if len(recorder.Snapshot()) != 3 {
		t.Fatalf("snapshot entries = %d", len(recorder.Snapshot()))
	}
	for _, entry := range recorder.Snapshot() {
		if entry.Key.Date == "2026-09-15" && entry.Key.EffectiveModel == "gpt-6-astra" && (entry.Upgrades != 1 || entry.Failures != 1) {
			t.Fatalf("unexpected upgrade entry: %+v", entry)
		}
	}
}
