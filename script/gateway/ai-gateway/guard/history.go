package gocheck

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"time"
)

const HistoryInspectionVersion = "guard-history-v1"

type historyEntry struct {
	ExpiresAt time.Time
}

type historyInspection struct {
	input  SafetyInput
	key    string
	total  int
	reused int
}

// Only a verified, append-only prefix is reusable. The digest includes the
// complete envelope, identity and policy; edits or compression break the chain.
// No prompt text is retained. Credential rules still scan the full input first.
func (g *PreflightGate) historyInspection(input SafetyInput) historyInspection {
	plan := historyInspection{input: input}
	if g.Config.HistoryCacheTTL <= 0 || input.SessionHash == "" || input.ProviderPayload == "" {
		return plan
	}
	var body map[string]json.RawMessage
	if json.Unmarshal([]byte(input.ProviderPayload), &body) != nil {
		return plan
	}
	field := "messages"
	if _, ok := body["input"]; ok {
		field = "input"
	}
	var messages []json.RawMessage
	if json.Unmarshal(body[field], &messages) != nil || len(messages) == 0 {
		return plan
	}
	delete(body, field)
	envelope, err := json.Marshal(body)
	if err != nil {
		return plan
	}
	base := input
	base.RequestID, base.ProviderPayload, base.RawBody = "", string(envelope), nil
	encoded, err := json.Marshal(struct {
		Version, Rule, Model string
		Strict               bool
		Input                SafetyInput
	}{HistoryInspectionVersion, g.Config.RuleVersion, g.Config.ModelVersion, g.Config.Strict, base})
	if err != nil {
		return plan
	}
	prefix := sha256.Sum256(encoded)
	keys := make([]string, len(messages))
	for i, message := range messages {
		// Canonicalize object order, preserve exact JSON numbers and all fields.
		var normalized any
		decoder := json.NewDecoder(bytes.NewReader(message))
		decoder.UseNumber()
		if decoder.Decode(&normalized) != nil {
			return plan
		}
		canonical, err := json.Marshal(normalized)
		if err != nil {
			return plan
		}
		h := sha256.New()
		h.Write(prefix[:])
		h.Write([]byte{0})
		h.Write(canonical)
		copy(prefix[:], h.Sum(nil))
		keys[i] = hex.EncodeToString(prefix[:])
	}
	now, matched := g.Now(), 0
	g.mu.Lock()
	for i := len(keys) - 2; i >= 0; i-- {
		if entry, ok := g.history[keys[i]]; ok && now.Before(entry.ExpiresAt) {
			matched = i + 1
			break
		}
	}
	g.mu.Unlock()
	plan.key, plan.total = keys[len(keys)-1], len(messages)
	if matched == 0 {
		return plan
	}
	// Repeat the two boundary messages and the latest actual user message.
	// The new action is never reviewed without its user intent and envelope.
	start := matched - 2
	if start < 0 {
		start = 0
	}
	selected := make([]json.RawMessage, 0, len(messages))
	for i := 0; i < start; i++ {
		var message struct {
			Role string `json:"role"`
		}
		if json.Unmarshal(messages[i], &message) == nil && (message.Role == "user" || message.Role == "system" || message.Role == "developer") {
			selected = append(selected, messages[i])
		}
	}
	selected = append(selected, messages[start:]...)
	plan.reused = len(messages) - len(selected)
	if plan.reused <= 0 {
		plan.reused = 0
		return plan
	}
	body[field], _ = json.Marshal(selected)
	inspection, err := json.Marshal(body)
	if err != nil {
		plan.reused = 0
		return plan
	}
	plan.input.ProviderPayload = string(inspection)
	plan.input.RawBody = nil
	return plan
}

func (g *PreflightGate) rememberHistory(plan historyInspection) {
	if plan.key == "" {
		return
	}
	now := g.Now()
	g.mu.Lock()
	defer g.mu.Unlock()
	if g.history == nil {
		g.history = make(map[string]historyEntry)
	}
	limit := g.Config.HistoryCacheCapacity
	if limit <= 0 {
		limit = 4096
	}
	for key, entry := range g.history {
		if !now.Before(entry.ExpiresAt) {
			delete(g.history, key)
		}
	}
	if len(g.history) >= limit {
		oldestKey, oldest := "", now.Add(g.Config.HistoryCacheTTL)
		for key, entry := range g.history {
			if !entry.ExpiresAt.After(oldest) {
				oldestKey, oldest = key, entry.ExpiresAt
			}
		}
		delete(g.history, oldestKey)
	}
	g.history[plan.key] = historyEntry{ExpiresAt: now.Add(g.Config.HistoryCacheTTL)}
}
