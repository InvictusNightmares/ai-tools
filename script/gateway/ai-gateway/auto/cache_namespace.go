package autogateway

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"strings"
)

func CacheNamespace(secret, region, provider, effectiveModel, modelRevision, apiKeyID, clientPromptCacheKey string) (string, error) {
	return CacheNamespaceWithReasoningEffort(secret, region, provider, effectiveModel, "", modelRevision, apiKeyID, clientPromptCacheKey)
}

func CacheNamespaceWithReasoningEffort(secret, region, provider, effectiveModel string, effort ReasoningEffort, modelRevision, apiKeyID, clientPromptCacheKey string) (string, error) {
	if secret == "" {
		return "", errors.New("cache namespace secret is required")
	}
	material := strings.Join([]string{region, provider, effectiveModel, string(effort), modelRevision, apiKeyID, clientPromptCacheKey}, "\x1f")
	h := hmac.New(sha256.New, []byte(secret))
	_, _ = h.Write([]byte(material))
	return hex.EncodeToString(h.Sum(nil)), nil
}
