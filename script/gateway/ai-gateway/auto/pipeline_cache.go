package autogateway

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"net/http"
	"strings"
)

// PipelineMeta is request metadata supplied by the regional Gateway. It does
// not contain prompt text and is used only for cache isolation and usage.
type PipelineMeta struct {
	compactResponse      bool
	RequestID            string
	SessionID            string
	Region               string
	APIKeyID             string
	ClientPromptCacheKey string
	ModelRevision        string
	CacheSecret          string
	ClientHeaders        http.Header `json:"-"`
}

func CanonicalRequestDigest(request Request) string {
	encoded, err := json.Marshal(request)
	if err != nil {
		return ""
	}
	digest := sha256.Sum256(encoded)
	return hex.EncodeToString(digest[:])
}

func BuildPipelineCacheKey(meta PipelineMeta, provider, protocol string, model Model, effort ReasoningEffort, request Request) (string, error) {
	if strings.TrimSpace(meta.CacheSecret) == "" || strings.TrimSpace(meta.Region) == "" || strings.TrimSpace(meta.APIKeyID) == "" || strings.TrimSpace(meta.ModelRevision) == "" {
		return "", errors.New("cache_identity_incomplete")
	}
	// A provider response envelope cannot be replayed to another protocol.
	mapping := MapReasoningEffort(provider, protocol, effort, model.ReasoningEfforts)
	if mapping.Applied == "" {
		return "", errors.New("cache_effort_unverified")
	}
	envelope, err := json.Marshal([]string{"response-cache-v3", protocol, CanonicalRequestDigest(request)})
	if err != nil {
		return "", err
	}
	return ResponseCacheKey(meta.CacheSecret, meta.Region, provider, model.Name, mapping.Applied, meta.ModelRevision, meta.APIKeyID, meta.ClientPromptCacheKey, RequestDigest(envelope))
}

func sessionStoreKey(meta PipelineMeta) string {
	if meta.Region == "" || meta.APIKeyID == "" {
		return meta.SessionID
	}
	raw, _ := json.Marshal([]string{meta.Region, meta.APIKeyID, meta.SessionID})
	return RequestDigest(raw)
}
