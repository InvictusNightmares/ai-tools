package autogateway

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestClientUserAgentReachesEveryRegionalRequest(t *testing.T) {
	for _, ua := range []string{"opencode/1.18.4", "claude-cli/2.1.233", "codex_cli_rs/0.154.0", "hermes/0.21.0", ""} {
		t.Run(ua, func(t *testing.T) {
			seen := map[string]int{}
			var mu sync.Mutex
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				mu.Lock()
				seen[r.URL.Path]++
				mu.Unlock()
				if r.UserAgent() != ua {
					t.Errorf("%s UA=%q want=%q", r.URL.Path, r.UserAgent(), ua)
				}
				if r.Header.Get("X-Untrusted-Header") != "" {
					t.Error("unrelated header forwarded")
				}
				switch r.URL.Path {
				case "/models":
					io.WriteString(w, `{"data":[]}`)
				case "/classify":
					io.WriteString(w, classifierEnvelope(assessment("quick_qa", "simple")))
				case "/count":
					io.WriteString(w, `{"input_tokens":20}`)
				case "/stream":
					w.Header().Set("Content-Type", "text/event-stream")
					io.WriteString(w, "data: [DONE]\n\n")
				default:
					io.WriteString(w, `{"id":"fixture-response","model":"fixture","choices":[{"message":{"content":"ok"},"finish_reason":"stop"}]}`)
				}
			}))
			defer srv.Close()
			headers := http.Header{"User-Agent": {ua}, "Authorization": {"Bearer synthetic-user-key"}, "X-Untrusted-Header": {"do-not-forward"}}
			r, _ := http.NewRequest("GET", "/v1/models", nil)
			r.Header = headers.Clone()
			resolver := &Sub2APIIdentityResolver{CheckURL: srv.URL + "/models", Region: "tokyo", Secret: strings.Repeat("s", 32)}
			if _, err := resolver.Resolve(r); err != nil {
				t.Fatal(err)
			}
			classifier := &SemanticClassifier{Endpoint: srv.URL + "/classify", Model: "gpt-5.6-luna", ReviewerModel: "gpt-5.6-sol"}
			if _, err := classifier.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "hello"}}}, PipelineMeta{ClientHeaders: headers}); err != nil {
				t.Fatal(err)
			}
			counter := &HTTPTokenCounter{URL: srv.URL + "/count"}
			if _, err := counter.Count(context.Background(), []byte(`{"model":"gpt-5.6-luna"}`), headers, "fixture"); err != nil {
				t.Fatal(err)
			}
			client := &HTTPUpstreamClient{ForwardClientAuth: true, Endpoints: []ProviderEndpoint{{Provider: "openai", Protocol: "chat", URL: srv.URL + "/business"}}}
			request := UpstreamRequest{Provider: "openai", Protocol: "chat", Payload: []byte(`{}`), Headers: headers}
			if _, err := client.Complete(context.Background(), request); err != nil {
				t.Fatal(err)
			}
			client.Endpoints[0].URL = srv.URL + "/stream"
			request.Request.Stream = true
			response, err := client.OpenStream(context.Background(), request)
			if err != nil {
				t.Fatal(err)
			}
			response.Body.Close()
			mu.Lock()
			defer mu.Unlock()
			for _, path := range []string{"/models", "/classify", "/count", "/business", "/stream"} {
				if seen[path] != 1 {
					t.Fatalf("%s calls=%d", path, seen[path])
				}
			}
		})
	}
}
