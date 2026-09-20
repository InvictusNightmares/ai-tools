package autogateway

import (
	"context"
	"errors"
	"os"
	"strings"
	"testing"
	"time"
)

type recordingUpstream struct {
	calls int
	last  UpstreamRequest
	err   error
}

func (upstream *recordingUpstream) Complete(_ context.Context, request UpstreamRequest) (UpstreamResponse, error) {
	upstream.calls++
	upstream.last = request
	if upstream.err != nil {
		return UpstreamResponse{}, upstream.err
	}
	return UpstreamResponse{StatusCode: 200, ResponseBytes: 128, Usage: map[string]any{"prompt_tokens": 10}}, nil
}

func TestPipelineStopsBeforeUpstreamOnBlockAndUnavailable(t *testing.T) {
	for _, test := range []struct {
		name      string
		decision  PreflightDecision
		wantError string
	}{
		{name: "block", decision: PreflightBlock},
		{name: "unavailable", decision: PreflightUnavailable, wantError: "preflight_unavailable"},
	} {
		t.Run(test.name, func(t *testing.T) {
			upstream := &recordingUpstream{}
			pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: test.decision}}, Upstream: upstream, CachePolicy: DefaultResponseCachePolicy()}
			result, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 1, false, false, false, false)
			if upstream.calls != 0 || result.UpstreamCalled {
				t.Fatalf("upstream called: %+v", result)
			}
			if test.wantError == "" && err != nil {
				t.Fatal(err)
			}
			if test.wantError != "" && (err == nil || err.Error() != test.wantError) {
				t.Fatalf("error = %v", err)
			}
		})
	}
}

func TestPipelineAuditsPreflightBlockAndUnavailableWithoutPrompt(t *testing.T) {
	path := t.TempDir() + "/audit.jsonl"
	sink, err := NewJSONLAuditSink(path)
	if err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		name     string
		decision PreflightDecision
		action   string
	}{
		{name: "block", decision: PreflightBlock, action: "preflight_blocked"},
		{name: "unavailable", decision: PreflightUnavailable, action: "preflight_unavailable"},
	} {
		t.Run(test.name, func(t *testing.T) {
			pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: test.decision, ReasonCodes: []string{"test_reason"}}}, AuditSink: sink}
			_, _ = pipeline.Execute(context.Background(), "chat", "openai", "auto", Request{Messages: []Message{{Role: "user", Content: "private prompt must not be persisted"}}}, 1, false, false, false, false)
		})
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(data)
	if strings.Count(text, "\n") != 2 || !strings.Contains(text, "preflight_blocked") || !strings.Contains(text, "preflight_unavailable") || strings.Contains(text, "private prompt") {
		t.Fatalf("preflight audit = %s", text)
	}
}

func TestPipelineAllowMapsAutoDecisionAndCallsUpstreamOnce(t *testing.T) {
	upstream := &recordingUpstream{}
	pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, Upstream: upstream, CachePolicy: DefaultResponseCachePolicy()}
	result, err := pipeline.Execute(context.Background(), "responses", "openai", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 1, false, false, false, false)
	if err != nil {
		t.Fatal(err)
	}
	if upstream.calls != 1 || !result.UpstreamCalled || result.Upstream.StatusCode != 200 {
		t.Fatalf("pipeline = %+v calls=%d", result, upstream.calls)
	}
	reasoning, ok := upstream.last.Parameters.ReasoningParameter["reasoning"].(map[string]any)
	if upstream.last.Model.Name != "deepseek-flash" || !ok || reasoning["effort"] != string(ReasoningNone) {
		t.Fatalf("upstream request = %+v", upstream.last)
	}
	if !result.CacheEligible || result.CacheReason != "eligible" || result.Audit.EffectiveModel != "deepseek-flash" {
		t.Fatalf("cache/audit = %+v", result)
	}
}

func TestPipelinePropagatesUpstreamFailureWithoutRetry(t *testing.T) {
	upstream := &recordingUpstream{err: errors.New("provider_timeout")}
	pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, Upstream: upstream, CachePolicy: DefaultResponseCachePolicy()}
	result, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 1, false, false, false, false)
	if err == nil || err.Error() != "provider_timeout" || upstream.calls != 1 || !result.UpstreamCalled {
		t.Fatalf("failure = %+v err=%v calls=%d", result, err, upstream.calls)
	}
}

func TestPipelineResponseCacheHitSkipsUpstreamAndRecordsUsage(t *testing.T) {
	upstream := &recordingUpstream{}
	cache := NewMemoryResponseCache()
	usage := NewDailyUsageRecorder()
	meta := PipelineMeta{Region: "tokyo", APIKeyID: "key-1", ModelRevision: "catalog-1", CacheSecret: "test-secret"}
	pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, Upstream: upstream, Cache: cache, Usage: usage, Meta: meta, CachePolicy: DefaultResponseCachePolicy()}
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	first, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", request, 1, false, false, false, false)
	if err != nil || !first.UpstreamCalled || first.CacheHit || upstream.calls != 1 {
		t.Fatalf("first = %+v calls=%d err=%v", first, upstream.calls, err)
	}
	second, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", request, 1, false, false, false, false)
	if err != nil || !second.CacheHit || second.UpstreamCalled || upstream.calls != 1 {
		t.Fatalf("second = %+v calls=%d err=%v", second, upstream.calls, err)
	}
	entries := usage.Snapshot()
	if len(entries) != 1 || entries[0].Requests != 2 || entries[0].Attempts != 1 || entries[0].Successes != 2 {
		t.Fatalf("usage = %+v", entries)
	}
}

func TestPipelineCacheExpiresAndUpstreamFailureIsNotStored(t *testing.T) {
	upstream := &recordingUpstream{}
	cache := NewMemoryResponseCache()
	now := time.Date(2026, 9, 15, 1, 0, 0, 0, time.UTC)
	meta := PipelineMeta{Region: "us-west", APIKeyID: "key-2", ModelRevision: "catalog-1", CacheSecret: "test-secret"}
	pipeline := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, Upstream: upstream, Cache: cache, Meta: meta, CachePolicy: ResponseCachePolicy{TTL: time.Minute, MaxEntryBytes: 1024}, Now: func() time.Time { return now }}
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	if _, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", request, 1, false, false, false, false); err != nil {
		t.Fatal(err)
	}
	now = now.Add(2 * time.Minute)
	second, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", request, 1, false, false, false, false)
	if err != nil || second.CacheHit || upstream.calls != 2 {
		t.Fatalf("expired cache = %+v calls=%d err=%v", second, upstream.calls, err)
	}
	upstream.err = errors.New("provider_timeout")
	if _, err := pipeline.Execute(context.Background(), "chat", "deepseek", "auto", Request{Messages: []Message{{Role: "user", Content: "new"}}}, 1, false, false, false, false); err == nil {
		t.Fatal("expected upstream failure")
	}
}
