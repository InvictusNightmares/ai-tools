package autogateway

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"local/ai-gateway/service"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Sub2API has no Files API. This regional, per-Key store implements the native
// upload/reference lifecycle and expands only our own IDs before forwarding.
type NativeFileStore struct {
	Root, Secret, Region string
	mu                   sync.Mutex
	Now                  func() time.Time
}
type nativeFile struct {
	ID       string `json:"id"`
	Object   string `json:"object"`
	Bytes    int    `json:"bytes"`
	Created  int64  `json:"created_at"`
	Expires  int64  `json:"expires_at"`
	Filename string `json:"filename"`
	Purpose  string `json:"purpose"`
	Status   string `json:"status"`
	MIME     string `json:"-"`
}

func (s *NativeFileStore) now() time.Time {
	if s.Now != nil {
		return s.Now()
	}
	return time.Now()
}
func (s *NativeFileStore) directory(key string) (string, error) {
	if s == nil || s.Root == "" || s.Secret == "" || s.Region == "" || key == "" {
		return "", errors.New("file_store_unavailable")
	}
	h := hmac.New(sha256.New, []byte(s.Secret))
	h.Write([]byte(s.Region + "\x00" + key))
	return filepath.Join(s.Root, hex.EncodeToString(h.Sum(nil))), nil
}
func (s *NativeFileStore) load(key, id string) (nativeFile, []byte, error) {
	var file nativeFile
	var data []byte
	err := s.withLock(func() (err error) { file, data, err = s.loadLocked(key, id); return })
	return file, data, err
}

