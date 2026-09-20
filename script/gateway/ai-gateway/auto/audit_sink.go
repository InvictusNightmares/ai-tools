package autogateway

import (
	"fmt"
	"local/ai-gateway/service"
	"os"
	"path/filepath"
)

// AuditSink persists route decisions without request content. Implementations
// can replace the local JSONL spool with the regional audit database writer.
type AuditSink interface {
	WriteRouteAudit(RouteAudit) error
}

type JSONLAuditSink struct {
	file service.JSONLFile
}

func NewJSONLAuditSink(path string) (*JSONLAuditSink, error) {
	if path == "" {
		return nil, fmt.Errorf("audit sink path is required")
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return nil, err
	}
	file, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, err
	}
	_ = file.Close()
	return &JSONLAuditSink{file: service.JSONLFile{Path: path}}, nil
}

func (sink *JSONLAuditSink) WriteRouteAudit(audit RouteAudit) error {
	if sink == nil {
		return fmt.Errorf("audit sink is nil")
	}
	return sink.file.Append(audit)
}
