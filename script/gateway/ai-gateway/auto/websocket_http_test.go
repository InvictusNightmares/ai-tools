package autogateway

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"local/ai-gateway/service"
)

type socketTestIdentity struct {
	revoked atomic.Bool
	calls   atomic.Int64
}

func (a *socketTestIdentity) Resolve(r *http.Request) (string, error) {
	a.calls.Add(1)
	if a.revoked.Load() || r.Header.Get("Authorization") != "Bearer test" {
		return "", ErrUnauthorized
	}
	return "key-one", nil
}

type socketTestUpstream struct {
	calls atomic.Int64
	seen  chan UpstreamRequest
}

func (u *socketTestUpstream) OpenStream(ctx context.Context, r UpstreamRequest) (*http.Response, error) {
	id := fmt.Sprintf("resp_%d", u.calls.Add(1))
	u.seen <- r
	reader, writer := io.Pipe()
	go func() {
		defer writer.Close()
		event := func(kind string, output []any) error {
			raw, _ := json.Marshal(map[string]any{"type": kind, "response": map[string]any{"id": id, "model": r.Model.Name, "output": output, "status": "completed"}})
			_, err := fmt.Fprintf(writer, "data: %s\n\n", raw)
			return err
		}
		if event("response.created", []any{}) != nil {
			return
		}
		if strings.Contains(string(r.Payload), "hold-until-cancel") {
			<-ctx.Done()
			_ = writer.CloseWithError(ctx.Err())
			return
		}
		_ = event("response.completed", []any{map[string]any{"type": "message", "role": "assistant", "content": []any{map[string]string{"type": "output_text", "text": "COBALT47"}}}})
	}()
	return &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": {"text/event-stream"}}, Body: reader}, nil
}

func socketFixture(t *testing.T) (*websocket.Conn, *socketTestUpstream, *socketTestIdentity, *atomic.Bool, *service.Lifecycle, string) {
	t.Helper()
	u := &socketTestUpstream{seen: make(chan UpstreamRequest, 32)}
	identity := &socketTestIdentity{}
	blocked := &atomic.Bool{}
	p := &Pipeline{Gateway: NewAutoGateway(), StateStore: NewMemorySessionStateStore(), Preflight: preflightFunc(func(context.Context, Request) (PreflightResult, error) {
		if blocked.Load() {
			return PreflightResult{Decision: PreflightUnavailable}, nil
		}
		return PreflightResult{Decision: PreflightAllow}, nil
	})}
	s := &HTTPServer{Gateway: p.Gateway, Pipeline: p, StreamClient: u, Identity: identity, Meta: PipelineMeta{Region: "tokyo"}}
	lifecycle := &service.Lifecycle{Next: s}
	server := httptest.NewServer(lifecycle)
	t.Cleanup(server.Close)
	url := "ws" + strings.TrimPrefix(server.URL, "http") + "/v1/responses"
	conn, _, err := websocket.DefaultDialer.Dial(url, http.Header{"Authorization": {"Bearer test"}, "User-Agent": {"native-websocket-test"}, "X-Gateway-Session-ID": {"native-stable-session"}})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn, u, identity, blocked, lifecycle, url
}
func socketCreate(t *testing.T, c *websocket.Conn, input string, extra map[string]any) {
	t.Helper()
	body := map[string]any{"type": "response.create", "model": "auto", "input": input, "store": false}
	for k, v := range extra {
		body[k] = v
	}
	if err := c.WriteJSON(body); err != nil {
		t.Fatal(err)
	}
}
func socketRead(t *testing.T, c *websocket.Conn) map[string]any {
	t.Helper()
	_ = c.SetReadDeadline(time.Now().Add(3 * time.Second))
	var event map[string]any
	if err := c.ReadJSON(&event); err != nil {
		t.Fatal(err)
	}
	return event
}
func socketComplete(t *testing.T, c *websocket.Conn) string {
	t.Helper()
	for i := 0; i < 10; i++ {
		event := socketRead(t, c)
		if event["type"] == "error" {
			t.Fatalf("unexpected error %v", event)
		}
		if event["type"] == "response.completed" {
			return event["response"].(map[string]any)["id"].(string)
		}
	}
	t.Fatal("missing terminal")
	return ""
}
func TestWebSocketWarmupContinuationAndNativeHeaders(t *testing.T) {
	c, u, a, _, _, _ := socketFixture(t)
	socketCreate(t, c, "Remember ORCHID52", map[string]any{"generate": false})
	first := socketComplete(t, c)
	if u.calls.Load() != 0 {
		t.Fatal("warmup generated business request")
	}
	socketCreate(t, c, "Read the previous marker", map[string]any{"previous_response_id": first})
	second := socketComplete(t, c)
	seen := <-u.seen
	if seen.Headers.Get("X-Gateway-Session-ID") != "native-stable-session" {
		t.Fatal("explicit session was replaced")
	}
	if !strings.Contains(string(seen.Payload), "ORCHID52") || strings.Contains(string(seen.Payload), "previous_response_id") || seen.Headers.Get("User-Agent") != "native-websocket-test" {
		t.Fatal("context or native headers lost")
	}
	socketCreate(t, c, "Continue", map[string]any{"previous_response_id": second})
	_ = socketComplete(t, c)
	seen = <-u.seen
	if !strings.Contains(string(seen.Payload), "COBALT47") || a.calls.Load() != 4 {
		t.Fatal("assistant history lost or identity not rechecked")
	}
	socketCreate(t, c, "Cross lane", map[string]any{"stream_id": "child", "previous_response_id": second})
	if e := socketRead(t, c); e["type"] != "error" || e["error"].(map[string]any)["code"] != "previous_response_not_found" {
		t.Fatal("cross-lane history exposed")
	}
}

