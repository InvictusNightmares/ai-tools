package requestcontent

import (
	"bytes"
	"compress/gzip"
	"context"
	"encoding/base64"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func fixtureMember(t *testing.T, e Entry) []byte {
	t.Helper()
	var b bytes.Buffer
	z := gzip.NewWriter(&b)
	if err := json.NewEncoder(z).Encode(e); err != nil {
		t.Fatal(err)
	}
	z.Close()
	return b.Bytes()
}
func TestPolicyRequestsReaderAppendFilterPrune(t *testing.T) {
	dir := t.TempDir()
	name := "requests-20260903T03-1-1-000001.jsonl.gz"
	path := filepath.Join(dir, name)
	one := fixtureMember(t, Entry{RecordedAt: time.Date(2026, 9, 3, 3, 0, 0, 0, time.UTC), APIKeyID: 65, APIKeyName: "测试人员", UserID: 9, ErrorCode: "cyber_policy", Model: "gpt-5.4", Body: []byte(`{"input":"SECRET_BODY <script>alert(1)</script>"}`), BodySHA256: "one"})
	two := fixtureMember(t, Entry{RecordedAt: time.Date(2026, 9, 3, 4, 0, 0, 0, time.UTC), APIKeyID: 66, APIKeyName: "other", UserID: 9, ErrorCode: "structured_refusal", Model: "gpt-5.5", Body: []byte(`{"input":"second"}`), BodySHA256: "two"})
	os.WriteFile(path, one, 0600)
	r := NewReader(dir)
	q := Query{Page: 1, PageSize: 20}
	ctx := context.Background()
	list, err := r.List(ctx, q)
	if err != nil || list.Total != 1 {
		t.Fatalf("list %+v %v", list, err)
	}
	raw, _ := json.Marshal(list)
	if strings.Contains(string(raw), "SECRET_BODY") || strings.Contains(string(raw), `"body":`) {
		t.Fatal("body leaked in metadata")
	}
	var gotBody []byte
	err = r.WithBody(ctx, list.Items[0].ID, func(_ Metadata, b io.Reader) error { var e error; gotBody, e = io.ReadAll(b); return e })
	if err != nil || !bytes.Contains(gotBody, []byte("SECRET_BODY")) {
		t.Fatalf("detail %v", err)
	}
	f, _ := os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0600)
	f.Write(two[:len(two)/2])
	f.Close()
	list, err = r.List(ctx, q)
	if err != nil || list.Total != 1 || !list.IndexPending || list.UnreadableFiles != 0 {
		t.Fatalf("partial append %+v %v", list, err)
	}
	f, _ = os.OpenFile(path, os.O_APPEND|os.O_WRONLY, 0600)
	f.Write(two[len(two)/2:])
	f.Close()
	list, err = r.List(ctx, q)
	if err != nil || list.Total != 2 || list.IndexPending || list.Items[0].APIKeyID != 66 {
		t.Fatalf("completed append %+v %v", list, err)
	}
	q.Key = "65"
	list, _ = r.List(ctx, q)
	if list.Total != 1 || list.Items[0].APIKeyName != "测试人员" {
		t.Fatal("key filter")
	}
	q.Key = "测试"
	q.Model = "5.4"
	q.ErrorCode = "cyber_policy"
	q.Start = time.Date(2026, 9, 3, 3, 0, 0, 0, time.UTC)
	q.End = q.Start.Add(time.Hour)
	list, _ = r.List(ctx, q)
	if list.Total != 1 {
		t.Fatal("combined filters")
	}
	q.End = q.Start
	list, _ = r.List(ctx, q)
	if list.Total != 0 {
		t.Fatal("end must be exclusive")
	}
	q = Query{Page: 2, PageSize: 1}
	list, _ = r.List(ctx, q)
	if list.Total != 2 || len(list.Items) != 1 || list.Items[0].APIKeyID != 65 {
		t.Fatal("pagination")
	}
	id := list.Items[0].ID
	os.Remove(path)
	if err := r.WithBody(ctx, id, func(Metadata, io.Reader) error { return nil }); !os.IsNotExist(err) {
		t.Fatal("deleted detail")
	}
	list, _ = r.List(ctx, q)
	if list.Total != 0 {
		t.Fatal("deleted cache survived")
	}
}
func TestPolicyRequestsReaderPathAndConcurrency(t *testing.T) {
	dir := t.TempDir()
	outside := filepath.Join(t.TempDir(), "private.txt")
	os.WriteFile(outside, []byte("private"), 0600)
	name := "requests-20260903T03-1-1-000001.jsonl.gz"
	os.Symlink(outside, filepath.Join(dir, name))
	r := NewReader(dir)
	list, err := r.List(context.Background(), Query{Page: 1, PageSize: 20})
	if err != nil || list.Total != 0 {
		t.Fatal("symlink indexed")
	}
	for _, id := range []string{"../private.txt", strings.Repeat("x", 64), strings.Repeat("0", 64)} {
		if err := r.WithBody(context.Background(), id, func(Metadata, io.Reader) error { return nil }); !os.IsNotExist(err) {
			t.Fatal("unsafe id accepted")
		}
	}
	r.gate <- struct{}{}
	if _, err := r.List(context.Background(), Query{Page: 1, PageSize: 20}); err != ErrReadBusy {
		t.Fatal("parallel scans not bounded")
	}
	<-r.gate
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	r.gate <- struct{}{}
	if _, err := r.List(ctx, Query{Page: 1, PageSize: 20}); err == nil {
		t.Fatal("cancel ignored")
	}
	<-r.gate
}

