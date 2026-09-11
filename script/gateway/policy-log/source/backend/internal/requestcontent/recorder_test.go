package requestcontent

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func testOptions(t *testing.T) Options {
	t.Helper()
	return Options{Directory: t.TempDir(), Retention: 24 * time.Hour, MaxDiskBytes: 1 << 20, MaxQueuedBytes: 1 << 20, SegmentBytes: 1 << 16}
}

func closeForTest(t *testing.T, r *Recorder) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := r.Close(ctx); err != nil {
		t.Fatal(err)
	}
}

func readEntries(t *testing.T, dir string) []Entry {
	t.Helper()
	paths, err := filepath.Glob(filepath.Join(dir, "requests-*.jsonl.gz"))
	if err != nil {
		t.Fatal(err)
	}
	var entries []Entry
	for _, p := range paths {
		st, err := os.Stat(p)
		if err != nil {
			t.Fatal(err)
		}
		if st.Mode().Perm() != 0600 {
			t.Fatalf("insecure mode %v", st.Mode())
		}
		b, err := os.ReadFile(p)
		if err != nil {
			t.Fatal(err)
		}
		zr, err := gzip.NewReader(bytes.NewReader(b))
		if err != nil {
			t.Fatal(err)
		}
		dec := json.NewDecoder(zr)
		for {
			var e Entry
			err = dec.Decode(&e)
			if err == io.EOF {
				break
			}
			if err != nil {
				t.Fatal(err)
			}
			entries = append(entries, e)
		}
		if err := zr.Close(); err != nil {
			t.Fatal(err)
		}
	}
	return entries
}

func TestOnlyConfirmedPolicyBodiesPersistAndAreCopied(t *testing.T) {
	opts := testOptions(t)
	r, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	body := []byte(`{"input":"normal text mentioning cyber_policy"}`)
	for _, code := range []string{"", "rate_limit_exceeded", "server_error", "cyber_policy_session_blocked", "policy_violation", "openai_silent_refusal"} {
		if r.Capture(Entry{APIKeyID: 1, ErrorCode: code, Body: body}) {
			t.Fatalf("unexpected capture: %s", code)
		}
	}
	groupID := int64(198)
	entry := Entry{APIKeyID: 65, APIKeyName: "synthetic-owner", UserID: 9, AccountID: 51, GroupID: &groupID, RequestID: "synthetic-policy-1", ErrorCode: "cyber_policy", UpstreamStatus: 200, Body: body}
	if !r.Capture(entry) {
		t.Fatal("policy request was not queued")
	}
	body[10] = 'X'
	groupID = 777
	closeForTest(t, r)
	entries := readEntries(t, opts.Directory)
	if len(entries) != 1 {
		t.Fatalf("want one entry, got %d", len(entries))
	}
	e := entries[0]
	if string(e.Body) != `{"input":"normal text mentioning cyber_policy"}` || *e.GroupID != 198 {
		t.Fatal("request buffer was reused")
	}
	if e.APIKeyID != 65 || e.AccountID != 51 || e.APIKeyName != "synthetic-owner" || e.UpstreamStatus != 200 || e.RequestID != "synthetic-policy-1" {
		t.Fatal("identity or upstream metadata lost")
	}
	if len(e.BodySHA256) != 64 || e.BodyBytes != len(body) {
		t.Fatal("content fingerprint missing")
	}
	if st, err := os.Stat(opts.Directory); err != nil || st.Mode().Perm() != 0700 {
		t.Fatal("insecure directory")
	}
	if s := r.Snapshot(); s.Written != 1 || s.Dropped != 0 || s.QueuedBytes != 0 {
		t.Fatalf("unexpected status %+v", s)
	}
}

