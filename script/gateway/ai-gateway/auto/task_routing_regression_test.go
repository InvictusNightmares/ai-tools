package autogateway

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func summaryAssessment() TaskAssessment {
	a := assessment("summary", "bounded")
	a.Stage, a.Scope, a.Uncertainty, a.Verification = "understand", "cross_module", "low", "inspection"
	a.ReasoningDependencies, a.FailedAttempts, a.Confidence = 0, 0, 0.98
	a.NeedsTools = true
	return a
}

func TestTaskQualityFloorsAndCapabilities(t *testing.T) {
	for _, item := range []struct {
		kind, complexity, model string
		effort                  ReasoningEffort
	}{
		{"coding", "bounded", "gpt-5.6-luna", ReasoningLow},
		{"debugging", "multi_step", "gpt-5.6-terra", ReasoningMedium},
		{"architecture", "complex", "gpt-5.6-sol", ReasoningHigh},
		{"debugging", "exceptional", "gpt-6-astra", ReasoningXHigh},
	} {
		c := classificationFromAssessment(Request{}, assessment(item.kind, item.complexity))
		d := DecideRoute(NewRouteState(), c, DefaultCatalog, nil, 1, time.Now(), false, false, false)
		if d.SelectedModel == nil || d.SelectedModel.Name != item.model || d.ReasoningEffort != item.effort {
			t.Fatalf("quality floor lost: %+v", d)
		}
		if bestModel(c, DefaultCatalog[:1], nil) != nil {
			t.Fatal("silently routed below quality floor")
		}
	}
	c := classificationFromAssessment(Request{}, summaryAssessment())
	c.RequiredCapabilities = append(c.RequiredCapabilities, CapabilityFiles)
	if m := bestModel(c, DefaultCatalog, nil); m == nil || m.Name != "gpt-5.6-luna" {
		t.Fatal("routine task ignored native file capability")
	}
	c.RequiredCapabilities = []Capability{CapabilityText}
	if m := bestModel(c, DefaultCatalog, map[string]Health{"deepseek-flash": {Unavailable: true}}); m == nil || m.Name != "gpt-5.6-luna" {
		t.Fatal("routine task ignored failed provider")
	}
}

func TestTaskFloorUpgradesImmediatelyAtUserBoundary(t *testing.T) {
	for _, complexity := range []string{"bounded", "multi_step", "complex", "exceptional"} {
		d := DecideRoute(NewRouteState(), classificationFromAssessment(Request{}, summaryAssessment()), DefaultCatalog, nil, 1, time.Now(), false, false, false)
		a := assessment("coding", complexity)
		a.Continuation = true
		c := classificationFromAssessment(Request{}, a)
		d = DecideRoute(d.State, c, DefaultCatalog, nil, 2, time.Now(), false, false, false)
		if d.SelectedModel == nil || d.SelectedModel.Tier < taskModelFloor(c) || !modelSupportsReasoningEffort(*d.SelectedModel, d.ReasoningEffort) {
			t.Fatalf("cooldown overrode quality: %+v", d)
		}
	}
}

func TestRoutineLabelDoesNotHideDifficultWork(t *testing.T) {
	for _, change := range []func(*TaskAssessment){
		func(a *TaskAssessment) { a.Complexity = "complex" },
		func(a *TaskAssessment) { a.Uncertainty = "high" },
		func(a *TaskAssessment) { a.FailedAttempts = 1 },
		func(a *TaskAssessment) { a.ReasoningDependencies = 3 },
		func(a *TaskAssessment) { a.Verification = "proof" },
		func(a *TaskAssessment) { a.Confidence = 0.7 },
		func(a *TaskAssessment) { a.Stage = "implement" },
		func(a *TaskAssessment) { a.TaskLabels = append(a.TaskLabels, "audit") },
	} {
		a := summaryAssessment()
		change(&a)
		if routineInformationTask(a) {
			t.Fatalf("routine shortcut hid nonroutine work: %+v", a)
		}
	}
}

