package autogateway

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

func TestRuntimeCircuitIsolationSingleRecoveryAndCancellation(t *testing.T) {
	now := time.Unix(1000, 0)
	h := &RuntimeHealth{Now: func() time.Time { return now }}
	meta := PipelineMeta{Region: "tokyo", APIKeyID: "key-a"}
	for i := 0; i < 3; i++ {
		h.Observe(meta, "responses", "deepseek-flash", UpstreamResponse{StatusCode: 503}, errors.New("rejected"), time.Second)
	}
	if h.Acquire(meta, "responses", "deepseek-flash") {
		t.Fatal("open circuit admitted request")
	}
	for _, other := range []PipelineMeta{{Region: "us", APIKeyID: "key-a"}, {Region: "tokyo", APIKeyID: "key-b"}} {
		if !h.Acquire(other, "responses", "deepseek-flash") {
			t.Fatal("cross-identity circuit pollution")
		}
	}
	if !h.Acquire(meta, "chat", "deepseek-flash") {
		t.Fatal("cross-protocol circuit pollution")
	}
	now = now.Add(31 * time.Second)
	var admitted atomic.Int32
	var wg sync.WaitGroup
	for i := 0; i < 32; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if h.Acquire(meta, "responses", "deepseek-flash") {
				admitted.Add(1)
			}
		}()
	}
	wg.Wait()
	if admitted.Load() != 1 {
		t.Fatalf("recovery probes=%d", admitted.Load())
	}
	h.Observe(meta, "responses", "deepseek-flash", UpstreamResponse{}, context.Canceled, time.Second)
	if !h.Acquire(meta, "responses", "deepseek-flash") {
		t.Fatal("canceled recovery never released")
	}
	h.Observe(meta, "responses", "deepseek-flash", UpstreamResponse{StatusCode: 200, Complete: true}, nil, time.Second)
	if h.Snapshot(meta, "responses", nil)["deepseek-flash"].Unavailable {
		t.Fatal("success did not recover circuit")
	}
}

type healthTestUpstream struct {
	calls     []string
	status    int
	ambiguous bool
}

func (u *healthTestUpstream) Complete(_ context.Context, r UpstreamRequest) (UpstreamResponse, error) {
	u.calls = append(u.calls, r.Model.Name)
	if len(u.calls) == 1 {
		if u.ambiguous {
			return UpstreamResponse{}, context.DeadlineExceeded
		}
		return UpstreamResponse{StatusCode: u.status}, errors.New("rejected")
	}
	return UpstreamResponse{StatusCode: 200, Complete: true, Body: []byte(`{"ok":true}`), ResponseModel: r.Model.Name, Usage: map[string]any{"input_tokens": 12, "output_tokens": 4}}, nil
}
func TestRuntimeFailoverCountsBothAttemptsAndPreservesGuardOrdering(t *testing.T) {
	for _, status := range []int{429, 502, 503, 504, 401, 403, 400} {
		t.Run(fmt.Sprint(status), func(t *testing.T) {
			u := &healthTestUpstream{status: status}
			guardCalls := 0
			p := &Pipeline{Health: &RuntimeHealth{}, Gateway: NewAutoGateway(), StateStore: NewMemorySessionStateStore(), Usage: NewDailyUsageRecorder(), Upstream: u,
				Preflight: preflightFunc(func(context.Context, Request) (PreflightResult, error) {
					guardCalls++
					return PreflightResult{Decision: PreflightAllow}, nil
				})}
			meta := PipelineMeta{Region: "tokyo", APIKeyID: "key-a", SessionID: "session"}
			result, err := p.ExecuteWithMeta(context.Background(), "responses", "", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 0, false, false, false, false, meta)
			want := 1
			if transientProviderStatus(status) {
				want = 2
			}
			if len(u.calls) != want || guardCalls != 1 || (want == 2 && (err != nil || u.calls[0] == u.calls[1] || result.Decision.Action != "failover")) {
				t.Fatalf("calls=%v guard=%d err=%v", u.calls, guardCalls, err)
			}
			attempts, outputs, failures := 0, 0, 0
			for _, row := range p.Usage.Snapshot() {
				attempts += row.Attempts
				outputs += row.OutputTokens
				failures += row.Failures
			}
			if attempts != want || failures != 1 || (want == 2 && outputs != 4) {
				t.Fatalf("usage=%+v", p.Usage.Snapshot())
			}
		})
	}
	u := &healthTestUpstream{ambiguous: true}
	p := &Pipeline{Health: &RuntimeHealth{}, Gateway: NewAutoGateway(), Upstream: u, Preflight: fixedPreflight{PreflightResult{Decision: PreflightAllow}}}
	_, _ = p.Execute(context.Background(), "responses", "", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, 0, false, false, false, false)
	if len(u.calls) != 1 {
		t.Fatal("ambiguous timeout was replayed")
	}
	p.Preflight = fixedPreflight{PreflightResult{Decision: PreflightUnavailable}}
	_, _ = p.Execute(context.Background(), "responses", "", "auto", Request{}, 0, false, false, false, false)
	if len(u.calls) != 1 {
		t.Fatal("Guard failure reached upstream")
	}
}

