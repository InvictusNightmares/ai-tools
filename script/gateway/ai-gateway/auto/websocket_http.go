package autogateway

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"local/ai-gateway/service"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

const websocketHistoryLimit = 64 << 20

var websocketLaneName = regexp.MustCompile(`^[A-Za-z0-9_.-]{1,256}$`)

type websocketHistory struct {
	Input []json.RawMessage
	Bytes int
	Lane  string
}
type websocketTurn struct {
	body []byte
	lane string
}
type responsesSocket struct {
	server                    *HTTPServer
	conn                      *websocket.Conn
	request                   *http.Request
	ctx                       context.Context
	writeMu                   sync.Mutex
	mu                        sync.Mutex
	history                   map[string]websocketHistory
	latest                    map[string]string
	lanes                     map[string]chan websocketTurn
	cancels                   map[string]context.CancelFunc
	queuedBytes, historyBytes int
	outstanding               int
	draining                  bool
	capacity                  chan struct{}
	id                        string
}

// Client WebSocket turns use the same authenticated Guard/Auto/SSE pipeline.
// Connection-local history supplies full context across model changes; it is
// never persisted and is destroyed on disconnect, including store=false runs.
func (s *HTTPServer) handleResponsesWebSocket(w http.ResponseWriter, r *http.Request) {
	upgrader := websocket.Upgrader{HandshakeTimeout: 10 * time.Second, ReadBufferSize: 4096, WriteBufferSize: 4096}
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	defer conn.Close()
	ctx, cancel := context.WithTimeout(r.Context(), time.Hour)
	defer cancel()
	state := &responsesSocket{server: s, conn: conn, request: r, ctx: ctx, history: map[string]websocketHistory{}, latest: map[string]string{}, lanes: map[string]chan websocketTurn{}, cancels: map[string]context.CancelFunc{}, capacity: make(chan struct{}, 16), id: withRequestID(PipelineMeta{}).RequestID}
	// Preserve explicit client session identity across reconnects. History itself
	// remains connection-local; named lanes and child-agent headers stay isolated.
	if value, _ := clientSessionHeader(r.Header, "responses"); value != "" {
		state.id = value
	}
	conn.SetReadLimit(MaxNativeRequestBytes)
	go func() { <-ctx.Done(); conn.Close() }()
	go func() {
		select {
		case <-ctx.Done():
			return
		case <-service.DrainSignal(r.Context()):
			state.mu.Lock()
			state.draining = true
			empty := state.outstanding == 0
			state.mu.Unlock()
			if empty {
				state.closeForDrain()
			}
		}
	}()
	for {
		kind, raw, err := conn.ReadMessage()
		if err != nil {
			return
		}
		if kind != websocket.TextMessage {
			state.failure("", 400, "invalid_event_type")
			continue
		}
		var event struct {
			Type       string  `json:"type"`
			Lane       *string `json:"stream_id"`
			ResponseID string  `json:"response_id"`
		}
		if json.Unmarshal(raw, &event) != nil {
			state.failure("", 400, "invalid_json")
			continue
		}
		lane := ""
		if event.Lane != nil {
			lane = *event.Lane
			if !websocketLaneName.MatchString(lane) {
				state.failure("", 400, "invalid_stream_id")
				continue
			}
		}
		if event.Type == "response.cancel" {
			state.mu.Lock()
			stop := state.cancels[event.ResponseID]
			state.mu.Unlock()
			if stop == nil {
				state.failure(lane, 400, "response_not_found")
			} else {
				stop()
			}
			continue
		}
		if event.Type != "response.create" {
			state.failure(lane, 400, "unsupported_event_type")
			continue
		}
		state.mu.Lock()
		if state.draining {
			state.mu.Unlock()
			state.failure(lane, 503, "gateway_draining")
			continue
		}
		queue := state.lanes[lane]
		if queue == nil {
			named := len(state.lanes)
			if _, ok := state.lanes[""]; ok {
				named--
			}
			if lane != "" && named >= 32 {
				state.mu.Unlock()
				state.failure(lane, 400, "websocket_stream_limit_reached")
				continue
			}
			queue = make(chan websocketTurn, 32)
			state.lanes[lane] = queue
			go state.runLane(queue)
		}
		if state.queuedBytes+len(raw) > websocketHistoryLimit {
			state.mu.Unlock()
			state.failure(lane, 413, "websocket_input_limit_reached")
			continue
		}
		state.queuedBytes += len(raw)
		state.outstanding++
		select {
		case queue <- websocketTurn{body: raw, lane: lane}:
			state.mu.Unlock()
		default:
			state.outstanding--
			state.queuedBytes -= len(raw)
			state.mu.Unlock()
			state.failure(lane, 429, "websocket_queue_full")
		}
	}
}

