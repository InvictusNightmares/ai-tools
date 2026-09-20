package main

import (
	"context"
	"errors"
	gateway "local/ai-gateway/auto"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestGuardTransportBudgetIsBounded(t *testing.T) {
	for _, tc := range []struct {
		raw     string
		seconds int
	}{{"", 5}, {"35", 35}, {"0", 5}, {"-1", 5}, {"invalid", 5}, {"121", 5}} {
		t.Setenv("AUTO_GUARD_TIMEOUT_SECONDS", tc.raw)
		c := guardHTTPClient()
		if c.Timeout != time.Duration(tc.seconds)*time.Second {
			t.Fatalf("input=%q timeout=%v", tc.raw, c.Timeout)
		}
		if c.CheckRedirect(nil, nil) != http.ErrUseLastResponse {
			t.Fatal("Guard redirect must remain disabled")
		}
	}
}

func TestLongGuardBudgetStillCancelsAndFailsClosed(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-r.Context().Done():
		case <-time.After(100 * time.Millisecond):
		}
	}))
	defer server.Close()
	t.Setenv("AUTO_GUARD_TIMEOUT_SECONDS", "35")
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	checker := &gateway.HTTPPreflightChecker{Endpoint: server.URL, Client: guardHTTPClient()}
	result, err := checker.Evaluate(ctx, gateway.Request{})
	if !errors.Is(err, context.DeadlineExceeded) || result.Decision != gateway.PreflightUnavailable {
		t.Fatalf("result=%+v err=%v", result, err)
	}
}
