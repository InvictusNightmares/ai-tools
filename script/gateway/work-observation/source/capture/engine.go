package capture

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

// Sink methods run exclusively in the background worker, never while forwarding.
type Sink interface {
	Begin(Event) error
	Write(Event) error
	StoredBytes() int64
}

// LossSink is optional so lightweight test sinks and other adapters can keep
// running without a filesystem. DiskStore implements it to persist a bounded,
// body-free ledger of every dropped/truncated location.
type LossSink interface {
	RecordLoss(Loss) error
}
type Limits struct {
	Queue                  int
	MemoryBytes, BodyBytes int64
}
type Loss struct {
	ID     string    `json:"id"`
	At     time.Time `json:"at"`
	Reason string    `json:"reason"`
}
type Engine struct {
	sink         Sink
	limits       Limits
	jobs         chan job
	done         chan struct{}
	enabled      atomic.Bool
	seq          atomic.Uint64
	generation   atomic.Uint64
	prefix       string
	ws           map[string]*wsState
	metrics      Metrics
	lossesMu     sync.Mutex
	losses       []Loss
	lossOverflow uint64
	active       atomic.Int64
	forcedClose  atomic.Bool
	unavailable  atomic.Pointer[string]
	bypassed     atomic.Uint64
	admission    sync.RWMutex
	closed       bool
}
type job struct {
	owner             *Exchange
	maintenance       func()
	wireData          []byte
	wireBuffer        *wireBuffer
	wireResponse      bool
	wireAt            time.Time
	start             bool
	event             Event
	request, response bodyCopy
	held              int64
}
type bodyCopy struct {
	chunks      [][]byte
	bytes, held int64
	lost        bool
}
type Exchange struct {
	engine            *Engine
	mu                sync.Mutex
	event             Event
	request, response bodyCopy
	closed            bool
	started           time.Time
	generation        uint64
	disableNoted      bool
	finishDropped     bool
	pendingWire       atomic.Int64
}

func NewEngine(sink Sink, limits Limits, enabled bool) *Engine {
	if limits.Queue < 1 {
		limits.Queue = 4096
	}
	if limits.MemoryBytes < 1 {
		limits.MemoryBytes = 512 << 20
	}
	if limits.BodyBytes < 1 {
		limits.BodyBytes = 32 << 20
	}
	var nonce [12]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		panic("random_source_unavailable")
	}
	e := &Engine{sink: sink, limits: limits, jobs: make(chan job, limits.Queue), done: make(chan struct{}), prefix: hex.EncodeToString(nonce[:]), ws: make(map[string]*wsState)}
	e.enabled.Store(enabled)
	e.metrics.started = time.Now().UTC()
	e.metrics.stored.Store(sink.StoredBytes())
	go e.run()
	return e
}
func (e *Engine) Enabled() bool { return e != nil && e.enabled.Load() }
func (e *Engine) SetEnabled(on bool) {
	if e.unavailable.Load() != nil {
		on = false
	}
	if e.enabled.Swap(on) != on {
		e.generation.Add(1)
	}
}

