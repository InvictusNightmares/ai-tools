package main

import (
	"errors"
	"net/url"
	"os"
	"path/filepath"
	"strings"
)

const classifierTokenFileEnv = "AUTO_CLASSIFIER_TOKEN_FILE"

func validateRegionalConfig() error {
	for _, name := range []string{"AUTO_GATEWAY_API_KEY_ID", "AUTO_GATEWAY_PILOT_TOKEN_FILE", "AUTO_UPSTREAM_TOKEN", "AUTO_CLASSIFIER_TOKEN"} {
		if os.Getenv(name) != "" {
			return errors.New("regional mode must use caller credentials; remove " + name)
		}
	}
	previewClassifier := strings.TrimSpace(os.Getenv("AUTO_GATEWAY_ROUTE_PREVIEW")) == "1" && strings.TrimSpace(os.Getenv(classifierTokenFileEnv)) != ""
	if tokenFile := strings.TrimSpace(os.Getenv(classifierTokenFileEnv)); tokenFile != "" {
		if !previewClassifier {
			return errors.New("classifier token file is allowed only for route preview")
		}
		if _, err := readPreviewClassifierToken(tokenFile); err != nil {
			return err
		}
	}
	if len(os.Getenv("AUTO_GATEWAY_CACHE_SECRET")) < 32 {
		return errors.New("regional mode requires a persistent private cache secret of at least 32 bytes")
	}
	check, err := url.Parse(os.Getenv("AUTO_GATEWAY_AUTH_CHECK_URL"))
	if err != nil || check.User != nil || check.RawQuery != "" || check.Fragment != "" || check.Host == "" || (check.Scheme != "http" && check.Scheme != "https") || check.Path != "/v1/models" {
		return errors.New("regional auth check must target regional Sub2API /v1/models")
	}
	for _, name := range []string{"AUTO_CLASSIFIER_URL", "AUTO_UPSTREAM_CHAT_URL", "AUTO_UPSTREAM_RESPONSES_URL", "AUTO_UPSTREAM_ANTHROPIC_URL", "AUTO_UPSTREAM_COUNT_TOKENS_URL"} {
		u, err := url.Parse(os.Getenv(name))
		if name == "AUTO_CLASSIFIER_URL" && previewClassifier {
			if err != nil || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.Path != "/v1/chat/completions" {
				return errors.New("preview classifier endpoint is invalid")
			}
			continue
		}
		if err != nil || u.User != nil || u.RawQuery != "" || u.Fragment != "" || u.Scheme != check.Scheme || !strings.EqualFold(u.Host, check.Host) {
			return errors.New("regional endpoints must share the authenticated Sub2API origin: " + name)
		}
	}
	return nil
}

func readPreviewClassifierToken(path string) (string, error) {
	clean := filepath.Clean(strings.TrimSpace(path))
	if !filepath.IsAbs(clean) || clean == string(filepath.Separator) || clean != path {
		return "", errors.New("preview classifier token file path is invalid")
	}
	info, err := os.Lstat(clean)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		return "", errors.New("preview classifier token file is unavailable")
	}
	raw, err := os.ReadFile(clean)
	if err != nil {
		return "", errors.New("preview classifier token file is unavailable")
	}
	token := strings.TrimSpace(string(raw))
	if token == "" || len(token) > 4096 || strings.ContainsAny(token, " \t\r\n,") {
		return "", errors.New("preview classifier token is invalid")
	}
	return token, nil
}
