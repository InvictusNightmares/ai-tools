package guarddeployment

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	goCheck "local/ai-gateway/guard"
)

func TestHTTPModelClientSendsSanitizedInputOnly(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request struct {
			Model    string `json:"model"`
			Messages []struct {
				Role    string `json:"role"`
				Content string `json:"content"`
			} `json:"messages"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		if request.Model != "qwen3guard-gen-8b" {
			t.Fatalf("model = %q", request.Model)
		}
		if len(request.Messages) != 1 || request.Messages[0].Content == "" {
			t.Fatalf("messages = %+v", request.Messages)
		}
		var input goCheck.SafetyInput
		input.Messages = []goCheck.SafetyMessage{{Role: request.Messages[0].Role, Content: request.Messages[0].Content}}
		if input.Messages[0].Content != "password=<REDACTED:secret>" {
			t.Fatalf("content = %q", input.Messages[0].Content)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"Safety: Safe\nCategories: None"}}]}`))
	}))
	defer server.Close()
	client := HTTPModelClient{Endpoint: server.URL, Model: "qwen3guard-gen-8b"}
	_, err := client.Classify(context.Background(), goCheck.SafetyInput{RawBody: []byte(`{"password":"secret"}`), Messages: []goCheck.SafetyMessage{{Role: "user", Content: "password=plain-secret"}}})
	if err != nil {
		t.Fatal(err)
	}
}

func TestHTTPModelClientChecksAllLongInputChunks(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var request struct {
			Messages []struct {
				Content string `json:"content"`
			} `json:"messages"`
		}
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Fatal(err)
		}
		if len(request.Messages) != 1 || len([]rune(request.Messages[0].Content)) > 10000 {
			t.Fatalf("chunk too large: %+v", request.Messages)
		}
		calls.Add(1)
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"Safety: Safe\nCategories: None"}}]}`))
	}))
	defer server.Close()
	client := HTTPModelClient{Endpoint: server.URL, Model: "qwen3guard-gen-8b", MaxChunkChars: 10000}
	result, err := client.Classify(context.Background(), goCheck.SafetyInput{Messages: []goCheck.SafetyMessage{{Role: "user", Content: strings.Repeat("x", 25001)}}})
	if err != nil {
		t.Fatal(err)
	}
	if result.Decision != goCheck.SafetyAllow || calls.Load() != 3 {
		t.Fatalf("result=%+v calls=%d", result, calls.Load())
	}
}

func TestSafetyUsageEachChunkAndSinkFailureClosesGate(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"choices":[{"message":{"content":"Safety: Safe\nCategories: None"}}],"usage":{"prompt_tokens":11,"completion_tokens":3,"prompt_tokens_details":{"cached_tokens":4}}}`))
	}))
	defer server.Close()
	events := []goCheck.ModelUsage{}
	client := HTTPModelClient{Endpoint: server.URL, Model: "qwen3guard-gen-8b", MaxChunkChars: 10000, OnUsage: func(event goCheck.ModelUsage) error { events = append(events, event); return nil }}
	input := goCheck.SafetyInput{RequestID: "r", Region: "tokyo", AccountID: "key-hmac-v1:fixture", Messages: []goCheck.SafetyMessage{{Role: "user", Content: strings.Repeat("x", 25001)}}}
	_, err := client.Classify(context.Background(), input)
	if err != nil || len(events) != 3 {
		t.Fatalf("err=%v events=%d", err, len(events))
	}
	for _, event := range events {
		if !event.Attempt || !event.Success || event.InputTokens != 11 || event.OutputTokens != 3 || event.CacheHitTokens != 4 || event.CacheMissTokens != 7 || event.APIKeyID != input.AccountID {
			t.Fatalf("event=%+v", event)
		}
	}
	client.OnUsage = func(goCheck.ModelUsage) error { return errors.New("disk_full") }
	verdict, err := client.Classify(context.Background(), input)
	if err == nil || err.Error() != "security_usage_unavailable" || verdict.Decision != "" {
		t.Fatalf("verdict=%+v err=%v", verdict, err)
	}
}
