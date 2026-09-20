package gocheck

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"strings"
	"testing"
)

func TestBasicProseInAgentToolsDoesNotBlockGreetings(t *testing.T) {
	for _, client := range []string{"opencode", "hermes-chat", "codex-responses", "claude-code", "hermes-messages"} {
		for _, greeting := range []string{"你好", "hello", "你好 hello"} {
			t.Run(client+"/"+greeting, func(t *testing.T) {
				payload := map[string]any{
					"messages": []any{map[string]any{"role": "system", "content": "Use the provided tools to explore and verify code."}, map[string]any{"role": "user", "content": greeting}},
					"tools":    []any{map[string]any{"type": "function", "function": map[string]any{"name": "task", "description": "Use this tool for basic exploration, basic implementation, and BASIC VALIDATION.", "parameters": map[string]any{"type": "object"}}}},
				}
				if client == "codex-responses" {
					delete(payload, "messages")
					payload["instructions"] = "Use the tools to verify code."
					payload["input"] = []any{map[string]any{"role": "user", "content": []any{map[string]any{"type": "input_text", "text": greeting}}}}
					payload["tools"] = []any{map[string]any{"type": "function", "name": "task", "description": "Use this for basic exploration and basic implementation.", "parameters": map[string]any{"type": "object"}}}
				} else if client == "claude-code" || client == "hermes-messages" {
					payload["system"] = []any{map[string]any{"type": "text", "text": "Use the tools to verify code.", "cache_control": map[string]string{"type": "ephemeral"}}}
					payload["messages"] = []any{map[string]any{"role": "user", "content": []any{map[string]any{"type": "text", "text": greeting}}}}
					payload["tools"] = []any{map[string]any{"name": "task", "description": "Use this for basic exploration and basic implementation.", "input_schema": map[string]any{"type": "object"}}}
				}
				body, _ := json.Marshal(payload)
				classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
				result := testPreflightGate(classifier, nil).Evaluate(context.Background(), SafetyInput{ProviderPayload: string(body)})
				if result.Decision != SafetyAllow || result.SanitizedPayload != string(body) || classifier.calls != 1 {
					t.Fatalf("agent tool prose treated as credentials: decision=%s reasons=%v calls=%d", result.Decision, result.ReasonCodes, classifier.calls)
				}
			})
		}
	}
}

func TestBasicCredentialSyntaxAndShortCredentials(t *testing.T) {
	for _, pair := range []string{"fixture:secret", "u:p", "user:", ":secret", "用户:密码", "user:pass:word", ":"} {
		for _, encoding := range []*base64.Encoding{base64.StdEncoding, base64.RawStdEncoding} {
			token := encoding.EncodeToString([]byte(pair))
			for _, scheme := range []string{"Basic", "basic", "BASIC"} {
				body := "Use this " + scheme + " " + token + ". Verify login."
				if clean := redactSecretText(body); strings.Contains(clean, token) {
					t.Fatal("valid Basic credential survived redaction")
				}
				classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
				result := testPreflightGate(classifier, nil).Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: body}}})
				if result.Decision != SafetyBlock || classifier.calls != 0 {
					t.Fatal("credential-use hard gate was bypassed")
				}
			}
		}
	}
}

func TestBasicProseAndExplicitAuthFields(t *testing.T) {
	for _, text := range []string{"basic exploration", "BASIC VALIDATION", "basic implementation", "basic authentication", "basic YWJjZA==", "basic YTpiCg=="} {
		if redactSecretText(text) != text {
			t.Fatalf("ordinary text or invalid Basic syntax changed: %q", text)
		}
	}
	// Explicit credential fields are always protected, even with invalid syntax.
	for _, text := range []string{`{"Authorization":"Basic YTpiCg=="}`, "Authorization: Basic malformed", "proxy-authorization: Basic dTpw"} {
		if clean := redactSecretText(text); clean == text || !strings.Contains(clean, "<REDACTED:") {
			t.Fatal("explicit authentication field was not redacted")
		}
	}
}

func TestAuthTemplateInNestedAgentToolDoesNotBlockGreeting(t *testing.T) {
	for _, reference := range []string{"Bearer {siwc_bypass_bearer_token}.", "Bearer ${ACCESS_TOKEN}", "Bearer <REDACTED:token>"} {
		body, _ := json.Marshal(map[string]any{
			"instructions": "Use the available tools only when requested.",
			"input":        []any{map[string]any{"role": "user", "content": "你好"}},
			"tools": []any{map[string]any{"type": "namespace", "name": "site", "tools": []any{map[string]any{
				"type": "function", "name": "token", "description": "Pass the returned token as OAI-Sites-Authorization: " + reference,
			}}}},
		})
		classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
		result := testPreflightGate(classifier, nil).Evaluate(context.Background(), SafetyInput{ProviderPayload: string(body)})
		if result.Decision != SafetyAllow || result.SanitizedPayload != string(body) || classifier.calls != 1 {
			t.Fatal("authentication template in tool documentation was treated as a real credential")
		}
	}
	for _, value := range []string{"Bearer fixtureRealAuthMaterial123", "Bearer {TOKEN}. then actual-secret", "Bearer {sk-real-secret}"} {
		text := "Use the OAI-Sites-Authorization: " + value
		if clean := redactSecretText(text); clean == text || strings.Contains(clean, value) {
			t.Fatal("real or mixed authentication material survived redaction")
		}
	}
}

