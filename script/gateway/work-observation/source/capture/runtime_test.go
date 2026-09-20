package capture

import (
	"bytes"
	"compress/flate"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func fixtureEvent(id string) Event {
	return Event{Schema: SchemaVersion, ContentPolicy: LiteralContentPolicy, ID: id, At: time.Now().UTC(), Region: "synthetic", Ingress: "isolated", Kind: "http_exchange", Protocol: "responses", Outcome: "completed", Version: "test", Request: json.RawMessage(`{"input":"literal password=fixture"}`)}
}
func disk(t *testing.T, limit int64) *DiskStore {
	t.Helper()
	s, err := NewDiskStore(t.TempDir(), limit)
	if err != nil {
		t.Fatal(err)
	}
	s.free = func(string) (uint64, error) { return 1 << 40, nil }
	t.Cleanup(func() { s.Close() })
	return s
}
func exportRecords(t *testing.T, s *DiskStore) []Event {
	t.Helper()
	var b bytes.Buffer
	if _, err := Export(s.root, &b, time.Time{}); err != nil {
		t.Fatal(err)
	}
	var out []Event
	decoder := json.NewDecoder(&b)
	for {
		var e Event
		err := decoder.Decode(&e)
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		out = append(out, e)
	}
	return out
}
func TestStorePlaintextIntegrityAndPrivatePermissions(t *testing.T) {
	s := disk(t, 1<<20)
	ev := fixtureEvent("event1")
	if err := s.Begin(ev); err != nil {
		t.Fatal(err)
	}
	if err := s.Write(ev); err != nil {
		t.Fatal(err)
	}
	entries := exportRecords(t, s)
	if len(entries) != 1 || !bytes.Equal(entries[0].Request, ev.Request) {
		t.Fatal("content not preserved")
	}
	path := filepath.Join(s.root, "events", ev.At.Format("2006-01-02"), ev.ID+".json")
	raw, _ := os.ReadFile(path)
	if !bytes.Contains(raw, []byte("password=fixture")) {
		t.Fatal("not literal plaintext")
	}
	info, _ := os.Stat(path)
	if info.Mode().Perm() != 0600 {
		t.Fatal("wrong record permissions")
	}
	raw = bytes.Replace(raw, []byte("password=fixture"), []byte("password=changed"), 1)
	_ = os.WriteFile(path, raw, 0600)
	if _, err := ReadRecord(path); err == nil {
		t.Fatal("corrupt content accepted")
	}
}
func TestStoreCapacityDoesNotEvictUnexpiredContent(t *testing.T) {
	s := disk(t, 1000)
	ev := fixtureEvent("one")
	if err := s.Write(ev); err != nil {
		t.Fatal(err)
	}
	before := s.StoredBytes()
	large := fixtureEvent("two")
	large.Request = json.RawMessage(`{"input":"` + strings.Repeat("x", 2000) + `"}`)
	if err := s.Write(large); !errors.Is(err, ErrCapacity) {
		t.Fatalf("%v", err)
	}
	if s.StoredBytes() != before || len(exportRecords(t, s)) != 1 {
		t.Fatal("unexpired data removed")
	}
	s.free = func(string) (uint64, error) { return 0, nil }
	if err := s.Write(fixtureEvent("three")); !errors.Is(err, ErrCapacity) {
		t.Fatal("low disk not handled")
	}
}
func TestLossLedgerPersistsLocationWithoutBody(t *testing.T) {
	s := disk(t, 1<<20)
	if err := s.RecordLoss(Loss{ID: "event-loss", At: time.Date(2026, 9, 17, 12, 0, 0, 0, time.UTC), Reason: "completion_queue_full"}); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(filepath.Join(s.root, "losses", "2026-09-17.jsonl"))
	if err != nil || !bytes.Contains(raw, []byte("event-loss")) || bytes.Contains(raw, []byte("password")) {
		t.Fatalf("loss ledger invalid: %v %s", err, raw)
	}
	if err := s.RecordLoss(Loss{ID: "../escape", At: time.Now(), Reason: "bad"}); err == nil {
		t.Fatal("unsafe loss ID accepted")
	}
	var exported bytes.Buffer
	if n, err := ExportLosses(s.root, &exported, time.Time{}); err != nil || n != 1 || !bytes.Contains(exported.Bytes(), []byte("completion_queue_full")) {
		t.Fatalf("loss export invalid: %d %v %s", n, err, exported.Bytes())
	}
}
func TestRetentionUsesEventTimestampAndSurvivesRestart(t *testing.T) {
	s := disk(t, 1<<20)
	now := time.Date(2026, 9, 17, 12, 0, 0, 0, time.UTC)
	s.now = func() time.Time { return now }
	old := fixtureEvent("old")
	old.At = now.Add(-Retention)
	fresh := fixtureEvent("fresh")
	fresh.At = now.Add(-Retention + time.Second)
	for _, e := range []Event{old, fresh} {
		if err := s.Write(e); err != nil {
			t.Fatal(err)
		}
	}
	n, err := s.Prune()
	if err != nil || n != 1 {
		t.Fatalf("%d %v", n, err)
	}
	if got := exportRecords(t, s); len(got) != 1 || got[0].ID != "fresh" {
		t.Fatal("wrong retention boundary")
	}
	pending := fixtureEvent("active")
	if err := s.Begin(pending); err != nil {
		t.Fatal(err)
	}
	root := s.root
	s.Close()
	next, err := NewDiskStore(root, 1<<20)
	if err != nil {
		t.Fatal(err)
	}
	defer next.Close()
	next.free = s.free
	n, err = next.Recover()
	if err != nil || n != 1 {
		t.Fatalf("%d %v", n, err)
	}
	got := exportRecords(t, next)
	found := false
	for _, e := range got {
		if e.ID == "active" {
			found = e.Outcome == "process_interrupted" && len(e.Missing) > 0
		}
	}
	if !found {
		t.Fatal("restart gap was hidden")
	}
}
func TestSingleWriterAndUnsafeIDsRejected(t *testing.T) {
	s := disk(t, 1<<20)
	if other, err := NewDiskStore(s.root, 1<<20); err == nil {
		other.Close()
		t.Fatal("second writer admitted")
	}
	if err := s.Write(fixtureEvent("../escape")); err == nil {
		t.Fatal("unsafe ID accepted")
	}
}

type memorySink struct {
	mu      sync.Mutex
	events  []Event
	gate    chan struct{}
	started chan struct{}
	once    sync.Once
	fail    bool
}

func (s *memorySink) Begin(Event) error {
	if s.gate != nil {
		s.once.Do(func() { close(s.started) })
		<-s.gate
	}
	return nil
}
func (s *memorySink) Write(e Event) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.fail {
		return errors.New("synthetic disk failure")
	}
	s.events = append(s.events, e)
	return nil
}
func (s *memorySink) StoredBytes() int64 { return 0 }
func TestSlowSinkAndQueueOverflowNeverWaitOnSubmission(t *testing.T) {
	s := &memorySink{gate: make(chan struct{}), started: make(chan struct{})}
	e := NewEngine(s, Limits{Queue: 1, MemoryBytes: 1024, BodyBytes: 512}, true)
	x := e.Begin(fixtureEvent("ignored"))
	<-s.started
	done := make(chan struct{})
	go func() {
		x.Observe(false, []byte(`{"input":"ok"}`))
		x.Finish("completed")
		for i := 0; i < 100; i++ {
			y := e.Begin(fixtureEvent("ignore"))
			y.Finish("canceled")
		}
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(time.Second):
		t.Fatal("forwarding waited on storage")
	}
	close(s.gate)
	e.Close()
	if e.metrics.dropped.Load() == 0 {
		t.Fatal("queue loss not counted")
	}
	if e.metrics.queued.Load() != 0 {
		t.Fatal("copy budget leaked")
	}
}
func TestBodyLimitAndWriteFailureHaveExplicitEvidence(t *testing.T) {
	s := &memorySink{}
	e := NewEngine(s, Limits{Queue: 16, MemoryBytes: 64, BodyBytes: 16}, true)
	x := e.Begin(Event{ContentType: "application/json", ResponseContentType: "text/event-stream"})
	x.Observe(false, []byte(strings.Repeat("x", 17)))
	x.Observe(true, []byte("data: {}\n\n"))
	x.Finish("canceled")
	e.Close()
	if len(s.events) != 1 || len(s.events[0].Missing) == 0 || s.events[0].Outcome != "canceled" {
		t.Fatal("missing limit/cancel evidence")
	}
	broken := &memorySink{fail: true}
	e = NewEngine(broken, Limits{Queue: 8}, true)
	e.Begin(Event{}).Finish("completed")
	e.Close()
	if e.metrics.writeErrors.Load() != 1 || e.metrics.dropped.Load() != 1 {
		t.Fatal("write failure hidden")
	}
}
func TestPartialSSERetainsEarlierEventsWithoutClaimingComplete(t *testing.T) {
	body, gaps := ProjectBody([]byte("data: {\"type\":\"response.output_text.delta\",\"delta\":\"keep\"}\n\ndata: {\"delta\":\"unfinished"), "text/event-stream", "", "", 1024)
	if !bytes.Contains(body, []byte("keep")) || len(gaps) != 1 {
		t.Fatalf("%s %v", body, gaps)
	}
}
func wsFrame(op byte, fin, compressed, masked bool, payload []byte) []byte {
	first := op
	if fin {
		first |= 128
	}
	if compressed {
		first |= 64
	}
	maskBit := byte(0)
	if masked {
		maskBit = 128
	}
	out := []byte{first}
	n := len(payload)
	if n < 126 {
		out = append(out, byte(n)|maskBit)
	} else if n <= 65535 {
		out = append(out, 126|maskBit, byte(n>>8), byte(n))
	} else {
		out = append(out, 127|maskBit)
		out = binary.BigEndian.AppendUint64(out, uint64(n))
	}
	mask := []byte{2, 3, 5, 7}
	if masked {
		out = append(out, mask...)
	}
	for i, c := range payload {
		if masked {
			c ^= mask[i%4]
		}
		out = append(out, c)
	}
	return out
}
func TestWebsocketSplitMaskedFragmentsAndControlFrame(t *testing.T) {
	d := newWSDecoder("", true, 1<<20)
	raw := append(wsFrame(1, false, false, true, []byte(`{"input":"`)), wsFrame(9, true, false, true, []byte("ping"))...)
	raw = append(raw, wsFrame(0, true, false, true, []byte(`literal"}`))...)
	var got []string
	for _, c := range raw {
		if err := d.feed([]byte{c}, func(p []byte, _ bool) error { got = append(got, string(p)); return nil }); err != nil {
			t.Fatal(err)
		}
	}
	if len(got) != 1 || got[0] != `{"input":"literal"}` || d.held() != 0 {
		t.Fatal(got)
	}
}
func TestWebsocketCompressionWithContextTakeover(t *testing.T) {
	var compressed bytes.Buffer
	w, _ := flate.NewWriter(&compressed, flate.BestCompression)
	defer w.Close()
	d := newWSDecoder("permessage-deflate", false, 1<<20)
	offset := 0
	for _, body := range []string{strings.Repeat("same literal context ", 100), strings.Repeat("same literal context ", 100) + "second"} {
		_, _ = w.Write([]byte(body))
		_ = w.Flush()
		all := compressed.Bytes()
		payload := bytes.Clone(all[offset : len(all)-4])
		offset = len(all)
		frame := wsFrame(1, true, true, false, payload)
		got := ""
		if err := d.feed(frame, func(p []byte, _ bool) error { got = string(p); return nil }); err != nil {
			t.Fatal(err)
		}
		if got != body {
			t.Fatal("compressed text changed")
		}
	}
}
func TestWebsocketRecordsMessagesBeforeConnectionCloses(t *testing.T) {
	s := &memorySink{}
	e := NewEngine(s, Limits{Queue: 32, MemoryBytes: 1 << 20}, true)
	x := e.Begin(fixtureEvent("connection"))
	x.Update(func(ev *Event) { ev.Kind = "websocket_connection" })
	x.ObserveWire(false, wsFrame(1, true, false, true, []byte(`{"input":"hello"}`)))
	x.ObserveWire(true, wsFrame(1, true, false, false, []byte(`{"output":[{"type":"message","role":"assistant","content":"answer"}]}`)))
	wait := make(chan struct{})
	if !e.Maintain(func() { close(wait) }) {
		t.Fatal("test queue full")
	}
	<-wait
	s.mu.Lock()
	n := len(s.events)
	s.mu.Unlock()
	if n != 2 {
		t.Fatalf("messages not persisted while connected: %d", n)
	}
	x.Finish("websocket_closed")
	e.Close()
	if e.metrics.queued.Load() != 0 {
		t.Fatal("WS copy budget leaked")
	}
	if len(s.events) != 3 || s.events[0].Sequence != 1 || s.events[1].Sequence != 2 || s.events[0].ConnectionID == "" {
		t.Fatal("WS ordering missing")
	}
}

