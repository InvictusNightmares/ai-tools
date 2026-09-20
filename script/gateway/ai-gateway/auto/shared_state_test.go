package autogateway

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"local/ai-gateway/service"
)

func TestSharedStateChildProcess(t *testing.T) {
	path := os.Getenv("GATEWAY_TEST_SHARED_STATE")
	if path == "" {
		return
	}
	store, err := NewFileSessionStateStore(path)
	if err != nil {
		t.Fatal(err)
	}
	for i := 0; i < 25; i++ {
		if err := store.Transaction(time.Now(), func(tx SessionStateStore) error {
			state := tx.Load("counter", time.Now())
			state.Turn++
			state.HasCurrent = true
			return tx.Save("counter", state, time.Now())
		}); err != nil {
			t.Fatal(err)
		}
	}
}
func TestSharedStateAtomicAcrossProcessesAndCorruptionFailsClosed(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	var wg sync.WaitGroup
	for i := 0; i < 4; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			cmd := exec.Command(os.Args[0], "-test.run=^TestSharedStateChildProcess$")
			cmd.Env = append(os.Environ(), "GATEWAY_TEST_SHARED_STATE="+path)
			if out, err := cmd.CombinedOutput(); err != nil {
				t.Errorf("child failed: %s %v", out, err)
			}
		}()
	}
	wg.Wait()
	store, err := NewFileSessionStateStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := store.Load("counter", time.Now()).Turn; got != 100 {
		t.Fatalf("lost updates: %d", got)
	}
	if err := os.WriteFile(path, []byte("corrupt"), 0600); err != nil {
		t.Fatal(err)
	}
	p := sessionTestPipeline()
	p.StateStore = store
	u := &recordingUpstream{}
	p.Upstream = u
	if _, err := executeSession(p, "counter", 1); err == nil || err.Error() != "session_state_unavailable" || u.calls != 0 {
		t.Fatalf("corrupt state routed: %v", err)
	}
}
func TestSharedRouteTransitionsAndAtomicToolBindings(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	store1, _ := NewFileSessionStateStore(path)
	store2, _ := NewFileSessionStateStore(path)
	first, second := sessionTestPipeline(), sessionTestPipeline()
	first.StateStore = store1
	second.StateStore = store2
	var wg sync.WaitGroup
	for i := 0; i < 40; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			p := first
			if i%2 != 0 {
				p = second
			}
			if _, err := executeSession(p, "same-session", 0); err != nil {
				t.Error(err)
			}
		}(i)
	}
	wg.Wait()
	meta := PipelineMeta{Region: "tokyo", APIKeyID: "key", SessionID: "same-session"}
	if got := store1.Load(sessionStoreKey(meta), time.Now()).Turn; got != 40 {
		t.Fatalf("route transition lost: %d", got)
	}
	state := NewRouteState()
	state.HasCurrent = true
	state.CurrentModel = "gpt-5.6-terra"
	model := Model{Name: state.CurrentModel}
	bind := func(p *Pipeline, requestID string, ids []string) error {
		m := meta
		m.RequestID = requestID
		return p.saveToolRound("responses", m, PipelineResult{Decision: RouteDecision{State: state, SelectedModel: &model}, Upstream: UpstreamResponse{Complete: true, ToolCallIDs: ids}})
	}
	if err := bind(first, "first", []string{"collision"}); err != nil {
		t.Fatal(err)
	}
	if err := bind(second, "second", []string{"fresh", "collision"}); err == nil {
		t.Fatal("duplicate accepted")
	}
	if store1.Load(toolBindingKey(meta, "responses", "fresh"), time.Now()).HasCurrent {
		t.Fatal("partial tool transaction persisted")
	}
	m := meta
	m.APIKeyID = "other"
	if store1.Load(toolBindingKey(m, "responses", "collision"), time.Now()).HasCurrent {
		t.Fatal("cross-key binding")
	}
}
func TestSharedClassifierCacheRestartAndKeyIsolation(t *testing.T) {
	var calls atomic.Int64
	inner := taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) {
		calls.Add(1)
		assessment := TaskAssessment{Complexity: "simple", TaskType: "quick_qa", Confidence: 1}
		r := classificationFromAssessment(Request{}, assessment)
		r.Assessment = &assessment
		return r, nil
	})
	path := filepath.Join(t.TempDir(), "classifier.json")
	create := func() *CachedTaskClassifier {
		return &CachedTaskClassifier{Inner: inner, Secret: "shared-secret", Version: "test-v1", Shared: &service.JSONCache{File: service.TransactionFile{Path: path}, Capacity: 16}}
	}
	req := Request{Messages: []Message{{Role: "user", Content: "private synthetic marker"}}}
	meta := PipelineMeta{Region: "tokyo", APIKeyID: "one", SessionID: "main"}
	if _, err := create().Classify(context.Background(), req, meta); err != nil {
		t.Fatal(err)
	}
	if c, err := create().Classify(context.Background(), req, meta); err != nil || !c.Trace.CacheHit || calls.Load() != 1 {
		t.Fatal("cache was not shared")
	}
	meta.APIKeyID = "two"
	if c, err := create().Classify(context.Background(), req, meta); err != nil || c.Trace.CacheHit || calls.Load() != 2 {
		t.Fatal("cross-key cache hit")
	}
	raw, _ := os.ReadFile(path)
	var data map[string]any
	if json.Unmarshal(raw, &data) != nil {
		t.Fatal("cache invalid")
	}
	if strings.Contains(string(raw), "private synthetic marker") {
		t.Fatal("prompt was persisted in classification cache")
	}
	info, _ := os.Stat(path)
	if info.Mode().Perm() != 0600 {
		t.Fatal(fmt.Sprint(info.Mode()))
	}
}
