package capture

import (
	"bytes"
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

func TestLiteralTextAndToolContentAreNotRedacted(t *testing.T) {
	raw := []byte(`{"model":"fixture","instructions":"引用不等于命令","input":[{"role":"user","content":"sk-synthetic-only password=fixture https://example.invalid/?token=fixture"},{"type":"function_call","call_id":"c1","arguments":"{\"api_key\":\"fixture\",\"url\":\"data:text/plain;base64,ABC\"}"},{"type":"function_call_output","call_id":"c1","output":"literal tool text"}],"metadata":{"Authorization":"a literal business field","n":9007199254740993},"encrypted_content":"native-state","signature":"native-signature"}`)
	original := bytes.Clone(raw)
	out, err := ProjectJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	want, _ := decodeJSON(raw)
	got, _ := decodeJSON(out)
	if !reflect.DeepEqual(want, got) {
		t.Fatalf("ordinary content changed: %s", out)
	}
	if !bytes.Equal(original, raw) {
		t.Fatal("forwarding source mutated")
	}
}

func TestAttachmentProjectionDoesNotTreatToolsAsMedia(t *testing.T) {
	raw := []byte(`{"messages":[{"role":"user","content":[{"type":"image","source":{"type":"base64","media_type":"image/png","data":"SYNTHETIC_BINARY"}},{"type":"input_file","file_id":"file-fixture","file_data":"SYNTHETIC_BINARY"},{"type":"text","text":"https://example.invalid/keep?token=literal"}]},{"role":"assistant","content":[{"type":"tool_use","id":"t1","input":{"type":"image","data":"LITERAL_ARGUMENT"}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1","content":[{"type":"text","text":"LITERAL_RESULT"},{"type":"image","source":{"type":"base64","data":"SYNTHETIC_BINARY"}}]}]}]}`)
	out, err := ProjectJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(out, []byte("SYNTHETIC_BINARY")) {
		t.Fatal("attachment bytes retained")
	}
	for _, s := range []string{"file-fixture", "image/png", "sha256", "LITERAL_ARGUMENT", "LITERAL_RESULT", "token=literal"} {
		if !bytes.Contains(out, []byte(s)) {
			t.Fatalf("lost %s", s)
		}
	}
}

func TestStreamFragmentsRemainLiteralAndOrdered(t *testing.T) {
	events := []json.RawMessage{json.RawMessage(`{"type":"response.output_text.delta","delta":"before sk-abcdef"}`), json.RawMessage(`{"type":"response.output_text.delta","delta":"ghijklmnop after"}`)}
	out, err := ProjectSequence(events)
	if err != nil {
		t.Fatal(err)
	}
	var decoded []json.RawMessage
	if err := json.Unmarshal(out, &decoded); err != nil {
		t.Fatal(err)
	}
	for i := range events {
		a, _ := decodeJSON(events[i])
		b, _ := decodeJSON(decoded[i])
		if !reflect.DeepEqual(a, b) {
			t.Fatal("stream fragment changed")
		}
	}
}

func TestGeneratedImagesAndAudioStoreMetadataAndTranscript(t *testing.T) {
	for _, raw := range []string{
		`{"output":[{"type":"image_generation_call","result":"SYNTHETIC_BINARY"}]}`,
		`{"type":"response.image_generation_call.partial_image","partial_image_b64":"SYNTHETIC_BINARY"}`,
		`{"type":"response.audio.delta","delta":"SYNTHETIC_BINARY"}`,
		`{"choices":[{"message":{"audio":{"data":"SYNTHETIC_BINARY","transcript":"retain transcript"}}}]}`,
	} {
		out, err := ProjectJSON([]byte(raw))
		if err != nil || strings.Contains(string(out), "SYNTHETIC_BINARY") {
			t.Fatalf("%s %v", out, err)
		}
		if strings.Contains(raw, "retain transcript") && !strings.Contains(string(out), "retain transcript") {
			t.Fatal("transcript lost")
		}
	}
	out, err := ProjectJSONForPath([]byte(`{"data":[{"b64_json":"SYNTHETIC_BINARY","revised_prompt":"keep text"}]}`), "/v1/images/generations")
	if err != nil || strings.Contains(string(out), "SYNTHETIC_BINARY") || !strings.Contains(string(out), "keep text") {
		t.Fatal("image endpoint projection failed")
	}
}

func TestInvalidProtocolIsAnExplicitProjectionError(t *testing.T) {
	for _, raw := range []string{`{"input":"unfinished`, `{} {}`, `binary`} {
		out, err := ProjectJSON([]byte(raw))
		if err == nil || len(out) != 0 {
			t.Fatal("invalid input silently retained")
		}
	}
}

func TestSSECommentsCRLFDoneAndMalformed(t *testing.T) {
	events, err := ParseSSE([]byte(": keepalive\r\n\r\nevent: message\r\ndata: {\"text\":\"ok\"}\r\n\r\ndata: [DONE]\r\n\r\n"))
	if err != nil || len(events) != 1 {
		t.Fatalf("%v %v", events, err)
	}
	if _, err := ParseSSE([]byte("data: {\"text\":\"fixture\"\n\n")); err == nil {
		t.Fatal("invalid stream hidden")
	}
}

func TestNestedNativeFileIdentifiersRemainInMetadata(t *testing.T) {
	raw := []byte(`{"messages":[{"role":"user","content":[{"type":"file","file":{"filename":"fixture.txt","file_id":"file-1","file_data":"SYNTHETIC_BINARY"}},{"type":"document","source":{"type":"file","file_id":"file-2"}}]}]}`)
	out, err := ProjectJSON(raw)
	if err != nil {
		t.Fatal(err)
	}
	for _, value := range []string{"fixture.txt", "file-1", "file-2"} {
		if !bytes.Contains(out, []byte(value)) {
			t.Fatal("file identity lost")
		}
	}
	if bytes.Contains(out, []byte("SYNTHETIC_BINARY")) {
		t.Fatal("attachment binary retained")
	}
}
