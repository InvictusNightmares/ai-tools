package requestcontent

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
)

func TestAllPolicySignalsPersistIncludingMultipartBody(t *testing.T) {
	opts := testOptions(t)
	r, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	for _, code := range []string{"cyber_policy", "content_policy", "content_policy_violation", "invalid_prompt", "content_filter", "structured_refusal"} {
		if !r.Capture(Entry{APIKeyID: 65, ErrorCode: code, Body: []byte(`{"input":"harmless test fixture"}`)}) {
			t.Fatal(code)
		}
	}
	raw := []byte("--fixture\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\nharmless fixture\r\n--fixture--")
	if !r.Capture(Entry{APIKeyID: 65, ErrorCode: "content_policy", Body: raw}) {
		t.Fatal("multipart capture failed")
	}
	closeForTest(t, r)
	entries := readEntries(t, opts.Directory)
	if len(entries) != 7 {
		t.Fatalf("got %d entries", len(entries))
	}
	e := entries[6]
	var encoded string
	if err := json.Unmarshal(e.Body, &encoded); err != nil {
		t.Fatal(err)
	}
	decoded, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil || string(decoded) != string(raw) || e.BodyEncoding != "base64" || e.BodyBytes != len(raw) {
		t.Fatal("raw multipart did not round trip")
	}
}

func TestPolicyQueueBudgetIncludesMetadata(t *testing.T) {
	opts := testOptions(t)
	opts.MaxQueuedBytes = 1024
	r, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if r.Capture(Entry{APIKeyID: 1, ErrorCode: "content_policy", ErrorType: strings.Repeat("x", 1024), Body: []byte(`{}`)}) {
		t.Fatal("large metadata bypassed queue limit")
	}
	closeForTest(t, r)
	if len(readEntries(t, opts.Directory)) != 0 {
		t.Fatal("oversize record was persisted")
	}
}
