package requestcontent

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"time"
)

var defaultOnce sync.Once
var defaultRecorder atomic.Pointer[Recorder]
var closing atomic.Bool

// InitDefault reads an administrator-owned file in the persistent data volume.
// Missing, disabled or invalid configuration leaves content storage disabled.
// No moderation service or external endpoint is involved.
func InitDefault() {
	defaultOnce.Do(func() {
		base := os.Getenv("DATA_DIR")
		if base == "" {
			base = "/app/data"
		}
		body, err := os.ReadFile(filepath.Join(base, "policy-request-log.json"))
		if os.IsNotExist(err) {
			return
		}
		if err != nil {
			log.Print("policy_request_log.disabled config_read_failed")
			return
		}
		cfg := struct {
			Enabled       bool  `json:"enabled"`
			RetentionDays int   `json:"retention_days"`
			MaxDiskMB     int64 `json:"max_disk_mb"`
		}{RetentionDays: 30, MaxDiskMB: 1024}
		if err := json.Unmarshal(body, &cfg); err != nil {
			log.Print("policy_request_log.disabled invalid_config")
			return
		}
		if !cfg.Enabled {
			return
		}
		if cfg.RetentionDays < 1 || cfg.RetentionDays > 365 || cfg.MaxDiskMB < 128 || cfg.MaxDiskMB > 1<<20 {
			log.Print("policy_request_log.disabled invalid_limits")
			return
		}
		opts := Options{
			Directory:    filepath.Join(base, "policy-requests"),
			Retention:    time.Duration(cfg.RetentionDays) * 24 * time.Hour,
			MaxDiskBytes: cfg.MaxDiskMB << 20, MaxQueuedBytes: 64 << 20,
			SegmentBytes: 128 << 20, MinFreeBytes: 2 << 30,
		}
		r, err := New(opts)
		if err != nil {
			log.Print("policy_request_log.disabled storage_initialization_failed")
			return
		}
		defaultRecorder.Store(r)
		if closing.Load() {
			closeRecorder(r)
			return
		}
		log.Printf("policy_request_log.enabled signals=cyber_policy,content_policy,content_policy_violation,invalid_prompt_policy,content_filter,structured_refusal retention_days=%d max_disk_mb=%d", cfg.RetentionDays, cfg.MaxDiskMB)
	})
}

func Capture(e Entry) {
	if closing.Load() || !isPolicySignal(e.ErrorCode) {
		return
	}
	InitDefault()
	if r := defaultRecorder.Load(); r != nil {
		r.Capture(e)
	}
}

func CloseDefault() {
	closing.Store(true)
	if r := defaultRecorder.Load(); r != nil {
		closeRecorder(r)
	}
}

func closeRecorder(r *Recorder) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := r.Close(ctx); err != nil {
		log.Print("policy_request_log.shutdown flush_timeout")
	}
}

// Enabled reports recorder availability without retaining request data.
func Enabled() bool {
	if closing.Load() {
		return false
	}
	InitDefault()
	return defaultRecorder.Load() != nil
}