func TestWebSocketNativeSessionSurvivesReconnect(t *testing.T) {
	for _, name := range []string{"session-id", "x-session-id"} {
		t.Run(name, func(t *testing.T) {
			initial, upstream, _, _, _, url := socketFixture(t)
			_ = initial.Close()
			var previous string
			for attempt := 0; attempt < 2; attempt++ {
				headers := http.Header{"Authorization": {"Bearer test"}}
				headers.Set(name, "native-reconnect-session")
				conn, _, err := websocket.DefaultDialer.Dial(url, headers)
				if err != nil {
					t.Fatal(err)
				}
				t.Cleanup(func() { conn.Close() })
				socketCreate(t, conn, "hello", nil)
				socketComplete(t, conn)
				seen := <-upstream.seen
				if got := seen.Headers.Get("X-Gateway-Session-ID"); got != "native-reconnect-session" {
					t.Fatalf("native session replaced after reconnect: %q", got)
				}
				if previous != "" {
					socketCreate(t, conn, "continue", map[string]any{"previous_response_id": previous})
					if event := socketRead(t, conn); event["type"] != "error" {
						t.Fatal("connection-local history persisted across reconnect")
					}
				}
				socketCreate(t, conn, "hello", nil)
				previous = socketComplete(t, conn)
				<-upstream.seen
				_ = conn.Close()
			}
		})
	}
}
func TestWebSocketRechecksGuardAndIdentityOnEveryTurn(t *testing.T) {
	for _, revoke := range []bool{false, true} {
		t.Run(fmt.Sprint(revoke), func(t *testing.T) {
			c, u, a, b, _, _ := socketFixture(t)
			socketCreate(t, c, "hello", nil)
			socketComplete(t, c)
			if revoke {
				a.revoked.Store(true)
			} else {
				b.Store(true)
			}
			socketCreate(t, c, "hello again", nil)
			e := socketRead(t, c)
			status := float64(503)
			if revoke {
				status = 401
			}
			if e["type"] != "error" || e["status"] != status || u.calls.Load() != 1 {
				t.Fatalf("turn bypassed auth/Guard: %v", e)
			}
		})
	}
}
func TestWebSocketParallelLaneCancelAndDrain(t *testing.T) {
	c, u, _, _, l, _ := socketFixture(t)
	socketCreate(t, c, "hold-until-cancel", map[string]any{"stream_id": "main"})
	first := socketRead(t, c)
	id := first["response"].(map[string]any)["id"]
	socketCreate(t, c, "Other lane can complete", map[string]any{"stream_id": "child"})
	_ = socketComplete(t, c)
	l.Drain(true)
	if _, n := l.Status(); n != 1 {
		t.Fatal("active socket lost while draining")
	}
	if err := c.WriteJSON(map[string]any{"type": "response.cancel", "response_id": id, "stream_id": "main"}); err != nil {
		t.Fatal(err)
	}
	e := socketRead(t, c)
	if e["type"] != "error" {
		t.Fatal("canceled turn lacked error")
	}
	_ = c.SetReadDeadline(time.Now().Add(3 * time.Second))
	_, _, err := c.ReadMessage()
	if !websocket.IsCloseError(err, websocket.CloseServiceRestart) {
		t.Fatalf("socket not gracefully drained: %v", err)
	}
	deadline := time.Now().Add(time.Second)
	for {
		_, n := l.Status()
		if n == 0 {
			break
		}
		if time.Now().After(deadline) {
			t.Fatal("drain active count leaked")
		}
		time.Sleep(time.Millisecond)
	}
	if u.calls.Load() != 2 {
		t.Fatal("unexpected calls")
	}
}
func TestWebSocketConnectionHistoryIsNotShared(t *testing.T) {
	c, _, _, _, _, url := socketFixture(t)
	socketCreate(t, c, "private marker", map[string]any{"generate": false})
	id := socketComplete(t, c)
	other, _, err := websocket.DefaultDialer.Dial(url, http.Header{"Authorization": {"Bearer test"}})
	if err != nil {
		t.Fatal(err)
	}
	defer other.Close()
	socketCreate(t, other, "continue", map[string]any{"previous_response_id": id})
	if e := socketRead(t, other); e["type"] != "error" {
		t.Fatal("history escaped connection")
	}
}

