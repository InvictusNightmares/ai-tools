package autogateway

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestKnownClientModelsRemainAutomaticAfterMigration(t *testing.T) {
	for _, model := range DefaultCatalog {
		for _, path := range []string{"/v1/responses", "/v1/responses/compact"} {
			t.Run(model.Name+path, func(t *testing.T) {
				g := NewAutoGateway()
				u := &compactEndpointUpstream{valid: true}
				guardCalls := 0
				p := &Pipeline{Gateway: g, Upstream: u, Preflight: preflightFunc(func(context.Context, Request) (PreflightResult, error) {
					guardCalls++
					return PreflightResult{Decision: PreflightAllow}, nil
				})}
				input := `[{"role":"user","content":"remember marker"}]`
				if path == "/v1/responses" {
					input = `[{"role":"user","content":"remember marker"},{"type":"compaction_trigger"}]`
				}
				raw := `{"model":"` + model.Name + `","input":` + input + `}`
				w := httptest.NewRecorder()
				(&HTTPServer{Gateway: g, Pipeline: p}).ServeHTTP(w, httptest.NewRequest("POST", path, strings.NewReader(raw)))
				if w.Code != 200 || guardCalls != 1 || u.calls != 1 {
					t.Fatalf("migration failed: status=%d guard=%d upstream=%d", w.Code, guardCalls, u.calls)
				}
				if u.last.Model.Name != "gpt-5.6-luna" {
					t.Fatalf("client model forced business selection: %s", u.last.Model.Name)
				}
			})
		}
	}
}

func TestRoutinePhaseCanDownshiftAfterComplexWork(t *testing.T) {
	for _, kind := range []string{"summary", "extraction", "translation", "formatting", "quick_qa"} {
		t.Run(kind, func(t *testing.T) {
			a := assessment(kind, "simple")
			a.TaskLabels, a.Stage = []string{kind}, "continue"
			a.Continuation, a.NewTask, a.Confidence = true, false, .96
			a.Uncertainty, a.Verification, a.ReasoningDependencies = "low", "inspection", 0
			c := classificationFromAssessment(Request{}, a)
			state := NewRouteState()
			state.HasCurrent, state.CurrentModel, state.CurrentTier = true, "gpt-5.6-terra", 2
			state.CurrentReasoningEffort, state.LastSwitchTurn = ReasoningMedium, 7
			for _, locked := range []bool{false, true} {
				r := DecideRoute(state, c, DefaultCatalog, nil, 8, time.Now(), false, locked, false)
				want := "deepseek-flash"
				if locked {
					want = "gpt-5.6-terra"
				}
				if r.SelectedModel == nil || r.SelectedModel.Name != want || (!locked && r.ReasoningEffort != ReasoningNone) {
					t.Fatalf("locked=%v got %+v", locked, r)
				}
			}
		})
	}
}

func TestRoutineDownshiftRetainsUnresolvedWorkAndNativeCapabilities(t *testing.T) {
	for _, variant := range []string{"uncertain", "failure", "audit", "dependencies", "confidence", "tools", "stream", "native_state", "unhealthy"} {
		t.Run(variant, func(t *testing.T) {
			a := assessment("summary", "simple")
			a.TaskLabels, a.Stage, a.Uncertainty, a.Verification = []string{"summary"}, "continue", "low", "inspection"
			a.Confidence, a.Continuation, a.NewTask, a.ReasoningDependencies = .96, true, false, 0
			switch variant {
			case "uncertain":
				a.Uncertainty = "high"
			case "failure":
				a.FailedAttempts = 1
			case "audit":
				a.TaskLabels = []string{"summary", "audit"}
			case "dependencies":
				a.ReasoningDependencies = 3
			case "confidence":
				a.Confidence = .89
			}
			c := classificationFromAssessment(Request{}, a)
			state := NewRouteState()
			state.HasCurrent, state.CurrentModel, state.CurrentTier = true, "gpt-5.6-terra", 2
			state.CurrentReasoningEffort = ReasoningMedium
			want := state.CurrentModel
			health := map[string]Health{}
			if variant == "native_state" {
				c.RequiredCapabilities = append(c.RequiredCapabilities, CapabilityCompaction)
				want = "gpt-5.6-luna"
			}
			if variant == "unhealthy" {
				health["deepseek-flash"], health["gpt-5.6-luna"] = Health{Score: .1}, Health{Score: .1}
			}
			r := DecideRouteAtTurnBoundary(state, c, DefaultCatalog, health, 8, time.Now(), false, variant == "tools", false, variant == "stream")
			if r.SelectedModel == nil || r.SelectedModel.Name != want {
				t.Fatalf("unsafe downshift: %+v", r)
			}
		})
	}
}

func TestRejectedModelAuditDistinguishesCompactionWithoutRawInput(t *testing.T) {
	path := filepath.Join(t.TempDir(), "audit.jsonl")
	sink, _ := NewJSONLAuditSink(path)
	g := NewAutoGateway()
	p := &Pipeline{Gateway: g, AuditSink: sink}
	s := &HTTPServer{Gateway: g, Pipeline: p}
	raw := `{"model":"private-model-value","input":[{"role":"user","content":"private-prompt"},{"type":"compaction_trigger"}]}`
	r := httptest.NewRequest("POST", "/v1/responses", strings.NewReader(raw))
	r.Header.Set("session-id", "private-session")
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	data, _ := os.ReadFile(path)
	var row map[string]any
	if json.Unmarshal(data, &row) != nil || w.Code != 404 || row["request_operation"] != "compaction" || row["protocol"] != "responses" || row["session_hash"] == nil || row["requested_model_hash"] == nil {
		t.Fatalf("missing diagnostic metadata: %s", data)
	}
	if strings.Contains(string(data), "private-") || strings.Contains(w.Body.String(), "private-") {
		t.Fatal("private request data leaked")
	}
}
