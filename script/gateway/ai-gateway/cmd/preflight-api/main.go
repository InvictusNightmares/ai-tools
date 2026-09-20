package main

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	goCheck "local/ai-gateway/guard"
	guarddeployment "local/ai-gateway/guard/model"
	"local/ai-gateway/service"
)

type jsonlAuditSink struct {
	path    string
	durable service.JSONLFile
	mu      sync.Mutex
	file    *os.File
}

func (s *jsonlAuditSink) WritePreflightAudit(_ context.Context, entry goCheck.PreflightAudit) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.path != "" {
		return s.durable.Append(entry)
	}
	return json.NewEncoder(s.file).Encode(entry)
}

type server struct {
	region         string
	decisionUsage  *service.JSONLFile
	latencyBuckets [8]atomic.Uint64
	queueBuckets   [8]atomic.Uint64
	gate           *goCheck.PreflightGate
	requestTimeout time.Duration
	queueTimeout   time.Duration
	queue          chan struct{}
	maxBodyBytes   int64
	guardBaseURL   string
	model          string
	requests       atomic.Uint64
	allows         atomic.Uint64
	blocks         atomic.Uint64
	unavailable    atomic.Uint64
	historyTotal   atomic.Uint64
	historyReused  atomic.Uint64
}

func main() {
	if service.PrintVersion() {
		return
	}
	config := goCheck.DefaultPreflightConfig()
	config.ModelVersion = env("GUARD_MODEL_VERSION", "qwen3guard-gen-8b")
	config.MaxBodyBytes = envInt64("PREFLIGHT_MAX_BODY_BYTES", config.MaxBodyBytes)
	config.FailClosed = envBool("PREFLIGHT_FAIL_CLOSED", true)
	config.Strict = envBool("PREFLIGHT_STRICT", true)

	audit, closeAudit, err := openAuditSink(env("PREFLIGHT_AUDIT_LOG", "/var/log/gateway/preflight-security.jsonl"))
	if err != nil {
		log.Fatal(err)
	}
	defer closeAudit()

	guardBaseURL := strings.TrimRight(env("GUARD_VLLM_BASE_URL", "http://127.0.0.1:8001/v1"), "/")
	model := env("GUARD_MODEL", "qwen3guard-gen-8b")
	classifier := &guarddeployment.HTTPModelClient{
		Endpoint: guardBaseURL + "/chat/completions", Model: model,
		MaxChunkChars:     int(envInt64("PREFLIGHT_MAX_CHUNK_CHARS", 20000)),
		TokenizerEndpoint: strings.TrimSuffix(guardBaseURL, "/v1") + "/tokenize",
	}
	usagePath := env("PREFLIGHT_USAGE_LOG", filepath.Join(filepath.Dir(env("PREFLIGHT_AUDIT_LOG", "/var/log/gateway/preflight-security.jsonl")), "security-usage.jsonl"))
	usageFile := &service.JSONLFile{Path: usagePath}
	classifier.OnUsage = func(event goCheck.ModelUsage) error {
		if err := usageFile.Append(event); err != nil {
			raw, _ := json.Marshal(event)
			log.Printf("security_usage_sink_failed event=%s", raw)
			return err
		}
		return nil
	}
	app := &server{
		region:         env("PREFLIGHT_REGION", "unattributed"),
		decisionUsage:  &service.JSONLFile{Path: filepath.Join(filepath.Dir(usagePath), "security-decisions.jsonl")},
		gate:           goCheck.NewPreflightGate(config, classifier, audit),
		requestTimeout: envDuration("PREFLIGHT_REQUEST_TIMEOUT", 3*time.Second),
		queueTimeout:   envDuration("PREFLIGHT_QUEUE_TIMEOUT", time.Second),
		queue:          make(chan struct{}, int(envInt64("PREFLIGHT_MAX_QUEUE", 128))),
		maxBodyBytes:   config.MaxBodyBytes,
		guardBaseURL:   guardBaseURL,
		model:          model,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/v1/preflight", app.handlePreflight)
	mux.HandleFunc("/healthz", app.handleHealth)
	mux.HandleFunc("/readyz", app.handleReady)
	mux.HandleFunc("/metrics", app.handleMetrics)
	addr := env("PREFLIGHT_LISTEN_ADDR", "0.0.0.0:8011")
	log.Printf("preflight API listening on %s, guard model %s", addr, model)
	adminSecret := ""
	if path := os.Getenv("GATEWAY_ADMIN_SECRET_FILE"); path != "" {
		data, err := os.ReadFile(path)
		if err != nil {
			log.Fatal("admin secret unavailable")
		}
		adminSecret = strings.TrimSpace(string(data))
	}
	lifecycle := &service.Lifecycle{Next: loggingMiddleware(mux), AdminSecret: adminSecret}
	server := &http.Server{Addr: addr, ReadHeaderTimeout: 10 * time.Second, IdleTimeout: 60 * time.Second}
	if err := service.Run(server, lifecycle, envDuration("GATEWAY_SHUTDOWN_TIMEOUT", time.Minute)); err != nil {
		log.Fatal(err)
	}
}

func (s *server) handlePreflight(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"code": "method_not_allowed"})
		return
	}
	s.requests.Add(1)
	ctx, cancel := context.WithTimeout(r.Context(), s.requestTimeout)
	defer cancel()
	r.Body = http.MaxBytesReader(w, r.Body, s.maxBodyBytes+1)
	raw, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"code": "invalid_body"})
		return
	}
	var input goCheck.SafetyInput
	if err := json.Unmarshal(raw, &input); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"code": "invalid_json"})
		return
	}
	input.RawBody = raw
	// Internal diagnostics may omit identity. Keep them visible without
	// attributing them to a user's Key or poisoning the regional spool.
	if input.Region == "" {
		input.Region = s.region
		if input.Region == "" {
			input.Region = "unattributed"
		}
	}
	if input.AccountID == "" {
		input.AccountID = "unattributed"
	}
	queueStarted := time.Now()
	queueTimer := time.NewTimer(s.queueTimeout)
	defer queueTimer.Stop()
	select {
	case s.queue <- struct{}{}:
		defer func() { <-s.queue }()
	case <-queueTimer.C:
		result := s.gate.Unavailable(ctx, input, "queue_timeout")
		result = s.recordDecision(input, result, time.Since(queueStarted))
		s.unavailable.Add(1)
		s.writeDecision(w, result)
		return
	case <-ctx.Done():
		result := s.gate.Unavailable(context.Background(), input, "request_timeout")
		result = s.recordDecision(input, result, time.Since(queueStarted))
		s.unavailable.Add(1)
		s.writeDecision(w, result)
		return
	}
	queueWait := time.Since(queueStarted)
	result := s.gate.Evaluate(ctx, input)
	result = s.recordDecision(input, result, queueWait)
	s.historyTotal.Add(uint64(result.HistoryTotalMessages))
	s.historyReused.Add(uint64(result.HistoryReusedMessages))
	switch result.Decision {
	case goCheck.SafetyAllow:
		s.allows.Add(1)
	case goCheck.SafetyBlock:
		s.blocks.Add(1)
	case goCheck.SafetyUnavailable:
		s.unavailable.Add(1)
	}
	s.writeDecision(w, result)
}

