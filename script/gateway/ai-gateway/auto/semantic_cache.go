package autogateway

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"local/ai-gateway/service"
	"sync"
	"time"
)

// Cache only an assessment: protocol constraints are recomputed for each request.
// The digest includes all normalized context and tenant/session identity. No raw text is stored.
type CachedTaskClassifier struct {
	OnCacheHit      func(UsageEvent) error
	Shared          *service.JSONCache
	Inner           TaskClassifier
	Secret, Version string
	TTL             time.Duration
	Capacity        int
	mu              sync.Mutex
	entries         map[string]cachedAssessment
	Now             func() time.Time
}
type cachedAssessment struct {
	Trace         ClassifierTrace
	Assessment    TaskAssessment
	Expires, Used time.Time
}

func (c *CachedTaskClassifier) Classify(ctx context.Context, r Request, m PipelineMeta) (Classification, error) {
	if c.Inner == nil {
		return Classification{}, ErrClassifierUnavailable
	}
	if c.Secret == "" || c.Version == "" || m.Region == "" || m.APIKeyID == "" || m.SessionID == "" {
		return c.Inner.Classify(ctx, r, m)
	}
	now := time.Now()
	if c.Now != nil {
		now = c.Now()
	}
	rForDigest := r
	rForDigest.RawPayload = nil
	raw, err := json.Marshal(struct {
		Region, Key, Session, Version string
		Request                       Request
	}{m.Region, m.APIKeyID, m.SessionID, c.Version, rForDigest})
	if err != nil {
		return Classification{}, ErrClassifierUnavailable
	}
	h := hmac.New(sha256.New, []byte(c.Secret))
	h.Write(raw)
	key := hex.EncodeToString(h.Sum(nil))
	var entry cachedAssessment
	var ok bool
	if c.Shared != nil {
		raw, hit, err := c.Shared.Get(key, now)
		if err != nil {
			return Classification{}, ErrClassifierUnavailable
		}
		if hit {
			if json.Unmarshal(raw, &entry) != nil {
				return Classification{}, ErrClassifierUnavailable
			}
			ok = true
		}
	} else {
		c.mu.Lock()
		entry, ok = c.entries[key]
		if ok && now.Before(entry.Expires) {
			entry.Used = now
			c.entries[key] = entry
		} else {
			delete(c.entries, key)
		}
		c.mu.Unlock()
	}
	if ok && now.Before(entry.Expires) {
		result := classificationFromAssessment(r, entry.Assessment)
		result.Trace = entry.Trace
		result.Trace.CacheHit = true
		result.ReasonCodes = append(result.ReasonCodes, "classification_cache_hit")
		if c.OnCacheHit != nil {
			model := entry.Trace.DecisionModel
			if model == "" {
				model = entry.Trace.PrimaryModel
			}
			if err := c.OnCacheHit(UsageEvent{At: now, Region: m.Region, APIKeyID: m.APIKeyID, RequestID: m.RequestID, Purpose: "classification", EffectiveModel: model, Success: true, ClassificationCacheHit: true}); err != nil {
				return Classification{}, ErrClassifierUnavailable
			}
		}
		return result, nil
	}
	result, err := c.Inner.Classify(ctx, r, m)
	if err != nil || result.Assessment == nil {
		return result, err
	}
	ttl := c.TTL
	if ttl <= 0 {
		ttl = 5 * time.Minute
	}
	if c.Shared != nil {
		finished := c.completedAt()
		entry := cachedAssessment{Trace: result.Trace, Assessment: *result.Assessment, Expires: finished.Add(ttl), Used: finished}
		raw, _ := json.Marshal(entry)
		if err := c.Shared.Put(key, raw, entry.Expires, finished); err != nil {
			return Classification{}, ErrClassifierUnavailable
		}
		return result, nil
	}
	cap := c.Capacity
	if cap <= 0 {
		cap = 1024
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.entries == nil {
		c.entries = make(map[string]cachedAssessment)
	}
	if len(c.entries) >= cap {
		old := ""
		var oldest time.Time
		for k, v := range c.entries {
			if old == "" || v.Used.Before(oldest) {
				old = k
				oldest = v.Used
			}
		}
		delete(c.entries, old)
	}
	c.entries[key] = cachedAssessment{Trace: result.Trace, Assessment: *result.Assessment, Expires: c.completedAt().Add(ttl), Used: now}
	return result, nil
}

func (c *CachedTaskClassifier) completedAt() time.Time {
	if c.Now != nil {
		return c.Now()
	}
	return time.Now()
}
