package capture

import (
	"bytes"
	"encoding/json"
	"testing"
)

func TestLiteralJSONCannotBypassAttachmentProjection(t *testing.T) {
	for _, raw := range []string{
		`{"input":[{"type":"input_image","image_url":"data:image/png;base64,PRIVATE_MEDIA"}]}`,
		`{"input":[{"type":"input_\u0069mage","image_url":"PRIVATE_MEDIA"}]}`,
		`{"input":[{"\u0074ype":"input_file","file_data":"PRIVATE_MEDIA"}]}`,
		`{"choices":[{"delta":{"audio":{"data":"PRIVATE_MEDIA","transcript":"keep me"}}}]}`,
		`{"type":"response.output_audio.delta","delta":"PRIVATE_MEDIA"}`,
		`{"type":"response.image_generation_call.partial_image","partial_image_b64":"PRIVATE_MEDIA"}`,
		`{"output":[{"type":"image_generation_call","result":"PRIVATE_MEDIA"}]}`,
	} {
		if literalJSON([]byte(raw), "") {
			t.Fatal("attachment bypassed projection")
		}
		projected, err := ProjectJSON([]byte(raw))
		if err != nil || bytes.Contains(projected, []byte("PRIVATE_MEDIA")) {
			t.Fatal("attachment content retained", err)
		}
	}
	if literalJSON([]byte(`{"data":[{"b64_json":"PRIVATE_MEDIA"}]}`), "/v1/images/generations") {
		t.Fatal("image endpoint bypass")
	}
	for _, raw := range []string{`{"input":"unfinished"`, `{} {}`, "{\"input\":\"\xff\"}"} {
		if literalJSON([]byte(raw), "") {
			t.Fatal("invalid JSON admitted")
		}
	}
}

func TestLiteralJSONPreservesTextAndNativeContext(t *testing.T) {
	raw := []byte(`{ "model":"auto", "input":[{"role":"user","content":"中文与literal sk-fixture"}], "encrypted_content":"opaque-fixture", "count":9007199254740993 }`)
	if !literalJSON(raw, "") {
		t.Fatal("ordinary JSON not eligible")
	}
	projected, err := ProjectJSON(raw)
	if err != nil || !bytes.Equal(raw, projected) || !json.Valid(projected) {
		t.Fatal("literal JSON changed", err)
	}
	escaped := []byte(`{"input":[{"type":"function_call","arguments":"{\"type\":\"image\",\"data\":\"literal tool argument\"}"}]}`)
	projected, err = ProjectJSON(escaped)
	if err != nil || !bytes.Contains(projected, []byte("literal tool argument")) {
		t.Fatal("ordinary tool text removed", err)
	}
}
