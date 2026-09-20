package autogateway

import (
	"crypto/sha256"
	"crypto/subtle"
	"errors"
	"net/http"
	"strings"
	"time"
)

// IdentityResolver must validate the request before Guard, classifiers or any
// cache. A production implementation also needs the regional quota policy.
type IdentityResolver interface {
	Resolve(*http.Request) (string, error)
}

var ErrUnauthorized = errors.New("unauthorized")

// PilotIdentityResolver intentionally supports ONE explicitly configured test
// key. It checks revocation at the regional API on every request, even a cache
// hit. It is not multi-user quota authorization and cannot be used for rollout.
type PilotIdentityResolver struct {
	Token, APIKeyID, CheckURL string
	Client                    *http.Client
}

func (p *PilotIdentityResolver) Resolve(r *http.Request) (string, error) {
	provided := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	if provided == "" {
		provided = r.Header.Get("X-API-Key")
	}
	left, right := sha256.Sum256([]byte(provided)), sha256.Sum256([]byte(p.Token))
	if p.Token == "" || p.APIKeyID == "" || subtle.ConstantTimeCompare(left[:], right[:]) != 1 {
		return "", ErrUnauthorized
	}
	if p.CheckURL == "" {
		return "", errors.New("identity_check_unavailable")
	}
	req, err := http.NewRequestWithContext(r.Context(), "GET", p.CheckURL, nil)
	if err != nil {
		return "", errors.New("identity_check_unavailable")
	}
	req.Header.Set("Authorization", "Bearer "+p.Token)
	client := p.Client
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	}
	resp, err := client.Do(req)
	if err != nil {
		return "", errors.New("identity_check_unavailable")
	}
	defer resp.Body.Close()
	if resp.StatusCode == 401 || resp.StatusCode == 403 {
		return "", ErrUnauthorized
	}
	if resp.StatusCode != 200 {
		return "", errors.New("identity_check_unavailable")
	}
	return p.APIKeyID, nil
}
