package autogateway

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"time"
)

// StreamUpstreamClient is the separate lifecycle seam for SSE. It exposes a
// response body instead of buffering it so cancellation and backpressure are
// preserved end to end.
type StreamUpstreamClient interface {
	OpenStream(context.Context, UpstreamRequest) (*http.Response, error)
}

func (client *HTTPUpstreamClient) OpenStream(ctx context.Context, request UpstreamRequest) (*http.Response, error) {
	if !request.Parameters.Stream && !request.Request.Stream {
		return nil, errors.New("stream_flag_required")
	}
	if needsNativeMessagesBridge(request) {
		return client.openNativeMessagesStream(ctx, request)
	}
	endpoint, ok := client.endpoint(request.Provider, request.Protocol)
	if !ok || strings.TrimSpace(endpoint.URL) == "" {
		return nil, errors.New("provider_endpoint_unconfigured")
	}
	httpClient := client.Client
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 10 * time.Minute, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	}
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.URL, bytes.NewReader(request.Payload))
	if err != nil {
		return nil, fmt.Errorf("build_upstream_request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	if request.RequestID != "" {
		httpRequest.Header.Set("X-Request-ID", request.RequestID)
	}
	httpRequest.Header.Set("Accept", "text/event-stream")
	for key, values := range client.DefaultHeaders {
		for _, value := range values {
			httpRequest.Header.Add(key, value)
		}
	}
	if client.ForwardClientAuth && endpoint.Token == "" {
		copyAuthHeaders(httpRequest.Header, request.Headers)
	}
	copyClientUserAgent(httpRequest.Header, request.Headers)
	if endpoint.Token != "" {
		header := endpoint.Header
		if header == "" {
			header = "Authorization"
		}
		if strings.EqualFold(header, "Authorization") {
			httpRequest.Header.Set(header, "Bearer "+endpoint.Token)
		} else {
			httpRequest.Header.Set(header, endpoint.Token)
		}
	}
	response, err := httpClient.Do(httpRequest)
	if err != nil {
		return nil, fmt.Errorf("upstream_transport: %w", err)
	}
	return response, nil
}

// RelaySSE copies a provider SSE body to the client until EOF or cancellation.
// It intentionally performs no model switching and never writes a response
// cache entry; turn completion is the caller's boundary for the next route.
func RelaySSE(ctx context.Context, writer http.ResponseWriter, response *http.Response) error {
	if response == nil || response.Body == nil {
		return errors.New("stream_response_missing")
	}
	defer response.Body.Close()
	writer.Header().Set("Content-Type", "text/event-stream")
	writer.Header().Set("Cache-Control", "no-cache")
	writer.WriteHeader(response.StatusCode)
	flusher, _ := writer.(http.Flusher)
	buffer := make([]byte, 32*1024)
	terminalDelivered := false
	observed, _ := response.Body.(interface{ streamComplete() bool })
	for {
		select {
		case <-ctx.Done():
			return newSSETransportError("canceled", ctx.Err(), terminalDelivered)
		default:
		}
		count, err := response.Body.Read(buffer)
		if count > 0 {
			written, writeErr := writer.Write(buffer[:count])
			if writeErr != nil {
				return newSSETransportError("client_write", writeErr, terminalDelivered)
			}
			if written != count {
				return newSSETransportError("client_write", io.ErrShortWrite, terminalDelivered)
			}
			if flusher != nil {
				flusher.Flush()
			}
			terminalDelivered = observed != nil && observed.streamComplete()
		}
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return newSSETransportError("upstream_read", err, terminalDelivered)
		}
	}
}

func (s *observedSSEBody) streamComplete() bool {
	return s.Complete && !s.Invalid && s.ID != "" && s.Model != ""
}

// A completed protocol event and a successfully written terminal batch are
// separate facts. Never turn a failed terminal write into successful delivery.
type sseTransportError struct {
	phase, kind       string
	terminalDelivered bool
	err               error
}

func (e *sseTransportError) Error() string { return e.phase + ":" + e.kind }
func (e *sseTransportError) Unwrap() error { return e.err }
func isClientDeliveryFailure(err error) bool {
	var transport *sseTransportError
	return errors.As(err, &transport) && transport.phase == "client_write"
}
func newSSETransportError(phase string, err error, delivered bool) error {
	kind := "transport_error"
	var network net.Error
	switch {
	case errors.Is(err, context.Canceled):
		kind = "context_canceled"
	case errors.Is(err, context.DeadlineExceeded):
		kind = "deadline_exceeded"
	case errors.Is(err, io.ErrUnexpectedEOF):
		kind = "unexpected_eof"
	case errors.Is(err, io.ErrShortWrite):
		kind = "short_write"
	case errors.As(err, &network) && network.Timeout():
		kind = "network_timeout"
	}
	return &sseTransportError{phase: phase, kind: kind, terminalDelivered: delivered, err: err}
}

func streamTermination(err error, complete bool) (string, error) {
	if err == nil {
		return "eof", nil
	}
	var transport *sseTransportError
	if !errors.As(err, &transport) {
		return "stream_error", err
	}
	reason := transport.phase + ":" + transport.kind
	if complete && transport.terminalDelivered {
		// A client may cancel immediately after response.completed. Record this
		// known normal close explicitly; unknown tail failures remain failures.
		if errors.Is(transport.err, context.Canceled) {
			return "client_closed_after_complete", nil
		}
		return "after_complete:" + reason, err
	}
	return reason, err
}
