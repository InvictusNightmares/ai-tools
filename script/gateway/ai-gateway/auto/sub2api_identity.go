package autogateway

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"strings"
	"time"
)

// Sub2APIIdentityResolver delegates authorization to the regional Sub2API on
// EVERY request. It holds no user list, quota, key mapping or authorization cache.
// The returned key-hmac-v1 identifier is local, NOT a Sub2API database key ID.
type Sub2APIIdentityResolver struct {
	CheckURL, Region, Secret string
	Client                   *http.Client
}

type identityError struct {
	status int
	code   string
}

func (e *identityError) Error() string { return e.code }

func (s *Sub2APIIdentityResolver) Resolve(r *http.Request) (string, error) {
	token, err := requestToken(r)
	if err != nil {
		return "", err
	}
	unavailable := &identityError{503, "identity_check_unavailable"}
	if s.CheckURL == "" || s.Region == "" || len(s.Secret) < 32 {
		return "", unavailable
	}
	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, s.CheckURL, nil)
	if err != nil {
		return "", unavailable
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Cache-Control", "no-cache")
	copyTrustedClientIP(req.Header, r.Header)
	copyClientUserAgent(req.Header, r.Header)
	client := http.Client{Timeout: 10 * time.Second}
	if s.Client != nil {
		client = *s.Client
		if client.Timeout == 0 {
			client.Timeout = 10 * time.Second
		}
	}
	client.CheckRedirect = func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }
	resp, err := client.Do(req)
	if err != nil {
		return "", unavailable
	}
	defer resp.Body.Close()
	switch resp.StatusCode {
	case 200:
	case 401:
		return "", ErrUnauthorized
	case 403:
		return "", &identityError{403, "sub2api_access_denied"}
	case 429:
		return "", &identityError{429, "sub2api_rate_limited"}
	default:
		return "", unavailable
	}
	// A login page or reverse-proxy error with HTTP 200 must not authorize access.
	body, err := io.ReadAll(io.LimitReader(resp.Body, (1<<20)+1))
	var models struct {
		Data []json.RawMessage `json:"data"`
	}
	if err != nil || len(body) > 1<<20 || json.Unmarshal(body, &models) != nil || models.Data == nil {
		return "", unavailable
	}
	digest := hmac.New(sha256.New, []byte(s.Secret))
	digest.Write([]byte("sub2api-identity-v1\x00" + s.Region + "\x00" + token))
	return "key-hmac-v1:" + hex.EncodeToString(digest.Sum(nil)), nil
}

// Auto only listens on loopback; the ingress overwrites this trusted header
// with its socket peer. Never trust the caller's X-Forwarded-For value.
func copyTrustedClientIP(destination, source http.Header) {
	if ip := net.ParseIP(source.Get("X-Gateway-Client-IP")); ip != nil {
		destination.Set("X-Real-IP", ip.String())
		destination.Set("X-Forwarded-For", ip.String())
	}
}

// Resolve and forward the same credential. Conflicting/duplicate authentication
// headers are rejected before any request to Sub2API or Guard.
func requestToken(r *http.Request) (string, error) {
	if len(r.Header.Values("Authorization")) > 1 || len(r.Header.Values("X-API-Key")) > 1 || r.URL.Query().Has("api_key") || r.URL.Query().Has("key") {
		return "", ErrUnauthorized
	}
	auth, key := r.Header.Get("Authorization"), r.Header.Get("X-API-Key")
	token := ""
	if auth != "" {
		parts := strings.Fields(auth)
		if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
			return "", ErrUnauthorized
		}
		token = parts[1]
	}
	if key != "" {
		if token != "" && token != key {
			return "", ErrUnauthorized
		}
		token = key
	}
	if token == "" || len(token) > 4096 || strings.ContainsAny(token, " \t\r\n,") {
		return "", ErrUnauthorized
	}
	return token, nil
}
