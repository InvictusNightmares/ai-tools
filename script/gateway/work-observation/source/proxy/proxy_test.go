package proxy

import (
	"bufio"
	"bytes"
	"context"
	"crypto/sha1"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"testing"
	"time"

	"local/work-observation/source/capture"
)

type sink struct {
	mu      sync.Mutex
	records []capture.Event
	gate    chan struct{}
	once    sync.Once
	started chan struct{}
}

func (s *sink) Begin(capture.Event) error {
	if s.gate != nil {
		s.once.Do(func() { close(s.started) })
		<-s.gate
	}
	return nil
}
func (s *sink) Write(e capture.Event) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.records = append(s.records, e)
	return nil
}
func (s *sink) StoredBytes() int64 { return 0 }
func setup(t *testing.T, upstream string, s *sink, enabled bool) (*httptest.Server, *capture.Engine) {
	t.Helper()
	engine := capture.NewEngine(s, capture.Limits{Queue: 128, MemoryBytes: 8 << 20, BodyBytes: 2 << 20}, enabled)
	handler, err := New(Config{Upstream: upstream, Region: "verified-region", Ingress: "isolated-listener", Version: "test", IdentitySalt: bytes.Repeat([]byte{1}, 32)}, engine)
	if err != nil {
		t.Fatal(err)
	}
	frontend := httptest.NewServer(handler)
	t.Cleanup(func() { frontend.Close(); engine.Close() })
	return frontend, engine
}
func flush(t *testing.T, e *capture.Engine) {
	t.Helper()
	ch := make(chan struct{})
	if !e.Maintain(func() { close(ch) }) {
		t.Fatal("unexpected test queue full")
	}
	select {
	case <-ch:
	case <-time.After(2 * time.Second):
		t.Fatal("worker failed to drain")
	}
}
func TestProtocolsPreserveForwardingAndCaptureNoAuthenticationHeaders(t *testing.T) {
	cases := []struct{ name, path, body string }{
		{"codex", "/v1/responses", `{"model":"fixture","input":[{"role":"user","content":"literal password=fixture"}]}`},
		{"opencode", "/v1/chat/completions", `{"model":"fixture","messages":[{"role":"tool","tool_call_id":"c1","content":"tool literal"}]}`},
		{"hermes", "/v1/chat/completions", `{"model":"fixture","messages":[{"role":"user","content":"continue"}],"tools":[{"type":"function","function":{"name":"read","parameters":{"type":"object"}}}]}`},
		{"claude", "/v1/messages", `{"model":"fixture","system":"system literal","messages":[{"role":"user","content":[{"type":"tool_result","tool_use_id":"u1","content":"tool result"}]}]}`},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			headers := make(chan http.Header, 1)
			seen := make(chan string, 1)
			upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				b, _ := io.ReadAll(r.Body)
				seen <- string(b)
				headers <- r.Header.Clone()
				w.Header().Set("Content-Type", "application/json")
				w.Header().Set("X-Request-Id", "upstream-id")
				w.WriteHeader(201)
				_, _ = w.Write([]byte(`{"output":[{"role":"assistant","content":"literal reply"}]}`))
			}))
			defer upstream.Close()
			s := &sink{}
			front, e := setup(t, upstream.URL, s, true)
			r, _ := http.NewRequest("POST", front.URL+tc.path, strings.NewReader(tc.body))
			r.Header.Set("Content-Type", "application/json")
			r.Header.Set("Authorization", "Bearer synthetic-transport-secret")
			r.Header.Set("Cookie", "synthetic-cookie")
			r.Header.Set("User-Agent", tc.name+"/fixture")
			r.Header.Set("Session-Id", "claimed-session")
			r.Header.Set("X-Observation-Ingress", "spoofed")
			r.Header.Set("X-Forwarded-For", "existing chain")
			resp, err := front.Client().Do(r)
			if err != nil {
				t.Fatal(err)
			}
			b, _ := io.ReadAll(resp.Body)
			resp.Body.Close()
			if resp.StatusCode != 201 || string(b) != `{"output":[{"role":"assistant","content":"literal reply"}]}` || <-seen != tc.body {
				t.Fatal("forwarded content changed")
			}
			h := <-headers
			if h.Get("User-Agent") != tc.name+"/fixture" || h.Get("Authorization") != "Bearer synthetic-transport-secret" || h.Get("X-Forwarded-For") != "existing chain" {
				t.Fatal("forwarded header changed")
			}
			flush(t, e)
			s.mu.Lock()
			defer s.mu.Unlock()
			if len(s.records) != 1 {
				t.Fatal(len(s.records))
			}
			ev := s.records[0]
			if ev.Region != "verified-region" || ev.Ingress != "isolated-listener" || ev.Association != "client_claimed" || ev.Status != 201 || len(ev.Missing) > 0 || len(ev.Request) == 0 || len(ev.Response) == 0 {
				t.Fatalf("bad observation: %s %s %v", ev.Region, ev.Outcome, ev.Missing)
			}
			encoded, _ := json.Marshal(ev)
			if bytes.Contains(encoded, []byte("synthetic-transport-secret")) || bytes.Contains(encoded, []byte("synthetic-cookie")) {
				t.Fatal("auth headers collected")
			}
		})
	}
}
func TestSSEForwardingIsImmediateAndCancelRetainsPrefix(t *testing.T) {
	ended := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer close(ended)
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = io.WriteString(w, "data: {\"delta\":\"prefix\"}\n\n")
		w.(http.Flusher).Flush()
		<-r.Context().Done()
	}))
	defer upstream.Close()
	s := &sink{}
	front, e := setup(t, upstream.URL, s, true)
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	r, _ := http.NewRequestWithContext(ctx, "POST", front.URL+"/v1/responses", strings.NewReader(`{"input":"hi"}`))
	r.Header.Set("Content-Type", "application/json")
	resp, err := front.Client().Do(r)
	if err != nil {
		t.Fatal(err)
	}
	reader := bufio.NewReader(resp.Body)
	line, err := reader.ReadString('\n')
	if err != nil || !strings.Contains(line, "prefix") {
		t.Fatal("first SSE event buffered")
	}
	cancel()
	resp.Body.Close()
	<-ended
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		flush(t, e)
		s.mu.Lock()
		n := len(s.records)
		s.mu.Unlock()
		if n > 0 {
			break
		}
		time.Sleep(time.Millisecond)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.records) != 1 || s.records[0].Outcome != "canceled" || !bytes.Contains(s.records[0].Response, []byte("prefix")) {
		t.Fatal("cancel evidence missing")
	}
}
func TestRequestBodyStreamsBeforeEOF(t *testing.T) {
	sawPrefix := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b := make([]byte, 5)
		_, _ = io.ReadFull(r.Body, b)
		close(sawPrefix)
		_, _ = io.Copy(io.Discard, r.Body)
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"ok":true}`)
	}))
	defer upstream.Close()
	s := &sink{}
	front, _ := setup(t, upstream.URL, s, true)
	rd, wr := io.Pipe()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	r, _ := http.NewRequestWithContext(ctx, "POST", front.URL+"/v1/responses", rd)
	r.Header.Set("Content-Type", "application/json")
	result := make(chan error, 1)
	go func() {
		resp, err := front.Client().Do(r)
		if err == nil {
			_, err = io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
		result <- err
	}()
	_, _ = wr.Write([]byte(`{"inp`))
	select {
	case <-sawPrefix:
	case <-ctx.Done():
		t.Fatal("request was buffered before forwarding")
	}
	_, _ = wr.Write([]byte(`ut":"literal"}`))
	wr.Close()
	if err := <-result; err != nil {
		t.Fatal(err)
	}
}

