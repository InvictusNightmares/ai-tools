package gocheck

import (
	"context"
	"errors"
	"testing"
	"time"
)

type fakeSafetyClassifier struct {
	verdict ModelVerdict
	err     error
	seen    SafetyInput
	calls   int
}

func (f *fakeSafetyClassifier) Classify(_ context.Context, input SafetyInput) (ModelVerdict, error) {
	f.calls++
	f.seen = input
	return f.verdict, f.err
}

func TestPreflightDecisionCacheAvoidsRepeatedGuardCall(t *testing.T) {
	classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow, Confidence: 0.9}}
	gate := testPreflightGate(classifier, nil)
	input := SafetyInput{Protocol: "chat", Provider: "openai", Model: "auto", SessionHash: "session-cache", Messages: []SafetyMessage{{Role: "user", Content: "safe request"}}}
	first := gate.Evaluate(context.Background(), input)
	second := gate.Evaluate(context.Background(), input)
	if first.Decision != SafetyAllow || second.Decision != SafetyAllow {
		t.Fatalf("unexpected decisions: %+v %+v", first, second)
	}
	if classifier.calls != 1 {
		t.Fatalf("classifier calls = %d, want 1", classifier.calls)
	}
}

type memoryAuditSink struct{ entries []PreflightAudit }

func (m *memoryAuditSink) WritePreflightAudit(_ context.Context, entry PreflightAudit) error {
	m.entries = append(m.entries, entry)
	return nil
}

type failingAuditSink struct{}

func (failingAuditSink) WritePreflightAudit(context.Context, PreflightAudit) error {
	return errors.New("audit unavailable")
}

func TestPreflightRulesRunBeforeSanitizedDecisionCache(t *testing.T) {
	classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
	gate := testPreflightGate(classifier, nil)
	first := gate.Evaluate(context.Background(), SafetyInput{SessionHash: "cache-order", Messages: []SafetyMessage{{Role: "user", Content: "password=<REDACTED:secret>"}}})
	if first.Decision != SafetyAllow {
		t.Fatalf("first decision = %s", first.Decision)
	}
	second := gate.Evaluate(context.Background(), SafetyInput{SessionHash: "cache-order", Messages: []SafetyMessage{{Role: "user", Content: "Use this password=plain-secret"}}})
	if second.Decision != SafetyBlock {
		t.Fatalf("plaintext credential bypassed rules: %+v", second)
	}
}

func TestPreflightAuditFailureFailsClosed(t *testing.T) {
	gate := testPreflightGate(&fakeSafetyClassifier{err: errors.New("model unavailable")}, failingAuditSink{})
	result := gate.Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: "ordinary request"}}})
	if result.Decision != SafetyUnavailable {
		t.Fatalf("decision = %s", result.Decision)
	}
	if len(result.ReasonCodes) == 0 || result.ReasonCodes[len(result.ReasonCodes)-1] != "audit_write_failed" {
		t.Fatalf("reason codes = %v", result.ReasonCodes)
	}
}

func testPreflightGate(classifier SafetyClassifier, audit AuditSink) *PreflightGate {
	config := DefaultPreflightConfig()
	config.SessionBlockTTL = time.Hour
	config.AccountQuarantineTTL = time.Hour
	gate := NewPreflightGate(config, classifier, audit)
	gate.Now = func() time.Time { return time.Unix(100, 0) }
	return gate
}

func TestPreflightAllowsBenignRequestThroughModel(t *testing.T) {
	gate := testPreflightGate(&fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow, Confidence: 0.98}}, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{Protocol: "responses", Provider: "openai", Messages: []SafetyMessage{{Role: "user", Content: "Explain how to harden an HTTP server."}}})
	if result.Decision != SafetyAllow {
		t.Fatalf("decision = %s", result.Decision)
	}
}

func TestPreflightBlocksCredentialUseBeforeModel(t *testing.T) {
	classifier := &fakeSafetyClassifier{err: errors.New("model must not be called")}
	audit := &memoryAuditSink{}
	gate := testPreflightGate(classifier, audit)
	result := gate.Evaluate(context.Background(), SafetyInput{
		Protocol: "chat", Provider: "openai", AccountID: "acct-1", SessionHash: "session-1",
		RawBody:  []byte(`{"messages":[{"role":"user","content":"Use this password=synthetic-fixture-secret to login"}]}`),
		Messages: []SafetyMessage{{Role: "user", Content: "Use this password=synthetic-fixture-secret to login."}},
	})
	if result.Decision != SafetyBlock || result.RiskLevel != RiskHigh {
		t.Fatalf("unexpected result: %+v", result)
	}
	if len(audit.entries) != 1 || audit.entries[0].BodySHA256 == "" || len(audit.entries[0].RawBody) == 0 {
		t.Fatalf("audit evidence missing: %+v", audit.entries)
	}
	blocked := gate.Evaluate(context.Background(), SafetyInput{AccountID: "acct-1", SessionHash: "session-1", Messages: []SafetyMessage{{Role: "user", Content: "hello"}}})
	if blocked.Decision != SafetyBlock {
		t.Fatalf("session should remain blocked: %+v", blocked)
	}
}

func TestPreflightFailClosedWhenModelUnavailable(t *testing.T) {
	gate := testPreflightGate(nil, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: "ordinary request"}}})
	if result.Decision != SafetyUnavailable {
		t.Fatalf("decision = %s", result.Decision)
	}
}

