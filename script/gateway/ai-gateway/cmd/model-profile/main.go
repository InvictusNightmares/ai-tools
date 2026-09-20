// model-profile is an isolated capability evaluation endpoint. It compares a
// fixed candidate, not Auto's model selection quality. It never changes the
// regional gateway or bypasses its upstream identity and Guard checks.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	ag "local/ai-gateway/auto"
	"local/ai-gateway/service"
)

type fixedAssessment struct{ effort ag.ReasoningEffort }

// Capability comparison uses one text/tool Chat wire for every candidate.
// Do not expose native endpoints that have independent routing semantics.
func profileEndpoint(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if (r.Method == http.MethodGet && r.URL.Path == "/healthz") || (r.Method == http.MethodPost && r.URL.Path == "/v1/chat/completions") {
			next.ServeHTTP(w, r)
			return
		}
		http.NotFound(w, r)
	})
}

func (f fixedAssessment) Classify(_ context.Context, request ag.Request, _ ag.PipelineMeta) (ag.Classification, error) {
	// This evaluator deliberately covers text coding tasks only. Native media
	// and compression use the regular gateway's separate acceptance matrix.
	if request.Native != nil || request.CompactionState || request.CompactionTrigger {
		return ag.Classification{}, errors.New("profile_requires_text_task")
	}
	var body map[string]json.RawMessage
	if json.Unmarshal(request.RawPayload, &body) != nil {
		return ag.Classification{}, errors.New("invalid_profile_request")
	}
	budget := ag.ContextBudget{InputEstimateTokens: len(request.RawPayload) + 1024 + 64*len(request.Messages) + 256*len(request.Tools), Method: "profile_utf8_bytes_with_framing_v1"}
	for _, key := range []string{"max_tokens", "max_completion_tokens", "max_output_tokens"} {
		if value, ok := body[key]; ok && string(value) != "null" {
			var limit int
			if json.Unmarshal(value, &limit) != nil || limit <= 0 {
				return ag.Classification{}, errors.New("invalid_output_limit")
			}
			if limit > budget.OutputLimitTokens {
				budget.OutputLimitTokens = limit
			}
		}
	}
	capabilities := []ag.Capability{ag.CapabilityText, ag.CapabilityCode}
	if len(request.Tools) > 0 {
		capabilities = append(capabilities, ag.CapabilityTools)
	}
	if request.Stream {
		capabilities = append(capabilities, ag.CapabilityStream)
	}
	if request.ResponseFormat {
		capabilities = append(capabilities, ag.CapabilityStructured)
	}
	return ag.Classification{ContextBudget: budget, InputTokens: budget.InputEstimateTokens, MessageCount: len(request.Messages), ToolCount: len(request.Tools), RequiredCapabilities: capabilities, Intent: "coding", Source: "fixed-model-capability-profile-v1", Score: 25, Confidence: 1, EffectiveReasoningEffort: f.effort, ReasonCodes: []string{"fixed_candidate_comparison_not_auto_selection"}}, nil
}

func validateTarget(listen, origin, guard, region, model string, effort ag.ReasoningEffort) (*ag.Model, error) {
	host, port, err := net.SplitHostPort(listen)
	portNumber, portErr := strconv.Atoi(port)
	if err != nil || portErr != nil || portNumber < 1 || portNumber > 65535 || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
		return nil, errors.New("explicit_loopback_listener_required")
	}
	if region != "tokyo" && region != "us" {
		return nil, errors.New("verified_region_required")
	}
	for _, value := range []string{origin, guard} {
		u, err := url.Parse(value)
		if err != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Scheme != "http" && u.Scheme != "https") {
			return nil, errors.New("invalid_evaluation_endpoint")
		}
	}
	u, _ := url.Parse(origin)
	if strings.TrimRight(u.Path, "/") != "/v1" {
		return nil, errors.New("upstream_v1_origin_required")
	}
	m := ag.ModelByName(model, ag.DefaultCatalog)
	if m == nil {
		return nil, errors.New("unknown_candidate")
	}
	for _, supported := range m.ReasoningEfforts {
		if effort == supported {
			return m, nil
		}
	}
	return nil, errors.New("unsupported_native_effort")
}

