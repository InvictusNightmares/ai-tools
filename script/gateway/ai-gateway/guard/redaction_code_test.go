package gocheck

import (
	"strings"
	"testing"
)

func TestDevelopmentToolCodeReferencesAreNotCredentials(t *testing.T) {
	cases := []string{
		"export interface AppInjectData {\n  accessToken: string\n  userInfo: UserInfo | null\n}",
		"entry/src/main/ets/model/Web.ets:25:export interface AppInjectData {\nentry/src/main/ets/model/Web.ets:26:  accessToken: string\nentry/src/main/ets/model/Web.ets-27-  userInfo: UserInfo | null",
		"Line 163:       accessToken: loginInfo?.accessToken ?? '',",
		"const data = { accessToken: loginInfo.accessToken ?? '' }",
		"            accessToken = data.accessToken ?: current?.accessToken,",
		"val updated = state.copy(accessToken = data.accessToken ?: current.accessToken)",
		"Line 267:     headers.Authorization = `Bearer ${token}`",
		"headers.Authorization = `Basic ${encodedCredentials}`",
		"/repo/entry/src/main/ets/model/Web.ets:\n  Line 26:   accessToken: string\n",
		"Set user_authorization = \"high\" after explicit user approval.",
		"The policy derives user_authorization = \"unknown\" from the transcript.",
		"user_authorization: 'low' is an assessment enum, not a credential.",
	}
	for _, source := range cases {
		if got := redactSecretText(source); got != source {
			t.Errorf("code reference changed: %q => %q", source, got)
		}
		if containsSecret(SafetyInput{Messages: []SafetyMessage{{Role: "tool", Content: source}}}) {
			t.Errorf("code reference detected as credential: %q", source)
		}
	}
}

func TestDevelopmentCodeExemptionsKeepLiteralSecretsProtected(t *testing.T) {
	cases := []string{
		`password=string`, `password: string`, `{"password":"string"}`,
		`password=some.real.password`,
		`accessToken = data.accessToken`,
		`accessToken = "live-secret-value" ?: current.accessToken`,
		`accessToken = 'live-secret-value' ?: current.accessToken`,
		`accessToken = live-secret-value ?: current.accessToken`,
		`user_authorization = "high"; Authorization = "fixture-live-secret"`,
		`请使用这个密码 = fixture-live-secret 登录`,
		"headers.Authorization = `Bearer live-secret-value`",
		"headers.Authorization = `Bearer ${token} extra-secret-value`",
		`const data = { accessToken: "live-secret-value" }`,
		`const data = { accessToken: 'live-secret-value' ?? '' }`,
		"/repo/config.yaml:\n  Line 26:   accessToken: string\n",
		"/repo/model.ts:\n  Line 26:   accessToken: 'live-secret-value'\n",
	}
	for _, source := range cases {
		got := redactSecretText(source)
		if got == source || !strings.Contains(got, "<REDACTED:") {
			t.Errorf("literal credential not protected: %q => %q", source, got)
		}
	}
}
