package gocheck

import (
	"context"
	"testing"
)

func TestRequestCorrelationDoesNotInvalidateSafetyCache(t *testing.T) {
	input := SafetyInput{RequestID: "request-one", Region: "tokyo", SessionHash: "isolated-session", Messages: []SafetyMessage{{Role: "user", Content: "ordinary development task"}}}
	first := decisionCacheKey(input, "rules", "model")
	input.RequestID = "request-two"
	if first != decisionCacheKey(input, "rules", "model") {
		t.Fatal("request correlation changed safety cache identity")
	}
	audit := &memoryAuditSink{}
	gate := testPreflightGate(nil, audit)
	gate.Unavailable(context.Background(), input, "queue_timeout")
	if len(audit.entries) != 1 || audit.entries[0].RequestID != "request-two" {
		t.Fatal("unavailable event lost request correlation")
	}
}