func main() {
	listen := flag.String("listen", "", "explicit loopback host:port")
	origin := flag.String("upstream", "", "authorized regional /v1 origin")
	guard := flag.String("guard", "", "real Guard preflight URL")
	region := flag.String("region", "", "tokyo or us")
	model := flag.String("model", "", "one catalog candidate")
	effort := flag.String("effort", "high", "fixed native effort, independent of client settings")
	directory := flag.String("output", "", "new private evaluation directory")
	acknowledged := flag.Bool("fixed-candidate-evaluation", false, "acknowledge this is not Auto selection acceptance")
	flag.Parse()
	candidate, err := validateTarget(*listen, *origin, *guard, *region, *model, ag.ReasoningEffort(*effort))
	if err != nil || !*acknowledged || *directory == "" {
		log.Fatal("invalid evaluation configuration")
	}
	if err := os.Mkdir(*directory, 0700); err != nil {
		log.Fatal("evaluation directory must be new")
	}
	secret := make([]byte, 32)
	if _, err := rand.Read(secret); err != nil {
		log.Fatal("entropy_unavailable")
	}
	cacheSecret := hex.EncodeToString(secret)
	if err := os.WriteFile(filepath.Join(*directory, "identity-secret"), []byte(cacheSecret), 0600); err != nil {
		log.Fatal("private_identity_write_failed")
	}
	upstream := strings.TrimRight(*origin, "/")
	client := &http.Client{Timeout: 5 * time.Minute, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	transport := &ag.HTTPUpstreamClient{Client: client, ForwardClientAuth: true, BufferedSSE: true, Endpoints: []ag.ProviderEndpoint{{Provider: "default", Protocol: "chat", URL: upstream + "/chat/completions"}, {Provider: "default", Protocol: "responses", URL: upstream + "/responses"}, {Provider: "default", Protocol: "anthropic", URL: upstream + "/messages"}}}
	gateway := ag.NewAutoGateway()
	gateway.Catalog = []ag.Model{*candidate}
	meta := ag.PipelineMeta{Region: *region, CacheSecret: cacheSecret, ModelRevision: "fixed-model-capability-profile-v1"}
	state, err := ag.NewFileSessionStateStore(filepath.Join(*directory, "sessions.json"))
	if err != nil {
		log.Fatal("evaluation_state_unavailable")
	}
	audit, err := ag.NewJSONLAuditSink(filepath.Join(*directory, "audit.jsonl"))
	if err != nil {
		log.Fatal("evaluation_audit_unavailable")
	}
	usage, err := ag.NewJSONLUsageSink(filepath.Join(*directory, "usage.jsonl"))
	if err != nil {
		log.Fatal("evaluation_usage_unavailable")
	}
	preflight := &ag.HTTPPreflightChecker{Endpoint: *guard, Region: *region, Provider: candidate.Provider, Client: &http.Client{Timeout: 35 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}}
	pipeline := &ag.Pipeline{Gateway: gateway, Preflight: preflight, Classifier: fixedAssessment{ag.ReasoningEffort(*effort)}, Upstream: transport, StateStore: state, Meta: meta, AuditSink: audit, UsageSink: usage, Usage: ag.NewDailyUsageRecorder()}
	identity := &ag.Sub2APIIdentityResolver{CheckURL: upstream + "/models", Region: *region, Secret: cacheSecret}
	handler := &ag.HTTPServer{Gateway: gateway, Pipeline: pipeline, Identity: identity, StreamClient: transport, Meta: meta}
	lifecycle := &service.Lifecycle{Next: profileEndpoint(handler), AdminSecret: cacheSecret}
	server := &http.Server{Addr: *listen, Handler: lifecycle, ReadHeaderTimeout: 10 * time.Second, IdleTimeout: time.Minute}
	log.Printf("fixed candidate evaluation: region=%s model=%s effort=%s listen=%s; real identity and Guard required; response cache disabled", *region, *model, *effort, *listen)
	if err := service.Run(server, lifecycle, 60*time.Second); err != nil {
		log.Fatal(err)
	}
}
