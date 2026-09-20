package autogateway

import (
	"context"
	"os"
	"sync"
	"testing"
	"time"
)

func TestFailedStateWriteDoesNotPublishMemoryState(t *testing.T) {
	parent := t.TempDir() + "/blocked"
	store, err := NewFileSessionStateStore(parent + "/state.json")
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(parent, []byte("not a directory"), 0600); err != nil {
		t.Fatal(err)
	}
	state := NewRouteState()
	state.HasCurrent = true
	state.CurrentModel = "gpt-6-astra"
	store.Save("session", state, time.Now())
	if store.Load("session", time.Now()).HasCurrent {
		t.Fatal("failed disk write was published as successful route state")
	}
}

func TestFileSessionStateStorePersistsOnlyRouteState(t *testing.T) {
	path := t.TempDir() + "/sessions/state.json"
	store, err := NewFileSessionStateStore(path)
	if err != nil {
		t.Fatal(err)
	}
	now := time.Unix(500, 0)
	state := NewRouteState()
	state.HasCurrent = true
	state.CurrentModel = "gpt-5.6-terra"
	state.SessionTTL = time.Hour
	store.Save("session-a", state, now)
	reloaded, err := NewFileSessionStateStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if got := reloaded.Load("session-a", now.Add(time.Minute)); got.CurrentModel != state.CurrentModel || !got.HasCurrent {
		t.Fatalf("reloaded state = %+v", got)
	}
	if got := reloaded.Load("session-a", now.Add(2*time.Hour)); got.HasCurrent {
		t.Fatal("expired state was returned")
	}
}

func sessionTestPipeline() *Pipeline {
	return &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, StateStore: NewMemorySessionStateStore(), CachePolicy: ResponseCachePolicy{}}
}

func executeSession(p *Pipeline, sessionID string, turn int) (PipelineResult, error) {
	return p.ExecuteWithMeta(context.Background(), "chat", "deepseek", "auto", Request{Messages: []Message{{Role: "user", Content: "hello"}}}, turn, false, false, false, false, PipelineMeta{SessionID: sessionID, Region: "tokyo", APIKeyID: "key", ModelRevision: "v1", CacheSecret: "secret"})
}

func TestSessionStateStoreSeparatesSessionsAndKeepsOneSessionSticky(t *testing.T) {
	p := sessionTestPipeline()
	at := time.Date(2026, 9, 15, 3, 0, 0, 0, time.UTC)
	p.Now = func() time.Time { return at }
	firstA, err := executeSession(p, "user-a/session-1", 1)
	if err != nil {
		t.Fatal(err)
	}
	secondA, err := executeSession(p, "user-a/session-1", 2)
	if err != nil {
		t.Fatal(err)
	}
	firstB, err := executeSession(p, "user-b/session-1", 1)
	if err != nil {
		t.Fatal(err)
	}
	if firstA.Decision.Action != "select" || secondA.Decision.Action != "keep" || firstB.Decision.Action != "select" {
		t.Fatalf("session actions: A1=%+v A2=%+v B1=%+v", firstA.Decision, secondA.Decision, firstB.Decision)
	}
}

func TestSessionStateStoreExpiresAndDoesNotUseSharedGatewayState(t *testing.T) {
	p := sessionTestPipeline()
	at := time.Date(2026, 9, 15, 3, 0, 0, 0, time.UTC)
	clock := at
	p.Now = func() time.Time { return clock }
	first, err := executeSession(p, "expiring", 1)
	if err != nil {
		t.Fatal(err)
	}
	if first.Decision.Action != "select" {
		t.Fatal(first.Decision)
	}
	p.Gateway.State = RouteState{HasCurrent: true, CurrentModel: "gpt-6-astra", CurrentTier: 4, CurrentReasoningEffort: ReasoningXHigh, SessionTTL: time.Hour}
	clock = at.Add(2 * time.Hour)
	expired, err := executeSession(p, "expiring", 2)
	if err != nil {
		t.Fatal(err)
	}
	if expired.Decision.Action != "select" || expired.Decision.SelectedModel.Name != "deepseek-flash" {
		t.Fatalf("expired/shared state leaked: %+v", expired.Decision)
	}
}

func TestSessionStateStoreConcurrentSessions(t *testing.T) {
	p := sessionTestPipeline()
	at := time.Date(2026, 9, 15, 3, 0, 0, 0, time.UTC)
	p.Now = func() time.Time { return at }
	var group sync.WaitGroup
	for i := 0; i < 32; i++ {
		group.Add(1)
		go func(i int) {
			defer group.Done()
			id := "session-" + string(rune('a'+i))
			if result, err := executeSession(p, id, 1); err != nil || result.Decision.Action != "select" {
				t.Errorf("id=%s result=%+v err=%v", id, result, err)
			}
		}(i)
	}
	group.Wait()
}