func TestRedactionPreservesJSONAndCoversCredentialShapes(t *testing.T) {
	for name, body := range map[string]string{
		"quoted_value":   `{"password":"fixture value with spaces","content":"Explain password rotation"}`,
		"escaped_nested": `{"content":"Explain this config: {\"api_key\":\"sk-fixtureplaintext123456\"}"}`,
		"private_key":    `{"content":"Inspect format:\n-----BEGIN PRIVATE KEY-----\nfixtureprivatekeymaterial\n-----END PRIVATE KEY-----"}`,
		"db_url":         `{"content":"postgres://demo:fixturedbpassword@db.invalid/app"}`,
		"cookie":         `{"headers":{"Cookie":"session=fixturesession; other=fixtureother"}}`,
		"oauth":          `{"refresh_token":"fixturerefreshtoken","content":"Describe rotation"}`,
		"authorization":  `{"Authorization":"Basic Zml4dHVyZTpmaXh0dXJl"}`,
	} {
		t.Run(name, func(t *testing.T) {
			input := SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: body}}, RawBody: []byte(body)}
			result := SanitizeInputForModel(input)
			if !json.Valid(result.RawBody) || !json.Valid([]byte(result.Messages[0].Content)) {
				t.Fatal("redaction corrupted JSON")
			}
			if strings.Contains(string(result.RawBody), "fixture") || strings.Contains(result.Messages[0].Content, "fixture") || strings.Contains(string(result.RawBody), "Zml4dHVyZTpmaXh0dXJl") {
				t.Fatal("credential material survived redaction")
			}
			again := SanitizeInputForModel(result)
			if string(again.RawBody) != string(result.RawBody) {
				t.Fatal("redaction is not idempotent")
			}
		})
	}
}

func TestRedactionRetainsSchemaReferencesAndOpaqueState(t *testing.T) {
	body := `{"tools":[{"input_schema":{"properties":{"password":{"type":"string","description":"account password"}}}}],"content":"Use password=${DB_PASSWORD} and api_key=<REDACTED:secret>","signature":"opaque-provider-signature","counter":9007199254740993}`
	result := SanitizeInputForModel(SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: body}}, RawBody: []byte(body)})
	if string(result.RawBody) != body {
		t.Fatal("safe schema/reference or numeric/provider state changed")
	}
}

func TestOpaqueSignatureDoesNotTriggerCredentialQuarantine(t *testing.T) {
	opaque := "gAAAAAfixture-Ghp-" + strings.Repeat("SignedOpaqueMaterial", 7) + "=="
	body, _ := json.Marshal(map[string]any{"messages": []any{
		map[string]any{"role": "assistant", "content": []any{map[string]any{"type": "thinking", "thinking": "Inspecting code", "signature": opaque}}},
		map[string]any{"role": "user", "content": "App resume 后 login 闪一下，再到 home；修复 navigation guard 并验证 lifecycle。"},
	}})
	classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
	gate := testPreflightGate(classifier, nil)
	result := gate.Evaluate(context.Background(), SafetyInput{SessionHash: "signed-history", ProviderPayload: string(body)})
	if result.Decision != SafetyAllow || result.SanitizedPayload != string(body) || classifier.calls != 1 {
		t.Fatal("opaque provider state was changed or caused credential quarantine")
	}
}

func TestKnownCredentialBoundaries(t *testing.T) {
	for _, token := range []string{"sk-fixturesecret123456789", "ghp_fixturesecret123456789", "github_pat_fixturesecret123456789", "xoxb-fixturesecret123456789", "eyJfixture.fixture.fixture"} {
		for _, text := range []string{token, "Here: (" + token + ")", "token=" + token, "'" + token + "', '" + token + "'"} {
			if strings.Contains(redactSecretText(text), token) {
				t.Fatal("standalone credential survived redaction")
			}
		}
	}
	// An explicit credential field is redacted even if its value is opaque.
	if clean := redactSecretText(`{"signature":"sk-fixturesecret123456789","password":"opaque-sk-fixturesecret123456789"}`); strings.Contains(clean, "fixturesecret") {
		t.Fatal("field names must not exempt credentials")
	}
}

func TestPayloadContractBindsEachInputAfterCacheHit(t *testing.T) {
	classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
	gate := testPreflightGate(classifier, nil)
	for _, secret := range []string{"fixtureone", "fixturetwo"} {
		body := `{"messages":[{"role":"user","content":"Explain this config: password=` + secret + `"}]}`
		result := gate.Evaluate(context.Background(), SafetyInput{ProviderPayload: body})
		digest := sha256.Sum256([]byte(body))
		if result.Decision != SafetyAllow || result.InputSHA256 != hex.EncodeToString(digest[:]) || result.RedactionVersion != RedactionVersion || strings.Contains(result.SanitizedPayload, "fixture") || !json.Valid([]byte(result.SanitizedPayload)) {
			t.Fatal("unbound or unsanitized payload")
		}
		if strings.Contains(normalizedSafetyText(classifier.seen), "fixture") {
			t.Fatal("Guard model received plaintext")
		}
	}
	if classifier.calls != 1 {
		t.Fatal("sanitized cache failed to reuse verdict")
	}
	result := gate.Evaluate(context.Background(), SafetyInput{ProviderPayload: `{"messages":[{"role":"user","content":"Use this password=fixtureone to login"}]}`})
	if result.Decision != SafetyBlock || result.SanitizedPayload != "" || result.RedactionVersion != "" {
		t.Fatal("credential-use block was bypassed by sanitized cache")
	}
}