// A failed startup never accepts a later enable command with an invalid store
// or an unverified identity salt. An operator repairs storage and restarts.
func (e *Engine) SetUnavailable(reason string) {
	e.unavailable.Store(&reason)
	e.SetEnabled(false)
}
func (e *Engine) RecordBypass() {
	if e != nil && e.unavailable.Load() != nil {
		e.bypassed.Add(1)
	}
}
func (e *Engine) loss(ev Event, reason string) {
	e.metrics.dropped.Add(1)
	loss := Loss{ev.ID, time.Now().UTC(), reason}
	e.lossesMu.Lock()
	if len(e.losses) == 256 {
		copy(e.losses, e.losses[1:])
		e.losses = e.losses[:255]
		e.lossOverflow++
	}
	e.losses = append(e.losses, loss)
	e.lossesMu.Unlock()
	if sink, ok := e.sink.(LossSink); ok {
		if err := sink.RecordLoss(loss); err != nil {
			e.metrics.lossPersistErrors.Add(1)
		}
	}
}
func (e *Engine) submit(j job) bool {
	e.admission.RLock()
	defer e.admission.RUnlock()
	if e.closed {
		return false
	}
	select {
	case e.jobs <- j:
		return true
	default:
		return false
	}
}
func (e *Engine) Begin(ev Event) *Exchange {
	if !e.Enabled() {
		return nil
	}
	now := time.Now()
	ev.ID = fmt.Sprintf("%s-%020d", e.prefix, e.seq.Add(1))
	ev.At = now.UTC()
	ev.Schema = SchemaVersion
	ev.ContentPolicy = LiteralContentPolicy
	ev.Kind = "http_exchange"
	ev.Outcome = "in_progress"
	ev.FirstByteMS = -1
	x := &Exchange{engine: e, event: ev, started: now, generation: e.generation.Load()}
	e.metrics.captured.Add(1)
	e.active.Add(1)
	if !e.submit(job{start: true, event: ev}) {
		e.loss(ev, "start_queue_full")
	}
	return x
}
func (e *Engine) reserve(n int64) bool {
	for {
		old := e.metrics.queued.Load()
		if n > e.limits.MemoryBytes-old {
			return false
		}
		if e.metrics.queued.CompareAndSwap(old, old+n) {
			return true
		}
	}
}
func (x *Exchange) Observe(response bool, p []byte) {
	if x == nil || len(p) == 0 {
		return
	}
	x.mu.Lock()
	defer x.mu.Unlock()
	if x.closed {
		return
	}
	b := &x.request
	if response {
		b = &x.response
		if b.bytes == 0 {
			x.event.FirstByteMS = time.Since(x.started).Milliseconds()
		}
	}
	b.bytes += int64(len(p))
	if !x.captureAllowed() {
		b.lost = true
		return
	}
	if b.lost {
		return
	}
	if b.bytes > x.engine.limits.BodyBytes || !x.engine.reserve(int64(len(p))) {
		b.lost = true
		x.engine.metrics.truncated.Add(1)
		return
	}
	b.chunks = append(b.chunks, cloneCaptureChunk(p))
	b.held += int64(len(p))
}
func (x *Exchange) Update(fn func(*Event)) {
	if x == nil {
		return
	}
	x.mu.Lock()
	defer x.mu.Unlock()
	if !x.closed {
		fn(&x.event)
	}
}
func (x *Exchange) Finish(outcome string) {
	if x == nil {
		return
	}
	x.mu.Lock()
	if x.closed {
		x.mu.Unlock()
		return
	}
	x.closed = true
	x.event.RequestBytes = x.request.bytes
	x.event.ResponseBytes = x.response.bytes
	x.captureAllowed()
	if x.engine.forcedClose.Load() {
		x.event.Missing = append(x.event.Missing, "collector_forced_connection_close")
	}
	x.event.Outcome = outcome
	x.event.DurationMS = time.Since(x.started).Milliseconds()
	j := job{event: x.event, request: x.request, response: x.response, held: x.request.held + x.response.held}
	x.request = bodyCopy{}
	x.response = bodyCopy{}
	x.mu.Unlock()
	x.engine.active.Add(-1)
	if !x.engine.submit(j) {
		x.engine.metrics.queued.Add(-j.held)
		releaseCaptureChunks(j.request.chunks)
		releaseCaptureChunks(j.response.chunks)
		x.engine.loss(j.event, "completion_queue_full")
		x.mu.Lock()
		x.finishDropped = true
		x.mu.Unlock()
	}
}
func join(b bodyCopy) []byte {
	if len(b.chunks) == 0 {
		return nil
	}
	if len(b.chunks) == 1 {
		return b.chunks[0]
	}
	out := make([]byte, 0, b.held)
	for _, p := range b.chunks {
		out = append(out, p...)
	}
	return out
}
func (e *Engine) process(j job) {
	if j.maintenance != nil {
		j.maintenance()
		return
	}
	if j.wireData != nil {
		e.wire(j)
		return
	}
	if j.start {
		if err := e.sink.Begin(j.event); err != nil {
			e.metrics.writeErrors.Add(1)
			e.loss(j.event, "start_write_failed")
		}
		return
	}
	defer e.metrics.queued.Add(-j.held)
	defer releaseCaptureChunks(j.request.chunks)
	defer releaseCaptureChunks(j.response.chunks)
	ev := j.event
	ev.RequestBytes = j.request.bytes
	ev.ResponseBytes = j.response.bytes
	if ev.Kind == "websocket_connection" {
		if j.request.lost || j.response.lost {
			ev.Missing = append(ev.Missing, "websocket_wire_capture_gap")
		}
		if state := e.ws[ev.ID]; state != nil {
			n := state.request.held() + state.response.held()
			if n > 0 || state.failed {
				ev.Missing = append(ev.Missing, "websocket_decode_incomplete")
			}
			e.metrics.queued.Add(-n)
			delete(e.ws, ev.ID)
		}
		if err := e.sink.Write(ev); err != nil {
			e.metrics.writeErrors.Add(1)
			e.loss(ev, "connection_record_write_failed")
		} else {
			e.metrics.written.Add(1)
		}
		e.metrics.stored.Store(e.sink.StoredBytes())
		return
	}
	rawRequest, rawResponse := join(j.request), join(j.response)
	if !j.request.lost {
		ev.RequestSHA = digest(rawRequest)
	} else {
		ev.Missing = append(ev.Missing, "request_capture_truncated")
	}
	if !j.response.lost {
		ev.ResponseSHA = digest(rawResponse)
	} else {
		ev.Missing = append(ev.Missing, "response_capture_truncated")
	}
	var gaps []string
	ev.Request, gaps = ProjectBody(rawRequest, ev.ContentType, ev.ContentEncoding, ev.Path, e.limits.BodyBytes)
	ev.Missing = append(ev.Missing, gaps...)
	if len(gaps) > 0 {
		e.metrics.projectionErrors.Add(1)
	}
	ev.Response, gaps = ProjectBody(rawResponse, ev.ResponseContentType, ev.ResponseContentEncoding, ev.Path, e.limits.BodyBytes)
	ev.Missing = append(ev.Missing, gaps...)
	if len(gaps) > 0 {
		e.metrics.projectionErrors.Add(1)
	}
	if ev.Association == "" {
		ev.Association = "unknown"
	}
	if err := e.sink.Write(ev); err != nil {
		e.metrics.writeErrors.Add(1)
		e.loss(ev, "record_write_failed")
	} else {
		e.metrics.written.Add(1)
	}
	e.metrics.stored.Store(e.sink.StoredBytes())
}
func (e *Engine) run() {
	defer close(e.done)
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	for {
		select {
		case j, ok := <-e.jobs:
			if !ok {
				e.cleanOrphanedWS()
				return
			}
			e.process(j)
		case <-ticker.C:
			e.cleanOrphanedWS()
		}
	}
}