func (s *responsesSocket) send(lane string, event map[string]json.RawMessage) error {
	if lane != "" {
		event["stream_id"], _ = json.Marshal(lane)
	}
	s.writeMu.Lock()
	defer s.writeMu.Unlock()
	_ = s.conn.SetWriteDeadline(time.Now().Add(30 * time.Second))
	return s.conn.WriteJSON(event)
}
func (s *responsesSocket) failure(lane string, status int, code string) {
	raw, _ := json.Marshal(map[string]any{"type": "error", "status": status, "error": map[string]string{"type": "invalid_request_error", "code": code, "message": code}})
	var event map[string]json.RawMessage
	_ = json.Unmarshal(raw, &event)
	_ = s.send(lane, event)
}

func (s *responsesSocket) runLane(queue <-chan websocketTurn) {
	for {
		select {
		case <-s.ctx.Done():
			return
		case turn := <-queue:
			select {
			case s.capacity <- struct{}{}:
			case <-s.ctx.Done():
				return
			}
			s.runTurn(turn)
			<-s.capacity
			s.mu.Lock()
			s.queuedBytes -= len(turn.body)
			s.outstanding--
			empty := s.draining && s.outstanding == 0
			s.mu.Unlock()
			if empty {
				s.closeForDrain()
				return
			}
		}
	}
}

func responseInputItems(raw json.RawMessage) ([]json.RawMessage, error) {
	if len(raw) == 0 || string(raw) == "null" {
		return nil, nil
	}
	var text string
	if json.Unmarshal(raw, &text) == nil {
		item, _ := json.Marshal(map[string]any{"role": "user", "content": text})
		return []json.RawMessage{item}, nil
	}
	var items []json.RawMessage
	if json.Unmarshal(raw, &items) != nil {
		return nil, errors.New("invalid_input")
	}
	return items, nil
}

func (s *responsesSocket) runTurn(turn websocketTurn) {
	var body map[string]json.RawMessage
	if json.Unmarshal(turn.body, &body) != nil {
		s.failure(turn.lane, 400, "invalid_json")
		return
	}
	delete(body, "type")
	delete(body, "stream_id")
	var background bool
	_ = json.Unmarshal(body["background"], &background)
	if background {
		s.failure(turn.lane, 400, "background_not_supported")
		return
	}
	delete(body, "background")
	var generate *bool
	_ = json.Unmarshal(body["generate"], &generate)
	delete(body, "generate")
	items, err := responseInputItems(body["input"])
	if err != nil {
		s.failure(turn.lane, 400, "invalid_input")
		return
	}
	var previous string
	_ = json.Unmarshal(body["previous_response_id"], &previous)
	if previous != "" {
		s.mu.Lock()
		history, ok := s.history[previous]
		s.mu.Unlock()
		if !ok || history.Lane != turn.lane {
			s.failure(turn.lane, 400, "previous_response_not_found")
			return
		}
		items = append(append([]json.RawMessage(nil), history.Input...), items...)
	}
	delete(body, "previous_response_id")
	body["input"], _ = json.Marshal(items)
	body["stream"] = json.RawMessage(`true`)
	raw, err := json.Marshal(body)
	if err != nil || len(raw) > MaxNativeRequestBytes {
		s.failure(turn.lane, 413, "websocket_input_limit_reached")
		return
	}
	ctx, cancel := context.WithCancel(s.ctx)
	defer cancel()
	request := s.request.Clone(ctx)
	request.Method = http.MethodPost
	request.URL.Path = "/v1/responses"
	request.URL.RawQuery = ""
	request.Header = s.request.Header.Clone()
	request.Header.Del("Upgrade")
	request.Header.Del("Connection")
	request.Header.Set("Content-Type", "application/json")
	session := s.id
	if turn.lane != "" {
		raw, _ := json.Marshal([]string{s.id, turn.lane})
		session = RequestDigest(raw)
	}
	request.Header.Set("X-Gateway-Session-ID", session)
	request.Body = io.NopCloser(bytes.NewReader(raw))
	request.ContentLength = int64(len(raw))
	writer := &websocketResponseWriter{socket: s, lane: turn.lane, header: http.Header{}, cancel: cancel, input: items}
	if generate != nil && !*generate {
		// Warmup creates no paid response. Instruction-only review setup is
		// buffered as untrusted context; the complete turn runs Guard before use.
		request = request.WithContext(context.WithValue(request.Context(), websocketWarmupKey{}, true))
	}
	s.server.ServeHTTP(writer, request)
	writer.finish()
}

