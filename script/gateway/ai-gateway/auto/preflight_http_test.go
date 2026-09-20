package autogateway

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHTTPPreflightCheckerSendsSanitizedShapeAndParsesAllow(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		var payload map[string]any
		if err := json.NewDecoder(request.Body).Decode(&payload); err != nil {
			t.Fatal(err)
		}
		encoded, _ := json.Marshal(payload)
		if strings.Contains(string(encoded), "secret-raw") || strings.Contains(string(encoded), "Raw") {
			t.Fatalf("raw content leaked to Guard: %s", encoded)
		}
		_, _ = writer.Write([]byte(`{"decision":"allow","reason_codes":[]}`))
	}))
	defer server.Close()
	checker := &HTTPPreflightChecker{Endpoint: server.URL, Provider: "openai", Region: "tokyo", SessionID: "session-a"}
	result, err := checker.Evaluate(context.Background(), Request{Messages: []Message{{Role: "user", Content: "safe", Parts: []ContentPart{{Type: "image_url", Raw: []byte(`{"url":"secret-raw"}`)}}}}})
	if err != nil || result.Decision != PreflightAllow {
		t.Fatalf("result=%+v err=%v", result, err)
	}
}

func TestHTTPPreflightCheckerFailsClosedOnUnavailable(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		writer.WriteHeader(http.StatusServiceUnavailable)
		_, _ = writer.Write([]byte(`{"decision":"unavailable","reason_codes":["queue_timeout"]}`))
	}))
	defer server.Close()
	checker := &HTTPPreflightChecker{Endpoint: server.URL}
	result, err := checker.Evaluate(context.Background(), Request{Messages: []Message{{Role: "user", Content: "hello"}}})
	if err == nil || result.Decision != PreflightUnavailable || len(result.ReasonCodes) != 1 {
		t.Fatalf("result=%+v err=%v", result, err)
	}
}

func TestGuardReceivesIsolatedSessionAndRequestID(t *testing.T) {
	var seen []map[string]any
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		if r.Header.Get("Authorization") != "" || r.Header.Get("X-API-Key") != "" || body["request_id"] != r.Header.Get("X-Request-ID") {
			t.Error("Guard identity correlation or auth boundary violated")
		}
		seen = append(seen, body)
		w.Write([]byte(`{"decision":"allow"}`))
	}))
	defer server.Close()
	checker := &HTTPPreflightChecker{Endpoint: server.URL}
	for _, key := range []string{"key-a", "key-b"} {
		meta := PipelineMeta{RequestID: "request-" + key, Region: "tokyo", APIKeyID: key, SessionID: "shared-client-id", ClientHeaders: http.Header{"Authorization": []string{"Bearer synthetic"}}}
		_, err := evaluatePreflight(context.Background(), checker, Request{Messages: []Message{{Role: "user", Content: "ordinary task"}}}, meta)
		if err != nil {
			t.Fatal(err)
		}
	}
	if len(seen) != 2 || seen[0]["session_hash"] == "" || seen[0]["session_hash"] == seen[1]["session_hash"] || seen[0]["region"] != "tokyo" {
		t.Fatal("Guard session state is not isolated by region and key")
	}
}

func TestGuardAllowWithoutBoundPayloadFailsClosed(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(`{"decision":"allow"}`)) }))
	defer server.Close()
	request, err := NormalizeProtocolRequest("chat", []byte(`{"messages":[{"role":"user","content":"Explain this config: password=fixtureplain"}]}`))
	if err != nil {
		t.Fatal(err)
	}
	checker := &HTTPPreflightChecker{Endpoint: server.URL}
	result, err := checker.Evaluate(context.Background(), request)
	if err == nil || result.Decision != PreflightUnavailable {
		t.Fatal("allow-only Guard let original unredacted payload through")
	}
}