func (s *NativeFileStore) withLock(fn func() error) error {
	if s == nil || s.Root == "" {
		return errors.New("file_store_unavailable")
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	lock := service.TransactionFile{Path: filepath.Join(s.Root, ".native-files")}
	var operationErr error
	err := lock.Update(func([]byte) ([]byte, error) { operationErr = fn(); return nil, operationErr })
	if operationErr != nil {
		return operationErr
	}
	if err != nil {
		return errors.New("file_store_unavailable")
	}
	return nil
}

// Only stable public error codes leave the store; filesystem paths and lock
// details are implementation data, and storage faults are retryable outages.
func nativeFileError(err error) (int, string) {
	switch err.Error() {
	case "file_not_found", "file_expired":
		return http.StatusNotFound, err.Error()
	case "file_size_limit", "file_storage_quota_exceeded", "attachment_total_size_limit":
		return http.StatusRequestEntityTooLarge, err.Error()
	case "invalid_json":
		return http.StatusBadRequest, "invalid_json"
	default:
		return http.StatusServiceUnavailable, "file_store_unavailable"
	}
}
func (s *NativeFileStore) loadLocked(key, id string) (nativeFile, []byte, error) {
	var f nativeFile
	dir, err := s.directory(key)
	if err != nil {
		return f, nil, err
	}
	if !strings.HasPrefix(id, "file-gw_") || !nativeFilePath.MatchString("/v1/files/"+id) {
		return f, nil, errors.New("file_not_found")
	}
	b, err := os.ReadFile(filepath.Join(dir, id+".json"))
	if os.IsNotExist(err) {
		return f, nil, errors.New("file_not_found")
	}
	if err != nil || json.Unmarshal(b, &f) != nil || f.ID != id {
		return f, nil, errors.New("file_store_unavailable")
	}
	if s.now().Unix() >= f.Expires {
		_ = os.Remove(filepath.Join(dir, id+".bin"))
		_ = os.Remove(filepath.Join(dir, id+".json"))
		return nativeFile{}, nil, errors.New("file_expired")
	}
	data, err := os.ReadFile(filepath.Join(dir, id+".bin"))
	if err != nil || len(data) != f.Bytes {
		return nativeFile{}, nil, errors.New("file_unavailable")
	}
	f.MIME = nativeFileMIME(f.Filename, data)
	return f, data, nil
}
func (s *NativeFileStore) save(key, name, purpose string, data []byte, retention ...time.Duration) (nativeFile, error) {
	var file nativeFile
	err := s.withLock(func() (err error) { file, err = s.saveLocked(key, name, purpose, data, retention...); return })
	return file, err
}

func (s *NativeFileStore) saveLocked(key, name, purpose string, data []byte, retention ...time.Duration) (nativeFile, error) {
	var out nativeFile
	dir, err := s.directory(key)
	if err != nil {
		return out, err
	}
	if len(data) == 0 || len(data) > 50<<20 {
		return out, errors.New("file_size_limit")
	}
	if err = os.MkdirAll(dir, 0700); err != nil {
		return out, errors.New("file_store_unavailable")
	}
	// Sweep expired uploads and enforce both per-Key and global disk budgets.
	tenant, total := 0, 0
	entries := 0
	err = filepath.WalkDir(s.Root, func(path string, d os.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if d.IsDir() || !strings.HasSuffix(path, ".json") {
			return nil
		}
		b, e := os.ReadFile(path)
		if e != nil {
			return e
		}
		var f nativeFile
		if json.Unmarshal(b, &f) != nil {
			return errors.New("file_store_unavailable")
		}
		if s.now().Unix() >= f.Expires {
			_ = os.Remove(strings.TrimSuffix(path, ".json") + ".bin")
			_ = os.Remove(path)
			return nil
		}
		total += f.Bytes
		if filepath.Dir(path) == dir {
			tenant += f.Bytes
			entries++
		}
		return nil
	})
	if err != nil {
		return out, errors.New("file_store_unavailable")
	}
	if total+len(data) > 4<<30 || tenant+len(data) > 512<<20 || entries >= 128 {
		return out, errors.New("file_storage_quota_exceeded")
	}
	var id [16]byte
	if _, err = rand.Read(id[:]); err != nil {
		return out, errors.New("file_store_unavailable")
	}
	now := s.now()
	ttl := 30 * 24 * time.Hour
	if len(retention) > 0 {
		ttl = retention[0]
	}
	out = nativeFile{ID: "file-gw_" + hex.EncodeToString(id[:]), Object: "file", Bytes: len(data), Created: now.Unix(), Expires: now.Add(ttl).Unix(), Filename: filepath.Base(name), Purpose: purpose, Status: "processed"}
	path := filepath.Join(dir, out.ID)
	if err = os.WriteFile(path+".bin", data, 0600); err != nil {
		return nativeFile{}, errors.New("file_store_unavailable")
	}
	b, _ := json.Marshal(out)
	if err = os.WriteFile(path+".json", b, 0600); err != nil {
		_ = os.Remove(path + ".bin")
		return nativeFile{}, errors.New("file_store_unavailable")
	}
	return out, nil
}

func (s *HTTPServer) handleNativeFiles(w http.ResponseWriter, r *http.Request) {
	fail := func(status int, code string) {
		errorType := "invalid_request_error"
		if status >= 500 {
			errorType = "server_error"
		}
		writeJSON(w, status, map[string]any{"error": map[string]string{"type": errorType, "code": code, "message": code}})
	}
	key := r.Header.Get("X-Gateway-API-Key-ID")
	if s.Pipeline == nil || s.Files == nil {
		fail(503, "file_store_unavailable")
		return
	}
	if r.Method == "DELETE" && strings.HasSuffix(r.URL.Path, "/content") {
		fail(405, "method_not_allowed")
		return
	}
	if key == "" {
		key = s.Meta.APIKeyID
	}
	meta := withRequestID(s.Meta)
	meta.APIKeyID = key
	meta.ClientHeaders = r.Header
	w.Header().Set("X-Gateway-Request-ID", meta.RequestID)
	w.Header().Set("X-Gateway-Guard-Scope", NativeGuardScope)
	var data []byte
	name, purpose := "", ""
	ttl := 30 * 24 * time.Hour
	if r.Method == "POST" && r.URL.Path == "/v1/files" {
		r.Body = http.MaxBytesReader(w, r.Body, MaxNativeRequestBytes)
		reader, err := r.MultipartReader()
		if err != nil {
			fail(400, "invalid_multipart")
			return
		}
		for {
			part, e := reader.NextPart()
			if e == io.EOF {
				break
			}
			if e != nil {
				fail(400, "invalid_multipart")
				return
			}
			b, e := io.ReadAll(io.LimitReader(part, (50<<20)+1))
			part.Close()
			if e != nil || len(b) > 50<<20 {
				fail(413, "file_size_limit")
				return
			}
			switch part.FormName() {
			case "file":
				if data != nil {
					fail(400, "duplicate_file")
					return
				}
				data = b
				name = part.FileName()
			case "purpose":
				purpose = string(b)
			case "expires_after[anchor]":
				if string(b) != "created_at" {
					fail(400, "invalid_expiration_anchor")
					return
				}
			case "expires_after[seconds]":
				seconds, e := strconv.Atoi(string(b))
				if e != nil || seconds < 3600 || seconds > 2592000 {
					fail(400, "invalid_expiration_seconds")
					return
				}
				ttl = time.Duration(seconds) * time.Second
			default:
				fail(400, "unsupported_file_field")
				return
			}
		}
		if len(data) == 0 || name == "" || purpose == "" {
			fail(400, "file_and_purpose_required")
			return
		}
	} else if r.Method != "GET" && r.Method != "DELETE" {
		fail(405, "method_not_allowed")
		return
	}
	inspection, _ := json.Marshal(map[string]any{"operation": "native_file_" + r.Method, "filename": name, "purpose": purpose, "bytes": len(data), "attachment_contents_not_inspected": true})
	body, _ := json.Marshal(map[string]any{"messages": []any{map[string]any{"role": "user", "content": string(inspection)}}})
	request, _ := NormalizeProtocolRequest("chat", body)
	preflight, err := evaluatePreflight(r.Context(), s.Pipeline.Preflight, request, meta)
	if err != nil || preflight.Decision != PreflightAllow {
		status, code := 503, "preflight_unavailable"
		if preflight.Decision == PreflightBlock {
			status, code = 403, "preflight_blocked"
		}
		s.Pipeline.writePreflightAudit(meta, "files", request, preflight, code)
		fail(status, code)
		return
	}
	if preflight.SanitizedRequest != nil && !bytesEqualJSON(preflight.SanitizedRequest.RawPayload, request.RawPayload) {
		fail(403, "file_metadata_rejected")
		return
	}
	audit := RouteAudit{At: time.Now(), RequestID: meta.RequestID, Region: meta.Region, APIKeyID: key, Stage: "native_file_request", GuardScope: NativeGuardScope, PreflightDecision: PreflightAllow, UpstreamCalled: false}
	if s.Pipeline.AuditSink != nil && s.Pipeline.AuditSink.WriteRouteAudit(audit) != nil {
		fail(503, "audit_unavailable")
		return
	}
	store := s.Files
	if r.Method == "POST" {
		f, e := store.save(key, name, purpose, data, ttl)
		if e != nil {
			fail(nativeFileError(e))
			return
		}
		writeJSON(w, 200, f)
		return
	}
	if r.URL.Path == "/v1/files" {
		files := []nativeFile{}
		e := store.withLock(func() error {
			dir, e := store.directory(key)
			if e != nil {
				return e
			}
			entries, e := os.ReadDir(dir)
			if os.IsNotExist(e) {
				return nil
			}
			if e != nil {
				return e
			}
			for _, entry := range entries {
				if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".json") {
					continue
				}
				id := strings.TrimSuffix(entry.Name(), ".json")
				f, _, e := store.loadLocked(key, id)
				if e == nil {
					files = append(files, f)
				} else if e.Error() != "file_expired" && e.Error() != "file_not_found" {
					return e
				}
			}
			return nil
		})
		if e != nil {
			fail(503, "file_store_unavailable")
			return
		}
		sort.Slice(files, func(i, j int) bool { return files[i].Created > files[j].Created })
		writeJSON(w, 200, map[string]any{"object": "list", "data": files, "has_more": false})
		return
	}
	id := strings.TrimSuffix(strings.TrimPrefix(r.URL.Path, "/v1/files/"), "/content")
	f, content, e := store.load(key, id)
	if e != nil {
		fail(nativeFileError(e))
		return
	}
	if r.Method == "DELETE" {
		err := store.withLock(func() error {
			dir, err := store.directory(key)
			if err != nil {
				return err
			}
			e1 := os.Remove(filepath.Join(dir, id+".bin"))
			e2 := os.Remove(filepath.Join(dir, id+".json"))
			if e1 != nil || e2 != nil {
				return errors.New("file_delete_failed")
			}
			return nil
		})
		if err != nil {
			fail(503, "file_delete_failed")
			return
		}
		writeJSON(w, 200, map[string]any{"id": id, "object": "file", "deleted": true})
		return
	}
	if strings.HasSuffix(r.URL.Path, "/content") {
		w.Header().Set("Content-Type", f.MIME)
		w.Header().Set("Content-Disposition", mime.FormatMediaType("attachment", map[string]string{"filename": f.Filename}))
		_, _ = w.Write(content)
		return
	}
	writeJSON(w, 200, f)
}
func bytesEqualJSON(a, b []byte) bool {
	var x, y any
	if json.Unmarshal(a, &x) != nil || json.Unmarshal(b, &y) != nil {
		return false
	}
	ax, _ := json.Marshal(x)
	by, _ := json.Marshal(y)
	return string(ax) == string(by)
}