func (s *responsesSocket) retain(lane, id string, items []json.RawMessage) error {
	size := 0
	for _, item := range items {
		size += len(item)
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	oldID := s.latest[lane]
	old := s.history[oldID]
	if size > websocketHistoryLimit || s.historyBytes-old.Bytes+size > websocketHistoryLimit {
		return errors.New("websocket_history_limit_reached")
	}
	delete(s.history, oldID)
	s.historyBytes -= old.Bytes
	s.history[id] = websocketHistory{Input: items, Bytes: size, Lane: lane}
	s.latest[lane] = id
	s.historyBytes += size
	return nil
}

type websocketResponseWriter struct {
	socket          *responsesSocket
	lane            string
	header          http.Header
	status          int
	pending, nonSSE []byte
	data            []string
	eventBytes      int
	cancel          context.CancelFunc
	input           []json.RawMessage
	responseID      string
	terminal        bool
}

func (w *websocketResponseWriter) Header() http.Header { return w.header }
func (w *websocketResponseWriter) WriteHeader(status int) {
	if w.status == 0 {
		w.status = status
	}
}
func (w *websocketResponseWriter) Flush() {}
func (w *websocketResponseWriter) Write(p []byte) (int, error) {
	if w.status == 0 {
		w.status = 200
	}
	if w.status >= 300 || !strings.Contains(w.header.Get("Content-Type"), "text/event-stream") {
		if len(w.nonSSE)+len(p) > 1<<20 {
			return 0, errors.New("websocket_error_body_limit")
		}
		w.nonSSE = append(w.nonSSE, p...)
		return len(p), nil
	}
	w.pending = append(w.pending, p...)
	for {
		i := bytes.IndexByte(w.pending, '\n')
		if i < 0 {
			break
		}
		line := strings.TrimSuffix(string(w.pending[:i]), "\r")
		w.pending = w.pending[i+1:]
		if line == "" {
			if err := w.event(); err != nil {
				return 0, err
			}
		} else if strings.HasPrefix(line, "data:") {
			w.eventBytes += len(line)
			if w.eventBytes > 128<<20 {
				return 0, errors.New("websocket_event_limit")
			}
			w.data = append(w.data, strings.TrimPrefix(strings.TrimPrefix(line, "data:"), " "))
		}
	}
	if len(w.pending) > 128<<20 {
		return 0, errors.New("websocket_event_limit")
	}
	return len(p), nil
}
func (w *websocketResponseWriter) event() error {
	if len(w.data) == 0 {
		return nil
	}
	data := strings.Join(w.data, "\n")
	w.data = nil
	w.eventBytes = 0
	if data == "[DONE]" {
		return nil
	}
	var event map[string]json.RawMessage
	if json.Unmarshal([]byte(data), &event) != nil {
		return errors.New("websocket_invalid_upstream_event")
	}
	var kind string
	_ = json.Unmarshal(event["type"], &kind)
	if kind == "response.created" {
		var response struct {
			ID string `json:"id"`
		}
		_ = json.Unmarshal(event["response"], &response)
		w.responseID = response.ID
		w.socket.mu.Lock()
		w.socket.cancels[response.ID] = w.cancel
		w.socket.mu.Unlock()
	}
	if kind == "response.completed" {
		var response struct {
			ID     string            `json:"id"`
			Output []json.RawMessage `json:"output"`
		}
		if json.Unmarshal(event["response"], &response) != nil || response.ID == "" {
			return errors.New("websocket_incomplete_response")
		}
		if err := w.socket.retain(w.lane, response.ID, append(append([]json.RawMessage(nil), w.input...), response.Output...)); err != nil {
			return err
		}
		w.terminal = true
	}
	if kind == "response.failed" || kind == "response.incomplete" {
		w.terminal = true
	}
	err := w.socket.send(w.lane, event)
	if err != nil {
		w.cancel()
	}
	return err
}
func (w *websocketResponseWriter) finish() {
	w.socket.mu.Lock()
	delete(w.socket.cancels, w.responseID)
	w.socket.mu.Unlock()
	if len(w.nonSSE) > 0 {
		code := "upstream_request_failed"
		var body map[string]json.RawMessage
		if json.Unmarshal(w.nonSSE, &body) == nil {
			var value string
			if json.Unmarshal(body["error"], &value) == nil && len(value) < 128 {
				code = value
			}
		}
		status := w.status
		if status < 400 {
			status = 502
		}
		w.socket.failure(w.lane, status, code)
	} else if !w.terminal {
		w.socket.failure(w.lane, 502, "upstream_stream_incomplete")
	}
}

func (s *responsesSocket) closeForDrain() {
	_ = s.conn.WriteControl(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseServiceRestart, "gateway_draining"), time.Now().Add(time.Second))
	_ = s.conn.Close()
}

