package main

import (
	"context"
	"crypto/rand"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	"local/work-observation/source/capture"
	"local/work-observation/source/proxy"
)

var version = "observation-dev.9"

type config struct {
	Listen         string `json:"listen"`
	Upstream       string `json:"upstream"`
	Region         string `json:"region"`
	Ingress        string `json:"ingress"`
	StoreDir       string `json:"store_dir"`
	RuntimeDir     string `json:"runtime_dir"`
	SaltFile       string `json:"identity_salt_file"`
	CaptureEnabled bool   `json:"capture_enabled"`
	Queue          int    `json:"queue_items"`
	MemoryBytes    int64  `json:"memory_bytes"`
	BodyBytes      int64  `json:"body_bytes"`
	StorageBytes   int64  `json:"storage_bytes"`
}

func readConfig(path string) (config, error) {
	var c config
	f, err := os.Open(path)
	if err != nil {
		return c, err
	}
	defer f.Close()
	d := json.NewDecoder(io.LimitReader(f, 64<<10))
	d.DisallowUnknownFields()
	if err = d.Decode(&c); err != nil {
		return c, errors.New("invalid_config")
	}
	if c.StorageBytes == 0 {
		c.StorageBytes = 200 << 30
	}
	if c.StorageBytes < 1 || c.StorageBytes > 200<<30 {
		return c, errors.New("invalid_storage_limit")
	}
	host, _, err := net.SplitHostPort(c.Listen)
	if err != nil || net.ParseIP(host) == nil || !net.ParseIP(host).IsLoopback() {
		return c, errors.New("development_listener_must_be_loopback")
	}
	if c.Queue < 0 || c.Queue > 4096 || c.MemoryBytes < 0 || c.MemoryBytes > 1<<30 || c.BodyBytes < 0 || c.BodyBytes > 32<<20 {
		return c, errors.New("invalid_capture_buffer_limits")
	}
	if !filepath.IsAbs(c.StoreDir) || !filepath.IsAbs(c.SaltFile) {
		return c, errors.New("absolute_private_paths_required")
	}
	if c.RuntimeDir == "" {
		c.RuntimeDir = c.StoreDir
	}
	if !filepath.IsAbs(c.RuntimeDir) {
		return c, errors.New("absolute_runtime_path_required")
	}
	return c, nil
}
func serve(path string) error {
	c, err := readConfig(path)
	if err != nil {
		return err
	}
	store, salt, recovered, unavailable := openCapture(c)
	var sink capture.Sink = unavailableSink{}
	if store != nil {
		defer store.Close()
		sink = store
	}
	control := filepath.Join(c.RuntimeDir, "control.json")
	enabled := captureSwitch(control, c.CaptureEnabled) && unavailable == ""
	engine := capture.NewEngine(sink, capture.Limits{Queue: c.Queue, MemoryBytes: c.MemoryBytes, BodyBytes: c.BodyBytes}, enabled)
	if unavailable != "" {
		engine.SetUnavailable(unavailable)
		fmt.Fprintln(os.Stderr, "collector_capture_unavailable", unavailable)
	}
	defer engine.Close()
	handler, err := proxy.New(proxy.Config{Upstream: c.Upstream, Region: c.Region, Ingress: c.Ingress, Version: version, IdentitySalt: salt}, engine)
	if err != nil {
		return err
	}
	server := &http.Server{Addr: c.Listen, Handler: handler, ReadHeaderTimeout: 10 * time.Second, IdleTimeout: 90 * time.Second, MaxHeaderBytes: 1 << 20}
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, syscall.SIGTERM, os.Interrupt)
	defer signal.Stop(sig)
	listener, err := net.Listen("tcp", c.Listen)
	if err != nil {
		return err
	}
	connections := &trackedListener{Listener: listener, connections: make(map[*trackedConn]struct{})}
	result := make(chan error, 1)
	go func() { result <- server.Serve(connections) }()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	prune := time.NewTicker(5 * time.Minute)
	defer prune.Stop()
	publish := func() {
		status := engine.Status()
		status["storage_limit_bytes"] = c.StorageBytes
		status["recovered_interrupted_requests"] = recovered
		status["version"] = version
		if err := capture.WritePrivateJSON(filepath.Join(c.RuntimeDir, "status.json"), status); err != nil {
			fmt.Fprintln(os.Stderr, "collector_status_write_failed")
		}
	}
	publish()
	for {
		select {
		case err := <-result:
			if errors.Is(err, http.ErrServerClosed) {
				return nil
			}
			return err
		case <-ticker.C:
			engine.SetEnabled(captureSwitch(control, engine.Enabled()))
			publish()
		case <-prune.C:
			if store != nil && unavailable == "" {
				engine.Maintain(func() { n, err := store.Prune(); engine.RecordPrune(n, err) })
			}
		case <-sig:
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			err := server.Shutdown(ctx)
			for connections.count() > 0 && ctx.Err() == nil {
				time.Sleep(10 * time.Millisecond)
			}
			if connections.count() > 0 {
				engine.MarkForcedClose()
				connections.closeConnections()
				_ = server.Close()
			}
			cancel()
			deadline := time.Now().Add(2 * time.Second)
			for engine.Active() > 0 && time.Now().Before(deadline) {
				time.Sleep(time.Millisecond)
			}
			engine.Close()
			publish()
			return err
		}
	}
}
func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: observe serve|export|losses|status|enable|disable|init|prune|version")
		os.Exit(2)
	}
	command := os.Args[1]
	if command == "version" {
		fmt.Println(version)
		return
	}
	f := flag.NewFlagSet(command, flag.ExitOnError)
	conf := f.String("config", "", "configuration file")
	dir := f.String("dir", "", "restricted store directory")
	since := f.String("since", "", "RFC3339 lower bound")
	_ = f.Parse(os.Args[2:])
	var err error
	if command != "serve" && !filepath.IsAbs(*dir) {
		fmt.Fprintln(os.Stderr, "absolute store directory required")
		os.Exit(2)
	}
	switch command {
	case "serve":
		err = serve(*conf)
	case "init":
		if !filepath.IsAbs(*dir) {
			err = errors.New("absolute_store_path_required")
			break
		}
		if err = os.MkdirAll(*dir, 0700); err != nil {
			break
		}
		var salt [32]byte
		if _, err = rand.Read(salt[:]); err != nil {
			break
		}
		var file *os.File
		file, err = os.OpenFile(filepath.Join(*dir, "identity.salt"), os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err == nil {
			_, err = file.Write(salt[:])
			closeErr := file.Close()
			if err == nil {
				err = closeErr
			}
		}
	case "enable", "disable":
		err = capture.WritePrivateJSON(filepath.Join(*dir, "control.json"), map[string]bool{"enabled": command == "enable"})
	case "status":
		var data []byte
		data, err = os.ReadFile(filepath.Join(*dir, "status.json"))
		if err == nil {
			_, err = os.Stdout.Write(data)
		}
	case "export":
		var at time.Time
		if *since != "" {
			at, err = time.Parse(time.RFC3339, *since)
		}
		if err == nil {
			_, err = capture.Export(*dir, os.Stdout, at)
		}
	case "losses":
		var at time.Time
		if *since != "" {
			at, err = time.Parse(time.RFC3339, *since)
		}
		if err == nil {
			_, err = capture.ExportLosses(*dir, os.Stdout, at)
		}
	case "prune":
		var s *capture.DiskStore
		s, err = capture.NewDiskStore(*dir, 200<<30)
		if err == nil {
			var n int
			n, err = s.Prune()
			s.Close()
			if err == nil {
				_ = json.NewEncoder(os.Stdout).Encode(map[string]int{"pruned": n})
			}
		}
	default:
		err = errors.New("unknown_command")
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "observation command failed:", err)
		os.Exit(1)
	}
}
