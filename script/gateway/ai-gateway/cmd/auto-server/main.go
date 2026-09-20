package main

import (
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	autogateway "local/ai-gateway/auto"
	"local/ai-gateway/service"
)

func main() {
	if service.PrintVersion() {
		return
	}
	listen := envOr("AUTO_GATEWAY_LISTEN", "127.0.0.1:8091")
	host, _, err := net.SplitHostPort(listen)
	mode := os.Getenv("AUTO_GATEWAY_MODE")
	if (mode != "pilot" && mode != "regional") || err != nil || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
		log.Fatal("pilot or regional mode and loopback listen address required")
	}
	if os.Getenv("AUTO_GATEWAY_AUTH_CHECK_URL") == "" || os.Getenv("AUTO_GATEWAY_REGION") == "" {
		log.Fatal("region and live Sub2API auth check required")
	}
	var identity autogateway.IdentityResolver
	if mode == "pilot" {
		pilotToken, err := os.ReadFile(os.Getenv("AUTO_GATEWAY_PILOT_TOKEN_FILE"))
		if err != nil || os.Getenv("AUTO_GATEWAY_API_KEY_ID") == "" {
			log.Fatal("pilot token file and key ID required")
		}
		identity = &autogateway.PilotIdentityResolver{Token: strings.TrimSpace(string(pilotToken)), APIKeyID: os.Getenv("AUTO_GATEWAY_API_KEY_ID"), CheckURL: os.Getenv("AUTO_GATEWAY_AUTH_CHECK_URL")}
	} else {
		if err := validateRegionalConfig(); err != nil {
			log.Fatal(err)
		}
		identity = &autogateway.Sub2APIIdentityResolver{CheckURL: os.Getenv("AUTO_GATEWAY_AUTH_CHECK_URL"), Region: os.Getenv("AUTO_GATEWAY_REGION"), Secret: os.Getenv("AUTO_GATEWAY_CACHE_SECRET")}
	}
	for _, name := range []string{"AUTO_GUARD_ENDPOINT", "AUTO_GATEWAY_SESSION_STATE_PATH", "AUTO_GATEWAY_USAGE_SINK_PATH", "AUTO_GATEWAY_AUDIT_SINK_PATH", "AUTO_GATEWAY_CACHE_SECRET"} {
		if os.Getenv(name) == "" {
			log.Fatal("required gateway configuration missing: " + name)
		}
	}
	gateway := autogateway.NewAutoGateway()
	meta := autogateway.PipelineMeta{Region: os.Getenv("AUTO_GATEWAY_REGION"), APIKeyID: os.Getenv("AUTO_GATEWAY_API_KEY_ID"), ModelRevision: envOr("AUTO_GATEWAY_MODEL_REVISION", "catalog-v1"), CacheSecret: os.Getenv("AUTO_GATEWAY_CACHE_SECRET")}
	preflight := &autogateway.HTTPPreflightChecker{Client: guardHTTPClient(), Endpoint: os.Getenv("AUTO_GUARD_ENDPOINT"), Provider: envOr("AUTO_GATEWAY_PROVIDER", "openai"), Region: meta.Region}
	client := &autogateway.HTTPUpstreamClient{Client: &http.Client{Timeout: time.Duration(envInt("AUTO_GATEWAY_UPSTREAM_TIMEOUT_SECONDS", 600)) * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}, BufferedSSE: os.Getenv("AUTO_GATEWAY_BUFFERED_SSE") == "1", MaxResponseSize: int64(envInt("AUTO_GATEWAY_MAX_RESPONSE_BYTES", 16<<20)), ForwardClientAuth: true, Endpoints: []autogateway.ProviderEndpoint{
		{Provider: "default", Protocol: "chat", URL: os.Getenv("AUTO_UPSTREAM_CHAT_URL"), Token: os.Getenv("AUTO_UPSTREAM_TOKEN")},
		{Provider: "default", Protocol: "responses", URL: os.Getenv("AUTO_UPSTREAM_RESPONSES_URL"), Token: os.Getenv("AUTO_UPSTREAM_TOKEN")},
		{Provider: "default", Protocol: "anthropic", URL: os.Getenv("AUTO_UPSTREAM_ANTHROPIC_URL"), Token: os.Getenv("AUTO_UPSTREAM_TOKEN"), Header: "x-api-key"},
	}}
	pipeline := &autogateway.Pipeline{Health: &autogateway.RuntimeHealth{}, Gateway: gateway, Preflight: preflight, Upstream: client, CachePolicy: autogateway.DefaultResponseCachePolicy(), Cache: autogateway.NewMemoryResponseCacheWithCapacity(envInt("AUTO_GATEWAY_CACHE_MAX_ENTRIES", 10000)), Usage: autogateway.NewDailyUsageRecorder(), Meta: meta}
	if mode == "regional" {
		// Always send business requests to Sub2API for final model permissions and billing.
		pipeline.Cache = nil
	}
	if path := os.Getenv("AUTO_GATEWAY_SESSION_STATE_PATH"); path != "" {
		store, err := autogateway.NewFileSessionStateStore(path)
		if err != nil {
			log.Fatal(err)
		}
		pipeline.StateStore = store
	}
	if path := os.Getenv("AUTO_GATEWAY_USAGE_SINK_PATH"); path != "" {
		sink, err := autogateway.NewJSONLUsageSink(path)
		if err != nil {
			log.Fatal(err)
		}
		pipeline.UsageSink = sink
	}
	if path := os.Getenv("AUTO_GATEWAY_AUDIT_SINK_PATH"); path != "" {
		sink, err := autogateway.NewJSONLAuditSink(path)
		if err != nil {
			log.Fatal(err)
		}
		pipeline.AuditSink = sink
	}
	endpoint := os.Getenv("AUTO_CLASSIFIER_URL")
	primary := os.Getenv("AUTO_CLASSIFIER_MODEL")
	reviewer := os.Getenv("AUTO_CLASSIFIER_REVIEW_MODEL")
	if endpoint == "" || primary == "" || reviewer == "" || primary == "auto" || reviewer == "auto" || primary == reviewer {
		log.Fatal("explicit semantic classifier endpoint, primary and reviewer are required")
	}
	classifierToken := os.Getenv("AUTO_CLASSIFIER_TOKEN")
	if tokenFile := strings.TrimSpace(os.Getenv(classifierTokenFileEnv)); tokenFile != "" {
		var err error
		classifierToken, err = readPreviewClassifierToken(tokenFile)
		if err != nil {
			log.Fatal(err)
		}
	}
	classifier := &autogateway.SemanticClassifier{Endpoint: endpoint, Model: primary, ReviewerModel: reviewer, Token: classifierToken, Client: &http.Client{Timeout: 30 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}
	classifier.OnUsage = func(event autogateway.UsageEvent) error {
		pipeline.Usage.Record(event)
		if pipeline.UsageSink != nil {
			return pipeline.UsageSink.WriteUsageEvent(event)
		}
		return nil
	}
	pipeline.Classifier = &autogateway.CachedTaskClassifier{OnCacheHit: classifier.OnUsage, Shared: &service.JSONCache{File: service.TransactionFile{Path: filepath.Join(filepath.Dir(os.Getenv("AUTO_GATEWAY_SESSION_STATE_PATH")), "classifier-cache.json"), MaxBytes: 16 << 20}, Capacity: 1024}, Inner: classifier, Secret: meta.CacheSecret, Version: autogateway.SemanticPolicyVersion + "/" + primary + "/" + reviewer, TTL: 5 * time.Minute, Capacity: 1024}
	server := &http.Server{Addr: listen, ReadHeaderTimeout: 10 * time.Second, IdleTimeout: 60 * time.Second, Handler: &autogateway.HTTPServer{Files: &autogateway.NativeFileStore{Root: os.Getenv("AUTO_NATIVE_FILES_ROOT"), Secret: meta.CacheSecret, Region: meta.Region}, NativeAPI: &autogateway.NativeAPI{BaseURL: os.Getenv("AUTO_NATIVE_API_ORIGIN")}, Identity: identity, AllowRoutePreview: os.Getenv("AUTO_GATEWAY_ROUTE_PREVIEW") == "1", Gateway: gateway, Pipeline: pipeline, StreamClient: client, TokenCounter: &autogateway.HTTPTokenCounter{EstimateModels: map[string]bool{"deepseek-flash": true}, URL: os.Getenv("AUTO_UPSTREAM_COUNT_TOKENS_URL")}, Meta: meta}}
	log.Printf("auto gateway listening on %s", server.Addr)
	lifecycle := &service.Lifecycle{Next: server.Handler, AdminSecret: meta.CacheSecret}
	if err := service.Run(server, lifecycle, time.Duration(envInt("GATEWAY_SHUTDOWN_TIMEOUT_SECONDS", 120))*time.Second); err != nil {
		log.Fatal(err)
	}
}

func envOr(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func envInt(name string, fallback int) int {
	value, err := strconv.Atoi(os.Getenv(name))
	if err != nil || value <= 0 {
		return fallback
	}
	return value
}

// Keep the transport budget above Guard's bounded whole-input deadline. Long
// coding sessions can require several Qwen chunks; callers may cancel earlier.
func guardHTTPClient() *http.Client {
	seconds := envInt("AUTO_GUARD_TIMEOUT_SECONDS", 5)
	if seconds > 120 {
		seconds = 5
	}
	return &http.Client{Timeout: time.Duration(seconds) * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
}
