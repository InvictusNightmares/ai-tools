package autogateway

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"
)

type cacheTestUpstream struct {
	calls    int
	response UpstreamResponse
	err      error
}

func (u *cacheTestUpstream) Complete(context.Context, UpstreamRequest) (UpstreamResponse, error) {
	u.calls++
	return u.response, u.err
}

type observedResponseCache struct {
	gets, sets int
}

func (c *observedResponseCache) Get(string, time.Time) (UpstreamResponse, bool) {
	c.gets++
	return UpstreamResponse{}, false
}

func (c *observedResponseCache) Set(string, UpstreamResponse, time.Time) { c.sets++ }

func cacheTestPipeline() (*Pipeline, *cacheTestUpstream) {
	u := &cacheTestUpstream{response: UpstreamResponse{StatusCode: 200, Body: []byte(`{"text":"hello"}`), ResponseBytes: 16, Usage: map[string]any{
		"prompt_tokens": 10, "completion_tokens": 2,
		"prompt_cache_hit_tokens": 6, "prompt_cache_miss_tokens": 4,
	}}}
	p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}},
		Upstream: u, Cache: NewMemoryResponseCache(), Usage: NewDailyUsageRecorder(), CachePolicy: DefaultResponseCachePolicy(),
		Meta: PipelineMeta{Region: "tokyo", APIKeyID: "key-1", ModelRevision: "v1", CacheSecret: "test-only-cache-secret"},
	}
	return p, u
}

func executeCacheTest(p *Pipeline, protocol string) (PipelineResult, error) {
	return p.Execute(context.Background(), protocol, "openai", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 1, false, false, false, false)
}

func TestCachePipelineBillingOnResponseHit(t *testing.T) {
	p, u := cacheTestPipeline()
	if _, err := executeCacheTest(p, "chat"); err != nil {
		t.Fatal(err)
	}
	hit, err := executeCacheTest(p, "chat")
	if err != nil || !hit.CacheHit || hit.UpstreamCalled || u.calls != 1 {
		t.Fatalf("result=%+v calls=%d err=%v", hit, u.calls, err)
	}
	daily := p.Usage.Snapshot()
	if len(daily) != 1 {
		t.Fatalf("usage=%+v", daily)
	}
	entry := daily[0]
	if entry.ResponseCacheHits != 1 || string(hit.Upstream.Body) != `{"text":"hello"}` {
		t.Fatalf("cached body/hits: result=%+v daily=%+v", hit, entry)
	}
	if entry.Requests != 2 || entry.Attempts != 1 || entry.InputTokens != 10 || entry.OutputTokens != 2 || entry.CacheHitTokens != 6 || entry.CacheMissTokens != 4 {
		t.Fatalf("response replay must not bill old provider tokens again: %+v", entry)
	}
}

func TestCachePipelineRejectsUnsuccessfulHTTPAndOversize(t *testing.T) {
	for _, tc := range []struct {
		name         string
		status, size int
		transportErr error
	}{
		{"unavailable", 503, 16, nil}, {"rate_limited", 429, 16, nil}, {"redirect", 302, 16, nil},
		{"oversize", 200, 5 << 20, nil}, {"transport_error", 0, 0, errors.New("timeout")},
	} {
		t.Run(tc.name, func(t *testing.T) {
			p, u := cacheTestPipeline()
			u.response.StatusCode, u.response.ResponseBytes, u.err = tc.status, tc.size, tc.transportErr
			for i := 0; i < 2; i++ {
				result, _ := executeCacheTest(p, "chat")
				if result.CacheHit {
					t.Fatalf("non-reusable response was cached: %+v", result)
				}
			}
			if u.calls != 2 {
				t.Fatalf("calls=%d", u.calls)
			}
			if tc.status != 200 && p.Usage.Snapshot()[0].Failures != 2 {
				t.Fatalf("failures=%+v", p.Usage.Snapshot())
			}
		})
	}
}

func TestCachePipelineGuardBeforeCache(t *testing.T) {
	for _, decision := range []PreflightDecision{PreflightBlock, PreflightUnavailable, "invalid"} {
		t.Run(string(decision), func(t *testing.T) {
			p, u := cacheTestPipeline()
			cache := &observedResponseCache{}
			p.Cache = cache
			p.Preflight = fixedPreflight{result: PreflightResult{Decision: decision}}
			_, err := executeCacheTest(p, "chat")
			if decision != PreflightBlock && (err == nil || err.Error() != "preflight_unavailable") {
				t.Fatalf("error=%v", err)
			}
			if cache.gets != 0 || cache.sets != 0 || u.calls != 0 || len(p.Usage.Snapshot()) != 0 || p.Gateway.State.HasCurrent {
				t.Fatalf("blocked request reached business path: cache=%+v calls=%d", cache, u.calls)
			}
		})
	}
}

