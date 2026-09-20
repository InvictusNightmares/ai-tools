package autogateway

import (
	"encoding/json"
	"sync"
	"time"
)

// ResponseCache stores only completed, reusable business responses. It is
// deliberately separate from provider prompt caches and route-decision state.
type ResponseCache interface {
	Get(key string, now time.Time) (UpstreamResponse, bool)
	Set(key string, response UpstreamResponse, expiresAt time.Time)
}

type responseCacheEntry struct {
	Response  UpstreamResponse
	ExpiresAt time.Time
	LastUsed  uint64
}

type MemoryResponseCache struct {
	mu       sync.Mutex
	entries  map[string]responseCacheEntry
	capacity int
	sequence uint64
}

func NewMemoryResponseCache() *MemoryResponseCache {
	return NewMemoryResponseCacheWithCapacity(0)
}

// NewMemoryResponseCacheWithCapacity creates a bounded in-memory cache. A
// non-positive capacity keeps the historical unbounded behavior and should
// only be used for tests or a short-lived preview process.
func NewMemoryResponseCacheWithCapacity(capacity int) *MemoryResponseCache {
	return &MemoryResponseCache{entries: make(map[string]responseCacheEntry), capacity: capacity}
}

func (cache *MemoryResponseCache) Get(key string, now time.Time) (UpstreamResponse, bool) {
	if cache == nil || key == "" {
		return UpstreamResponse{}, false
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	entry, ok := cache.entries[key]
	if !ok {
		return UpstreamResponse{}, false
	}
	if !entry.ExpiresAt.IsZero() && !now.Before(entry.ExpiresAt) {
		delete(cache.entries, key)
		return UpstreamResponse{}, false
	}
	cache.sequence++
	entry.LastUsed = cache.sequence
	cache.entries[key] = entry
	return cloneCachedResponse(entry.Response), true
}

func (cache *MemoryResponseCache) Set(key string, response UpstreamResponse, expiresAt time.Time) {
	if cache == nil || key == "" {
		return
	}
	cache.mu.Lock()
	defer cache.mu.Unlock()
	if cache.entries == nil {
		cache.entries = make(map[string]responseCacheEntry)
	}
	cache.sequence++
	cache.entries[key] = responseCacheEntry{Response: cloneCachedResponse(response), ExpiresAt: expiresAt, LastUsed: cache.sequence}
	if cache.capacity > 0 && len(cache.entries) > cache.capacity {
		oldestKey := ""
		var oldest uint64
		for candidate, entry := range cache.entries {
			if candidate == key {
				continue
			}
			if oldestKey == "" || entry.LastUsed < oldest {
				oldestKey, oldest = candidate, entry.LastUsed
			}
		}
		if oldestKey != "" {
			delete(cache.entries, oldestKey)
		}
	}
}

func cloneCachedResponse(response UpstreamResponse) UpstreamResponse {
	response.Body = append([]byte(nil), response.Body...)
	response.ToolCallIDs = append([]string(nil), response.ToolCallIDs...)
	if response.Usage != nil {
		// Usage is JSON metadata. Copy the full tree so callers cannot mutate
		// a cached entry through a nested map shared with another request.
		encoded, err := json.Marshal(response.Usage)
		response.Usage = nil
		if err == nil {
			_ = json.Unmarshal(encoded, &response.Usage)
		}
	}
	return response
}
