package main

import (
	"os"
	"strings"
	"testing"
)

func TestAcceptanceConfigurationCannotUseSharedCredentials(t *testing.T) {
	for _, name := range []string{"AUTO_GATEWAY_API_KEY_ID", "AUTO_GATEWAY_PILOT_TOKEN_FILE", "AUTO_UPSTREAM_TOKEN", "AUTO_CLASSIFIER_TOKEN"} {
		t.Setenv(name, "")
	}
	t.Setenv("AUTO_GATEWAY_ROUTE_PREVIEW", "")
	t.Setenv(classifierTokenFileEnv, "")
	t.Setenv("AUTO_GATEWAY_CACHE_SECRET", strings.Repeat("s", 32))
	t.Setenv("AUTO_GATEWAY_AUTH_CHECK_URL", "http://regional.invalid/v1/models")
	for _, name := range []string{"AUTO_CLASSIFIER_URL", "AUTO_UPSTREAM_CHAT_URL", "AUTO_UPSTREAM_RESPONSES_URL", "AUTO_UPSTREAM_ANTHROPIC_URL", "AUTO_UPSTREAM_COUNT_TOKENS_URL"} {
		t.Setenv(name, "http://regional.invalid/v1/chat/completions")
	}
	if err := validateRegionalConfig(); err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"AUTO_GATEWAY_API_KEY_ID", "AUTO_GATEWAY_PILOT_TOKEN_FILE", "AUTO_UPSTREAM_TOKEN", "AUTO_CLASSIFIER_TOKEN"} {
		t.Run(name, func(t *testing.T) {
			t.Setenv(name, "synthetic")
			if validateRegionalConfig() == nil {
				t.Fatal("shared identity accepted")
			}
		})
	}
	t.Run("other-region", func(t *testing.T) {
		t.Setenv("AUTO_CLASSIFIER_URL", "http://other.invalid/v1/chat/completions")
		if validateRegionalConfig() == nil {
			t.Fatal("credential origin mismatch accepted")
		}
	})
	t.Run("billing-skips-quota", func(t *testing.T) {
		t.Setenv("AUTO_GATEWAY_AUTH_CHECK_URL", "http://regional.invalid/v1/usage")
		if validateRegionalConfig() == nil {
			t.Fatal("billing bypass endpoint accepted")
		}
	})
}

func TestAcceptancePreviewCanUseDedicatedClassifierTokenFile(t *testing.T) {
	t.Setenv("AUTO_GATEWAY_API_KEY_ID", "")
	t.Setenv("AUTO_GATEWAY_PILOT_TOKEN_FILE", "")
	t.Setenv("AUTO_UPSTREAM_TOKEN", "")
	t.Setenv("AUTO_CLASSIFIER_TOKEN", "")
	t.Setenv("AUTO_GATEWAY_CACHE_SECRET", strings.Repeat("s", 32))
	t.Setenv("AUTO_GATEWAY_AUTH_CHECK_URL", "http://regional.invalid/v1/models")
	t.Setenv("AUTO_GATEWAY_ROUTE_PREVIEW", "1")
	file := t.TempDir() + "/classifier.token"
	if err := os.WriteFile(file, []byte("preview-token\n"), 0600); err != nil {
		t.Fatal(err)
	}
	t.Setenv(classifierTokenFileEnv, file)
	t.Setenv("AUTO_CLASSIFIER_URL", "http://106.14.254.110:9881/v1/chat/completions")
	for _, name := range []string{"AUTO_UPSTREAM_CHAT_URL", "AUTO_UPSTREAM_RESPONSES_URL", "AUTO_UPSTREAM_ANTHROPIC_URL", "AUTO_UPSTREAM_COUNT_TOKENS_URL"} {
		t.Setenv(name, "http://regional.invalid/v1/chat/completions")
	}
	if err := validateRegionalConfig(); err != nil {
		t.Fatal(err)
	}
	if token, err := readPreviewClassifierToken(file); err != nil || token != "preview-token" {
		t.Fatalf("preview token read failed: %q %v", token, err)
	}
	t.Setenv("AUTO_GATEWAY_ROUTE_PREVIEW", "")
	if err := validateRegionalConfig(); err == nil {
		t.Fatal("preview token accepted without route preview")
	}
}