var latencyBoundsMS = [...]int64{50, 100, 200, 300, 1000, 5000, 10000, 30000}

func (s *server) recordDecision(input goCheck.SafetyInput, result goCheck.SafetyDecisionResult, queue time.Duration) goCheck.SafetyDecisionResult {
	for i, bound := range latencyBoundsMS {
		if result.Latency.Milliseconds() <= bound {
			s.latencyBuckets[i].Add(1)
		}
		if queue.Milliseconds() <= bound {
			s.queueBuckets[i].Add(1)
		}
	}
	if s.decisionUsage == nil {
		return result
	}
	status := 200
	if result.Decision == goCheck.SafetyUnavailable {
		status = 503
	}
	event := goCheck.ModelUsage{At: time.Now(), Purpose: "security_check", RequestID: input.RequestID, Region: input.Region, APIKeyID: input.AccountID, EffectiveModel: s.model,
		Decision: string(result.Decision), Success: result.Decision != goCheck.SafetyUnavailable, HTTPStatus: status, LatencyMS: result.Latency.Milliseconds(), QueueWaitMS: queue.Milliseconds(),
		RuleVersion: s.gate.Config.RuleVersion, ModelVersion: s.gate.Config.ModelVersion, ErrorType: strings.Join(result.ReasonCodes, ",")}
	if err := s.decisionUsage.Append(event); err != nil {
		raw, _ := json.Marshal(event)
		log.Printf("security_decision_usage_failed event=%s", raw)
		return s.gate.Unavailable(context.Background(), input, "security_usage_unavailable")
	}
	return result
}