func TestSSETransportIDsAndDoneRemainInEvidence(t *testing.T) {
	b, err := ProjectSSE([]byte("id: e1\nevent: response.output_text.delta\ndata: {\"delta\":\"literal\"}\n\ndata: [DONE]\n\n"))
	if err != nil {
		t.Fatal(err)
	}
	var records []struct {
		Transport, Event, ID string
		Data                 json.RawMessage
	}
	if err = json.Unmarshal(b, &records); err != nil {
		t.Fatal(err)
	}
	if len(records) != 2 || records[0].ID != "e1" || records[1].ID != "e1" || string(records[1].Data) != `"[DONE]"` {
		t.Fatalf("%s", b)
	}
}

func TestDisableStopsExistingExchangeAndDoesNotResumeAcrossGap(t *testing.T) {
	s := &memorySink{}
	e := NewEngine(s, Limits{Queue: 32}, true)
	x := e.Begin(Event{ContentType: "application/json", ResponseContentType: "text/plain"})
	x.Observe(false, []byte(`{"input":"before switch"}`))
	x.Observe(true, []byte("before"))
	e.SetEnabled(false)
	x.Observe(true, []byte("AFTER_DISABLED"))
	e.SetEnabled(true)
	x.Observe(true, []byte("AFTER_REENABLED"))
	x.Finish("completed")
	e.Close()
	if len(s.events) != 1 {
		t.Fatal("missing exchange")
	}
	b, _ := json.Marshal(s.events[0])
	if bytes.Contains(b, []byte("AFTER_DISABLED")) || bytes.Contains(b, []byte("AFTER_REENABLED")) {
		t.Fatal("capture continued after disabling an existing exchange")
	}
	if !strings.Contains(string(b), "capture_disabled_during_request") {
		t.Fatal("switch gap not explicit")
	}
}

