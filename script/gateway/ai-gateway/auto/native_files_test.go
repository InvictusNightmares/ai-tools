package autogateway

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func TestNativeFilesQuotaChild(t *testing.T) {
	root := os.Getenv("GATEWAY_FILE_QUOTA_CHILD")
	if root == "" {
		t.Skip("subprocess fixture")
	}
	store := &NativeFileStore{Root: root, Secret: "fixture", Region: "tokyo"}
	success := 0
	for i := 0; i < 40; i++ {
		_, err := store.save("same-key", "fixture.txt", "user_data", []byte("fixture"))
		if err == nil {
			success++
		} else if err.Error() != "file_storage_quota_exceeded" {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(os.Getenv("GATEWAY_FILE_QUOTA_RESULT"), []byte(strconv.Itoa(success)), 0600); err != nil {
		t.Fatal(err)
	}
}

func TestNativeFilesQuotaIsAtomicAcrossProcesses(t *testing.T) {
	root := t.TempDir()
	results := t.TempDir()
	commands := []*exec.Cmd{}
	for i := 0; i < 4; i++ {
		command := exec.Command(os.Args[0], "-test.run=^TestNativeFilesQuotaChild$")
		command.Env = append(os.Environ(), "GATEWAY_FILE_QUOTA_CHILD="+root, "GATEWAY_FILE_QUOTA_RESULT="+filepath.Join(results, strconv.Itoa(i)))
		command.Stdout = os.Stdout
		command.Stderr = os.Stderr
		if err := command.Start(); err != nil {
			t.Fatal(err)
		}
		commands = append(commands, command)
	}
	total := 0
	for i, command := range commands {
		if err := command.Wait(); err != nil {
			t.Fatal(err)
		}
		data, err := os.ReadFile(filepath.Join(results, strconv.Itoa(i)))
		if err != nil {
			t.Fatal(err)
		}
		n, err := strconv.Atoi(string(data))
		if err != nil {
			t.Fatal(err)
		}
		total += n
	}
	if total != 128 {
		t.Fatalf("quota race: accepted %d files", total)
	}
	store := &NativeFileStore{Root: root, Secret: "fixture", Region: "tokyo"}
	dir, _ := store.directory("same-key")
	files, _ := filepath.Glob(filepath.Join(dir, "*.json"))
	if len(files) != 128 {
		t.Fatalf("stored %d files", len(files))
	}
	if _, err := store.save("other-key", "fixture.txt", "user_data", []byte("fixture")); err != nil {
		t.Fatal("per-Key quota crossed", err)
	}
}

func TestNativeFileIsolationPersistenceExpiryAndExpansion(t *testing.T) {
	now := time.Date(2026, 9, 16, 0, 0, 0, 0, time.UTC)
	store := &NativeFileStore{Root: t.TempDir(), Secret: "fixture-secret", Region: "tokyo", Now: func() time.Time { return now }}
	data := []byte("private attachment contents")
	f, err := store.save("key-a", "test.pdf", "user_data", data)
	if err != nil {
		t.Fatal(err)
	}
	if _, _, err := store.load("key-b", f.ID); err == nil {
		t.Fatal("cross-Key file access")
	}
	reopened := &NativeFileStore{Root: store.Root, Secret: store.Secret, Region: store.Region, Now: store.Now}
	_, got, err := reopened.load("key-a", f.ID)
	if err != nil || !bytes.Equal(data, got) {
		t.Fatal("restart lost content")
	}
	otherRegion := &NativeFileStore{Root: store.Root, Secret: store.Secret, Region: "us", Now: store.Now}
	if _, _, err := otherRegion.load("key-a", f.ID); err == nil {
		t.Fatal("cross-region file access")
	}
	body := []byte(`{"input":[{"role":"user","content":[{"type":"input_file","file_id":"` + f.ID + `"}]}],"metadata":{"file_id":"` + f.ID + `"}}`)
	expanded, err := store.Expand("key-a", body)
	if err != nil || !strings.Contains(string(expanded), base64.StdEncoding.EncodeToString(data)) {
		t.Fatal("file reference not expanded")
	}
	var obj map[string]any
	_ = json.Unmarshal(expanded, &obj)
	if obj["metadata"].(map[string]any)["file_id"] != f.ID {
		t.Fatal("unrelated metadata changed")
	}
	if _, err := store.Expand("key-b", body); err == nil {
		t.Fatal("cross-Key file expansion")
	}
	imageBody := []byte(`{"images":[{"file_id":"` + f.ID + `"}]}`)
	expanded, err = store.Expand("key-a", imageBody)
	if err != nil || !strings.Contains(string(expanded), `"image_url"`) {
		t.Fatal("image edit reference not adapted")
	}
	now = now.Add(31 * 24 * time.Hour)
	if _, _, err := store.load("key-a", f.ID); err == nil {
		t.Fatal("expired upload remained accessible")
	}
}

func TestNativeFilesHTTPUploadReferenceDownloadAndDelete(t *testing.T) {
	guard := nativeTestGuard(t, nil)
	defer guard.Close()
	gateway := NewAutoGateway()
	s := &HTTPServer{Gateway: gateway, Pipeline: &Pipeline{Gateway: gateway, Preflight: &HTTPPreflightChecker{Endpoint: guard.URL}}, Files: &NativeFileStore{Root: t.TempDir(), Secret: "fixture", Region: "tokyo"}}
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	_ = writer.WriteField("purpose", "user_data")
	p, _ := writer.CreateFormFile("file", "fixture.txt")
	p.Write([]byte("private attachment contents"))
	writer.Close()
	r := httptest.NewRequest("POST", "/v1/files", &body)
	r.Header.Set("Content-Type", writer.FormDataContentType())
	r.Header.Set("X-Gateway-API-Key-ID", "a")
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 200 {
		t.Fatalf("upload %d %s", w.Code, w.Body.String())
	}
	var file nativeFile
	if json.Unmarshal(w.Body.Bytes(), &file) != nil || file.ID == "" {
		t.Fatal("file envelope missing")
	}
	for _, tc := range []struct {
		method, path, key string
		want              int
	}{{"GET", "/v1/files/" + file.ID, "b", 404}, {"GET", "/v1/files/" + file.ID + "/content", "a", 200}, {"GET", "/v1/files", "a", 200}, {"DELETE", "/v1/files/" + file.ID, "a", 200}, {"GET", "/v1/files/" + file.ID, "a", 404}} {
		r = httptest.NewRequest(tc.method, tc.path, nil)
		r.Header.Set("X-Gateway-API-Key-ID", tc.key)
		w = httptest.NewRecorder()
		s.ServeHTTP(w, r)
		if w.Code != tc.want {
			t.Fatalf("%s %s %d %s", tc.method, tc.path, w.Code, w.Body.String())
		}
	}
}

func TestNativeFilesHTTPStorageFailuresAreUnavailable(t *testing.T) {
	guard := nativeTestGuard(t, nil)
	defer guard.Close()
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		t.Error("storage failure reached upstream")
		w.WriteHeader(502)
	}))
	defer upstream.Close()
	for _, fault := range []string{"lock", "metadata", "content", "quota"} {
		t.Run(fault, func(t *testing.T) {
			store := &NativeFileStore{Root: t.TempDir(), Secret: "fixture", Region: "tokyo"}
			file, err := store.save("a", "fixture.txt", "user_data", []byte("fixture"))
			if err != nil {
				t.Fatal(err)
			}
			dir, _ := store.directory("a")
			switch fault {
			case "lock":
				if err := os.Remove(filepath.Join(store.Root, ".native-files.lock")); err != nil {
					t.Fatal(err)
				}
				if err := os.Mkdir(filepath.Join(store.Root, ".native-files.lock"), 0700); err != nil {
					t.Fatal(err)
				}
			case "metadata":
				if err := os.WriteFile(filepath.Join(dir, file.ID+".json"), []byte("{"), 0600); err != nil {
					t.Fatal(err)
				}
			case "content":
				if err := os.WriteFile(filepath.Join(dir, file.ID+".bin"), []byte("truncated"), 0600); err != nil {
					t.Fatal(err)
				}
			case "quota":
				for i := 1; i < 128; i++ {
					if _, err := store.save("a", "fixture.txt", "user_data", []byte("fixture")); err != nil {
						t.Fatal(err)
					}
				}
			}
			gateway := NewAutoGateway()
			s := &HTTPServer{Gateway: gateway, Pipeline: &Pipeline{Gateway: gateway, Preflight: &HTTPPreflightChecker{Endpoint: guard.URL}}, Files: store, NativeAPI: &NativeAPI{BaseURL: upstream.URL}}
			cases := []struct{ method, path, contentType, body string }{
				{"GET", "/v1/files/" + file.ID, "", ""},
				{"GET", "/v1/files/" + file.ID + "/content", "", ""},
				{"GET", "/v1/files", "", ""},
				{"DELETE", "/v1/files/" + file.ID, "", ""},
				{"POST", "/v1/responses", "application/json", `{"model":"auto","input":[{"role":"user","content":[{"type":"input_file","file_id":"` + file.ID + `"}]}]}`},
				{"POST", "/v1/images/edits", "application/json", `{"model":"gpt-image-2.5-flare","prompt":"Edit this image.","images":[{"file_id":"` + file.ID + `"}]}`},
			}
			if fault == "quota" {
				cases = nil
			}
			if fault != "content" {
				var body bytes.Buffer
				writer := multipart.NewWriter(&body)
				_ = writer.WriteField("purpose", "user_data")
				part, _ := writer.CreateFormFile("file", "fixture.txt")
				_, _ = part.Write([]byte("fixture"))
				_ = writer.Close()
				cases = append(cases, struct{ method, path, contentType, body string }{"POST", "/v1/files", writer.FormDataContentType(), body.String()})
			}
			for _, tc := range cases {
				r := httptest.NewRequest(tc.method, tc.path, strings.NewReader(tc.body))
				r.Header.Set("Content-Type", tc.contentType)
				r.Header.Set("X-Gateway-API-Key-ID", "a")
				w := httptest.NewRecorder()
				s.ServeHTTP(w, r)
				want, code := 503, "file_store_unavailable"
				if fault == "quota" {
					want, code = 413, "file_storage_quota_exceeded"
				}
				if w.Code != want || !strings.Contains(w.Body.String(), code) || strings.Contains(w.Body.String(), store.Root) {
					t.Errorf("%s %s: want %d %s; got %d %s", tc.method, tc.path, want, code, w.Code, w.Body.String())
				}
			}
		})
	}
}
