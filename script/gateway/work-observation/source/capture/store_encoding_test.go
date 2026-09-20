package capture

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"testing"
)

func TestRecordEnvelopeByteCompatibility(t *testing.T) {
	for _, body := range []string{`{"input":"literal <tag> 中文 & \\\""}`, `{"input":[{"role":"tool","content":"` + string(bytes.Repeat([]byte("x"), 1<<20)) + `"}]}`} {
		event := Event{ID: "fixture", Request: json.RawMessage(body)}
		raw, err := json.Marshal(event)
		if err != nil {
			t.Fatal(err)
		}
		sum := sha256.Sum256(raw)
		digest := hex.EncodeToString(sum[:])
		previous, err := json.Marshal(recordEnvelope{digest, raw})
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.Equal(append(previous, '\n'), wrapRecord(raw, digest)) {
			t.Fatal("record format or checksum input changed")
		}
	}
}

func BenchmarkRecordEnvelope(b *testing.B) {
	raw, _ := json.Marshal(Event{ID: "fixture", Request: json.RawMessage(`{"input":"` + string(bytes.Repeat([]byte("x"), 8<<20)) + `"}`)})
	sum := sha256.Sum256(raw)
	digest := hex.EncodeToString(sum[:])
	b.Run("legacy", func(b *testing.B) {
		b.ReportAllocs()
		b.SetBytes(int64(len(raw)))
		for i := 0; i < b.N; i++ {
			out, err := json.Marshal(recordEnvelope{digest, raw})
			if err != nil || len(out) == 0 {
				b.Fatal("encode")
			}
		}
	})
	b.Run("direct", func(b *testing.B) {
		b.ReportAllocs()
		b.SetBytes(int64(len(raw)))
		for i := 0; i < b.N; i++ {
			out := wrapRecord(raw, digest)
			if len(out) == 0 {
				b.Fatal("encode")
			}
		}
	})
}
