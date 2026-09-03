// Package requestcontent saves only requests explicitly rejected by upstream
// with explicit policy/refusal signals. It does not classify requests or receive auth headers.
package requestcontent

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type Entry struct {
	RecordedAt         time.Time       `json:"recorded_at"`
	RequestID          string          `json:"request_id"`
	ClientRequestID    string          `json:"client_request_id,omitempty"`
	AccountID          int64           `json:"account_id"`
	ErrorCode          string          `json:"error_code"`
	ErrorType          string          `json:"error_type,omitempty"`
	SignalPath         string          `json:"signal_path,omitempty"`
	Reason             string          `json:"reason,omitempty"`
	UpstreamRequestID  string          `json:"upstream_request_id,omitempty"`
	UpstreamResponseID string          `json:"upstream_response_id,omitempty"`
	BodyEncoding       string          `json:"body_encoding,omitempty"`
	UpstreamStatus     int             `json:"upstream_status"`
	UserID             int64           `json:"user_id"`
	APIKeyID           int64           `json:"api_key_id"`
	APIKeyName         string          `json:"api_key_name"`
	GroupID            *int64          `json:"group_id,omitempty"`
	GroupName          string          `json:"group_name,omitempty"`
	Provider           string          `json:"provider"`
	Endpoint           string          `json:"endpoint"`
	Protocol           string          `json:"protocol"`
	Model              string          `json:"model"`
	Stage              string          `json:"stage"`
	BodyBytes          int             `json:"body_bytes"`
	BodySHA256         string          `json:"body_sha256"`
	Body               json.RawMessage `json:"body"`
}

type Options struct {
	Directory      string
	Retention      time.Duration
	MaxDiskBytes   int64
	MaxQueuedBytes int64
	SegmentBytes   int64
	MinFreeBytes   uint64
}

type Status struct {
	UpdatedAt   time.Time `json:"updated_at"`
	Written     uint64    `json:"written"`
	Dropped     uint64    `json:"dropped"`
	WriteErrors uint64    `json:"write_errors"`
	QueuedBytes int64     `json:"queued_bytes"`
	PrunedFiles uint64    `json:"pruned_files"`
	PrunedBytes uint64    `json:"pruned_bytes"`
}

type Recorder struct {
	opts      Options
	mu        sync.RWMutex
	closed    bool
	queue     chan Entry
	done      chan struct{}
	pending   atomic.Int64
	written   atomic.Uint64
	dropped   atomic.Uint64
	errors    atomic.Uint64
	pruned    atomic.Uint64
	prunedB   atomic.Uint64
	lastWarn  atomic.Int64
	file      *os.File // worker-owned
	fileName  string
	fileBytes int64
	fileHour  string
	sequence  uint64
	lastPrune time.Time
}

func New(opts Options) (*Recorder, error) {
	if opts.Directory == "" || opts.Retention <= 0 || opts.MaxDiskBytes <= 0 || opts.MaxQueuedBytes <= 0 || opts.SegmentBytes <= 0 || opts.SegmentBytes > opts.MaxDiskBytes {
		return nil, errors.New("invalid request content storage limits")
	}
	if err := os.MkdirAll(opts.Directory, 0700); err != nil {
		return nil, err
	}
	info, err := os.Lstat(opts.Directory)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return nil, errors.New("request content directory must be a real directory")
	}
	if err := os.Chmod(opts.Directory, 0700); err != nil {
		return nil, err
	}
	r := &Recorder{opts: opts, queue: make(chan Entry, 256), done: make(chan struct{})}
	if err := r.prune(0); err != nil {
		return nil, err
	}
	go r.run()
	return r, nil
}

// Capture makes a bounded copy before the caller can reuse the request body.
// Full queues and storage failures never block or reject an API request.
func (r *Recorder) Capture(e Entry) bool {
	if r == nil || !isPolicySignal(e.ErrorCode) || e.APIKeyID <= 0 || len(e.Body) == 0 {
		return false
	}
	r.mu.RLock()
	defer r.mu.RUnlock()
	if r.closed {
		return false
	}
	size := queuedEntryBytes(e)
	for {
		used := r.pending.Load()
		if size > r.opts.MaxQueuedBytes-used {
			r.drop("queue_bytes_limit")
			return false
		}
		if r.pending.CompareAndSwap(used, used+size) {
			break
		}
	}
	e.RecordedAt = time.Now().UTC()
	e.BodyBytes = len(e.Body)
	digest := sha256.Sum256(e.Body)
	e.BodySHA256 = hex.EncodeToString(digest[:])
	e.Body = bytes.Clone(e.Body)
	if e.GroupID != nil {
		id := *e.GroupID
		e.GroupID = &id
	}
	select {
	case r.queue <- e:
		return true
	default:
		r.pending.Add(-size)
		r.drop("queue_count_limit")
		return false
	}
}

func (r *Recorder) drop(reason string) {
	r.dropped.Add(1)
	now := time.Now().Unix()
	previous := r.lastWarn.Load()
	if now-previous >= 30 && r.lastWarn.CompareAndSwap(previous, now) {
		log.Printf("policy_request_log.record_dropped reason=%s dropped=%d", reason, r.dropped.Load())
	}
}

func (r *Recorder) Snapshot() Status {
	return Status{UpdatedAt: time.Now().UTC(), Written: r.written.Load(), Dropped: r.dropped.Load(), WriteErrors: r.errors.Load(), QueuedBytes: r.pending.Load(), PrunedFiles: r.pruned.Load(), PrunedBytes: r.prunedB.Load()}
}