func TestCachePipelineProtocolIsolation(t *testing.T) {
	p, u := cacheTestPipeline()
	if _, err := executeCacheTest(p, "chat"); err != nil {
		t.Fatal(err)
	}
	result, err := executeCacheTest(p, "responses")
	if err != nil || result.CacheHit || u.calls != 2 {
		t.Fatalf("cross-protocol replay: %+v calls=%d err=%v", result, u.calls, err)
	}
}

func TestMemoryCacheDoesNotAliasUsage(t *testing.T) {
	cache := NewMemoryResponseCache()
	response := UpstreamResponse{StatusCode: 200, Body: []byte("hello"), Usage: map[string]any{"prompt_tokens_details": map[string]any{"cached_tokens": 6}}}
	cache.Set("key", response, time.Now().Add(time.Hour))
	response.Body[0] = 'x'
	response.Usage["prompt_tokens_details"].(map[string]any)["cached_tokens"] = 999
	first, ok := cache.Get("key", time.Now())
	if !ok || NormalizeUsage(first.Usage).CacheHitTokens != 6 {
		t.Fatalf("write alias=%+v", first)
	}
	first.Usage["prompt_tokens_details"].(map[string]any)["cached_tokens"] = 888
	if string(first.Body) != "hello" {
		t.Fatalf("write body alias=%q", first.Body)
	}
	first.Body[0] = 'y'
	second, _ := cache.Get("key", time.Now())
	if NormalizeUsage(second.Usage).CacheHitTokens != 6 {
		t.Fatalf("read alias=%+v", second)
	}
	if string(second.Body) != "hello" {
		t.Fatalf("read body alias=%q", second.Body)
	}
}

func TestCachePipelineIdentityIsolation(t *testing.T) {
	p, _ := cacheTestPipeline()
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	model := DefaultCatalog[0]
	key, err := BuildPipelineCacheKey(p.Meta, "openai", "chat", model, ReasoningNone, request)
	if err != nil {
		t.Fatal(err)
	}
	for _, field := range []string{"region", "api_key", "revision", "client_key", "model", "effort", "protocol"} {
		t.Run(field, func(t *testing.T) {
			meta, selected, effort, protocol := p.Meta, model, ReasoningNone, "chat"
			switch field {
			case "region":
				meta.Region = "us-west"
			case "api_key":
				meta.APIKeyID = "key-2"
			case "revision":
				meta.ModelRevision = "v2"
			case "client_key":
				meta.ClientPromptCacheKey = "other"
			case "model":
				selected = DefaultCatalog[1]
			case "effort":
				effort = ReasoningHigh
			case "protocol":
				protocol = "responses"
			}
			other, err := BuildPipelineCacheKey(meta, "openai", protocol, selected, effort, request)
			if err != nil || key == other {
				t.Fatalf("identity collision: %s err=%v", field, err)
			}
		})
	}
	for _, field := range []string{"region", "api_key", "revision", "secret"} {
		t.Run("missing_"+field, func(t *testing.T) {
			p, u := cacheTestPipeline()
			switch field {
			case "region":
				p.Meta.Region = ""
			case "api_key":
				p.Meta.APIKeyID = ""
			case "revision":
				p.Meta.ModelRevision = ""
			case "secret":
				p.Meta.CacheSecret = ""
			}
			for i := 0; i < 2; i++ {
				result, err := executeCacheTest(p, "chat")
				if err != nil || result.CacheHit || result.CacheEligible || result.CacheReason != "cache_identity_incomplete" {
					t.Fatalf("result=%+v err=%v", result, err)
				}
			}
			if u.calls != 2 {
				t.Fatalf("calls=%d", u.calls)
			}
		})
	}
}

func TestMemoryCacheConcurrentCopies(t *testing.T) {
	cache := &MemoryResponseCache{}
	var workers sync.WaitGroup
	for i := 0; i < 32; i++ {
		workers.Add(1)
		go func() {
			defer workers.Done()
			for j := 0; j < 20; j++ {
				cache.Set("shared", UpstreamResponse{StatusCode: 200, Body: []byte("body"), Usage: map[string]any{"prompt_tokens": 10}}, time.Now().Add(time.Minute))
				response, ok := cache.Get("shared", time.Now())
				if !ok {
					t.Error("unexpected cache miss")
					return
				}
				response.Usage["prompt_tokens"] = 99
				response.Body[0] = 'x'
			}
		}()
	}
	workers.Wait()
}

func TestCachePipelineInitialSelectionIsNotUpgrade(t *testing.T) {
	p, _ := cacheTestPipeline()
	p.Gateway.Catalog = p.Gateway.Catalog[2:3]
	if _, err := executeCacheTest(p, "chat"); err != nil {
		t.Fatal(err)
	}
	if daily := p.Usage.Snapshot(); len(daily) != 1 || daily[0].Upgrades != 0 {
		t.Fatalf("initial selection counted as upgrade: %+v", daily)
	}
}