func (s *NativeFileStore) Expand(key string, raw []byte) ([]byte, error) {
	if s == nil || !strings.Contains(string(raw), "file-gw_") {
		return raw, nil
	}
	root, err := nativeDecode(raw)
	if err != nil {
		return nil, errors.New("invalid_json")
	}
	expandedBytes := len(raw)
	var walk func(any, bool) error
	walk = func(value any, imageRef bool) error {
		switch node := value.(type) {
		case []any:
			for _, v := range node {
				if err := walk(v, imageRef); err != nil {
					return err
				}
			}
		case map[string]any:
			if id, ok := node["file_id"].(string); ok && strings.HasPrefix(id, "file-gw_") {
				f, data, e := s.load(key, id)
				if e != nil {
					return e
				}
				expandedBytes += base64.StdEncoding.EncodedLen(len(data))
				if expandedBytes > MaxNativeRequestBytes {
					return errors.New("attachment_total_size_limit")
				}
				encoded := base64.StdEncoding.EncodeToString(data)
				delete(node, "file_id")
				switch {
				case node["type"] == "input_image" || imageRef:
					node["image_url"] = "data:" + f.MIME + ";base64," + encoded
				case node["type"] == "file":
					node["type"] = "base64"
					node["media_type"] = f.MIME
					node["filename"] = f.Filename
					node["data"] = encoded
				default:
					node["filename"] = f.Filename
					node["file_data"] = "data:" + f.MIME + ";base64," + encoded
				}
			}
			for _, k := range []string{"messages", "input", "content", "output", "images", "image", "mask", "source", "file"} {
				if v, ok := node[k]; ok {
					if err := walk(v, imageRef || k == "images" || k == "image" || k == "mask"); err != nil {
						return err
					}
				}
			}
		}
		return nil
	}
	if err := walk(root, false); err != nil {
		return nil, err
	}
	return json.Marshal(root)
}
