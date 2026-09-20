package main

import (
	"encoding/json"
	"errors"
	"os"

	"local/work-observation/source/capture"
)

func captureSwitch(path string, fallback bool) bool {
	data, err := os.ReadFile(path)
	if os.IsNotExist(err) {
		return fallback
	}
	if err != nil {
		return false
	}
	var command struct {
		Enabled bool `json:"enabled"`
	}
	if json.Unmarshal(data, &command) != nil {
		return false
	}
	return command.Enabled
}

type unavailableSink struct{}

func (unavailableSink) Begin(capture.Event) error { return errors.New("capture_unavailable") }
func (unavailableSink) Write(capture.Event) error { return errors.New("capture_unavailable") }
func (unavailableSink) StoredBytes() int64        { return 0 }

func openCapture(c config) (*capture.DiskStore, []byte, int, string) {
	// A placeholder is never used for hashing: the returned failure permanently
	// inhibits this process's capture engine before any listener is opened.
	placeholder := make([]byte, 32)
	info, err := os.Lstat(c.SaltFile)
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		return nil, placeholder, 0, "identity_salt_unavailable"
	}
	salt, err := os.ReadFile(c.SaltFile)
	if err != nil || len(salt) != 32 {
		return nil, placeholder, 0, "identity_salt_unavailable"
	}
	store, err := capture.NewDiskStore(c.StoreDir, c.StorageBytes)
	if err != nil {
		return nil, salt, 0, "capture_store_unavailable"
	}
	recovered, err := store.Recover()
	if err != nil {
		store.Close()
		return nil, salt, recovered, "capture_recovery_failed"
	}
	return store, salt, recovered, ""
}
