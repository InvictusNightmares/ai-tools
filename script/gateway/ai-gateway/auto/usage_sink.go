package autogateway

import (
	"fmt"
	"local/ai-gateway/service"
	"os"
	"path/filepath"
)

// UsageEventSink is intentionally append-only. Events contain identifiers and
// counters, never prompt text, authorization values or response bodies.
type UsageEventSink interface {
	WriteUsageEvent(UsageEvent) error
}

// JSONLUsageSink provides a durable local spool for later import into the
// regional usage database. Each line is fsynced before returning so a process
// crash cannot silently acknowledge a usage event that was never persisted.
type JSONLUsageSink struct {
	file service.JSONLFile
}

func NewJSONLUsageSink(path string) (*JSONLUsageSink, error) {
	if path == "" {
		return nil, fmt.Errorf("usage sink path is required")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, err
	}
	_ = file.Close()
	return &JSONLUsageSink{file: service.JSONLFile{Path: path}}, nil
}

func (sink *JSONLUsageSink) WriteUsageEvent(event UsageEvent) error {
	if sink == nil {
		return fmt.Errorf("usage sink is nil")
	}
	return sink.file.Append(event)
}
