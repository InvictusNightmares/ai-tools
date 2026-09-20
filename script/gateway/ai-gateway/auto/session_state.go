package autogateway

import (
	"encoding/json"
	"fmt"
	"local/ai-gateway/service"
	"os"
	"strings"
	"sync"
	"time"
)

// SessionStateStore isolates route stickiness and cooldowns by an already
// authenticated session. It never stores prompt text or credentials.
type SessionStateStore interface {
	Load(sessionID string, now time.Time) RouteState
	Save(sessionID string, state RouteState, now time.Time) error
}

// FileSessionStateStore uses an advisory file transaction on the shared local
// state volume. Every read reloads disk; route transitions and multi-tool binds
// commit atomically across processes while preserving the v1 JSON schema.
type FileSessionStateStore struct{ file service.TransactionFile }

func NewFileSessionStateStore(path string) (*FileSessionStateStore, error) {
	if strings.TrimSpace(path) == "" {
		return nil, fmt.Errorf("session state path is required")
	}
	store := &FileSessionStateStore{file: service.TransactionFile{Path: path, MaxBytes: 32 << 20}}
	raw, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return store, nil
	}
	if err != nil {
		return nil, err
	}
	var entries map[string]sessionStateEntry
	if len(raw) > 32<<20 || json.Unmarshal(raw, &entries) != nil || entries == nil {
		return nil, fmt.Errorf("invalid session state")
	}
	return store, nil
}

func (s *FileSessionStateStore) Load(id string, now time.Time) RouteState {
	state, _ := s.LoadChecked(id, now)
	return state
}
func (s *FileSessionStateStore) LoadChecked(id string, now time.Time) (RouteState, error) {
	state := NewRouteState()
	err := s.file.Update(func(raw []byte) ([]byte, error) {
		entries, err := decodeSessionEntries(raw)
		if err != nil {
			return nil, err
		}
		state = (&sessionTransaction{entries: entries}).Load(id, now)
		return nil, nil
	})
	return state, err
}
func (s *FileSessionStateStore) Save(id string, state RouteState, now time.Time) error {
	return s.Transaction(now, func(tx SessionStateStore) error { return tx.Save(id, state, now) })
}
func decodeSessionEntries(raw []byte) (map[string]sessionStateEntry, error) {
	entries := map[string]sessionStateEntry{}
	if len(raw) > 0 {
		if json.Unmarshal(raw, &entries) != nil || entries == nil {
			return nil, fmt.Errorf("session_state_corrupt")
		}
	}
	return entries, nil
}
func (s *FileSessionStateStore) Transaction(now time.Time, fn func(SessionStateStore) error) error {
	return s.file.Update(func(raw []byte) ([]byte, error) {
		entries, err := decodeSessionEntries(raw)
		if err != nil {
			return nil, err
		}
		for key, entry := range entries {
			if !entry.ExpiresAt.IsZero() && !now.Before(entry.ExpiresAt) {
				delete(entries, key)
			}
		}
		tx := &sessionTransaction{entries: entries}
		if err = fn(tx); err != nil {
			return nil, err
		}
		if len(entries) > 32768 {
			return nil, fmt.Errorf("session_state_capacity")
		}
		return json.Marshal(entries)
	})
}

type sessionTransaction struct{ entries map[string]sessionStateEntry }

func (s *sessionTransaction) Load(id string, now time.Time) RouteState {
	entry, ok := s.entries[id]
	if !ok || !entry.ExpiresAt.IsZero() && !now.Before(entry.ExpiresAt) {
		return NewRouteState()
	}
	return entry.State
}
func (s *sessionTransaction) Save(id string, state RouteState, now time.Time) error {
	if id == "" {
		return fmt.Errorf("session_state_unavailable")
	}
	if state.SessionTTL <= 0 {
		state.SessionTTL = time.Hour
	}
	s.entries[id] = sessionStateEntry{State: state, ExpiresAt: now.Add(state.SessionTTL)}
	return nil
}
func withStateTransaction(store SessionStateStore, now time.Time, fn func(SessionStateStore) error) error {
	if tx, ok := store.(interface {
		Transaction(time.Time, func(SessionStateStore) error) error
	}); ok {
		return tx.Transaction(now, fn)
	}
	return fn(store)
}
func loadSessionState(store SessionStateStore, id string, now time.Time) (RouteState, error) {
	if checked, ok := store.(interface {
		LoadChecked(string, time.Time) (RouteState, error)
	}); ok {
		return checked.LoadChecked(id, now)
	}
	return store.Load(id, now), nil
}

type sessionStateEntry struct {
	State     RouteState
	ExpiresAt time.Time
}

type MemorySessionStateStore struct {
	mu      sync.Mutex
	entries map[string]sessionStateEntry
}

func NewMemorySessionStateStore() *MemorySessionStateStore {
	return &MemorySessionStateStore{entries: make(map[string]sessionStateEntry)}
}

func (store *MemorySessionStateStore) Load(sessionID string, now time.Time) RouteState {
	if store == nil || strings.TrimSpace(sessionID) == "" {
		return NewRouteState()
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	entry, ok := store.entries[sessionID]
	if !ok {
		return NewRouteState()
	}
	if !entry.ExpiresAt.IsZero() && !now.Before(entry.ExpiresAt) {
		delete(store.entries, sessionID)
		return NewRouteState()
	}
	return entry.State
}

func (store *MemorySessionStateStore) Save(sessionID string, state RouteState, now time.Time) error {
	if store == nil || strings.TrimSpace(sessionID) == "" {
		return fmt.Errorf("session_state_unavailable")
	}
	if state.SessionTTL <= 0 {
		state.SessionTTL = time.Hour
	}
	store.mu.Lock()
	defer store.mu.Unlock()
	if store.entries == nil {
		store.entries = make(map[string]sessionStateEntry)
	}
	store.entries[sessionID] = sessionStateEntry{State: state, ExpiresAt: now.Add(state.SessionTTL)}
	return nil
}