func TestCancellationBeforeHeadersIsNotUpstreamFailure(t *testing.T) {
	started := make(chan struct{})
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		close(started)
		<-r.Context().Done()
	}))
	defer upstream.Close()
	s := &sink{}
	front, e := setup(t, upstream.URL, s, true)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	r, _ := http.NewRequestWithContext(ctx, "POST", front.URL+"/v1/chat/completions", strings.NewReader(`{"model":"fixture","messages":[]}`))
	r.Header.Set("Content-Type", "application/json")
	done := make(chan error, 1)
	go func() {
		resp, err := front.Client().Do(r)
		if resp != nil {
			resp.Body.Close()
		}
		done <- err
	}()
	select {
	case <-started:
	case <-time.After(2 * time.Second):
		t.Fatal("origin not reached")
	}
	cancel()
	if err := <-done; err == nil {
		t.Fatal("expected canceled client")
	}
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		flush(t, e)
		s.mu.Lock()
		if len(s.records) > 0 {
			event := s.records[0]
			s.mu.Unlock()
			if event.Outcome != "canceled" || event.Status != 0 || len(event.Missing) != 0 {
				t.Fatalf("caller abort misclassified: %s status=%d gaps=%v", event.Outcome, event.Status, event.Missing)
			}
			return
		}
		s.mu.Unlock()
		time.Sleep(time.Millisecond)
	}
	t.Fatal("cancellation record missing")
}

