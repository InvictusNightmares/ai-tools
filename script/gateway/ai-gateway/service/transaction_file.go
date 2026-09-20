package service

import (
	"errors"
	"io"
	"os"
	"path/filepath"
	"sync"
	"syscall"
	"time"
)

// TransactionFile serializes cooperating processes on one local filesystem.
// The stable lock inode is separate from the atomically replaced data inode.
// It is not a distributed lock and must not be placed on an NFS volume.
type TransactionFile struct {
	Path     string
	MaxBytes int64
	mu       sync.Mutex
}

func (f *TransactionFile) Update(fn func([]byte) ([]byte, error)) error {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.Path == "" {
		return errors.New("transaction_path_required")
	}
	directory := filepath.Dir(f.Path)
	if err := os.MkdirAll(directory, 0700); err != nil {
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
			return errors.New("transaction_lock_timeout")
		}
		time.Sleep(5 * time.Millisecond)
	}
	defer syscall.Flock(int(lock.Fd()), syscall.LOCK_UN)
	limit := f.MaxBytes
	if limit <= 0 {
		limit = 64 << 20
	}
	var raw []byte
	input, err := os.OpenFile(f.Path, os.O_RDONLY|syscall.O_NOFOLLOW, 0)
	if err == nil {
		raw, err = io.ReadAll(io.LimitReader(input, limit+1))
		_ = input.Close()
		if err != nil {
			return err
		}
		if int64(len(raw)) > limit {
			return errors.New("transaction_data_limit")
		}
	} else if !os.IsNotExist(err) {
		return err
	}
	next, err := fn(raw)
	if err != nil || next == nil {
		return err
	}
	if int64(len(next)) > limit {
		return errors.New("transaction_data_limit")
	}
	temp, err := os.CreateTemp(directory, ".gateway-transaction-*")
	if err != nil {
		return err
	}
	name := temp.Name()
	defer os.Remove(name)
	if err = temp.Chmod(0600); err == nil {
		_, err = temp.Write(next)
	}
	if err == nil {
		err = temp.Sync()
	}
	closeErr := temp.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if err = os.Rename(name, f.Path); err != nil {
		return err
	}
	dir, err := os.Open(directory)
	if err != nil {
		return err
	}
	defer dir.Close()
	return dir.Sync()
}
