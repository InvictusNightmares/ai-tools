// Controlled synthetic HTTP/SSE/WS origin and load generator; no model calls.
package main

import (
	"bufio"
	"bytes"
	"crypto/sha1"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

func replyBody(hash, mode string) []byte {
	if mode == "sse" {
		var b bytes.Buffer
		for i := 0; i < 16; i++ {
			fmt.Fprintf(&b, "data: {\"type\":\"response.output_text.delta\",\"delta\":\"测试文本-%s-%d\"}\n\n", hash, i)
		}
		b.WriteString("data: [DONE]\n\n")
		return b.Bytes()
	}
	return []byte(fmt.Sprintf("{\"id\":\"synthetic-response\",\"object\":\"response\",\"input_sha256\":\"%s\",\"output\":[{\"type\":\"message\",\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":\"合成测试通过\"}]}]}", hash))
}

func readFrame(r io.Reader) ([]byte, byte, error) {
	h := make([]byte, 2)
	if _, e := io.ReadFull(r, h); e != nil {
		return nil, 0, e
	}
	n := uint64(h[1] & 127)
	if n == 126 {
		b := make([]byte, 2)
		if _, e := io.ReadFull(r, b); e != nil {
			return nil, 0, e
		}
		n = uint64(binary.BigEndian.Uint16(b))
	}
	if n == 127 {
		b := make([]byte, 8)
		if _, e := io.ReadFull(r, b); e != nil {
			return nil, 0, e
		}
		n = binary.BigEndian.Uint64(b)
	}
	if n > 16<<20 {
		return nil, 0, fmt.Errorf("oversized synthetic frame")
	}
	var mask [4]byte
	if h[1]&128 != 0 {
		if _, e := io.ReadFull(r, mask[:]); e != nil {
			return nil, 0, e
		}
	}
	p := make([]byte, n)
	if _, e := io.ReadFull(r, p); e != nil {
		return nil, 0, e
	}
	if h[1]&128 != 0 {
		for i := range p {
			p[i] ^= mask[i%4]
		}
	}
	return p, h[0] & 15, nil
}
func writeFrame(w io.Writer, p []byte, op byte, masked bool) error {
	var out bytes.Buffer
	out.WriteByte(128 | op)
	bit := byte(0)
	if masked {
		bit = 128
	}
	switch {
	case len(p) < 126:
		out.WriteByte(bit | byte(len(p)))
	case len(p) <= 65535:
		out.WriteByte(bit | 126)
		_ = binary.Write(&out, binary.BigEndian, uint16(len(p)))
	default:
		out.WriteByte(bit | 127)
		_ = binary.Write(&out, binary.BigEndian, uint64(len(p)))
	}
	if masked {
		mask := []byte{1, 19, 73, 211}
		out.Write(mask)
		for i, c := range p {
			out.WriteByte(c ^ mask[i%4])
		}
	} else {
		out.Write(p)
	}
	_, err := w.Write(out.Bytes())
	return err
}

func serve(addr string) {
	h := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.EqualFold(r.Header.Get("Upgrade"), "websocket") {
			c, rw, e := w.(http.Hijacker).Hijack()
			if e != nil {
				return
			}
			defer c.Close()
			_ = c.SetDeadline(time.Now().Add(60 * time.Second))
			digest := sha1.Sum([]byte(r.Header.Get("Sec-WebSocket-Key") + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"))
			fmt.Fprintf(rw, "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: %s\r\n\r\n", base64.StdEncoding.EncodeToString(digest[:]))
			_ = rw.Flush()
			for {
				p, op, e := readFrame(rw)
				if e != nil {
					return
				}
				if op == 8 {
					_ = writeFrame(c, p, 8, false)
					return
				}
				if op == 9 {
					op = 10
				}
				if e = writeFrame(c, p, op, false); e != nil {
					return
				}
			}
		}
		p, e := io.ReadAll(io.LimitReader(r.Body, 16<<20))
		if e != nil {
			http.Error(w, "read", 400)
			return
		}
		hash := sha256.Sum256(p)
		body := replyBody(hex.EncodeToString(hash[:]), r.URL.Query().Get("mode"))
		delay, _ := strconv.Atoi(r.URL.Query().Get("delay_ms"))
		time.Sleep(time.Duration(delay) * time.Millisecond)
		if r.URL.Query().Get("mode") == "sse" {
			w.Header().Set("Content-Type", "text/event-stream")
			for _, chunk := range bytes.SplitAfter(body, []byte("\n\n")) {
				if len(chunk) == 0 {
					continue
				}
				if _, e := w.Write(chunk); e != nil {
					return
				}
				w.(http.Flusher).Flush()
				time.Sleep(time.Millisecond)
			}
		} else {
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("Content-Length", strconv.Itoa(len(body)))
			_, _ = w.Write(body)
		}
	})
	if e := (&http.Server{Addr: addr, Handler: h, ReadHeaderTimeout: 5 * time.Second}).ListenAndServe(); e != nil {
		panic(e)
	}
}

type sample struct {
	First, Total float64
	Error        string
}

func oneWS(target string, payload []byte) sample {
	t := time.Now()
	u, _ := url.Parse(target)
	c, e := net.DialTimeout("tcp", u.Host, 5*time.Second)
	if e != nil {
		return sample{Error: e.Error()}
	}
	defer c.Close()
	_ = c.SetDeadline(time.Now().Add(60 * time.Second))
	r := bufio.NewReader(c)
	fmt.Fprintf(c, "GET /v1/responses HTTP/1.1\r\nHost: %s\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: c3ludGhldGljLWJlbmNoIQ==\r\n\r\n", u.Host)
	resp, e := http.ReadResponse(r, &http.Request{Method: "GET"})
	if e != nil {
		return sample{Error: e.Error()}
	}
	if resp.StatusCode != 101 {
		return sample{Error: fmt.Sprint("upgrade ", resp.StatusCode)}
	}
	first := 0.0
	for i := 0; i < 8; i++ {
		if e = writeFrame(c, payload, 1, true); e != nil {
			return sample{Error: e.Error()}
		}
		received, op, e := readFrame(r)
		if e != nil {
			return sample{Error: e.Error()}
		}
		if op != 1 || !bytes.Equal(payload, received) {
			return sample{Error: "WS payload mismatch"}
		}
		if i == 0 {
			first = float64(time.Since(t).Microseconds()) / 1000
		}
	}
	_ = writeFrame(c, []byte{3, 232}, 8, true)
	return sample{First: first, Total: float64(time.Since(t).Microseconds()) / 1000}
}
func run(target, mode string, n, concurrency, size, delay, rate int) {
	payload, _ := json.Marshal(map[string]any{"model": "synthetic", "input": []any{map[string]any{"role": "user", "content": "阅读代码后总结变动 " + strings.Repeat("x", size)}}})
	hash := sha256.Sum256(payload)
	want := replyBody(hex.EncodeToString(hash[:]), mode)
	client := &http.Client{Timeout: 60 * time.Second, Transport: &http.Transport{MaxIdleConns: 128, MaxIdleConnsPerHost: 128, DisableCompression: true}}
	once := func() sample {
		if mode == "ws" {
			return oneWS(target, payload)
		}
		t := time.Now()
		req, _ := http.NewRequest("POST", target+"/v1/responses?mode="+mode+"&delay_ms="+strconv.Itoa(delay), bytes.NewReader(payload))
		req.Header.Set("Content-Type", "application/json")
		resp, e := client.Do(req)
		if e != nil {
			return sample{Error: e.Error()}
		}
		defer resp.Body.Close()
		b := make([]byte, 1)
		_, e = io.ReadFull(resp.Body, b)
		first := float64(time.Since(t).Microseconds()) / 1000
		if e != nil {
			return sample{Error: e.Error()}
		}
		rest, e := io.ReadAll(resp.Body)
		total := float64(time.Since(t).Microseconds()) / 1000
		if e != nil {
			return sample{Error: e.Error()}
		}
		if resp.StatusCode != 200 || !bytes.Equal(append(b, rest...), want) {
			return sample{Error: "HTTP content/status mismatch"}
		}
		return sample{First: first, Total: total}
	}
	for i := 0; i < 32; i++ {
		if s := once(); s.Error != "" {
			_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"warmup_error": s.Error, "target": target, "mode": mode})
			return
		}
	}
	results := make([]sample, n)
	jobs := make(chan int, concurrency)
	var wg sync.WaitGroup
	t := time.Now()
	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := range jobs {
				queued := 0.0
				if rate > 0 {
					scheduled := t.Add(time.Duration(j) * time.Second / time.Duration(rate))
					queued = float64(time.Since(scheduled).Microseconds()) / 1000
					if queued < 0 {
						queued = 0
					}
				}
				s := once()
				s.First += queued
				s.Total += queued
				results[j] = s
			}
		}()
	}
	for i := 0; i < n; i++ {
		if rate > 0 {
			time.Sleep(time.Until(t.Add(time.Duration(i) * time.Second / time.Duration(rate))))
		}
		jobs <- i
	}
	close(jobs)
	wg.Wait()
	elapsed := time.Since(t).Seconds()
	first, total := []float64{}, []float64{}
	errors := map[string]int{}
	for _, s := range results {
		if s.Error != "" {
			errors[s.Error]++
		} else {
			first = append(first, s.First)
			total = append(total, s.Total)
		}
	}
	sort.Float64s(first)
	sort.Float64s(total)
	quantile := func(a []float64, q float64) float64 {
		if len(a) == 0 {
			return 0
		}
		return a[int(float64(len(a)-1)*q)]
	}
	_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"target": target, "mode": mode, "count": n, "ok": len(total), "errors": errors, "concurrency": concurrency, "offered_rps": rate, "payload_bytes": len(payload), "delay_ms": delay, "elapsed_s": elapsed, "rps": float64(n) / elapsed, "first_p50_ms": quantile(first, .5), "first_p95_ms": quantile(first, .95), "total_p50_ms": quantile(total, .5), "total_p95_ms": quantile(total, .95), "first_ms": first, "total_ms": total})
}
func main() {
	role := flag.String("role", "run", "serve or run")
	addr := flag.String("addr", "127.0.0.1:18080", "loopback endpoint")
	mode := flag.String("mode", "json", "json/sse/ws")
	n := flag.Int("n", 500, "measured requests")
	c := flag.Int("c", 16, "concurrency")
	size := flag.Int("size", 1024, "synthetic padding bytes")
	delay := flag.Int("delay", 0, "origin delay milliseconds")
	rate := flag.Int("rate", 0, "fixed arrival RPS; 0 is closed loop")
	flag.Parse()
	if !strings.HasPrefix(*addr, "127.0.0.1:") {
		panic("experiment is loopback-only")
	}
	if *role == "serve" {
		serve(*addr)
	} else {
		run("http://"+*addr, *mode, *n, *c, *size, *delay, *rate)
	}
}