func TestPolicyRequestsLargeV2EscapingAndRollingIndex(t *testing.T) {
	t.Run("escaped body remains readable", func(t *testing.T) {
		dir := t.TempDir()
		name := "requests-20260903T03-1-1-000001.jsonl.gz"
		body, _ := json.Marshal(map[string]string{"input": strings.Repeat("<", 17<<20)})
		// Use an unescaped original body, matching RawMessage from a real request.
		body = bytes.ReplaceAll(body, []byte(`\u003c`), []byte("<"))
		member := fixtureMember(t, Entry{APIKeyID: 65, RecordedAt: time.Now(), Body: body, ErrorCode: "cyber_policy"})
		second := fixtureMember(t, Entry{APIKeyID: 66, RecordedAt: time.Now(), Body: []byte(`{}`), ErrorCode: "content_filter"})
		os.WriteFile(filepath.Join(dir, name), append(member, second...), 0600)
		r := NewReader(dir)
		list, err := r.List(context.Background(), Query{Page: 1, PageSize: 20})
		if err != nil || list.UnreadableFiles != 0 {
			t.Fatalf("large legacy record unreadable: %+v %v", list, err)
		}
		for list.IndexPending {
			list, err = r.List(context.Background(), Query{Page: 1, PageSize: 20})
			if err != nil {
				t.Fatal(err)
			}
		}
		if list.Total != 2 {
			t.Fatalf("later member inaccessible: %d", list.Total)
		}
		for _, row := range list.Items {
			if row.APIKeyID == 65 {
				var count int64
				err = r.WithBody(context.Background(), row.ID, func(_ Metadata, b io.Reader) error { var e error; count, e = io.Copy(io.Discard, b); return e })
				if err != nil || count < 96<<20 {
					t.Fatalf("large download %d %v", count, err)
				}
			}
		}
	})
	t.Run("newest admitted after capacity", func(t *testing.T) {
		r := NewReader(t.TempDir())
		base := time.Now()
		for i := 0; i < maxIndexedRecords+2; i++ {
			m := Metadata{ID: strconv.Itoa(i), RecordedAt: base.Add(time.Duration(i) * time.Second)}
			r.index(&indexedRecord{meta: m})
		}
		if len(r.entries) != maxIndexedRecords || !r.limited {
			t.Fatal("unbounded index")
		}
		if _, ok := r.entries[strconv.Itoa(maxIndexedRecords+1)]; !ok {
			t.Fatal("new event blocked")
		}
		if _, ok := r.entries["0"]; ok {
			t.Fatal("oldest retained")
		}
		r.index(&indexedRecord{meta: Metadata{ID: "old", RecordedAt: base.Add(-time.Hour)}})
		if _, ok := r.entries["old"]; ok {
			t.Fatal("old history displaced latest")
		}
	})
}
func TestPolicyRequestsMultipartStreamAndGate(t *testing.T) {
	dir := t.TempDir()
	raw := []byte("multipart bytes \x00 \xff")
	encoded, _ := json.Marshal(base64.StdEncoding.EncodeToString(raw))
	name := "requests-20260903T03-1-1-000001.jsonl.gz"
	os.WriteFile(filepath.Join(dir, name), fixtureMember(t, Entry{APIKeyID: 65, BodyEncoding: "base64", Body: encoded, RecordedAt: time.Now()}), 0600)
	r := NewReader(dir)
	list, err := r.List(context.Background(), Query{Page: 1, PageSize: 20})
	if err != nil {
		t.Fatal(err)
	}
	err = r.WithBody(context.Background(), list.Items[0].ID, func(_ Metadata, b io.Reader) error {
		if _, e := r.List(context.Background(), Query{Page: 1, PageSize: 20}); e != ErrReadBusy {
			t.Fatal("gate released during consumption")
		}
		got, e := io.ReadAll(b)
		if !bytes.Equal(got, raw) {
			t.Fatal("multipart bytes changed")
		}
		return e
	})
	if err != nil {
		t.Fatal(err)
	}
}
