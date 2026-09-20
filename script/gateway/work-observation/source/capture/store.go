package capture

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"syscall"
	"time"
)

const Retention = 30 * 24 * time.Hour

var ErrCapacity = errors.New("capture_capacity_exhausted")

type DiskStore struct {
	root          string
	limit, stored int64
	lock          *os.File
	// Only the background worker accesses these fields.
	now  func() time.Time
	free func(string) (uint64, error)
}

type recordEnvelope struct {
	SHA   string          `json:"sha256"`
	Event json.RawMessage `json:"event"`
}

func validID(id string) bool {
	if len(id) < 1 || len(id) > 100 {
		return false
	}
	for _, c := range id {
		if !(c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' || c >= '0' && c <= '9' || c == '-' || c == '_') {
			return false
		}
	}
	return true
}
func secureDir(path string) error {
	if err := os.MkdirAll(path, 0700); err != nil {
		return err
	}
	fi, err := os.Lstat(path)
	if err != nil {
		return err
	}
	if !fi.IsDir() || fi.Mode()&os.ModeSymlink != 0 {
		return errors.New("unsafe_store_directory")
	}
	return os.Chmod(path, 0700)
}
func atomicFile(path string, data []byte) error {
	return atomicFileParts(path, data)
}
func atomicFileParts(path string, parts ...[]byte) error {
	if err := secureDir(filepath.Dir(path)); err != nil {
		return err
	}
	f, err := os.CreateTemp(filepath.Dir(path), ".pending-")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	if err = f.Chmod(0600); err == nil {
		for _, part := range parts {
			if len(part) == 0 {
				continue
			}
			if _, err = f.Write(part); err != nil {
				break
			}
		}
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	if err = os.Rename(name, path); err != nil {
		return err
	}
	dir, err := os.Open(filepath.Dir(path))
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}
func NewDiskStore(root string, limit int64) (*DiskStore, error) {
	if !filepath.IsAbs(root) || limit <= 0 {
		return nil, errors.New("invalid_store_configuration")
	}
	if err := secureDir(root); err != nil {
		return nil, err
	}
	lock, err := os.OpenFile(filepath.Join(root, "writer.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if err != nil {
		return nil, err
	}
	if err = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); err != nil {
		lock.Close()
		return nil, errors.New("store_writer_already_running")
	}
	s := &DiskStore{root: root, limit: limit, lock: lock, now: time.Now, free: func(path string) (uint64, error) {
		var st syscall.Statfs_t
		err := syscall.Statfs(path, &st)
		return st.Bavail * uint64(st.Bsize), err
	}}
	for _, dir := range []string{"events", "active", "losses"} {
		if err = secureDir(filepath.Join(root, dir)); err != nil {
			s.Close()
			return nil, err
		}
	}
	err = filepath.WalkDir(root, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("store_symlink_refused")
		}
		if !d.IsDir() && (strings.HasSuffix(d.Name(), ".json") || strings.HasSuffix(d.Name(), ".jsonl")) &&
			(strings.HasPrefix(path, filepath.Join(root, "events")+string(os.PathSeparator)) || strings.HasPrefix(path, filepath.Join(root, "active")+string(os.PathSeparator)) || strings.HasPrefix(path, filepath.Join(root, "losses")+string(os.PathSeparator))) {
			info, e := d.Info()
			if e != nil {
				return e
			}
			s.stored += info.Size()
		}
		return nil
	})
	if err != nil {
		s.Close()
		return nil, err
	}
	return s, nil
}
func (s *DiskStore) Close() error {
	if s.lock == nil {
		return nil
	}
	err := s.lock.Close()
	s.lock = nil
	return err
}
func (s *DiskStore) StoredBytes() int64 { return s.stored }
func (s *DiskStore) check(size, old int64) error {
	if s.stored-old+size > s.limit {
		return ErrCapacity
	}
	free, err := s.free(s.root)
	if err != nil {
		return err
	}
	if free < uint64(size)+(64<<20) {
		return ErrCapacity
	}
	return nil
}
func (s *DiskStore) save(path string, e Event) error {
	raw, err := json.Marshal(e)
	if err != nil {
		return err
	}
	sum := sha256.Sum256(raw)
	sha := hex.EncodeToString(sum[:])
	prefix := make([]byte, 0, len(sha)+24)
	prefix = append(prefix, `{"sha256":"`...)
	prefix = append(prefix, sha...)
	prefix = append(prefix, `","event":`...)
	suffix := []byte{'}', '\n'}
	size := int64(len(prefix) + len(raw) + len(suffix))
	var old int64
	if info, err := os.Lstat(path); err == nil {
		if !info.Mode().IsRegular() {
			return errors.New("unsafe_record_path")
		}
		old = info.Size()
	} else if !os.IsNotExist(err) {
		return err
	}
	if err = s.check(size, old); err != nil {
		return err
	}
	if err = atomicFileParts(path, prefix, raw, suffix); err != nil {
		return err
	}
	s.stored += size - old
	return nil
}

