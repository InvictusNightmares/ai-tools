// Synthetic-only comparison proxy. Never deploy this benchmark as a collector.
package main

import (
	"crypto/sha256"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

var queued, captured, chunks, dropped, requests atomic.Int64
var queue chan []byte
var copies = sync.Pool{New: func() any { return make([]byte, 32<<10) }}
var checksum atomic.Uint64

type bufferPool struct{ pool sync.Pool }

func (p *bufferPool) Get() []byte {
	if v := p.pool.Get(); v != nil {
		return v.([]byte)
	}
	return make([]byte, 32<<10)
}
func (p *bufferPool) Put(b []byte) { p.pool.Put(b) }

func observe(p []byte) {
	if queue == nil || len(p) == 0 {
		return
	}
	n := int64(len(p))
	for {
		old := queued.Load()
		if old+n > 64<<20 {
			dropped.Add(1)
			return
		}
		if queued.CompareAndSwap(old, old+n) {
			break
		}
	}
	copy := copies.Get().([]byte)
	if cap(copy) < len(p) {
		copy = make([]byte, len(p))
	} else {
		copy = copy[:len(p)]
	}
	builtInCopy(copy, p)
	select {
	case queue <- copy:
	default:
		queued.Add(-n)
		dropped.Add(1)
		if cap(copy) == 32<<10 {
			copies.Put(copy)
		}
	}
}
func builtInCopy(dst, src []byte) { copy(dst, src) }

type tapReader struct{ io.ReadCloser }

func (r tapReader) Read(p []byte) (int, error) {
	n, e := r.ReadCloser.Read(p)
	observe(p[:n])
	return n, e
}

type tapDuplex struct{ io.ReadWriteCloser }

func (r tapDuplex) Read(p []byte) (int, error) {
	n, e := r.ReadWriteCloser.Read(p)
	observe(p[:n])
	return n, e
}
func (r tapDuplex) Write(p []byte) (int, error) {
	n, e := r.ReadWriteCloser.Write(p)
	observe(p[:n])
	return n, e
}

func main() {
	addr := os.Getenv("BENCH_LISTEN")
	if addr == "" {
		addr = "127.0.0.1:18081"
	}
	upstream := os.Getenv("BENCH_UPSTREAM")
	if upstream == "" {
		upstream = "127.0.0.1:18080"
	}
	if !strings.HasPrefix(addr, "127.0.0.1:") || !strings.HasPrefix(upstream, "127.0.0.1:") {
		panic("loopback only")
	}
	if os.Getenv("BENCH_CAPTURE") == "1" {
		queue = make(chan []byte, 4096)
		go func() {
			for p := range queue {
				hash := sha256.Sum256(p)
				checksum.Add(uint64(hash[0]))
				captured.Add(int64(len(p)))
				chunks.Add(1)
				queued.Add(-int64(len(p)))
				if cap(p) == 32<<10 {
					copies.Put(p)
				}
			}
		}()
	}
	go func() {
		for range time.NewTicker(2 * time.Second).C {
			_ = json.NewEncoder(os.Stderr).Encode(map[string]int64{
				"bytes": captured.Load(), "chunks": chunks.Load(), "drops": dropped.Load(), "queued": queued.Load(), "requests": requests.Load()})
		}
	}()
	target, _ := url.Parse("http://" + upstream)
	proxy := httputil.NewSingleHostReverseProxy(target)
	proxy.BufferPool = &bufferPool{}
	proxy.FlushInterval = -1
	proxy.Transport = &http.Transport{MaxIdleConns: 128, MaxIdleConnsPerHost: 128, DisableCompression: true}
	proxy.ModifyResponse = func(r *http.Response) error {
		if queue == nil {
			return nil
		}
		if duplex, ok := r.Body.(io.ReadWriteCloser); r.StatusCode == 101 && ok {
			r.Body = tapDuplex{duplex}
		} else {
			r.Body = tapReader{r.Body}
		}
		return nil
	}
	server := &http.Server{Addr: addr, ReadHeaderTimeout: 5 * time.Second, Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if queue != nil && r.Body != nil {
			r.Body = tapReader{r.Body}
		}
		proxy.ServeHTTP(w, r)
		requests.Add(1)
	})}
	if err := server.ListenAndServe(); err != nil {
		panic(err)
	}
}
