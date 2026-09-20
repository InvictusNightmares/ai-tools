package gocheck

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"
)

func historyFixture(extra string) SafetyInput {
	items := []map[string]string{{"role": "system", "content": "inspect code"}, {"role": "user", "content": "fix logout"}}
	for i := 0; i < 8; i++ {
		items = append(items, map[string]string{"role": "assistant", "content": "safe prior reasoning"}, map[string]string{"role": "tool", "content": "safe repository result"})
	}
	if extra != "" {
		items = append(items, map[string]string{"role": "user", "content": extra})
	}
	raw, _ := json.Marshal(map[string]any{"model": "auto", "messages": items, "tools": []any{}})
	return SafetyInput{SessionHash: "s", AccountID: "key-a", Region: "tokyo", ProviderPayload: string(raw)}
}

func TestHistoryAppendReusesOnlyVerifiedPrefixAndKeepsFullSanitizedBody(t *testing.T) {
	c := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
	g := NewPreflightGate(DefaultPreflightConfig(), c, nil)
	g.Evaluate(context.Background(), historyFixture(""))
	in := historyFixture("continue with these results")
	r := g.Evaluate(context.Background(), in)
	if r.Decision != SafetyAllow || r.HistoryReusedMessages < 10 || r.SanitizedPayload != in.ProviderPayload {
		t.Fatalf("bad reuse: %+v", r)
	}
	for _, text := range []string{"inspect code", "fix logout", "continue with these results"} {
		if !strings.Contains(c.seen.ProviderPayload, text) {
			t.Fatalf("context missing %s", text)
		}
	}
	if len(c.seen.ProviderPayload) >= len(in.ProviderPayload) {
		t.Fatal("history was not reduced")
	}
}

func TestHistoryInvalidationAndIdentity(t *testing.T) {
	for _, test := range []string{"edited", "tools", "key", "session", "region", "rule", "model", "expired", "restart", "compressed"} {
		t.Run(test, func(t *testing.T) {
			c := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
			g := NewPreflightGate(DefaultPreflightConfig(), c, nil)
			now := time.Now()
			g.Now = func() time.Time { return now }
			g.Evaluate(context.Background(), historyFixture(""))
			in := historyFixture("next")
			switch test {
			case "edited":
				in.ProviderPayload = strings.Replace(in.ProviderPayload, "safe repository result", "changed result", 1)
			case "tools":
				in.ProviderPayload = strings.Replace(in.ProviderPayload, `"tools":[]`, `"tools":[{"new":"tool"}]`, 1)
			case "key":
				in.AccountID = "key-b"
			case "session":
				in.SessionHash = "other"
			case "region":
				in.Region = "us"
			case "rule":
				g.Config.RuleVersion = "other"
			case "model":
				g.Config.ModelVersion = "other"
			case "expired":
				now = now.Add(10 * time.Minute)
			case "restart":
				g = NewPreflightGate(DefaultPreflightConfig(), c, nil)
			case "compressed":
				in.ProviderPayload = `{"model":"auto","messages":[{"role":"user","content":"summary of previous work"}]}`
			}
			if r := g.Evaluate(context.Background(), in); r.Decision != SafetyAllow || r.HistoryReusedMessages != 0 {
				t.Fatalf("unsafe reuse: %+v", r)
			}
		})
	}
}

func TestHistoryNeverCachesFailedInspection(t *testing.T) {
	for _, unavailable := range []bool{false, true} {
		c := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyBlock, RiskLevel: RiskHigh}}
		if unavailable {
			c.err = errors.New("offline")
		}
		g := NewPreflightGate(DefaultPreflightConfig(), c, nil)
		g.Evaluate(context.Background(), historyFixture(""))
		if len(g.history) != 0 {
			t.Fatal("failed history was cached")
		}
	}
}

func TestHistoryDoesNotSkipCredentialsOrNewUnsafeContent(t *testing.T) {
	c := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
	g := NewPreflightGate(DefaultPreflightConfig(), c, nil)
	g.Evaluate(context.Background(), historyFixture(""))
	c.verdict = ModelVerdict{Decision: SafetyBlock, RiskLevel: RiskHigh}
	if r := g.Evaluate(context.Background(), historyFixture("new unsafe instruction")); r.Decision != SafetyBlock || !strings.Contains(c.seen.ProviderPayload, "new unsafe instruction") {
		t.Fatal("new input skipped")
	}
	g = NewPreflightGate(DefaultPreflightConfig(), c, nil)
	c.verdict = ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}
	g.Evaluate(context.Background(), historyFixture(""))
	if r := g.Evaluate(context.Background(), historyFixture("Use this password=synthetic-secret")); r.Decision != SafetyBlock {
		t.Fatal("credential rules skipped")
	}
}

func TestHistoryCacheCapacity(t *testing.T) {
	c := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
	config := DefaultPreflightConfig()
	config.HistoryCacheCapacity = 2
	g := NewPreflightGate(config, c, nil)
	for _, session := range []string{"a", "b", "c", "d"} {
		in := historyFixture("")
		in.SessionHash = session
		g.Evaluate(context.Background(), in)
	}
	if len(g.history) > 2 {
		t.Fatal("history cache unbounded")
	}
}