// A saturated completion queue must not leave a closed connection's partial
// frame budget reserved forever. Pending start records preserve restart evidence.
func (e *Engine) cleanOrphanedWS() {
	for id, state := range e.ws {
		if state.owner == nil {
			continue
		}
		state.owner.mu.Lock()
		dropped := state.owner.finishDropped
		allowed := true
		if !state.owner.closed {
			allowed = state.owner.captureAllowed()
		}
		ev := state.owner.event
		state.owner.mu.Unlock()
		if !allowed && !state.failed {
			e.metrics.queued.Add(-(state.request.held() + state.response.held()))
			state.failed = true
			state.request.buf = nil
			state.request.fragment = nil
			state.request.dict = nil
			state.response.buf = nil
			state.response.fragment = nil
			state.response.dict = nil
		}
		if !dropped || state.owner.pendingWire.Load() != 0 {
			continue
		}
		e.metrics.queued.Add(-(state.request.held() + state.response.held()))
		delete(e.ws, id)
		ev.Missing = append(ev.Missing, "completion_queue_full")
		if err := e.sink.Write(ev); err != nil {
			e.metrics.writeErrors.Add(1)
			e.loss(ev, "orphan_connection_write_failed")
		} else {
			e.metrics.written.Add(1)
		}
	}
}

