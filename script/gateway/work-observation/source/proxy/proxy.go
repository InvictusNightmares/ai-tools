package proxy

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"strings"
	"sync"
	"time"

	"local/work-observation/source/capture"
)

type Config struct {
	Upstream, Region, Ingress, Version string
	IdentitySalt                       []byte
}
type pool struct{ p sync.Pool }

func (p *pool) Get() []byte {
	if v := p.p.Get(); v != nil {
		return v.([]byte)
	}
	return make([]byte, 32<<10)
}
func (p *pool) Put(b []byte) { p.p.Put(b) }

type tap struct {
	io.ReadCloser
	x        *capture.Exchange
	response bool
}

func (t tap) Read(p []byte) (int, error) {
	n, err := t.ReadCloser.Read(p)
	t.x.Observe(t.response, p[:n])
	return n, err
}

type exchangeKey struct{}

func identity(salt []byte, value string) string {
	if value == "" {
		return ""
	}
	h := hmac.New(sha256.New, salt)
	h.Write([]byte(value))
	return hex.EncodeToString(h.Sum(nil))
}
func client(ua string) string {
	u := strings.ToLower(ua)
	for _, c := range []string{"codex", "opencode", "hermes", "claude"} {
		if strings.Contains(u, c) {
			return c
		}
	}
	return "unknown"
}
func protocol(path string) string {
	switch {
	case strings.Contains(path, "/responses"):
		return "responses"
	case strings.Contains(path, "/chat/completions"):
		return "chat_completions"
	case strings.Contains(path, "/messages"):
		return "messages"
	default:
		return "other"
	}
}

func New(c Config, engine *capture.Engine) (http.Handler, error) {
	target, err := url.Parse(c.Upstream)
	if err != nil || target.Host == "" || (target.Scheme != "http" && target.Scheme != "https") || target.User != nil {
		return nil, errors.New("invalid_upstream")
	}
	if c.Region == "" || c.Ingress == "" || len(c.IdentitySalt) < 32 {
		return nil, errors.New("invalid_collector_identity")
	}
	p := &httputil.ReverseProxy{BufferPool: &pool{}, FlushInterval: -1, ErrorLog: log.New(io.Discard, "", 0)}
	// Preserve inbound forwarded headers exactly; original Nginx owns ingress/IP policy.
	p.Rewrite = func(r *httputil.ProxyRequest) {
		r.SetURL(target)
		r.Out.Host = r.In.Host
		if _, ok := r.Out.Header["User-Agent"]; !ok {
			r.Out.Header["User-Agent"] = []string{""}
		}
		for _, key := range []string{"Forwarded", "X-Forwarded-For", "X-Forwarded-Host", "X-Forwarded-Proto"} {
			if v, ok := r.In.Header[key]; ok {
				r.Out.Header[key] = append([]string(nil), v...)
			}
		}
	}
	p.Transport = &http.Transport{Proxy: nil, DisableCompression: true, MaxIdleConns: 256, MaxIdleConnsPerHost: 128,
		DialContext:     (&net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
		IdleConnTimeout: 90 * time.Second, TLSHandshakeTimeout: 10 * time.Second, ResponseHeaderTimeout: time.Hour}
	p.ModifyResponse = func(r *http.Response) error {
		x, _ := r.Request.Context().Value(exchangeKey{}).(*capture.Exchange)
		x.Update(func(e *capture.Event) {
			e.Status = r.StatusCode
			e.ResponseContentType = r.Header.Get("Content-Type")
			e.ResponseContentEncoding = r.Header.Get("Content-Encoding")
			e.RequestID = r.Header.Get("X-Request-Id")
		})
		if x != nil {
			if r.StatusCode == http.StatusSwitchingProtocols {
				// The transport must retain its duplex interface. Frame capture follows in
				// a dedicated reader; an HTTP body parser must never inspect WS wire bytes.
				if d, ok := r.Body.(io.ReadWriteCloser); ok {
					r.Body = newDuplex(d, x, r.Header.Get("Sec-WebSocket-Extensions"))
				}
			} else {
				r.Body = tap{r.Body, x, true}
			}
		}
		return nil
	}
	p.ErrorHandler = func(w http.ResponseWriter, r *http.Request, err error) {
		x, _ := r.Context().Value(exchangeKey{}).(*capture.Exchange)
		if r.Context().Err() != nil || errors.Is(err, context.Canceled) {
			// No upstream status was received. A caller abort is neither a 502
			// from the model nor an observation gap; Finish records cancellation.
			return
		}
		x.Update(func(e *capture.Event) { e.Status = 502; e.Missing = append(e.Missing, "upstream_transport_failure") })
		http.Error(w, "upstream unavailable", http.StatusBadGateway)
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !engine.Enabled() {
			engine.RecordBypass()
			p.ServeHTTP(w, r)
			return
		}
		credential := credentialValue(r.Header)
		session := r.Header.Get("Session-Id")
		if session == "" {
			session = r.Header.Get("X-Session-Id")
		}
		if session == "" {
			session = r.Header.Get("X-Claude-Code-Session-Id")
		}
		if session == "" {
			session = r.Header.Get("X-Gateway-Session-Id")
		}
		ev := capture.Event{Region: c.Region, Ingress: c.Ingress, Version: c.Version, Method: r.Method, Path: r.URL.Path, Protocol: protocol(r.URL.Path), Client: client(r.UserAgent()), UserAgent: r.UserAgent(), KeyHash: identity(c.IdentitySalt, c.Region+"\x00"+credential), Association: "unknown", ContentType: r.Header.Get("Content-Type"), ContentEncoding: r.Header.Get("Content-Encoding")}
		if credential == "" {
			ev.KeyHash = ""
		}
		if session != "" {
			ev.SessionHash = identity(c.IdentitySalt, c.Region+"\x00"+ev.KeyHash+"\x00"+session)
			ev.Association = "client_claimed"
		}
		if agent := r.Header.Get("X-Claude-Code-Agent-Id"); agent != "" {
			ev.AgentHash = identity(c.IdentitySalt, c.Region+"\x00"+ev.KeyHash+"\x00"+ev.SessionHash+"\x00"+agent)
		}
		x := engine.Begin(ev)
		if x == nil {
			p.ServeHTTP(w, r)
			return
		}
		r = r.WithContext(context.WithValue(r.Context(), exchangeKey{}, x))
		if r.Body != nil {
			r.Body = tap{r.Body, x, false}
		}
		outcome := "completed"
		defer func() {
			if rec := recover(); rec != nil {
				if r.Context().Err() != nil {
					x.Finish("canceled")
				} else {
					x.Finish("stream_interrupted")
				}
				panic(rec)
			}
			if r.Context().Err() != nil {
				outcome = "canceled"
			}
			x.Update(func(e *capture.Event) {
				if e.Status >= 400 && outcome == "completed" {
					outcome = "http_error"
				}
				if e.Status == 101 && outcome == "completed" {
					outcome = "websocket_closed"
				}
			})
			x.Finish(outcome)
		}()
		p.ServeHTTP(w, r)
	}), nil
}

func credentialValue(headers http.Header) string {
	authorization := headers.Get("Authorization")
	if authorization != "" {
		parts := strings.Fields(authorization)
		if len(parts) == 2 && strings.EqualFold(parts[0], "Bearer") {
			return parts[1]
		}
		return authorization
	}
	return strings.TrimSpace(headers.Get("X-Api-Key"))
}