type websocketWarmupKey struct{}

func (s *HTTPServer) handleWebSocketWarmup(w http.ResponseWriter, r *http.Request, request Request, meta PipelineMeta) {
	var envelope struct {
		Model string `json:"model"`
	}
	_ = json.Unmarshal(request.RawPayload, &envelope)
	model := envelope.Model
	if model == "" {
		model = "auto"
	}
	deferred := model == ActionReviewModel && instructionOnlyReviewSetup(request.RawPayload)
	decision := PreflightAllow
	stage := "websocket_warmup_completed"
	if deferred {
		// This is connection-local transport buffering, never a safety approval or
		// a reusable Guard result. The next generating turn includes all retained
		// input and runs the normal Guard path, even when it uses a previous ID.
		decision = PreflightDecision("deferred")
		stage = "websocket_review_context_buffered"
	} else {
		preflight, err := evaluatePreflight(r.Context(), s.Pipeline.Preflight, request, meta)
		if err != nil || preflight.Decision != PreflightAllow {
			status, code := 503, "preflight_unavailable"
			if preflight.Decision == PreflightBlock {
				status, code = 403, "preflight_blocked"
			}
			s.Pipeline.writePreflightAudit(meta, "auto", request, preflight, code)
			writeJSON(w, status, map[string]string{"error": code})
			return
		}
		if preflight.SanitizedRequest != nil {
			request = *preflight.SanitizedRequest
		}
	}

	if writer, ok := w.(*websocketResponseWriter); ok {
		var body map[string]json.RawMessage
		_ = json.Unmarshal(request.RawPayload, &body)
		writer.input, _ = responseInputItems(body["input"])
	}
	audit := RouteAudit{At: time.Now(), RequestID: meta.RequestID, Region: meta.Region, APIKeyID: meta.APIKeyID, SessionHash: hashIdentifier(meta.SessionID), RequestedModel: model, Stage: stage, PreflightDecision: decision}
	if s.Pipeline.AuditSink != nil {
		if err := s.Pipeline.AuditSink.WriteRouteAudit(audit); err != nil {
			writeJSON(w, 503, map[string]string{"error": "audit_unavailable"})
			return
		}
	}

	response := map[string]any{"id": "resp_gw_" + meta.RequestID, "object": "response", "created_at": time.Now().Unix(), "model": model, "status": "in_progress", "output": []any{}}
	w.Header().Set("Content-Type", "text/event-stream")
	for i, kind := range []string{"response.created", "response.completed"} {
		if i == 1 {
			response["status"] = "completed"
			response["usage"] = map[string]int{"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
		}
		raw, _ := json.Marshal(map[string]any{"type": kind, "sequence_number": i, "response": response})
		if _, err := fmt.Fprintf(w, "data: %s\n\n", raw); err != nil {
			return
		}
	}
}

// Only a native reviewer setup packet without a user task or conversation
// output can be buffered before the complete action exists. Unknown item types
// and non-text content take the ordinary checked path.
func instructionOnlyReviewSetup(raw json.RawMessage) bool {
	var body map[string]json.RawMessage
	if json.Unmarshal(raw, &body) != nil {
		return false
	}
	var items []json.RawMessage
	if json.Unmarshal(body["input"], &items) != nil || len(items) == 0 {
		return false
	}
	for _, item := range items {
		var value struct {
			Type    string          `json:"type"`
			Role    string          `json:"role"`
			Content json.RawMessage `json:"content"`
		}
		if json.Unmarshal(item, &value) != nil || (value.Role != "developer" && value.Role != "system") {
			return false
		}
		if value.Type != "" && value.Type != "message" && value.Type != "additional_tools" {
			return false
		}
		if value.Type == "additional_tools" {
			continue
		}
		var text string
		if json.Unmarshal(value.Content, &text) == nil {
			continue
		}
		var parts []struct {
			Type string `json:"type"`
		}
		if json.Unmarshal(value.Content, &parts) != nil {
			return false
		}
		for _, part := range parts {
			if part.Type != "text" && part.Type != "input_text" {
				return false
			}
		}
	}
	return true
}
