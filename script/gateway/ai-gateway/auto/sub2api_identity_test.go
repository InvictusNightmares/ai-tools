package autogateway

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestSub2APIIdentityDelegationAndIsolation(t *testing.T) {
	calls := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Header.Get("X-Gateway-API-Key-ID") != "" || r.Header.Get("X-Forwarded-For") != "" {
			t.Error("untrusted identity forwarded")
		}
		if r.Header.Get("Authorization") != "Bearer synthetic-a" && r.Header.Get("Authorization") != "Bearer synthetic-b" {
			t.Error("caller credential not forwarded")
		}
		w.Write([]byte(`{"object":"list","data":[]}`))
	}))
	defer upstream.Close()
	resolver := &Sub2APIIdentityResolver{CheckURL: upstream.URL, Region: "tokyo", Secret: strings.Repeat("s", 32)}
	resolve := func(token, header string) string {
		t.Helper()
		r := httptest.NewRequest("GET", "/v1/models", nil)
		r.Header.Set(header, token)
		r.Header.Set("X-Gateway-API-Key-ID", "141")
		r.Header.Set("X-Forwarded-For", "127.0.0.1")
		id, err := resolver.Resolve(r)
		if err != nil || !strings.HasPrefix(id, "key-hmac-v1:") || strings.Contains(id, "synthetic") {
			t.Fatalf("invalid identity: %v", err)
		}
		return id
	}
	a := resolve("Bearer synthetic-a", "Authorization")
	if a != resolve("synthetic-a", "X-API-Key") || a == resolve("Bearer synthetic-b", "Authorization") {
		t.Fatal("identity not stable per key or collides across keys")
	}
	resolver.Region = "us"
	if a == resolve("Bearer synthetic-a", "Authorization") || calls != 4 {
		t.Fatal("region isolation or per-request check failed")
	}
}

func TestSub2APIIdentityFailsClosed(t *testing.T) {
	for _, tc := range []struct {
		name   string
		status int
		body   string
		want   int
	}{
		{"revoked", 401, "private auth details", 401}, {"quota", 403, "private billing details", 403},
		{"rate", 429, "private rate details", 429}, {"outage", 500, "internal details", 503},
		{"redirect", 302, "", 503}, {"html", 200, "<html>login</html>", 503},
		{"wrong-json", 200, `{}`, 503}, {"null", 200, `{"data":null}`, 503},
		{"oversized", 200, strings.Repeat(" ", (1<<20)+1), 503},
	} {
		t.Run(tc.name, func(t *testing.T) {
			backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.Header().Set("Location", "/redirect-must-not-follow")
				w.WriteHeader(tc.status)
				w.Write([]byte(tc.body))
			}))
			defer backend.Close()
			resolver := &Sub2APIIdentityResolver{CheckURL: backend.URL, Region: "tokyo", Secret: strings.Repeat("s", 32)}
			r := httptest.NewRequest("GET", "/v1/models", nil)
			r.Header.Set("Authorization", "Bearer synthetic")
			id, err := resolver.Resolve(r)
			status := 401
			var failure *identityError
			if errors.As(err, &failure) {
				status = failure.status
			}
			if id != "" || err == nil || status != tc.want || strings.Contains(err.Error(), "private") {
				t.Fatalf("status=%d err=%v", status, err)
			}
		})
	}
}

func TestSub2APIRejectsAmbiguousCredentialsWithoutNetwork(t *testing.T) {
	for _, headers := range []http.Header{
		{}, {"Authorization": {"Basic synthetic"}}, {"Authorization": {"Bearer a", "Bearer a"}},
		{"X-Api-Key": {"a", "a"}}, {"Authorization": {"Bearer a"}, "X-Api-Key": {"b"}},
		{"X-Api-Key": {"a,b"}}, {"X-Api-Key": {"a b"}},
	} {
		r := httptest.NewRequest("GET", "/v1/models", nil)
		r.Header = headers
		if _, err := (&Sub2APIIdentityResolver{}).Resolve(r); !errors.Is(err, ErrUnauthorized) {
			t.Fatalf("err=%v", err)
		}
	}
	r := httptest.NewRequest("GET", "/v1/models?key=hidden", nil)
	r.Header.Set("Authorization", "Bearer synthetic")
	if _, err := requestToken(r); !errors.Is(err, ErrUnauthorized) {
		t.Fatal("query credential accepted")
	}
}

