package main

import (
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"local/work-observation/source/capture"
	"local/work-observation/source/proxy"
)

func TestPersistedCaptureSwitchOverridesConfigBeforeListening(t *testing.T) {
	path := filepath.Join(t.TempDir(), "control.json")
	if captureSwitch(path, false) {
		t.Fatal("capture must default off")
	}
	if err := os.WriteFile(path, []byte(`{"enabled":true}`), 0600); err != nil {
		t.Fatal(err)
	}
	if !captureSwitch(path, false) {
		t.Fatal("restart would miss initial requests after persisted enable")
	}
	if err := os.WriteFile(path, []byte(`{"enabled":false}`), 0600); err != nil {
		t.Fatal(err)
	}
	if captureSwitch(path, true) {
		t.Fatal("restart would collect before persisted disable")
	}
	if err := os.WriteFile(path, []byte(`broken`), 0600); err != nil {
		t.Fatal(err)
	}
	if captureSwitch(path, true) {
		t.Fatal("malformed control must disable capture")
	}
}

func TestCaptureStartupFailurePreservesForwarding(t *testing.T) {
	for _, mode := range []string{"missing_salt", "invalid_store", "corrupt_recovery"} {
		t.Run(mode, func(t *testing.T) {
			root := t.TempDir()
			c := config{StoreDir: filepath.Join(root, "store"), SaltFile: filepath.Join(root, "salt"), StorageBytes: 1 << 20}
			if mode != "missing_salt" {
				if err := os.WriteFile(c.SaltFile, make([]byte, 32), 0600); err != nil {
					t.Fatal(err)
				}
			}
			if mode == "invalid_store" {
				if err := os.WriteFile(c.StoreDir, []byte("unavailable mount fixture"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			if mode == "corrupt_recovery" {
				if err := os.MkdirAll(filepath.Join(c.StoreDir, "active"), 0700); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(c.StoreDir, "active", "broken.json"), []byte("broken fixture"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			store, salt, _, failure := openCapture(c)
			if store != nil || failure == "" {
				t.Fatal("expected isolated startup failure")
			}
			engine := capture.NewEngine(unavailableSink{}, capture.Limits{}, false)
			defer engine.Close()
			engine.SetUnavailable(failure)
			engine.SetEnabled(true)
			if engine.Enabled() {
				t.Fatal("failed startup accepted enable")
			}
			origin := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(201)
				_, _ = w.Write([]byte("unchanged origin reply"))
			}))
			defer origin.Close()
			handler, err := proxy.New(proxy.Config{Upstream: origin.URL, Region: "test", Ingress: "test", IdentitySalt: salt}, engine)
			if err != nil {
				t.Fatal(err)
			}
			out := httptest.NewRecorder()
			handler.ServeHTTP(out, httptest.NewRequest("GET", "http://fixture/v1/models", nil))
			body, _ := io.ReadAll(out.Result().Body)
			if out.Code != 201 || string(body) != "unchanged origin reply" {
				t.Fatal("capture fault broke business forwarding")
			}
			if engine.Status()["unavailable_bypassed_requests"] != uint64(1) {
				t.Fatal("uncaptured request not counted")
			}
		})
	}
}