func TestCaptureLimitsAndStorageFailureFailOpen(t *testing.T) {
	t.Run("queue bytes", func(t *testing.T) {
		opts := testOptions(t)
		opts.MaxQueuedBytes = 5
		r, err := New(opts)
		if err != nil {
			t.Fatal(err)
		}
		if r.Capture(Entry{APIKeyID: 1, ErrorCode: "cyber_policy", Body: []byte(`{"input":"too big"}`)}) {
			t.Fatal("over-limit body queued")
		}
		closeForTest(t, r)
		if r.Snapshot().Dropped != 1 || len(readEntries(t, opts.Directory)) != 0 {
			t.Fatal("over-limit body persisted")
		}
	})
	t.Run("free space", func(t *testing.T) {
		opts := testOptions(t)
		opts.MinFreeBytes = 1 << 62
		r, err := New(opts)
		if err != nil {
			t.Fatal(err)
		}
		if !r.Capture(Entry{APIKeyID: 1, ErrorCode: "cyber_policy", Body: []byte(`{}`)}) {
			t.Fatal("queue unexpectedly failed")
		}
		closeForTest(t, r)
		if s := r.Snapshot(); s.WriteErrors != 1 || s.Dropped != 1 || s.Written != 0 {
			t.Fatalf("unexpected status %+v", s)
		}
	})
}

func TestRetentionQuotaAndUnrelatedFiles(t *testing.T) {
	opts := testOptions(t)
	opts.MaxDiskBytes = 128
	opts.SegmentBytes = 64
	old := filepath.Join(opts.Directory, "requests-old.jsonl.gz")
	recent := filepath.Join(opts.Directory, "requests-recent.jsonl.gz")
	unrelated := filepath.Join(opts.Directory, "keep.txt")
	for _, p := range []string{old, recent, unrelated} {
		if err := os.WriteFile(p, []byte(strings.Repeat("x", 100)), 0600); err != nil {
			t.Fatal(err)
		}
	}
	then := time.Now().Add(-48 * time.Hour)
	if err := os.Chtimes(old, then, then); err != nil {
		t.Fatal(err)
	}
	r, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	closeForTest(t, r)
	if _, err := os.Stat(old); !os.IsNotExist(err) {
		t.Fatal("expired file retained")
	}
	if _, err := os.Stat(recent); err != nil {
		t.Fatal("recent file removed")
	}
	if _, err := os.Stat(unrelated); err != nil {
		t.Fatal("unrelated file removed")
	}
	// Force a quota prune without starting another worker.
	raw := &Recorder{opts: opts}
	if err := raw.prune(80); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(recent); !os.IsNotExist(err) {
		t.Fatal("quota not enforced")
	}
	if _, err := os.Stat(unrelated); err != nil {
		t.Fatal("unrelated file removed by quota")
	}
}

func TestConcurrentCaptureAndClose(t *testing.T) {
	r, err := New(testOptions(t))
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				r.Capture(Entry{APIKeyID: 1, ErrorCode: "cyber_policy", Body: []byte(`{}`)})
			}
		}()
	}
	closeForTest(t, r)
	wg.Wait()
	if r.Capture(Entry{APIKeyID: 1, ErrorCode: "cyber_policy", Body: []byte(`{}`)}) {
		t.Fatal("captured after shutdown")
	}
}

func TestDefaultConfigProcess(t *testing.T) {
	if os.Getenv("POLICY_LOG_TEST_CHILD") == "1" {
		InitDefault()
		Capture(Entry{APIKeyID: 1, ErrorCode: "", Body: []byte(`{"input":"normal"}`)})
		Capture(Entry{APIKeyID: 1, ErrorCode: "cyber_policy", Body: []byte(`{"input":"synthetic rejected fixture"}`)})
		CloseDefault()
		return
	}
	for _, tc := range []struct {
		name, config string
		count        int
	}{
		{"missing", "", 0}, {"disabled", `{"enabled":false}`, 0},
		{"invalid", `{"enabled":true,"retention_days":-1}`, 0},
		{"enabled", `{"enabled":true,"retention_days":30,"max_disk_mb":1024}`, 1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			dir := t.TempDir()
			if tc.config != "" {
				if err := os.WriteFile(filepath.Join(dir, "policy-request-log.json"), []byte(tc.config), 0600); err != nil {
					t.Fatal(err)
				}
			}
			cmd := exec.Command(os.Args[0], "-test.run=^TestDefaultConfigProcess$")
			cmd.Env = append(os.Environ(), "POLICY_LOG_TEST_CHILD=1", "DATA_DIR="+dir)
			if output, err := cmd.CombinedOutput(); err != nil {
				t.Fatalf("child: %v %s", err, output)
			}
			if got := len(readEntries(t, filepath.Join(dir, "policy-requests"))); got != tc.count {
				t.Fatalf("got %d entries, want %d", got, tc.count)
			}
		})
	}
}
