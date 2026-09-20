package service

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"time"
)

// JSONLFile reopens on every append and cooperates with the operations rotator
// through a stable .lock inode. An acknowledged record has reached fsync.
type JSONLFile struct {
	Path string
	mu   sync.Mutex
}

func (f *JSONLFile) Append(value any) error {
	encoded, err := json.Marshal(value)
	if err != nil {
		return err
	}
	if len(encoded) > 32<<20 {
		return errors.New("jsonl_record_limit")
	}
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.Path == "" {
		return errors.New("jsonl_path_required")
	}
	if err = os.MkdirAll(filepath.Dir(f.Path), 0700); err != nil {
		return err
	}
	lock, err := os.OpenFile(f.Path+".lock", os.O_CREATE|os.O_RDWR|syscall.O_NOFOLLOW, 0600)
	if err != nil {
		return err
	}
	defer lock.Close()
	deadline := time.Now().Add(3 * time.Second)
	for {
		err = syscall.Flock(int(lock.Fd()), syscall.LOCK_EX|syscall.LOCK_NB)
		if err == nil {
			break
		}
		if !errors.Is(err, syscall.EWOULDBLOCK) && !errors.Is(err, syscall.EAGAIN) {
			return err
		}
		if time.Now().After(deadline) {
			return errors.New("jsonl_lock_timeout")
		}
		time.Sleep(5 * time.Millisecond)
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	file, err := os.OpenFile(f.Path, os.O_CREATE|os.O_APPEND|os.O_WRONLY|syscall.O_NOFOLLOW, 0600)
	if err != nil {
		return err
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil {
		return err
	}
	if !info.Mode().IsRegular() {
		return errors.New("jsonl_regular_file_required")
	}
	if err = file.Chmod(0600); err != nil {
		return err
	}
	if _, err = file.Write(append(encoded, '\n')); err != nil {
		return err
	}
	return file.Sync()
}