func (r *Recorder) Close(ctx context.Context) error {
	if r == nil {
		return nil
	}
	r.mu.Lock()
	if !r.closed {
		r.closed = true
		close(r.queue)
	}
	r.mu.Unlock()
	select {
	case <-r.done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

func (r *Recorder) run() {
	defer close(r.done)
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	defer func() {
		r.closeFile()
		r.writeStatus()
	}()
	for {
		select {
		case e, ok := <-r.queue:
			if !ok {
				return
			}
			if err := r.write(e); err != nil {
				r.errors.Add(1)
				r.drop("storage_write_failed")
			} else {
				r.written.Add(1)
			}
			r.pending.Add(-queuedEntryBytes(e))
		case <-ticker.C:
			if r.file != nil && r.fileHour != time.Now().UTC().Format("20060102T15") {
				r.closeFile()
			}
			if r.file != nil {
				if err := r.file.Sync(); err != nil {
					r.errors.Add(1)
				}
			}
			if time.Since(r.lastPrune) >= time.Minute {
				if err := r.prune(0); err != nil {
					r.errors.Add(1)
				}
			}
			r.writeStatus()
		}
	}
}

func (r *Recorder) write(e Entry) error {
	if !json.Valid(e.Body) {
		e.BodyEncoding = "base64"
		e.Body, _ = json.Marshal(base64.StdEncoding.EncodeToString(e.Body))
	}
	var compressed bytes.Buffer
	zw, err := gzip.NewWriterLevel(&compressed, gzip.BestSpeed)
	if err != nil {
		return err
	}
	if err := json.NewEncoder(zw).Encode(e); err != nil {
		_ = zw.Close()
		return err
	}
	if err := zw.Close(); err != nil {
		return err
	}
	if int64(compressed.Len()) > r.opts.MaxDiskBytes {
		return errors.New("record exceeds disk budget")
	}
	if r.opts.MinFreeBytes > 0 {
		available, err := availableBytes(r.opts.Directory)
		if err != nil || available < r.opts.MinFreeBytes+uint64(compressed.Len()) {
			return errors.New("insufficient free disk space")
		}
	}
	hour := time.Now().UTC().Format("20060102T15")
	if r.file != nil && (r.fileHour != hour || r.fileBytes+int64(compressed.Len()) > r.opts.SegmentBytes) {
		r.closeFile()
	}
	if err := r.prune(int64(compressed.Len())); err != nil {
		return err
	}
	if r.file == nil {
		r.sequence++
		r.fileName = fmt.Sprintf("requests-%s-%d-%d-%06d.jsonl.gz", hour, time.Now().UnixNano(), os.Getpid(), r.sequence)
		f, err := os.OpenFile(filepath.Join(r.opts.Directory, r.fileName), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			return err
		}
		r.file, r.fileHour, r.fileBytes = f, hour, 0
	}
	previous := r.fileBytes
	n, err := r.file.Write(compressed.Bytes())
	if err != nil || n != compressed.Len() {
		_ = r.file.Truncate(previous)
		r.closeFile()
		return errors.New("request content append failed")
	}
	r.fileBytes += int64(n)
	return nil
}

func (r *Recorder) closeFile() {
	if r.file != nil {
		if err := r.file.Sync(); err != nil {
			r.errors.Add(1)
		}
		_ = r.file.Close()
	}
	r.file, r.fileName, r.fileBytes = nil, "", 0
}

// Prune only this module's segment files, never other application data.
func (r *Recorder) prune(incoming int64) error {
	entries, err := os.ReadDir(r.opts.Directory)
	if err != nil {
		return err
	}
	type segment struct {
		name     string
		size     int64
		modified time.Time
	}
	var files []segment
	var total int64
	for _, e := range entries {
		if !strings.HasPrefix(e.Name(), "requests-") || !strings.HasSuffix(e.Name(), ".jsonl.gz") || !e.Type().IsRegular() {
			continue
		}
		info, err := e.Info()
		if err != nil {
			return err
		}
		files = append(files, segment{e.Name(), info.Size(), info.ModTime()})
		total += info.Size()
	}
	sort.Slice(files, func(i, j int) bool { return files[i].modified.Before(files[j].modified) })
	cutoff := time.Now().Add(-r.opts.Retention)
	for _, f := range files {
		if f.name == r.fileName || (!f.modified.Before(cutoff) && total+incoming <= r.opts.MaxDiskBytes) {
			continue
		}
		if err := os.Remove(filepath.Join(r.opts.Directory, f.name)); err != nil {
			return err
		}
		total -= f.size
		r.pruned.Add(1)
		r.prunedB.Add(uint64(f.size))
	}
	r.lastPrune = time.Now()
	if total+incoming > r.opts.MaxDiskBytes {
		return errors.New("request content disk budget exhausted")
	}
	return nil
}

func (r *Recorder) writeStatus() {
	body, err := json.Marshal(r.Snapshot())
	if err != nil {
		return
	}
	path := filepath.Join(r.opts.Directory, ".status.tmp")
	if err := os.WriteFile(path, body, 0600); err == nil {
		_ = os.Rename(path, filepath.Join(r.opts.Directory, "status.json"))
	}
}

func queuedEntryBytes(e Entry) int64 {
	return int64(len(e.Body) + len(e.RequestID) + len(e.ClientRequestID) + len(e.ErrorCode) + len(e.ErrorType) + len(e.SignalPath) + len(e.Reason) + len(e.UpstreamRequestID) + len(e.UpstreamResponseID) + len(e.APIKeyName) + len(e.GroupName) + len(e.Provider) + len(e.Endpoint) + len(e.Protocol) + len(e.Model) + len(e.Stage) + len(e.BodyEncoding) + 256)
}
