package admin

import (
	"bytes"
	"compress/gzip"
	"encoding/json"
	"github.com/Wei-Shaw/sub2api/internal/requestcontent"
	"github.com/Wei-Shaw/sub2api/internal/server/middleware"
	"github.com/gin-gonic/gin"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func TestPolicyRequestsAdminBoundaryAndPreview(t *testing.T) {
	gin.SetMode(gin.TestMode)
	dir := t.TempDir()
	r := requestcontent.NewReader(dir)
	h := NewPolicyRequestsHandler(r)
	var data bytes.Buffer
	z := gzip.NewWriter(&data)
	body := []byte(`{"input":"` + strings.Repeat("a", 300000) + `"}`)
	json.NewEncoder(z).Encode(requestcontent.Entry{RecordedAt: time.Now(), APIKeyID: 65, ErrorCode: "cyber_policy", Body: body})
	z.Close()
	os.WriteFile(filepath.Join(dir, "requests-20260903T03-1-1-000001.jsonl.gz"), data.Bytes(), 0600)
	route := gin.New()
	route.Use(func(c *gin.Context) {
		if role := c.GetHeader("Test-Role"); role != "" {
			c.Set(string(middleware.ContextKeyUserRole), role)
		}
	})
	route.GET("/records", h.List)
	route.GET("/records/:id", h.Get)
	route.GET("/records/:id/body", h.Download)
	call := func(path, role string) *httptest.ResponseRecorder {
		w := httptest.NewRecorder()
		req := httptest.NewRequest("GET", path, nil)
		req.Header.Set("Test-Role", role)
		route.ServeHTTP(deadlineRecorder{w}, req)
		return w
	}
	for _, path := range []string{"/records", "/records/id", "/records/id/body"} {
		for role, want := range map[string]int{"": 401, "user": 403} {
			if w := call(path, role); w.Code != want {
				t.Fatalf("%s %s: %d", path, role, w.Code)
			}
		}
	}
	for _, query := range []string{"?page=0", "?page_size=101", "?start_time=oops", "?page=999999999999999999999", "?start_time=2026-09-03T00:00:00Z&end_time=2026-09-02T00:00:00Z"} {
		if w := call("/records"+query, "admin"); w.Code != 400 {
			t.Fatalf("invalid query %s: %d", query, w.Code)
		}
	}
	w := call("/records", "admin")
	if w.Code != 200 || w.Header().Get("Cache-Control") != "no-store" {
		t.Fatalf("list %d", w.Code)
	}
	var list struct {
		Data struct {
			Records requestcontent.Listing `json:"records"`
		} `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &list); err != nil || len(list.Data.Records.Items) != 1 {
		t.Fatalf("list decode %s", w.Body.String())
	}
	id := list.Data.Records.Items[0].ID
	w = call("/records/"+id, "admin")
	var detail struct {
		Data struct {
			Preview   string `json:"body_preview"`
			Truncated bool   `json:"preview_truncated"`
		} `json:"data"`
	}
	json.Unmarshal(w.Body.Bytes(), &detail)
	if w.Code != 200 || !detail.Data.Truncated || len(detail.Data.Preview) > 256<<10 {
		t.Fatal("unbounded preview")
	}
	w = call("/records/"+id+"/body", "admin")
	if w.Code != 200 || !bytes.Equal(w.Body.Bytes(), body) || w.Header().Get("Content-Length") != strconv.Itoa(len(body)) || !strings.Contains(w.Header().Get("Content-Disposition"), "attachment") {
		t.Fatal("download changed original")
	}
	// Real HTTP proves Content-Length makes an interrupted stream fail at the client.
	server := httptest.NewServer(route)
	defer server.Close()
	if err := os.Truncate(filepath.Join(dir, "requests-20260903T03-1-1-000001.jsonl.gz"), int64(data.Len()*3/4)); err != nil {
		t.Fatal(err)
	}
	req, _ := http.NewRequest("GET", server.URL+"/records/"+id+"/body", nil)
	req.Header.Set("Test-Role", "admin")
	resp, err := server.Client().Do(req)
	if err != nil {
		t.Fatal(err)
	}
	defer resp.Body.Close()
	_, err = io.ReadAll(resp.Body)
	if resp.StatusCode != 200 || err == nil {
		t.Fatalf("interrupted response appeared complete: status=%d err=%v", resp.StatusCode, err)
	}
}

type deadlineRecorder struct{ *httptest.ResponseRecorder }

func (deadlineRecorder) SetWriteDeadline(time.Time) error { return nil }