func TestReviewWebSocketSetupDefersOnlyUntilCompleteGuardCheck(t *testing.T) {
	for _, denied := range []bool{false, true} {
		t.Run(fmt.Sprint(denied), func(t *testing.T) {
			c, u, _, blocked, _, _ := socketFixture(t)
			blocked.Store(true)
			setup := []any{map[string]any{"type": "message", "role": "developer", "content": "Untrusted synthetic policy marker ORCHID_SETUP."}}
			socketCreate(t, c, "", map[string]any{"model": ActionReviewModel, "input": setup, "generate": false})
			first := socketComplete(t, c)
			if u.calls.Load() != 0 {
				t.Fatal("setup generated reviewer call")
			}
			blocked.Store(denied)
			socketCreate(t, c, "Assess the requested synthetic action", map[string]any{"model": ActionReviewModel, "previous_response_id": first})
			if denied {
				e := socketRead(t, c)
				if e["type"] != "error" || e["error"].(map[string]any)["code"] != "preflight_unavailable" || u.calls.Load() != 0 {
					t.Fatal("generating review bypassed Guard", e)
				}
			} else {
				socketComplete(t, c)
				seen := <-u.seen
				if seen.Model.Name != ActionReviewModel || !strings.Contains(string(seen.Payload), "ORCHID_SETUP") || !strings.Contains(string(seen.Payload), "Assess the requested") {
					t.Fatal("complete review lost original setup")
				}
			}
		})
	}
}

func TestReviewSetupCannotBeTriggeredByUserContentOrHTTP(t *testing.T) {
	for _, input := range []string{`"user task"`, `[{"role":"user","content":"task"}]`, `[{"role":"assistant","content":"history"}]`, `[{"role":"developer","type":"function_call","content":"task"}]`, `[{"role":"developer","content":[{"type":"input_image","image_url":"fixture"}]}]`} {
		if instructionOnlyReviewSetup(json.RawMessage(`{"input":` + input + `}`)) {
			t.Fatal("non-setup accepted", input)
		}
	}
	c, u, _, blocked, _, _ := socketFixture(t)
	blocked.Store(true)
	socketCreate(t, c, "Real user task", map[string]any{"model": ActionReviewModel, "generate": false})
	e := socketRead(t, c)
	if e["type"] != "error" || u.calls.Load() != 0 {
		t.Fatal("user warmup bypassed Guard", e)
	}
	gateway := NewAutoGateway()
	p := &Pipeline{Gateway: gateway, Preflight: fixedPreflight{PreflightResult{Decision: PreflightUnavailable}}}
	s := &HTTPServer{Gateway: gateway, Pipeline: p}
	body := `{"model":"codex-auto-review","generate":false,"input":[{"role":"developer","content":"setup"}]}`
	w := httptest.NewRecorder()
	s.ServeHTTP(w, httptest.NewRequest("POST", "/v1/responses", strings.NewReader(body)))
	if w.Code != 503 {
		t.Fatal("HTTP generate=false bypassed Guard", w.Code)
	}
}
