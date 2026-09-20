package autogateway

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"
)

type taskClassifierFunc func(context.Context, Request, PipelineMeta) (Classification, error)

type failingClassifierTransport struct{}

func (failingClassifierTransport) RoundTrip(*http.Request) (*http.Response, error) {
	return nil, errors.New("synthetic transport failure")
}

type retryingClassifierTransport struct{ calls int }

func (t *retryingClassifierTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	t.calls++
	if t.calls == 1 {
		return nil, errors.New("synthetic connection reset")
	}
	return &http.Response{StatusCode: http.StatusOK, Header: make(http.Header), Body: io.NopCloser(strings.NewReader(classifierEnvelope(assessment("quick_qa", "simple")))), Request: req}, nil
}

func TestClassifierTransportFailuresRetainAttemptedEffort(t *testing.T) {
	var events []UsageEvent
	c := &SemanticClassifier{Endpoint: "http://classifier.invalid/chat/completions", Model: "gpt-5.6-sol", ReviewerModel: "gpt-6-astra",
		Client: &http.Client{Transport: failingClassifierTransport{}}, OnUsage: func(e UsageEvent) error { events = append(events, e); return nil }}
	_, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "fixture"}}}, PipelineMeta{RequestID: "failed-request"})
	if !errors.Is(err, ErrClassifierUnavailable) || len(events) != 2 {
		t.Fatalf("unexpected classifier result: %v events=%d", err, len(events))
	}
	for i, expected := range []ReasoningEffort{ReasoningNone, ReasoningLow} {
		if events[i].ReasoningEffort != expected || events[i].Success || !events[i].Attempt || events[i].RequestID != "failed-request" {
			t.Fatalf("failed attempt lost effective effort: %+v", events[i])
		}
	}
}

func TestSemanticClassifierRetriesOneTransportFailure(t *testing.T) {
	transport := &retryingClassifierTransport{}
	c := &SemanticClassifier{Endpoint: "http://classifier.invalid/chat/completions", Model: "gpt-5.6-sol", ReviewerModel: "gpt-6-astra", Client: &http.Client{Transport: transport}}
	result, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "hello"}}}, PipelineMeta{})
	if err != nil || transport.calls != 2 || result.Intent != "quick_qa" {
		t.Fatalf("transport retry failed: calls=%d result=%+v err=%v", transport.calls, result, err)
	}
}

