package service

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDrainPreservesInflightAndRejectsNewRequests(t *testing.T) {
	entered, release, done := make(chan struct{}), make(chan struct{}), make(chan struct{})
	l := &Lifecycle{Next: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { close(entered); <-release; w.WriteHeader(200) })}
	first := httptest.NewRecorder()
	go func() { l.ServeHTTP(first, httptest.NewRequest("POST", "/v1/responses", nil)); close(done) }()
	<-entered
	l.Drain(true)
	if draining, n := l.Status(); !draining || n != 1 {
		t.Fatal("inflight count lost")
	}
	second := httptest.NewRecorder()
	l.ServeHTTP(second, httptest.NewRequest("POST", "/v1/responses", nil))
	if second.Code != 503 {
		t.Fatal("new request admitted")
	}
	close(release)
	<-done
	if first.Code != 200 {
		t.Fatal("inflight interrupted")
	}
	if _, n := l.Status(); n != 0 {
		t.Fatal("active count leaked")
	}
}

func TestAdminEndpointRequiresPrivateSecretAndMethod(t *testing.T) {
	l := &Lifecycle{AdminSecret: "internal-only", Next: http.NotFoundHandler()}
	for _, item := range []struct {
		secret, method string
		status         int
	}{{"", "POST", 404}, {"wrong", "POST", 404}, {"internal-only", "GET", 405}, {"internal-only", "POST", 200}} {
		request := httptest.NewRequest(item.method, "/_gateway/drain", strings.NewReader(`{"draining":true}`))
		request.Header.Set("X-Gateway-Admin", item.secret)
		w := httptest.NewRecorder()
		l.ServeHTTP(w, request)
		if w.Code != item.status {
			t.Fatalf("status %d", w.Code)
		}
	}
}
