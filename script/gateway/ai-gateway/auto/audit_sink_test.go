package autogateway

import (
	"os"
	"strings"
	"testing"
)

func TestJSONLAuditSinkDoesNotPersistPrompt(t *testing.T) {
	path := t.TempDir() + "/audit/events.jsonl"
	sink, err := NewJSONLAuditSink(path)
	if err != nil {
		t.Fatal(err)
	}
	err = sink.WriteRouteAudit(RouteAudit{RequestedModel: "auto", EffectiveModel: "deepseek-flash", Reason: "initial_selection"})
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(data), "deepseek-flash") || strings.Contains(string(data), "messages") {
		t.Fatalf("unexpected audit line: %s", data)
	}
}