func TestDroppedWebsocketCompletionReleasesPartialFrameBudget(t *testing.T) {
	s := &memorySink{}
	e := NewEngine(s, Limits{Queue: 1, MemoryBytes: 1024}, true)
	wait := make(chan struct{})
	for !e.Maintain(func() { close(wait) }) {
		time.Sleep(time.Millisecond)
	}
	<-wait
	x := e.Begin(Event{})
	wait = make(chan struct{})
	for !e.Maintain(func() { close(wait) }) {
		time.Sleep(time.Millisecond)
	}
	<-wait
	x.Update(func(ev *Event) { ev.Kind = "websocket_connection" })
	x.ObserveWire(false, []byte{0x81, 0x8f, 1})
	wait = make(chan struct{})
	for !e.Maintain(func() { close(wait) }) {
		time.Sleep(time.Millisecond)
	}
	<-wait
	gate := make(chan struct{})
	started := make(chan struct{})
	e.Maintain(func() { close(started); <-gate })
	<-started
	if !e.Maintain(func() {}) {
		t.Fatal("test queue not empty")
	}
	x.Finish("websocket_closed")
	close(gate)
	e.Close()
	if e.metrics.queued.Load() != 0 {
		t.Fatal("partial WS buffer leaked after completion drop")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.events) != 1 || !strings.Contains(strings.Join(s.events[0].Missing, ","), "completion_queue_full") {
		t.Fatal("missing connection loss record")
	}
}