func (s *server) writeDecision(w http.ResponseWriter, result goCheck.SafetyDecisionResult) {
	status := http.StatusOK
	response := map[string]any{
		"decision": result.Decision, "risk_level": result.RiskLevel,
		"categories": result.Categories, "confidence": result.Confidence,
		"reason_codes": result.ReasonCodes, "latency_ms": result.Latency.Milliseconds(),
		"upstream_called":         false,
		"history_total_messages":  result.HistoryTotalMessages,
		"history_reused_messages": result.HistoryReusedMessages,
		"history_version":         goCheck.HistoryInspectionVersion,
	}
	if result.Decision == goCheck.SafetyAllow && result.RedactionVersion != "" {
		response["sanitized_payload"] = result.SanitizedPayload
		response["input_sha256"] = result.InputSHA256
		response["redaction_version"] = result.RedactionVersion
	}
	if result.Decision == goCheck.SafetyUnavailable {
		status = http.StatusServiceUnavailable
		response["code"] = "preflight_unavailable"
		response["business_usage_written"] = false
		response["retry_suppressed"] = true
	}
	writeJSON(w, status, response)
}

func (s *server) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"code": "method_not_allowed"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func (s *server) handleReady(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"code": "method_not_allowed"})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 500*time.Millisecond)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.guardBaseURL+"/models", nil)
	if err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "unavailable"})
		return
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil || resp.StatusCode < 200 || resp.StatusCode >= 300 {
		if resp != nil {
			_ = resp.Body.Close()
		}
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "unavailable"})
		return
	}
	var models struct {
		Data []struct {
			ID string `json:"id"`
		} `json:"data"`
	}
	decodeErr := json.NewDecoder(resp.Body).Decode(&models)
	_ = resp.Body.Close()
	if decodeErr != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "unavailable"})
		return
	}
	found := false
	for _, item := range models.Data {
		if item.ID == s.model {
			found = true
			break
		}
	}
	if !found {
		writeJSON(w, http.StatusServiceUnavailable, map[string]string{"status": "unavailable"})
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ready", "model": s.model})
}

func (s *server) handleMetrics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"code": "method_not_allowed"})
		return
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	f := bufio.NewWriter(w)
	_, _ = fmt.Fprintf(f, "preflight_requests_total %d\n", s.requests.Load())
	_, _ = fmt.Fprintf(f, "preflight_history_messages_total %d\npreflight_history_reused_messages_total %d\n", s.historyTotal.Load(), s.historyReused.Load())
	_, _ = fmt.Fprintf(f, "preflight_decisions_total{decision=\"allow\"} %d\n", s.allows.Load())
	_, _ = fmt.Fprintf(f, "preflight_decisions_total{decision=\"block\"} %d\n", s.blocks.Load())
	_, _ = fmt.Fprintf(f, "preflight_decisions_total{decision=\"unavailable\"} %d\n", s.unavailable.Load())
	_, _ = fmt.Fprintf(f, "preflight_queue_active %d\npreflight_queue_capacity %d\n", len(s.queue), cap(s.queue))
	total := s.allows.Load() + s.blocks.Load() + s.unavailable.Load()
	_, _ = fmt.Fprintf(f, "preflight_latency_ms_bucket{le=\"+Inf\"} %d\npreflight_latency_ms_count %d\npreflight_queue_wait_ms_bucket{le=\"+Inf\"} %d\npreflight_queue_wait_ms_count %d\n", total, total, total, total)
	for i, bound := range latencyBoundsMS {
		_, _ = fmt.Fprintf(f, "preflight_latency_ms_bucket{le=\"%d\"} %d\npreflight_queue_wait_ms_bucket{le=\"%d\"} %d\n", bound, s.latencyBuckets[i].Load(), bound, s.queueBuckets[i].Load())
	}
	_ = f.Flush()
}

func openAuditSink(path string) (goCheck.AuditSink, func(), error) {
	if strings.TrimSpace(path) == "-" {
		return &jsonlAuditSink{file: os.Stdout}, func() {}, nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0750); err != nil {
		return nil, nil, err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0600)
	if err != nil {
		return nil, nil, err
	}
	_ = f.Close()
	return &jsonlAuditSink{path: path, durable: service.JSONLFile{Path: path}}, func() {}, nil
}

func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		log.Printf("method=%s path=%s duration_ms=%d", r.Method, r.URL.Path, time.Since(started).Milliseconds())
	})
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func env(key, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(key)); value != "" {
		return value
	}
	return fallback
}

func envBool(key string, fallback bool) bool {
	value, err := strconv.ParseBool(strings.TrimSpace(os.Getenv(key)))
	if err != nil {
		return fallback
	}
	return value
}

func envInt64(key string, fallback int64) int64 {
	value, err := strconv.ParseInt(strings.TrimSpace(os.Getenv(key)), 10, 64)
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}

func envDuration(key string, fallback time.Duration) time.Duration {
	value, err := time.ParseDuration(strings.TrimSpace(os.Getenv(key)))
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}
