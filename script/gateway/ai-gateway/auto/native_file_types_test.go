package autogateway

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
)

func TestNativeFileTypesAndMessagesFilename(t *testing.T) {
	for _, tc := range []struct{ name, mime string }{{"notes.txt", "text/plain"}, {"rows.csv", "text/csv"}, {"report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, {"table.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}, {"slides.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"}, {"report.pdf", "application/pdf"}} {
		t.Run(tc.name, func(t *testing.T) {
			data := []byte("PK\x03\x04synthetic opaque attachment")
			store := &NativeFileStore{Root: t.TempDir(), Secret: "fixture-secret", Region: "tokyo"}
			f, err := store.save("key", tc.name, "user_data", data)
			if err != nil {
				t.Fatal(err)
			}
			raw, _ := json.Marshal(map[string]any{"messages": []any{map[string]any{"role": "user", "content": []any{map[string]any{"type": "document", "source": map[string]any{"type": "file", "file_id": f.ID}}}}}})
			expanded, err := store.Expand("key", raw)
			if err != nil {
				t.Fatal(err)
			}
			v, _ := nativeDecode(expanded)
			part := v.(map[string]any)["messages"].([]any)[0].(map[string]any)["content"].([]any)[0]
			native, ok := nativeClassifierPart(part)
			if !ok {
				t.Fatal("no native classifier file")
			}
			p := native.(map[string]any)
			if p["filename"] != tc.name || p["file_data"] != "data:"+tc.mime+";base64,"+base64.StdEncoding.EncodeToString(data) {
				t.Fatalf("wrong file envelope: %v", p)
			}
			r, _ := NormalizeProtocolRequest("anthropic", expanded)
			_, view, err := inspectNativeMedia(r)
			if err != nil || !strings.Contains(string(view.RawPayload), tc.name) {
				t.Fatal("filename missing from Guard view")
			}
			source := part.(map[string]any)["source"].(map[string]any)
			delete(source, "filename")
			if nativeDocumentFilename(source) != "attachment"+tc.name[strings.LastIndex(tc.name, "."):] {
				t.Fatal("bad inline document extension")
			}
		})
	}
	if nativeFileMIME("unknown.source", []byte("plain text")) != "text/plain" {
		t.Fatal("charset leaked into MIME")
	}
}