type healthStreamUpstream struct {
	calls    []string
	truncate bool
}

func (u *healthStreamUpstream) OpenStream(_ context.Context, r UpstreamRequest) (*http.Response, error) {
	u.calls = append(u.calls, r.Model.Name)
	status := 200
	body := ""
	if len(u.calls) == 1 && !u.truncate {
		status = 503
		body = `{"error":"temporarily_unavailable"}`
	} else {
		body = `data: {"type":"response.created","response":{"id":"fixture","model":"` + r.Model.Name + `"}}` + "\n\n"
		if !u.truncate {
			body += `data: {"type":"response.completed","response":{"id":"fixture","model":"` + r.Model.Name + `","status":"completed","output":[],"usage":{"input_tokens":10,"output_tokens":2}}}` + "\n\n"
		}
	}
	return &http.Response{StatusCode: status, Header: http.Header{"Content-Type": {"text/event-stream"}}, Body: io.NopCloser(strings.NewReader(body))}, nil
}
func TestRuntimeStreamFailoverBeforeHeadersAndNeverAfterOutput(t *testing.T) {
	for _, truncate := range []bool{false, true} {
		u := &healthStreamUpstream{truncate: truncate}
		p := &Pipeline{Health: &RuntimeHealth{}, Gateway: NewAutoGateway(), Usage: NewDailyUsageRecorder(), Preflight: fixedPreflight{PreflightResult{Decision: PreflightAllow}}}
		s := &HTTPServer{Gateway: p.Gateway, Pipeline: p, StreamClient: u, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "key-a", SessionID: "stream"}}
		w := httptest.NewRecorder()
		s.ServeHTTP(w, httptest.NewRequest("POST", "/v1/responses", strings.NewReader(`{"model":"auto","input":"hello","stream":true}`)))
		want := 2
		if truncate {
			want = 1
		}
		if len(u.calls) != want || w.Code != 200 || strings.Contains(w.Body.String(), "temporarily_unavailable") {
			t.Fatalf("calls=%v status=%d body=%s", u.calls, w.Code, w.Body)
		}
		attempts := 0
		for _, row := range p.Usage.Snapshot() {
			attempts += row.Attempts
		}
		if attempts != want {
			t.Fatalf("usage attempts=%d want=%d", attempts, want)
		}
	}
}

func TestRuntimeUnavailableToolBindingFailsClosed(t *testing.T) {
	state := NewRouteState()
	state.HasCurrent = true
	state.CurrentModel = "gpt-5.6-terra"
	state.CurrentTier = 2
	state.ToolLoopLocked = true
	decision := DecideRoute(state, Classification{Intent: "coding", Score: 40}, DefaultCatalog, map[string]Health{"gpt-5.6-terra": {Unavailable: true}}, 2, time.Now(), false, true, false)
	if decision.SelectedModel != nil || decision.Reason != "tool_provider_unavailable" {
		t.Fatalf("decision=%+v", decision)
	}
	p := &Pipeline{Health: &RuntimeHealth{}}
	request := Request{Messages: []Message{{Role: "tool", ToolCallID: "call-1", Content: "fixture"}}}
	if p.mayFailover(request, UpstreamResponse{StatusCode: 503}, errors.New("reject")) {
		t.Fatal("tool round was replayed")
	}
}

func TestFailoverDoesNotLeaveCoalescedCacheMissStuck(t *testing.T) {
	u := &healthTestUpstream{status: 503}
	p := &Pipeline{Health: &RuntimeHealth{}, Gateway: NewAutoGateway(), Cache: NewMemoryResponseCache(), CachePolicy: DefaultResponseCachePolicy(), Upstream: u, StateStore: NewMemorySessionStateStore(), Preflight: fixedPreflight{PreflightResult{Decision: PreflightAllow}}}
	meta := PipelineMeta{Region: "tokyo", APIKeyID: "key-a", SessionID: "cache-session", ModelRevision: "test", CacheSecret: "private-fixture"}
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	first, err := p.ExecuteWithMeta(ctx, "responses", "", "auto", request, 0, true, false, false, false, meta)
	if err != nil || first.CacheEligible {
		t.Fatalf("first=%+v err=%v", first, err)
	}
	_, err = p.ExecuteWithMeta(ctx, "responses", "", "auto", request, 0, true, false, false, false, meta)
	if err != nil || len(p.inflight) != 0 || len(u.calls) != 3 {
		t.Fatalf("err=%v calls=%v inflight=%d", err, u.calls, len(p.inflight))
	}
}