func (f taskClassifierFunc) Classify(c context.Context, r Request, m PipelineMeta) (Classification, error) {
	return f(c, r, m)
}
func assessment(kind, complexity string) TaskAssessment {
	return TaskAssessment{TaskLabels: []string{kind}, Stage: "implement", TaskType: kind, Complexity: complexity, Scope: "local", Uncertainty: "low", Verification: "tests", Confidence: .95}
}
func classifierEnvelope(a TaskAssessment) string {
	content, _ := json.Marshal(a)
	out, _ := json.Marshal(map[string]any{"model": "judge", "choices": []any{map[string]any{"finish_reason": "stop", "message": map[string]any{"content": string(content)}}}, "usage": map[string]any{"prompt_tokens": 30, "completion_tokens": 12}})
	return string(out)
}
func TestSemanticClassificationDoesNotUseLanguageOrLengthAsDifficulty(t *testing.T) {
	for _, prompt := range []string{"退出后重启仍登录", "Restart restores an expired session", "logout 后 restart 仍登录", strings.Repeat("请解释", 10000)} {
		c := classificationFromAssessment(Request{Messages: []Message{{Role: "user", Content: prompt}}}, assessment("debugging", "complex"))
		if c.Score != 78 || c.EffectiveReasoningEffort != ReasoningHigh {
			t.Fatalf("%+v", c)
		}
	}
	r := Request{Messages: make([]Message, 20), Tools: []Tool{{Name: "exec"}}}
	for i := range r.Messages {
		r.Messages[i] = Message{Role: "user", Content: "hi"}
	}
	c := classificationFromAssessment(r, assessment("translation", "simple"))
	if c.LongContext || c.Score != 5 || c.Intent != "translation" {
		t.Fatalf("%+v", c)
	}
}
func TestSemanticInputSeparatesRolesAndContinuation(t *testing.T) {
	r := Request{Messages: []Message{{Role: "system", Content: "architecture regression agent"}, {Role: "user", Content: "fix session"}, {Role: "assistant", Content: "examined"}, {Role: "user", Content: "继续"}, {Role: "tool", Content: "failed"}}}
	in, err := splitSemanticInput(r)
	if err != nil || in.Current.Content != "继续" || len(in.History) != 2 || len(in.Instructions) != 1 || len(in.After) != 1 {
		t.Fatalf("%+v %v", in, err)
	}
}
func TestSemanticNormalizedPartsNotDuplicated(t *testing.T) {
	r, _ := NormalizeProtocolRequest("chat", []byte(`{"messages":[{"role":"user","content":[{"type":"text","text":"你好"}]}]}`))
	in, _ := splitSemanticInput(r)
	if in.Current.Content != "你好" {
		t.Fatal(in.Current)
	}
}
func TestSemanticClassifierValidatedReviewAndSeparateUsage(t *testing.T) {
	calls := 0
	var events []UsageEvent
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		var body map[string]any
		json.NewDecoder(r.Body).Decode(&body)
		if body["model"] == "auto" || (body["reasoning_effort"] != "none" && body["reasoning_effort"] != "low") {
			t.Error("invalid classifier request")
		}
		a := assessment("debugging", "complex")
		w.Write([]byte(classifierEnvelope(a)))
	}))
	defer srv.Close()
	c := &SemanticClassifier{Endpoint: srv.URL, Model: "primary", ReviewerModel: "reviewer", OnUsage: func(e UsageEvent) error { events = append(events, e); return nil }}
	result, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "fix concurrency"}}}, PipelineMeta{RequestID: "id"})
	if err != nil || calls != 2 || result.Score != 78 || len(events) != 2 {
		t.Fatalf("%+v %v calls=%d", result, err, calls)
	}
	for _, e := range events {
		if e.Purpose != "classification" || e.InputTokens != 30 || !e.Success || e.RequestID != "id" {
			t.Fatalf("%+v", e)
		}
	}
}
func TestSemanticClassifierFailsClosedOnBadResponse(t *testing.T) {
	for _, body := range []string{`<html>bad</html>`, `{"choices":[]}`, `{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}`, `{"choices":[{"finish_reason":"stop","message":{"content":"{\"model\":\"astra\"}"}}]}`} {
		srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(body)) }))
		c := &SemanticClassifier{Endpoint: srv.URL, Model: "primary", ReviewerModel: "reviewer"}
		_, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "hi"}}}, PipelineMeta{})
		srv.Close()
		if !errors.Is(err, ErrClassifierUnavailable) {
			t.Fatal(err)
		}
	}
}
func TestPipelineGuardPrecedesSemanticAndClassifierFailureHasNoUpstream(t *testing.T) {
	for _, decision := range []PreflightDecision{PreflightBlock, PreflightUnavailable, PreflightAllow} {
		calls := 0
		path := t.TempDir() + "/audit"
		sink, _ := NewJSONLAuditSink(path)
		p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: decision}}, AuditSink: sink, Classifier: taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) {
			calls++
			return Classification{}, ErrClassifierUnavailable
		})}
		result, err := p.Execute(context.Background(), "chat", "openai", "auto", Request{Messages: []Message{{Role: "user", Content: "private text"}}}, 0, false, false, false, false)
		if result.UpstreamCalled {
			t.Fatal("business upstream called")
		}
		if decision == PreflightAllow {
			if calls != 1 || !errors.Is(err, ErrClassifierUnavailable) {
				t.Fatalf("calls %d err %v", calls, err)
			}
		} else if calls != 0 {
			t.Fatal("classifier before guard")
		}
		raw, _ := os.ReadFile(path)
		if strings.Contains(string(raw), "private text") {
			t.Fatal("input leaked")
		}
	}
}
func TestSemanticCacheContextIdentityExpiryAndNoRawText(t *testing.T) {
	calls := 0
	now := time.Unix(1, 0)
	c := &CachedTaskClassifier{Secret: "test", Version: "v1", TTL: time.Second, Now: func() time.Time { return now }, Inner: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
		calls++
		return classificationFromAssessment(r, assessment("coding", "bounded")), nil
	})}
	r := Request{Messages: []Message{{Role: "user", Content: "context-sensitive"}}}
	m := PipelineMeta{Region: "tokyo", APIKeyID: "one", SessionID: "s"}
	c.Classify(context.Background(), r, m)
	c.Classify(context.Background(), r, m)
	if calls != 1 {
		t.Fatal(calls)
	}
	m.APIKeyID = "two"
	c.Classify(context.Background(), r, m)
	if calls != 2 {
		t.Fatal(calls)
	}
	now = now.Add(2 * time.Second)
	c.Classify(context.Background(), r, m)
	if calls != 3 {
		t.Fatal(calls)
	}
	r.Messages = append(r.Messages, Message{Role: "tool", Content: "new failure"})
	c.Classify(context.Background(), r, m)
	if calls != 4 {
		t.Fatal(calls)
	}
	for k := range c.entries {
		if strings.Contains(k, "context") {
			t.Fatal("raw text retained")
		}
	}
}
func TestSemanticEscalationAndContinuation(t *testing.T) {
	r := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	low := classificationFromAssessment(r, assessment("quick_qa", "simple"))
	d := DecideRoute(NewRouteState(), low, DefaultCatalog, nil, 1, time.Now(), false, false, false)
	high := classificationFromAssessment(r, assessment("debugging", "exceptional"))
	d = DecideRoute(d.State, high, DefaultCatalog, nil, 2, time.Now(), false, false, false)
	if d.SelectedModel.Name != "gpt-6-astra" {
		t.Fatal(d)
	}
	low.Assessment.Continuation = true
	d = DecideRoute(d.State, low, DefaultCatalog, nil, 3, time.Now(), false, false, false)
	if d.ReasoningEffort != ReasoningXHigh {
		t.Fatal(d)
	}
}
func TestUsagePurposeIsolation(t *testing.T) {
	r := NewDailyUsageRecorder()
	e := UsageEvent{At: time.Now(), EffectiveModel: "one", Purpose: "classification"}
	r.Record(e)
	e.Purpose = "business"
	r.Record(e)
	if len(r.Snapshot()) != 2 {
		t.Fatal(r.Snapshot())
	}
}
func TestHTTPUpstreamRejectsNonJSON200(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte("<html>gateway error</html>")) }))
	defer srv.Close()
	c := &HTTPUpstreamClient{Endpoints: []ProviderEndpoint{{Protocol: "chat", URL: srv.URL}}}
	r, err := c.Complete(context.Background(), UpstreamRequest{Protocol: "chat", Payload: []byte(`{}`)})
	if err == nil || r.Complete {
		t.Fatalf("%+v %v", r, err)
	}
}