// Call only after listeners/active handlers have drained. Never blocks forwarding.
func (e *Engine) Close() {
	e.SetEnabled(false)
	e.admission.Lock()
	if !e.closed {
		e.closed = true
		close(e.jobs)
	}
	e.admission.Unlock()
	<-e.done
}
func (e *Engine) Status() map[string]any {
	b, _ := json.Marshal(e.metrics.Snapshot())
	var out map[string]any
	_ = json.Unmarshal(b, &out)
	out["updated_at"] = time.Now().UTC()
	out["capture_enabled"] = e.Enabled()
	if reason := e.unavailable.Load(); reason != nil {
		out["capture_unavailable"] = *reason
	}
	out["unavailable_bypassed_requests"] = e.bypassed.Load()
	out["queue_limit_bytes"] = e.limits.MemoryBytes
	out["queue_items"] = len(e.jobs)
	out["active_requests"] = e.active.Load()
	out["complete_capture_claim"] = false
	e.lossesMu.Lock()
	out["recent_losses"] = append([]Loss(nil), e.losses...)
	out["older_loss_details_evicted"] = e.lossOverflow
	e.lossesMu.Unlock()
	return out
}

func fmtSequence(n uint64) string { return fmt.Sprintf("%020d", n) }
func (x *Exchange) ObserveWire(response bool, p []byte) {
	if x == nil || len(p) == 0 {
		return
	}
	x.mu.Lock()
	defer x.mu.Unlock()
	if x.closed {
		return
	}
	b := &x.request
	if response {
		b = &x.response
		if b.bytes == 0 {
			x.event.FirstByteMS = time.Since(x.started).Milliseconds()
		}
	}
	b.bytes += int64(len(p))
	if !x.captureAllowed() {
		b.lost = true
		return
	}
	if x.request.lost || x.response.lost {
		return
	}
	capacity, pool := wireBufferSize(len(p))
	if !x.engine.reserve(int64(capacity)) {
		b.lost = true
		x.engine.metrics.truncated.Add(1)
		return
	}
	buffer := copyWireBuffer(p, capacity, pool)
	j := job{owner: x, event: x.event, wireData: buffer.data[:len(p)], wireBuffer: buffer, wireResponse: response, wireAt: time.Now().UTC(), held: int64(capacity)}
	x.pendingWire.Add(1)
	if !x.engine.submit(j) {
		releaseWireBuffer(buffer)
		x.pendingWire.Add(-1)
		x.engine.metrics.queued.Add(-j.held)
		b.lost = true
		x.engine.loss(x.event, "websocket_queue_full")
	}
}

func (e *Engine) Maintain(fn func()) bool { return e.submit(job{maintenance: fn}) }
func (e *Engine) RecordPrune(n int, err error) {
	if n > 0 {
		e.metrics.pruned.Add(uint64(n))
	}
	if err != nil {
		e.metrics.writeErrors.Add(1)
	}
	e.metrics.stored.Store(e.sink.StoredBytes())
}

// Called with x.mu held. Re-enabling starts new observations; it never joins two
// retained prefixes across an unobserved gap in an existing exchange.
func (x *Exchange) captureAllowed() bool {
	if x.engine.Enabled() && x.generation == x.engine.generation.Load() {
		return true
	}
	if !x.disableNoted {
		x.disableNoted = true
		x.event.Missing = append(x.event.Missing, "capture_disabled_during_request")
		x.engine.metrics.truncated.Add(1)
	}
	return false
}

func (e *Engine) Active() int64    { return e.active.Load() }
func (e *Engine) MarkForcedClose() { e.forcedClose.Store(true) }
