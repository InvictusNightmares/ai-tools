package service

import (
	"encoding/json"
	"errors"
	"time"
)

type JSONCache struct {
	File     TransactionFile
	Capacity int
}
type cacheValue struct {
	Value   json.RawMessage `json:"value"`
	Expires time.Time       `json:"expires"`
	Written time.Time       `json:"written"`
}
type cacheEnvelope struct {
	Schema  string                `json:"schema"`
	Entries map[string]cacheValue `json:"entries"`
}

func decodeCache(raw []byte) (cacheEnvelope, error) {
	value := cacheEnvelope{Schema: "gateway-cache-v1", Entries: map[string]cacheValue{}}
	if len(raw) > 0 && (json.Unmarshal(raw, &value) != nil || value.Schema != "gateway-cache-v1" || value.Entries == nil) {
		return value, errors.New("cache_schema_invalid")
	}
	return value, nil
}
func (c *JSONCache) Get(key string, now time.Time) (json.RawMessage, bool, error) {
	var raw json.RawMessage
	found := false
	err := c.File.Update(func(data []byte) ([]byte, error) {
		envelope, err := decodeCache(data)
		if err != nil {
			return nil, err
		}
		entry, ok := envelope.Entries[key]
		if ok && now.Before(entry.Expires) {
			raw = entry.Value
			found = true
		}
		return nil, nil
	})
	return raw, found, err
}
func (c *JSONCache) Put(key string, value json.RawMessage, expires, now time.Time) error {
	if key == "" || !json.Valid(value) || !now.Before(expires) {
		return errors.New("cache_value_invalid")
	}
	return c.File.Update(func(data []byte) ([]byte, error) {
		envelope, err := decodeCache(data)
		if err != nil {
			return nil, err
		}
		for k, v := range envelope.Entries {
			if !now.Before(v.Expires) {
				delete(envelope.Entries, k)
			}
		}
		capacity := c.Capacity
		if capacity <= 0 {
			capacity = 1024
		}
		if _, exists := envelope.Entries[key]; !exists && len(envelope.Entries) >= capacity {
			oldest := ""
			var at time.Time
			for k, v := range envelope.Entries {
				if oldest == "" || v.Written.Before(at) {
					oldest = k
					at = v.Written
				}
			}
			delete(envelope.Entries, oldest)
		}
		envelope.Entries[key] = cacheValue{Value: value, Expires: expires, Written: now}
		return json.Marshal(envelope)
	})
}