func TestBoundReuseKeepsGuardAndChangedGoalChecks(t *testing.T) {
	for _, mode := range []string{"changed_goal", "block", "unavailable", "changed_instructions", "new_tools", "new_media"} {
		t.Run(mode, func(t *testing.T) {
			calls, guards := 0, 0
			verdict := PreflightAllow
			u := &toolRoundUpstream{}
			p := &Pipeline{Gateway: NewAutoGateway(), StateStore: NewMemorySessionStateStore(), Upstream: u, Preflight: preflightFunc(func(_ context.Context, r Request) (PreflightResult, error) {
				guards++
				return PreflightResult{Decision: verdict}, nil
			}), Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
				calls++
				return classificationFromAssessment(r, assessment("debugging", "bounded")), nil
			})}
			meta := PipelineMeta{RequestID: "first", Region: "tokyo", APIKeyID: "key", SessionID: "s"}
			_, err := p.ExecuteWithMeta(context.Background(), "chat", "", "auto", Request{Messages: []Message{{Role: "user", Content: "fix startup"}}}, 0, false, false, false, false, meta)
			if err != nil {
				t.Fatal(err)
			}
			r := toolResultFixture("chat", "call-1")
			meta.RequestID = "next"
			switch mode {
			case "changed_goal":
				r.Messages[0].Content = "now design a database"
				r.Messages[0].Parts = nil
			case "changed_instructions":
				r.Messages = append([]Message{{Role: "system", Content: "new constraints"}}, r.Messages...)
			case "block":
				verdict = PreflightBlock
			case "unavailable":
				verdict = PreflightUnavailable
			case "new_tools":
				r.Tools = []Tool{{Name: "new_read_tool"}}
			case "new_media":
				r.Native = &NativeMedia{Images: 1}
			}
			result, err := p.ExecuteWithMeta(context.Background(), "chat", "", "auto", r, 0, false, false, false, false, meta)
			if guards != 2 {
				t.Fatal("Guard skipped on tool result")
			}
			if mode == "block" || mode == "unavailable" {
				if calls != 1 || u.calls != 1 || result.UpstreamCalled {
					t.Fatal("Guard failure reached classification/provider")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if mode == "new_tools" {
				if calls != 1 || !result.Classification.Trace.ToolBindingReused {
					t.Fatal("stable goal unnecessarily reclassified")
				}
			} else if calls != 2 {
				t.Fatal("changed goal/instructions/media reused old assessment")
			}
		})
	}
}

func TestBoundReuseRejectsUserTextMixedWithResult(t *testing.T) {
	r := toolResultFixture("anthropic", "call-1")
	r.Messages[len(r.Messages)-1].Parts = append(r.Messages[len(r.Messages)-1].Parts, ContentPart{Type: "text", Text: "Also redesign the system"})
	if onlyPendingToolResults(r) {
		t.Fatal("fresh instruction treated as pure result")
	}
	r = toolResultFixture("chat", "call-1")
	r.Messages = append(r.Messages, Message{Role: "user", Content: "change the objective"})
	if onlyPendingToolResults(r) {
		t.Fatal("fresh user turn reused assessment")
	}
	if strings.Contains(taskGoalDigest(r), "objective") {
		t.Fatal("task text retained in digest")
	}
}

func TestRoutineSummarySelectsEconomicalCapableModel(t *testing.T) {
	r := Request{Messages: []Message{{Role: "user", Content: "Summarize the repository changes"}}, Tools: []Tool{{Name: "read"}}}
	c := classificationFromAssessment(r, summaryAssessment())
	d := DecideRoute(NewRouteState(), c, DefaultCatalog, nil, 1, time.Now(), false, false, false)
	if d.SelectedModel == nil || d.SelectedModel.Name != "deepseek-flash" || d.ReasoningEffort != ReasoningNone {
		t.Fatalf("routine inspection over-routed: %+v", d)
	}
}

func TestRoutineSummaryDoesNotRequirePaidReview(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.Write([]byte(classifierEnvelope(summaryAssessment())))
	}))
	defer srv.Close()
	c := &SemanticClassifier{Endpoint: srv.URL, Model: "primary", ReviewerModel: "reviewer"}
	result, err := c.Classify(context.Background(), Request{Messages: []Message{{Role: "user", Content: "Summarize the repository changes"}}}, PipelineMeta{})
	if err != nil || calls != 1 || result.Trace.Reviewed {
		t.Fatalf("routine inspection paid for redundant review: calls=%d result=%+v err=%v", calls, result, err)
	}
}

func TestBoundToolContinuationDoesNotReclassify(t *testing.T) {
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		for _, plan := range []bool{false, true} {
			t.Run(protocol+map[bool]string{true: "/plan", false: "/execute"}[plan], func(t *testing.T) {
				calls := 0
				p := &Pipeline{Gateway: NewAutoGateway(), Preflight: fixedPreflight{result: PreflightResult{Decision: PreflightAllow}}, StateStore: NewMemorySessionStateStore(), Upstream: &toolRoundUpstream{}, Classifier: taskClassifierFunc(func(_ context.Context, r Request, _ PipelineMeta) (Classification, error) {
					calls++
					return classificationFromAssessment(r, assessment("debugging", "bounded")), nil
				})}
				meta := PipelineMeta{RequestID: "first", Region: "tokyo", APIKeyID: "key", SessionID: "s"}
				_, err := p.ExecuteWithMeta(context.Background(), protocol, "", "auto", Request{Messages: []Message{{Role: "user", Content: "fix startup"}}}, 0, false, false, false, false, meta)
				if err != nil {
					t.Fatal(err)
				}
				meta.RequestID = "next"
				r := toolResultFixture(protocol, "call-1")
				if plan {
					_, err = p.Plan(context.Background(), protocol, "", "auto", r, 0, false, false, false, false, meta)
				} else {
					_, err = p.ExecuteWithMeta(context.Background(), protocol, "", "auto", r, 0, false, false, false, false, meta)
				}
				if err != nil || calls != 1 {
					t.Fatalf("bound result reclassified: calls=%d err=%v", calls, err)
				}
			})
		}
	}
}
