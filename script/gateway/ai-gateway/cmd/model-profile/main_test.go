package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	ag "local/ai-gateway/auto"
)

func TestProfileListenerAndCandidateBoundaries(t *testing.T) {
	for _, tc := range []struct {
		listen, model, effort string
		allowed               bool
	}{
		{"127.0.0.1:18021", "deepseek-flash", "high", true},
		{"[::1]:18021", "gpt-6-astra", "max", true},
		{"0.0.0.0:18021", "gpt-5.6-luna", "high", false},
		{"192.168.1.2:18021", "gpt-5.6-luna", "high", false},
		{"127.0.0.1:0", "gpt-5.6-luna", "high", false},
		{"127.0.0.1:18021", "auto", "high", false},
		{"127.0.0.1:18021", "gpt-6-astra", "none", false},
	} {
		_, err := validateTarget(tc.listen, "http://127.0.0.1:9881/v1", "http://127.0.0.1:8013/v1/preflight", "tokyo", tc.model, ag.ReasoningEffort(tc.effort))
		if (err == nil) != tc.allowed {
			t.Fatalf("unexpected validation for %s %s %s", tc.listen, tc.model, tc.effort)
		}
	}
}

func TestProfileDoesNotExposeIndependentNativeRoutes(t *testing.T) {
	calls := 0
	handler := profileEndpoint(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(http.StatusNoContent)
	}))
	for _, path := range []string{"/v1/responses", "/v1/responses/compact", "/v1/files", "/v1/images/generations", "/v1/messages"} {
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, httptest.NewRequest(http.MethodPost, path, nil))
		if w.Code != 404 || calls != 0 {
			t.Fatal("fixed candidate profile exposed a separate native route")
		}
	}
	w := httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/v1/chat/completions", nil))
	if w.Code != 204 || calls != 1 {
		t.Fatal("text/tool profile endpoint unavailable")
	}
}

func TestFixedComparisonIgnoresClientEffortAndRetainsBudget(t *testing.T) {
	r, err := ag.NormalizeProtocolRequest("chat", []byte(`{"model":"auto","reasoning_effort":"none","max_tokens":1234,"messages":[{"role":"user","content":"Implement a bounded fix."}]}`))
	if err != nil {
		t.Fatal(err)
	}
	c, err := (fixedAssessment{ag.ReasoningHigh}).Classify(context.Background(), r, ag.PipelineMeta{})
	if err != nil || c.EffectiveReasoningEffort != ag.ReasoningHigh || c.ContextBudget.OutputLimitTokens != 1234 || c.ContextBudget.InputEstimateTokens < len(r.RawPayload) || c.Source != "fixed-model-capability-profile-v1" {
		t.Fatal("fixed comparison contract lost", err)
	}
	r.Native = &ag.NativeMedia{Images: 1}
	if _, err := (fixedAssessment{ag.ReasoningHigh}).Classify(context.Background(), r, ag.PipelineMeta{}); err == nil {
		t.Fatal("text profile silently accepted a different modality")
	}
}

func TestProfileStillChecksIdentityAndGuardBeforeBusiness(t *testing.T) {
	var authCalls, guardCalls, businessCalls atomic.Int64
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v1/models" {
			authCalls.Add(1)
			w.Write([]byte(`{"data":[]}`))
			return
		}
		businessCalls.Add(1)
		w.WriteHeader(500)
	}))
	defer backend.Close()
	guard := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		guardCalls.Add(1)
		w.WriteHeader(503)
		w.Write([]byte(`{"decision":"unavailable"}`))
	}))
	defer guard.Close()
	gateway := ag.NewAutoGateway()
	gateway.Catalog = []ag.Model{*ag.ModelByName("gpt-5.6-luna", ag.DefaultCatalog)}
	transport := &ag.HTTPUpstreamClient{Endpoints: []ag.ProviderEndpoint{{Provider: "default", Protocol: "chat", URL: backend.URL + "/v1/chat/completions"}}}
	pipeline := &ag.Pipeline{Gateway: gateway, Classifier: fixedAssessment{ag.ReasoningHigh}, Preflight: &ag.HTTPPreflightChecker{Endpoint: guard.URL}, Upstream: transport}
	server := &ag.HTTPServer{Gateway: gateway, Pipeline: pipeline, Identity: &ag.Sub2APIIdentityResolver{CheckURL: backend.URL + "/v1/models", Region: "tokyo", Secret: strings.Repeat("s", 32)}, Meta: ag.PipelineMeta{Region: "tokyo"}}
	for _, token := range []string{"", "Bearer synthetic-test"} {
		r := httptest.NewRequest("POST", "/v1/chat/completions", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"Implement a bounded fix."}]}`))
		r.Header.Set("Authorization", token)
		w := httptest.NewRecorder()
		server.ServeHTTP(w, r)
		want := 503
		if token == "" {
			want = 401
		}
		if w.Code != want {
			t.Fatalf("status=%d want=%d", w.Code, want)
		}
	}
	if authCalls.Load() != 1 || guardCalls.Load() != 1 || businessCalls.Load() != 0 {
		t.Fatal("evaluation bypassed the required gate")
	}
}
