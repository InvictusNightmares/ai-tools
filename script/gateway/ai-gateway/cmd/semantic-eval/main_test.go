package main

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	ag "local/ai-gateway/auto"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

type classifierFixture struct {
	calls   int
	request ag.Request
}

func (c *classifierFixture) Classify(_ context.Context, request ag.Request, _ ag.PipelineMeta) (ag.Classification, error) {
	c.calls++
	c.request = request
	return ag.Classification{}, nil
}

func TestEvaluationUsesGuardPreparedInputAndFailsClosed(t *testing.T) {
	for _, decision := range []string{"allow", "block", "unavailable", "missing_contract"} {
		t.Run(decision, func(t *testing.T) {
			guard := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				raw, _ := io.ReadAll(r.Body)
				var body map[string]any
				if json.Unmarshal(raw, &body) != nil {
					t.Error("invalid guard payload")
					w.WriteHeader(400)
					return
				}
				if body["region"] != "us" || body["account_id"] != "test-identity" || body["request_id"] != "test-request" {
					t.Error("evaluation identity lost")
				}
				payload := body["provider_payload"].(string)
				digest := sha256.Sum256([]byte(payload))
				result := map[string]any{"decision": decision, "input_sha256": hex.EncodeToString(digest[:]), "redaction_version": "credential-redaction-v1", "sanitized_payload": strings.ReplaceAll(payload, "synthetic-private-value", "[REDACTED]")}
				if decision == "missing_contract" {
					result = map[string]any{"decision": "allow"}
				}
				_ = json.NewEncoder(w).Encode(result)
			}))
			defer guard.Close()
			request, err := ag.NormalizeProtocolRequest("chat", []byte(`{"messages":[{"role":"user","content":"Explain this synthetic-private-value without using it."}]}`))
			if err != nil {
				t.Fatal(err)
			}
			classifier := &classifierFixture{}
			_, _, err = classifySample(context.Background(), request, guard.URL, classifier, ag.PipelineMeta{Region: "us", APIKeyID: "test-identity", RequestID: "test-request"})
			if decision != "allow" {
				if err == nil || classifier.calls != 0 {
					t.Fatal("rejected input reached classifier")
				}
				return
			}
			if err != nil || classifier.calls != 1 {
				t.Fatal("allowed input not classified", err)
			}
			if strings.Contains(string(classifier.request.RawPayload), "synthetic-private-value") || !strings.Contains(classifier.request.Messages[0].Content, "[REDACTED]") {
				t.Fatal("original input bypassed Guard redaction")
			}
		})
	}
}
