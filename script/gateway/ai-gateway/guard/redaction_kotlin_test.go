package gocheck

import (
	"context"
	"encoding/json"
	"strings"
	"testing"
)

func TestKotlinCredentialDeclarationsContainReferencesOnly(t *testing.T) {
	for _, source := range []string{
		`val password = binding.etPassword.text.toString()`,
		`private var password = binding.password.text.toString().trim()`,
		`val accessToken = response.session.token`,
		`data class LoginRequest(val password: String, val phone: String)`,
		`    val password: String? = null,`,
		`    var password: String = ""`,
	} {
		if got := redactSecretText(source); got != source {
			t.Errorf("Kotlin reference changed: %q => %q", source, got)
		}
	}
}

func TestMarkdownPlaceholderComparisonsReachGuardUnchanged(t *testing.T) {
	for _, source := range []string{
		"修复 `accessToken == null` 的验证逻辑。",
		"Verify ``session.accessToken === undefined`` in the changelog.",
		"Review ```password == nil``` as a code example.",
		"Line 43: 验证 `authorization == false` 与 `cookie === true`。",
	} {
		t.Run(source, func(t *testing.T) {
			if got := redactSecretText(source); got != source {
				t.Fatalf("documentation comparison changed: %q => %q", source, got)
			}
			for _, role := range []string{"user", "assistant", "tool"} {
				classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
				gate := testPreflightGate(classifier, nil)
				messages := []SafetyMessage{{Role: "user", Content: "再分析下项目的改动"}, {Role: role, Content: source}}
				payload, err := json.Marshal(map[string]any{"model": "auto", "messages": messages})
				if err != nil {
					t.Fatal(err)
				}
				result := gate.Evaluate(context.Background(), SafetyInput{Messages: messages, ProviderPayload: string(payload)})
				if result.Decision != SafetyAllow || classifier.calls != 1 || result.SanitizedPayload != string(payload) {
					t.Fatalf("%s documentation rejected or altered: decision=%s calls=%d reasons=%v", role, result.Decision, classifier.calls, result.ReasonCodes)
				}
			}
		})
	}
}

func TestMarkdownComparisonsDoNotHideCredentialValues(t *testing.T) {
	for _, source := range []string{
		"Verify `password == \"fixture-live-secret\"`.",
		"Verify `password == null-secret`.",
		"Verify `password == null.secret`.",
		"Verify `password = null`.",
		"Verify `accessToken == null`; password=fixture-live-secret",
		"Verify `password == nil` and `api_key='fixture-live-secret'`.",
	} {
		t.Run(source, func(t *testing.T) {
			classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
			result := testPreflightGate(classifier, nil).Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "tool", Content: source}}})
			if result.Decision != SafetyBlock || classifier.calls != 0 {
				t.Fatalf("credential not blocked before model: decision=%s calls=%d", result.Decision, classifier.calls)
			}
		})
	}
}

func TestKotlinDeclarationContextDoesNotExposeLiteralCredentials(t *testing.T) {
	for _, source := range []string{
		`val password = "fixture-live-secret"`,
		`val password: String = "fixture-live-secret"`,
		`val password = decode("fixture-live-secret")`,
		`val password = binding.password.text.toString() + "fixture-live-secret"`,
		`password=binding.password.text.toString()`,
		`password: String`,
		`val password: String = ""; api_key="fixture-live-secret"`,
	} {
		if got := redactSecretText(source); got == source || !strings.Contains(got, "<REDACTED:") {
			t.Errorf("credential not protected: %q => %q", source, got)
		}
	}
}

func TestKotlinFunctionParameterTypesReachGuardUnchanged(t *testing.T) {
	for _, source := range []string{
		`fun isReady(accessToken: String?): Boolean { return accessToken != null }`,
		`fun login(username: String, password: String):Boolean = false`,
		"fun login(\n    password: String?,\n    accessToken: String\n): Boolean = false",
		"Review `fun verify(password: String): Boolean` in this synthetic changelog.",
		`private fun Session.verify(accessToken: String?) = false`,
	} {
		t.Run(source, func(t *testing.T) {
			classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
			messages := []SafetyMessage{{Role: "user", Content: "Verify this synthetic function declaration."}, {Role: "tool", Content: source}}
			payload, err := json.Marshal(map[string]any{"messages": messages})
			if err != nil {
				t.Fatal(err)
			}
			result := testPreflightGate(classifier, nil).Evaluate(context.Background(), SafetyInput{Messages: messages, ProviderPayload: string(payload)})
			if result.Decision != SafetyAllow || classifier.calls != 1 || result.SanitizedPayload != string(payload) {
				t.Fatalf("parameter annotation rejected or altered: decision=%s calls=%d reasons=%v", result.Decision, classifier.calls, result.ReasonCodes)
			}
		})
	}
}

func TestKotlinParameterAnnotationsDoNotHideCredentials(t *testing.T) {
	for _, source := range []string{
		`password: String`,
		`fun verify(password: "fixture-live-secret")`,
		`fun verify(password: String = "fixture-live-secret")`,
		`fun verify(password: String-secret)`,
		`fun verify(password: String.secret)`,
		`fun verify(password: String):password=fixture-live-secret`,
		`fun verify(password: String):api_key:fixture-live-secret`,
		`fun verify(password: String) {}; api_key="fixture-live-secret"`,
	} {
		t.Run(source, func(t *testing.T) {
			classifier := &fakeSafetyClassifier{verdict: ModelVerdict{Decision: SafetyAllow, RiskLevel: RiskLow}}
			result := testPreflightGate(classifier, nil).Evaluate(context.Background(), SafetyInput{Messages: []SafetyMessage{{Role: "user", Content: "Verify " + source}}})
			if result.Decision != SafetyBlock || classifier.calls != 0 {
				t.Fatalf("credential not blocked before model: decision=%s calls=%d", result.Decision, classifier.calls)
			}
		})
	}
}

func TestCredentialPlaceholderComparisonsAreNotAssignments(t *testing.T) {
	for _, source := range []string{
		`if (localVin.isEmpty() || userInfo?.accessToken == null) {`,
		`if (session.accessToken === undefined) return`,
		`if (password == nil) { return }`,
		`if (authorization == false || cookie === true) {}`,
		`accessToken == null`,
	} {
		if got := redactSecretText(source); got != source {
			t.Errorf("comparison changed: %q => %q", source, got)
		}
	}
}

func TestCredentialComparisonsStillProtectSuppliedSecrets(t *testing.T) {
	for _, source := range []string{
		`password == "fixture-live-secret"`,
		`password === 'fixture-live-secret'`,
		`password == null-secret`,
		`password == null.secret`,
		`password = null`,
		`password == "null"`,
		`if (accessToken == null) {}; password="fixture-live-secret"`,
	} {
		if got := redactSecretText(source); got == source || !strings.Contains(got, "<REDACTED:") {
			t.Errorf("credential not protected: %q => %q", source, got)
		}
	}
}
