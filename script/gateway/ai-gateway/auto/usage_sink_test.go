package autogateway

import (
	"os"
	"strings"
	"testing"
	"time"
)

func TestJSONLUsageSinkWritesRedactedCounters(t *testing.T) {
	path := t.TempDir() + "/usage/events.jsonl"
	sink, err := NewJSONLUsageSink(path)
	if err != nil {
		t.Fatal(err)
	}
	err = sink.WriteUsageEvent(UsageEvent{At: time.Unix(1, 0), Region: "tokyo", EffectiveModel: "deepseek-flash", APIKeyID: "key-42", InputTokens: 3, OutputTokens: 2, Success: true})
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	text := string(data)
	if !strings.Contains(text, "key-42") || !strings.Contains(text, "input_tokens") || strings.Contains(text, "prompt") {
		t.Fatalf("unexpected usage line: %s", text)
	}
}