func TestClassificationCacheUsageIsZeroTokenAndSinkFailureFailsClosed(t *testing.T) {
	events := []UsageEvent{}
	c := &CachedTaskClassifier{Secret: "private-fixture", Version: "v1", Inner: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
		result := classificationFromAssessment(r, assessment("quick_qa", "simple"))
		result.Trace = ClassifierTrace{PrimaryModel: "gpt-5.6-luna", DecisionModel: "gpt-5.6-luna"}
		return result, nil
	}), OnCacheHit: func(event UsageEvent) error { events = append(events, event); return nil }}
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	meta := PipelineMeta{Region: "tokyo", APIKeyID: "key", SessionID: "session", RequestID: "request"}
	_, err := c.Classify(context.Background(), request, meta)
	if err != nil {
		t.Fatal(err)
	}
	_, err = c.Classify(context.Background(), request, meta)
	if err != nil || len(events) != 1 {
		t.Fatalf("events=%d err=%v", len(events), err)
	}
	event := events[0]
	if !event.ClassificationCacheHit || event.Attempt || !event.Success || event.InputTokens != 0 || event.OutputTokens != 0 || event.EffectiveModel != "gpt-5.6-luna" {
		t.Fatalf("event=%+v", event)
	}
	c.OnCacheHit = func(UsageEvent) error { return ErrClassifierUnavailable }
	if _, err = c.Classify(context.Background(), request, meta); err == nil {
		t.Fatal("failed accounting was ignored")
	}
}

// The primary's boundary estimate must not decide whether nontrivial work gets
// independent review; equivalent languages may straddle adjacent categories.
func TestSemanticNontrivialReviewCoverage(t *testing.T) {
	for _, kind := range []string{"simple", "bounded", "multi_step", "complex", "exceptional"} {
		t.Run(kind, func(t *testing.T) {
			var events []UsageEvent
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var body struct {
					Model string `json:"model"`
				}
				json.NewDecoder(r.Body).Decode(&body)
				a := assessment("coding", kind)
				if body.Model == "reviewer" {
					a = assessment("coding", "multi_step")
				}
				w.Write([]byte(classifierEnvelope(a)))
			}))
			defer srv.Close()
			c := &SemanticClassifier{Endpoint: srv.URL, Model: "primary", ReviewerModel: "reviewer", OnUsage: func(e UsageEvent) error { events = append(events, e); return nil }}
			result, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "synthetic task"}}}, PipelineMeta{RequestID: "review-coverage"})
			if err != nil {
				t.Fatal(err)
			}
			reviewed := kind != "simple"
			expected := kind
			if reviewed {
				expected = "multi_step"
			}
			count := 1
			if reviewed {
				count = 2
			}
			if len(events) != count || result.Trace.Reviewed != reviewed || result.Assessment.Complexity != expected {
				t.Fatalf("coverage result: %+v, usage calls %d", result, len(events))
			}
			if reviewed && (events[1].EffectiveModel != "reviewer" || events[1].Purpose != "classification") {
				t.Fatal(events)
			}
		})
	}
}

func TestSemanticBoundedReviewerFailureIsUnavailable(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var body struct {
			Model string `json:"model"`
		}
		json.NewDecoder(r.Body).Decode(&body)
		if body.Model == "reviewer" {
			http.Error(w, "unavailable", http.StatusServiceUnavailable)
			return
		}
		w.Write([]byte(classifierEnvelope(assessment("coding", "bounded"))))
	}))
	defer srv.Close()
	c := &SemanticClassifier{Endpoint: srv.URL, Model: "primary", ReviewerModel: "reviewer"}
	_, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "synthetic local edit"}}}, PipelineMeta{})
	if !errors.Is(err, ErrClassifierUnavailable) {
		t.Fatalf("review failure: %v", err)
	}
}
