package capture

import (
	"encoding/json"
	"sync/atomic"
	"time"
)

const SchemaVersion = "work-observation-v1"
const LiteralContentPolicy = "literal_text_attachment_metadata"

type Event struct {
	ContentPolicy string          `json:"content_policy"`
	Schema        string          `json:"schema"`
	ID            string          `json:"id"`
	At            time.Time       `json:"at"`
	Region        string          `json:"region"`
	Ingress       string          `json:"ingress"`
	Kind          string          `json:"kind"`
	ConnectionID  string          `json:"connection_id,omitempty"`
	Direction     string          `json:"direction,omitempty"`
	Sequence      uint64          `json:"sequence,omitempty"`
	KeyHash       string          `json:"key_hash,omitempty"`
	SessionHash   string          `json:"session_hash,omitempty"`
	AgentHash     string          `json:"agent_hash,omitempty"`
	Protocol      string          `json:"protocol"`
	Method        string          `json:"method,omitempty"`
	Path          string          `json:"path"`
	Client        string          `json:"client"`
	UserAgent     string          `json:"user_agent,omitempty"`
	Status        int             `json:"status,omitempty"`
	DurationMS    int64           `json:"duration_ms"`
	FirstByteMS   int64           `json:"first_byte_ms"`
	Outcome       string          `json:"outcome"`
	RequestID     string          `json:"upstream_request_id,omitempty"`
	ResponseID    string          `json:"response_id,omitempty"`
	Association   string          `json:"association"`
	RequestBytes  int64           `json:"request_bytes"`
	ResponseBytes int64           `json:"response_bytes"`
	RequestSHA    string          `json:"request_sha256,omitempty"`
	ResponseSHA   string          `json:"response_sha256,omitempty"`
	Request       json.RawMessage `json:"request,omitempty"`
	Response      json.RawMessage `json:"response,omitempty"`
	Missing       []string        `json:"missing,omitempty"`
	Version       string          `json:"version"`
	// Private in-memory fields never serialize into a record or status output.
	ContentType             string `json:"-"`
	ResponseContentType     string `json:"-"`
	ContentEncoding         string `json:"-"`
	ResponseContentEncoding string `json:"-"`
	WebsocketExtensions     string `json:"-"`
}

type Status struct {
	StartedAt         time.Time `json:"started_at"`
	Captured          uint64    `json:"captured"`
	Written           uint64    `json:"written"`
	Dropped           uint64    `json:"dropped"`
	Truncated         uint64    `json:"truncated"`
	WriteErrors       uint64    `json:"write_errors"`
	ProjectionErrors  uint64    `json:"projection_errors"`
	LossPersistErrors uint64    `json:"loss_persist_errors"`
	QueuedBytes       int64     `json:"queued_bytes"`
	StoredBytes       int64     `json:"stored_bytes"`
	Pruned            uint64    `json:"pruned"`
}

type Metrics struct {
	started                                                                                         time.Time
	captured, written, dropped, truncated, writeErrors, projectionErrors, lossPersistErrors, pruned atomic.Uint64
	queued, stored                                                                                  atomic.Int64
}

func (m *Metrics) Snapshot() Status {
	return Status{StartedAt: m.started, Captured: m.captured.Load(), Written: m.written.Load(), Dropped: m.dropped.Load(), Truncated: m.truncated.Load(), WriteErrors: m.writeErrors.Load(), ProjectionErrors: m.projectionErrors.Load(), LossPersistErrors: m.lossPersistErrors.Load(), QueuedBytes: m.queued.Load(), StoredBytes: m.stored.Load(), Pruned: m.pruned.Load()}
}