func TestTrustedIngressClientIPMatchesAuthAndBusiness(t *testing.T) {
	for _, ip := range []string{"192.0.2.19", "", "forged,proxy"} {
		source := http.Header{"Authorization": {"Bearer synthetic"}, "X-Gateway-Client-Ip": {ip}, "X-Forwarded-For": {"198.51.100.99"}}
		destination := http.Header{}
		copyAuthHeaders(destination, source)
		expected := ""
		if ip == "192.0.2.19" {
			expected = ip
		}
		if destination.Get("X-Forwarded-For") != expected || destination.Get("X-Real-IP") != expected || destination.Get("X-Gateway-Client-IP") != "" {
			t.Fatal("client IP trust boundary failed")
		}
	}
}

func TestDelegatedIdentityPrecedesCacheAndOverridesStaticIdentity(t *testing.T) {
	status, checks, guardCalls := 200, 0, 0
	backend := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		checks++
		w.WriteHeader(status)
		w.Write([]byte(`{"data":[]}`))
	}))
	defer backend.Close()
	resolver := &Sub2APIIdentityResolver{CheckURL: backend.URL, Region: "tokyo", Secret: strings.Repeat("s", 32)}
	path := t.TempDir() + "/audit.jsonl"
	sink, err := NewJSONLAuditSink(path)
	if err != nil {
		t.Fatal(err)
	}
	upstream := &recordingUpstream{}
	p := &Pipeline{Gateway: NewAutoGateway(), Upstream: upstream, Cache: NewMemoryResponseCache(), CachePolicy: DefaultResponseCachePolicy(), AuditSink: sink,
		Preflight: preflightFunc(func(context.Context, Request) (PreflightResult, error) {
			guardCalls++
			return PreflightResult{Decision: PreflightAllow}, nil
		})}
	server := &HTTPServer{Gateway: p.Gateway, Pipeline: p, Identity: resolver, Meta: PipelineMeta{Region: "tokyo", APIKeyID: "141", SessionID: "shared-session", CacheSecret: strings.Repeat("s", 32), ModelRevision: "test"}}
	for _, item := range []struct {
		token                string
		upstreamStatus, want int
	}{
		{"synthetic-a", 200, 200}, {"synthetic-a", 200, 200}, {"synthetic-b", 200, 200},
		{"synthetic-a", 403, 403}, {"synthetic-a", 401, 401}, {"synthetic-a", 503, 503},
	} {
		status = item.upstreamStatus
		r := httptest.NewRequest("POST", "/v1/chat/completions", strings.NewReader(`{"model":"auto","messages":[{"role":"user","content":"hello"}]}`))
		r.Header.Set("Authorization", "Bearer "+item.token)
		r.Header.Set("X-Gateway-API-Key-ID", "forged")
		w := httptest.NewRecorder()
		server.ServeHTTP(w, r)
		if w.Code != item.want {
			t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
		}
		if w.Header().Get("X-Gateway-Request-ID") == "" {
			t.Fatal("missing audit correlation")
		}
	}
	if checks != 6 || guardCalls != 3 || upstream.calls != 2 {
		t.Fatalf("auth=%d guard=%d business=%d", checks, guardCalls, upstream.calls)
	}
	audit, _ := os.ReadFile(path)
	if !strings.Contains(string(audit), "identity_rejected") || strings.Contains(string(audit), "synthetic-") || strings.Contains(string(audit), `"api_key_id":"141"`) || strings.Contains(string(audit), "forged") {
		t.Fatal("audit isolation/redaction failed")
	}
}