// raw is the successful json.Marshal(Event) output above and sha is hex.
// Embedding it directly avoids parsing and escaping the full body a second
// time inside json.Marshal(recordEnvelope), while keeping identical bytes.
func wrapRecord(raw []byte, sha string) []byte {
	data := make([]byte, 0, len(raw)+len(sha)+24)
	data = append(data, `{"sha256":"`...)
	data = append(data, sha...)
	data = append(data, `","event":`...)
	data = append(data, raw...)
	return append(data, '}', '\n')
}
func (s *DiskStore) Begin(e Event) error {
	if !validID(e.ID) {
		return errors.New("invalid_event_id")
	}
	e.Request = nil
	e.Response = nil
	e.Outcome = "in_progress"
	e.Missing = []string{"pending_capture"}
	return s.save(filepath.Join(s.root, "active", e.ID+".json"), e)
}
func (s *DiskStore) Write(e Event) error {
	if !validID(e.ID) || e.At.IsZero() {
		return errors.New("invalid_event_identity")
	}
	path := filepath.Join(s.root, "events", e.At.UTC().Format("2006-01-02"), e.ID+".json")
	if _, err := os.Stat(path); err == nil {
		return errors.New("record_already_exists")
	}
	if err := s.save(path, e); err != nil {
		return err
	}
	return s.remove(filepath.Join(s.root, "active", e.ID+".json"))
}
func (s *DiskStore) remove(path string) error {
	fi, err := os.Lstat(path)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if !fi.Mode().IsRegular() {
		return errors.New("unsafe_remove_path")
	}
	if err = os.Remove(path); err != nil {
		return err
	}
	s.stored -= fi.Size()
	return nil
}

