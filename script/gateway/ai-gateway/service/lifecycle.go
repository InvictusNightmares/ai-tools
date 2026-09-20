package service

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

var ReleaseID = "development"
var SourceSHA256 = "unfrozen"

const StateSchema = "session-json-v1"
const ConfigSchema = "gateway-config-v1"

func Version() map[string]string {
	return map[string]string{"release_id": ReleaseID, "source_sha256": SourceSHA256, "state_schema": StateSchema, "config_schema": ConfigSchema}
}
func PrintVersion() bool {
	if len(os.Args) == 2 && os.Args[1] == "--version" {
		_ = json.NewEncoder(os.Stdout).Encode(Version())
		return true
	}
	return false
}

// Drain and active accounting share one lock, so an acknowledged empty drain
// cannot race a newly admitted request. Existing streams retain their context.
type Lifecycle struct {
	Next        http.Handler
	AdminSecret string
	mu          sync.Mutex
	draining    bool
	active      int
	drainSignal chan struct{}
}

type drainContextKey struct{}

func DrainSignal(ctx context.Context) <-chan struct{} {
	signal, _ := ctx.Value(drainContextKey{}).(<-chan struct{})
	return signal
}
func (l *Lifecycle) Drain(on bool) {
	l.mu.Lock()
	defer l.mu.Unlock()
	if on && !l.draining {
		if l.drainSignal == nil {
			l.drainSignal = make(chan struct{})
		}
		close(l.drainSignal)
	}
	if !on && l.draining {
		l.drainSignal = make(chan struct{})
	}
	l.draining = on
}
func (l *Lifecycle) Status() (bool, int) {
	l.mu.Lock()
	defer l.mu.Unlock()
	return l.draining, l.active
}
func (l *Lifecycle) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/_gateway/status" || r.URL.Path == "/_gateway/drain" {
		provided := r.Header.Get("X-Gateway-Admin")
		if l.AdminSecret == "" || subtle.ConstantTimeCompare([]byte(provided), []byte(l.AdminSecret)) != 1 {
			http.NotFound(w, r)
			return
		}
		if r.URL.Path == "/_gateway/drain" {
			if r.Method != http.MethodPost {
				w.WriteHeader(405)
				return
			}
			var request struct {
				Draining *bool `json:"draining"`
			}
			if json.NewDecoder(http.MaxBytesReader(w, r.Body, 1024)).Decode(&request) != nil || request.Draining == nil {
				w.WriteHeader(400)
				return
			}
			l.Drain(*request.Draining)
		} else if r.Method != http.MethodGet {
			w.WriteHeader(405)
			return
		}
		draining, active := l.Status()
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"version": Version(), "draining": draining, "active_requests": active})
		return
	}
	l.mu.Lock()
	if l.draining {
		l.mu.Unlock()
		w.Header().Set("Retry-After", "1")
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(503)
		_, _ = w.Write([]byte(`{"error":"gateway_draining"}`))
		return
	}
	l.active++
	if l.drainSignal == nil {
		l.drainSignal = make(chan struct{})
	}
	signal := l.drainSignal
	l.mu.Unlock()
	defer func() { l.mu.Lock(); l.active--; l.mu.Unlock() }()
	l.Next.ServeHTTP(w, r.WithContext(context.WithValue(r.Context(), drainContextKey{}, (<-chan struct{})(signal))))
}

func Run(server *http.Server, lifecycle *Lifecycle, timeout time.Duration) error {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	return RunContext(ctx, server, lifecycle, timeout)
}

func RunContext(ctx context.Context, server *http.Server, lifecycle *Lifecycle, timeout time.Duration) error {
	server.Handler = lifecycle
	finished := make(chan error, 1)
	go func() { finished <- server.ListenAndServe() }()
	select {
	case err := <-finished:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		lifecycle.Drain(true)
		shutdown, cancel := context.WithTimeout(context.Background(), timeout)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			return err
		}
		// net/http Shutdown does not wait for hijacked WebSockets. Their handler
		// observes DrainSignal, completes admitted turns, then closes the socket.
		ticker := time.NewTicker(10 * time.Millisecond)
		defer ticker.Stop()
		for {
			_, active := lifecycle.Status()
			if active == 0 {
				break
			}
			select {
			case <-shutdown.Done():
				return shutdown.Err()
			case <-ticker.C:
			}
		}
		err := <-finished
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}