func TestPreflightRedactsSecretsBeforeModelAndAudit(t *testing.T) {
	classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow, Confidence: 0.9}}
	audit := &memoryAuditSink{}
	gate := testPreflightGate(classifier, audit)
	result := gate.Evaluate(context.Background(), SafetyInput{
		RawBody:  []byte(`{"password":"plain-password-123","messages":[{"role":"user","content":"Please explain password rotation."}]}`),
		Messages: []SafetyMessage{{Role: "user", Content: "password=plain-password-123; explain password rotation."}},
	})
	if result.Decision != SafetyAllow {
		t.Fatalf("decision = %s", result.Decision)
	}
	if len(classifier.seen.Messages) != 1 || classifier.seen.Messages[0].Content == "password=plain-password-123; explain password rotation." {
		t.Fatalf("classifier received plaintext secret: %+v", classifier.seen.Messages)
	}
	if len(audit.entries) != 0 {
		t.Fatalf("allow request should not create hit audit: %+v", audit.entries)
	}
}

func TestPreflightDetectsQuotedJSONCredentialFields(t *testing.T) {
	classifier := &fakeSafetyClassifier{err: errors.New("model must not be called")}
	gate := testPreflightGate(classifier, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{
		RawBody:  []byte(`{"password":"plain-password-123","messages":[{"role":"user","content":"Use this password to login"}]}`),
		Messages: []SafetyMessage{{Role: "user", Content: `{"password":"plain-password-123"} Use this password to login`}},
	})
	if result.Decision != SafetyBlock {
		t.Fatalf("quoted credential was not blocked: %+v", result)
	}
}

func TestPreflightScansMetadataAndToolSchemaForCredentials(t *testing.T) {
	classifier := &fakeSafetyClassifier{err: errors.New("model must not be called")}
	gate := testPreflightGate(classifier, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{
		Metadata: map[string]string{"payload": `{"api_key":"plain-secret-123"}`},
		Tools:    []SafetyTool{{Name: "login", Schema: `{"password":"plain-password-123"}`}},
		Messages: []SafetyMessage{{Role: "user", Content: "Use this credential to login"}},
	})
	if result.Decision != SafetyBlock {
		t.Fatalf("metadata/tool credential was not blocked: %+v", result)
	}
}

func TestPreflightBlocksRealSecretWhenRequestWantsToUseIt(t *testing.T) {
	classifier := &fakeSafetyClassifier{err: errors.New("model must not be called")}
	gate := testPreflightGate(classifier, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: "Use this API key=sk-abcdefghijklmnopqrst to login to the production host."}}})
	if result.Decision != SafetyBlock || result.RiskLevel != RiskHigh {
		t.Fatalf("unexpected result: %+v", result)
	}
}

func TestPreflightStrictlyBlocksMediumModelVerdict(t *testing.T) {
	gate := testPreflightGate(&fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskMedium, Confidence: 0.6}}, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: "boundary request"}}})
	if result.Decision != SafetyBlock {
		t.Fatalf("decision = %s", result.Decision)
	}
}

func TestAmbiguousDevelopmentSignalsRequireSemanticVerdict(t *testing.T) {
	for name, content := range map[string]string{
		"zh_logout":         "退出登录时清空持久化存储。\n```ts\nawait storage.clear()\n```",
		"en_release":        "Review the production release script.\n```bash\nnpm test\n```",
		"three_signals":     "Review persistence in the production app.\n```ts\nawait storage.clear()\n```",
		"credential_schema": "Explain the API key configuration field.\n```json\n{\"required\": [\"api_key\"]}\n```",
		"quoted_injection":  "Explain why the phrase 'ignore previous instructions' is a prompt injection attempt.",
	} {
		t.Run(name, func(t *testing.T) {
			classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow, Confidence: 0.9}}
			gate := testPreflightGate(classifier, nil)
			input := SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: content}}}
			result := gate.Evaluate(context.Background(), input)
			if result.Decision != SafetyAllow || classifier.calls != 1 {
				t.Fatalf("ambiguous signals overrode semantic verdict: %+v, calls=%d", result, classifier.calls)
			}
			for _, risk := range []RiskLevel{RiskMedium, RiskHigh} {
				classifier.verdict = ModelVerdict{Decision: SafetyBlock, RiskLevel: risk}
				if got := testPreflightGate(classifier, nil).Evaluate(context.Background(), input); got.Decision != SafetyBlock {
					t.Fatalf("unsafe semantic verdict ignored: %+v", got)
				}
			}
			if got := testPreflightGate(nil, nil).Evaluate(context.Background(), input); got.Decision != SafetyUnavailable {
				t.Fatalf("missing classifier did not fail closed: %+v", got)
			}
		})
	}
}

func TestUpstreamCyberQuarantinesAccountAfterThreshold(t *testing.T) {
	gate := testPreflightGate(&fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}, nil)
	gate.ObserveUpstreamCyber("acct-9", "session-9")
	first := gate.Evaluate(context.Background(), SafetyInput{AccountID: "acct-9", Messages: []SafetyMessage{{Role: "user", Content: "safe"}}})
	if first.Decision == SafetyBlock {
		t.Fatalf("first cyber signal should not quarantine account: %+v", first)
	}
	gate.ObserveUpstreamCyber("acct-9", "other-session")
	second := gate.Evaluate(context.Background(), SafetyInput{AccountID: "acct-9", Messages: []SafetyMessage{{Role: "user", Content: "safe"}}})
	if second.Decision != SafetyBlock {
		t.Fatalf("account should be quarantined: %+v", second)
	}
}