func TestClaudeSessionAndAgentAreScopedToCredential(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"ok":true}`)
	}))
	defer upstream.Close()
	s := &sink{}
	front, e := setup(t, upstream.URL, s, true)
	for _, key := range []string{"fixture-a", "fixture-b"} {
		r, _ := http.NewRequest("GET", front.URL+"/v1/messages", nil)
		r.Header.Set("Authorization", "Bearer "+key)
		r.Header.Set("X-Claude-Code-Session-Id", "same-claimed-session")
		r.Header.Set("X-Claude-Code-Agent-Id", "same-agent")
		resp, err := front.Client().Do(r)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = io.Copy(io.Discard, resp.Body)
		resp.Body.Close()
	}
	flush(t, e)
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.records) != 2 {
		t.Fatal("missing request")
	}
	a, b := s.records[0], s.records[1]
	if a.SessionHash == "" || a.AgentHash == "" || a.SessionHash == b.SessionHash || a.AgentHash == b.AgentHash || a.Association != "client_claimed" {
		t.Fatal("unsafe native session association")
	}
}
func TestBlockedDiskDoesNotDelayBusinessResponse(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"ok":true}`)
	}))
	defer upstream.Close()
	s := &sink{gate: make(chan struct{}), started: make(chan struct{})}
	front, _ := setup(t, upstream.URL, s, true)
	defer close(s.gate)
	response := make(chan error, 1)
	go func() {
		r, err := front.Client().Get(front.URL)
		if err == nil {
			_, err = io.Copy(io.Discard, r.Body)
			r.Body.Close()
		}
		response <- err
	}()
	<-s.started
	select {
	case err := <-response:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(time.Second):
		t.Fatal("blocked storage blocked proxy")
	}
}
func TestDisabledCaptureAndAttachmentTransparency(t *testing.T) {
	var body bytes.Buffer
	mw := multipart.NewWriter(&body)
	_ = mw.WriteField("prompt", "ordinary prompt")
	p, _ := mw.CreateFormFile("image", "fixture.png")
	_, _ = p.Write([]byte("SYNTHETIC_IMAGE_BYTES"))
	_ = mw.Close()
	original := bytes.Clone(body.Bytes())
	seen := make(chan []byte, 2)
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		seen <- b
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"data":[{"b64_json":"SYNTHETIC_IMAGE_BYTES"}]}`)
	}))
	defer upstream.Close()
	s := &sink{}
	front, e := setup(t, upstream.URL, s, false)
	for i := 0; i < 2; i++ {
		r, _ := http.NewRequest("POST", front.URL+"/v1/images/edits", bytes.NewReader(original))
		r.Header.Set("Content-Type", mw.FormDataContentType())
		resp, err := front.Client().Do(r)
		if err != nil {
			t.Fatal(err)
		}
		b, _ := io.ReadAll(resp.Body)
		resp.Body.Close()
		if !bytes.Equal(<-seen, original) || !bytes.Contains(b, []byte("SYNTHETIC_IMAGE_BYTES")) {
			t.Fatal("attachment forwarding changed")
		}
		flush(t, e)
		if i == 0 {
			if len(s.records) != 0 {
				t.Fatal("disabled capture recorded body")
			}
			e.SetEnabled(true)
		}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.records) != 1 {
		t.Fatal("enabled request missing")
	}
	encoded, _ := json.Marshal(s.records[0])
	if bytes.Contains(encoded, []byte("SYNTHETIC_IMAGE_BYTES")) || !bytes.Contains(encoded, []byte("ordinary prompt")) {
		t.Fatal("attachment projection failed")
	}
}
func TestWebsocketUpgradeAndBidirectionalMessages(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		conn, rw, err := w.(http.Hijacker).Hijack()
		if err != nil {
			return
		}
		defer conn.Close()
		sum := sha1.Sum([]byte(r.Header.Get("Sec-WebSocket-Key") + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
		_, _ = fmt.Fprintf(rw, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n", base64.StdEncoding.EncodeToString(sum[:]))
		_ = rw.Flush()
		for i := 0; i < 2; i++ {
			header := make([]byte, 6)
			if _, err = io.ReadFull(rw, header); err != nil {
				return
			}
			n := int(header[1] & 127)
			payload := make([]byte, n)
			if _, err = io.ReadFull(rw, payload); err != nil {
				return
			}
			for j := range payload {
				payload[j] ^= header[2+j%4]
			}
			_, _ = conn.Write(append([]byte{0x81, byte(len(payload))}, payload...))
		}
	}))
	defer upstream.Close()
	s := &sink{}
	front, e := setup(t, upstream.URL, s, true)
	u, _ := url.Parse(front.URL)
	conn, err := net.Dial("tcp", u.Host)
	if err != nil {
		t.Fatal(err)
	}
	defer conn.Close()
	_ = conn.SetDeadline(time.Now().Add(2 * time.Second))
	_, _ = fmt.Fprintf(conn, "GET /v1/responses HTTP/1.1\r\nHost: %s\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n", u.Host)
	reader := bufio.NewReader(conn)
	resp, err := http.ReadResponse(reader, &http.Request{Method: "GET"})
	if err != nil || resp.StatusCode != 101 {
		t.Fatalf("upgrade failed: %v", err)
	}
	for _, value := range []string{`{"input":"first"}`, `{"input":"second"}`} {
		frame := []byte{0x81, 0x80 | byte(len(value)), 1, 2, 3, 4}
		for i, c := range []byte(value) {
			frame = append(frame, c^byte(i%4+1))
		}
		_, _ = conn.Write(frame)
		header := make([]byte, 2)
		if _, err = io.ReadFull(reader, header); err != nil {
			t.Fatal(err)
		}
		payload := make([]byte, int(header[1]))
		if _, err = io.ReadFull(reader, payload); err != nil || string(payload) != value {
			t.Fatal("WS payload changed")
		}
	}
	conn.Close()
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		flush(t, e)
		s.mu.Lock()
		n := len(s.records)
		s.mu.Unlock()
		if n >= 5 {
			break
		}
		time.Sleep(time.Millisecond)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	messages, summary := 0, 0
	for _, r := range s.records {
		if r.Kind == "websocket_message" {
			messages++
			if r.ConnectionID == "" || r.Sequence == 0 {
				t.Fatal("WS association missing")
			}
		} else if r.Kind == "websocket_connection" {
			summary++
		}
	}
	if messages != 4 || summary != 1 {
		t.Fatalf("messages %d summary %d", messages, summary)
	}
}

func TestSameAPIKeyAcrossClientAuthStylesHasSameIdentity(t *testing.T) {
	variants := []http.Header{{"Authorization": []string{"Bearer synthetic-key"}}, {"Authorization": []string{"bearer  synthetic-key"}}, {"X-Api-Key": []string{"synthetic-key"}}}
	var previous string
	for _, h := range variants {
		current := identity(bytes.Repeat([]byte{1}, 32), "region\x00"+credentialValue(h))
		if previous != "" && current != previous {
			t.Fatal("same Key split by auth header style")
		}
		previous = current
	}
}
