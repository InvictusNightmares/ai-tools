package autogateway

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"strings"
)

// ResponseCacheKey derives an opaque response-cache key. The request digest
// is supplied by the caller after canonicalizing the protocol body; neither
// raw prompts nor credentials are stored in the key.
func ResponseCacheKey(secret, region, provider, effectiveModel string, effort ReasoningEffort, modelRevision, apiKeyID, clientPromptCacheKey, requestDigest string) (string, error) {
	if strings.TrimSpace(secret) == "" {
		return "", errors.New("cache key secret is required")
	}
	material, err := json.Marshal([]string{region, provider, effectiveModel, string(effort), modelRevision, apiKeyID, clientPromptCacheKey, requestDigest})
	if err != nil {
		return "", err
	}
	h := hmac.New(sha256.New, []byte(secret))
	_, _ = h.Write(material)
	return hex.EncodeToString(h.Sum(nil)), nil
}

func RequestDigest(canonicalBody []byte) string {
	h := sha256.Sum256(canonicalBody)
	return hex.EncodeToString(h[:])
}
