package autogateway

import (
	"context"
	"sync"
	"testing"
	"time"
)

type blockingUpstream struct {
	mu    sync.Mutex
	calls int
	start chan struct{}
	gate  chan struct{}
}

func (u *blockingUpstream) Complete(context.Context, UpstreamRequest) (UpstreamResponse, error) {
	u.mu.Lock()
	u.calls++
	u.mu.Unlock()
	closeOnce(u.start)
	<-u.gate
	return UpstreamResponse{StatusCode: 200, Body: []byte(`{"ok":true}`), ResponseBytes: 11, Usage: map[string]any{"prompt_tokens": 3, "completion_tokens": 1}}, nil
}

func closeOnce(ch chan struct{}) {
	select {
	case <-ch:
	default:
		close(ch)
	}
}

func TestPipelineCoalescesConcurrentCacheMisses(t *testing.T) {
	upstream := &blockingUpstream{start: make(chan struct{}), gate: make(chan struct{})}
	pipeline := &Pipeline{
		Gateway:     NewAutoGateway(),
		Preflight:   fixedPreflight{result: PreflightResult{Decision: PreflightAllow}},
		Upstream:    upstream,
		Cache:       NewMemoryResponseCacheWithCapacity(8),
		CachePolicy: DefaultResponseCachePolicy(),
		Usage:       NewDailyUsageRecorder(),
		Meta:        PipelineMeta{Region: "test", APIKeyID: "key-1", ModelRevision: "rev-1", CacheSecret: "secret"},
		Now:         func() time.Time { return time.Unix(100, 0) },
	}
	request := Request{Messages: []Message{{Role: "user", Content: "same"}}}
	results := make(chan PipelineResult, 2)
	errs := make(chan error, 2)
	go func() {
		result, err := pipeline.Execute(context.Background(), "chat", "openai", "auto", request, 1, false, false, false, false)
		results <- result
		errs <- err
	}()
	select {
	case <-upstream.start:
	case <-time.After(time.Second):
		t.Fatal("upstream did not start")
	}
	go func() {
		result, err := pipeline.Execute(context.Background(), "chat", "openai", "auto", request, 1, false, false, false, false)
		results <- result
		errs <- err
	}()
	time.Sleep(20 * time.Millisecond)
	close(upstream.gate)
	for range 2 {
		if err := <-errs; err != nil {
			t.Fatalf("execute error: %v", err)
		}
		<-results
	}
	upstream.mu.Lock()
	calls := upstream.calls
	upstream.mu.Unlock()
	if calls != 1 {
		t.Fatalf("upstream calls = %d, want 1", calls)
	}
	entries := pipeline.Usage.Snapshot()
	if len(entries) != 1 || entries[0].Requests != 2 || entries[0].Attempts != 1 {
		t.Fatalf("usage = %+v, want two requests and one attempt", entries)
	}
}

func TestMemoryResponseCacheCapacityEvictsLeastRecentlyUsed(t *testing.T) {
	cache := NewMemoryResponseCacheWithCapacity(2)
	now := time.Unix(200, 0)
	cache.Set("a", UpstreamResponse{StatusCode: 200, Body: []byte("a")}, now.Add(time.Hour))
	cache.Set("b", UpstreamResponse{StatusCode: 200, Body: []byte("b")}, now.Add(time.Hour))
	if _, ok := cache.Get("a", now.Add(time.Second)); !ok {
		t.Fatal("a should be present")
	}
	cache.Set("c", UpstreamResponse{StatusCode: 200, Body: []byte("c")}, now.Add(time.Hour))
	if _, ok := cache.Get("b", now.Add(2*time.Second)); ok {
		t.Fatal("least recently used b should be evicted")
	}
	if _, ok := cache.Get("a", now.Add(2*time.Second)); !ok {
		t.Fatal("recently used a should remain")
	}
}