// RecordLoss appends only event identity, time and reason. It intentionally
// never receives or serializes request/response content. Daily files make the
// ledger independently retainable with the event records.
func (s *DiskStore) RecordLoss(loss Loss) error {
	if !validID(loss.ID) || loss.At.IsZero() || loss.Reason == "" {
		return errors.New("invalid_loss_identity")
	}
	data, err := json.Marshal(loss)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	if s.stored+int64(len(data)) > s.limit {
		return ErrCapacity
	}
	free, err := s.free(s.root)
	if err != nil {
		return err
	}
	if free < uint64(len(data)) {
		return ErrCapacity
	}
	dir := filepath.Join(s.root, "losses")
	if err := secureDir(dir); err != nil {
		return err
	}
	path := filepath.Join(dir, loss.At.UTC().Format("2006-01-02")+".jsonl")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return err
	}
	if err = f.Chmod(0600); err == nil {
		_, err = f.Write(data)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err == nil {
		err = closeErr
	}
	if err != nil {
		return err
	}
	s.stored += int64(len(data))
	return nil
}
func ReadRecord(path string) (Event, error) {
	var e Event
	fi, err := os.Lstat(path)
	if err != nil {
		return e, err
	}
	if !fi.Mode().IsRegular() {
		return e, errors.New("unsafe_record")
	}
	f, err := os.Open(path)
	if err != nil {
		return e, err
	}
	defer f.Close()
	// Includes metadata/escaping expansion, but never an unbounded read.
	b, err := io.ReadAll(io.LimitReader(f, 256<<20+1))
	if err != nil {
		return e, err
	}
	if len(b) > 256<<20 {
		return e, errors.New("oversized_record")
	}
	var env recordEnvelope
	if err = json.Unmarshal(b, &env); err != nil {
		return e, errors.New("invalid_record")
	}
	sum := sha256.Sum256(env.Event)
	if hex.EncodeToString(sum[:]) != env.SHA {
		return e, errors.New("record_checksum_mismatch")
	}
	if err = json.Unmarshal(env.Event, &e); err != nil {
		return e, errors.New("invalid_event")
	}
	return e, nil
}
func (s *DiskStore) Recover() (int, error) {
	entries, err := os.ReadDir(filepath.Join(s.root, "active"))
	if err != nil {
		return 0, err
	}
	count := 0
	for _, entry := range entries {
		if !strings.HasSuffix(entry.Name(), ".json") {
			continue
		}
		path := filepath.Join(s.root, "active", entry.Name())
		e, err := ReadRecord(path)
		if err != nil {
			return count, err
		}
		final := filepath.Join(s.root, "events", e.At.UTC().Format("2006-01-02"), e.ID+".json")
		if _, err := os.Stat(final); err == nil {
			if _, err = ReadRecord(final); err != nil {
				return count, err
			}
			if err = s.remove(path); err != nil {
				return count, err
			}
			continue
		}
		e.Outcome = "process_interrupted"
		e.Missing = []string{"capture_process_restart"}
		if err = s.Write(e); err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}
func (s *DiskStore) Prune() (int, error) {
	cutoff := s.now().Add(-Retention)
	count := 0
	pruneTree := func(root string, suffix string) error {
		return filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if d.IsDir() || !strings.HasSuffix(d.Name(), suffix) {
				return nil
			}
			// A daily partition only gets scanned when any record could have expired.
			partition := filepath.Base(filepath.Dir(path))
			if suffix == ".jsonl" {
				partition = strings.TrimSuffix(d.Name(), suffix)
			}
			day, err := time.Parse("2006-01-02", partition)
			if err != nil {
				return errors.New("invalid_record_partition")
			}
			if day.After(cutoff) {
				return nil
			}
			if suffix == ".jsonl" {
				if err = s.remove(path); err != nil {
					return err
				}
				count++
				return nil
			}
			e, err := ReadRecord(path)
			if err != nil {
				return err
			}
			if !e.At.After(cutoff) {
				if err = s.remove(path); err != nil {
					return err
				}
				count++
			}
			return nil
		})
	}
	err := pruneTree(filepath.Join(s.root, "events"), ".json")
	if err == nil {
		err = pruneTree(filepath.Join(s.root, "losses"), ".jsonl")
	}
	return count, err
}
func Export(root string, w io.Writer, since time.Time) (int, error) {
	var paths []string
	err := filepath.WalkDir(filepath.Join(root, "events"), func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("store_symlink_refused")
		}
		if !d.IsDir() && strings.HasSuffix(d.Name(), ".json") {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return 0, err
	}
	sort.Strings(paths)
	count := 0
	enc := json.NewEncoder(w)
	for _, path := range paths {
		e, err := ReadRecord(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return count, fmt.Errorf("record_validation_failed: %s", filepath.Base(path))
		}
		if e.At.Before(since) {
			continue
		}
		if err = enc.Encode(e); err != nil {
			return count, err
		}
		count++
	}
	return count, nil
}

// ExportLosses streams the body-free persistent loss ledger for administrators.
// It deliberately has a separate command and format from event export.
func ExportLosses(root string, w io.Writer, since time.Time) (int, error) {
	var paths []string
	err := filepath.WalkDir(filepath.Join(root, "losses"), func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type()&os.ModeSymlink != 0 {
			return errors.New("store_symlink_refused")
		}
		if !d.IsDir() && strings.HasSuffix(d.Name(), ".jsonl") {
			paths = append(paths, path)
		}
		return nil
	})
	if err != nil {
		return 0, err
	}
	sort.Strings(paths)
	count := 0
	enc := json.NewEncoder(w)
	for _, path := range paths {
		f, err := os.Open(path)
		if err != nil {
			return count, err
		}
		scanner := bufio.NewScanner(io.LimitReader(f, 16<<20))
		for scanner.Scan() {
			var loss Loss
			if err = json.Unmarshal(scanner.Bytes(), &loss); err != nil || loss.At.Before(since) {
				if err != nil {
					_ = f.Close()
					return count, errors.New("invalid_loss_record")
				}
				continue
			}
			if err = enc.Encode(loss); err != nil {
				_ = f.Close()
				return count, err
			}
			count++
		}
		if err = scanner.Err(); err != nil {
			_ = f.Close()
			return count, err
		}
		if err = f.Close(); err != nil {
			return count, err
		}
	}
	return count, nil
}

func WritePrivateJSON(path string, value any) error {
	b, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return atomicFile(path, append(b, '\n'))
}
