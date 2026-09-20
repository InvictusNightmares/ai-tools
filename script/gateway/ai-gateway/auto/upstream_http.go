package autogateway

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// ProviderEndpoint describes one provider/protocol ingress. Credentials are
// supplied at call time and are never included in errors or telemetry.
type ProviderEndpoint struct {
	Provider string
	Protocol string
	URL      string
	Token    string
	Header   string
}

// HTTPUpstreamClient is the buffered HTTP transport used by the local Auto
// pipeline. It deliberately rejects stream requests because a Complete call
// cannot preserve SSE backpressure or cancellation semantics; streaming must
// use a dedicated relay implementing StreamUpstreamClient.
type HTTPUpstreamClient struct {
	Client            *http.Client
	Endpoints         []ProviderEndpoint
	DefaultHeaders    http.Header
	MaxResponseSize   int64
	ForwardClientAuth bool
	// BufferedSSE uses one upstream stream while preserving a JSON client response.
	BufferedSSE bool
}

func (client *HTTPUpstreamClient) Complete(ctx context.Context, request UpstreamRequest) (UpstreamResponse, error) {
	if request.Parameters.Stream || request.Request.Stream {
		return UpstreamResponse{}, errors.New("streaming_requires_stream_transport")
	}
	if client.BufferedSSE || needsNativeMessagesBridge(request) {
		return client.completeBufferedSSE(ctx, request)
	}
	endpoint, ok := client.endpoint(request.Provider, request.Protocol)
	if !ok {
		return UpstreamResponse{}, errors.New("provider_endpoint_unconfigured")
	}
	if strings.TrimSpace(endpoint.URL) == "" {
		return UpstreamResponse{}, errors.New("provider_endpoint_invalid")
	}
	maxBytes := client.MaxResponseSize
	if maxBytes <= 0 {
		maxBytes = 16 << 20
	}
	httpClient := client.Client
	if httpClient == nil {
		httpClient = &http.Client{Timeout: 180 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	}
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint.URL, bytes.NewReader(request.Payload))
	if err != nil {
		return UpstreamResponse{}, fmt.Errorf("build_upstream_request: %w", err)
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	if request.RequestID != "" {
		httpRequest.Header.Set("X-Request-ID", request.RequestID)
	}
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
		return UpstreamResponse{}, fmt.Errorf("upstream_transport: %w", err)
	}
	defer response.Body.Close()
	result := UpstreamResponse{Transport: "buffered_json", StatusCode: response.StatusCode, ContentType: response.Header.Get("Content-Type"), RequestID: response.Header.Get("X-Request-ID"), ClientRequestID: response.Header.Get("X-Client-Request-ID")}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxBytes+1))
	result.ResponseBytes = len(body)
	if err != nil {
		// The transport can fail after a complete usage object arrived. Preserve
		// reported usage without declaring the response complete or forwarding
		// a partial body. Invalid/truncated JSON leaves usage explicitly unknown.
		result.Usage = extractUsage(body)
		return result, fmt.Errorf("read_upstream_response: %w", err)
	}
	if int64(len(body)) > maxBytes {
		return result, errors.New("upstream_response_too_large")
	}
	result.Body = body
	return validateBufferedResponse(request.Protocol, result)
}

func validateBufferedResponse(protocol string, result UpstreamResponse) (UpstreamResponse, error) {
	body := result.Body
	result.Usage = extractUsage(body)
	if result.StatusCode < 200 || result.StatusCode >= 300 {
		return result, fmt.Errorf("upstream_http_status_%d", result.StatusCode)
	}
	if !json.Valid(body) {
		return result, errors.New("upstream_invalid_json")
	}
	var envelope struct {
		Model     string          `json:"model"`
		ID        string          `json:"id"`
		Error     json.RawMessage `json:"error"`
		Reasoning struct {
			Effort ReasoningEffort `json:"effort"`
		} `json:"reasoning"`
	}
	_ = json.Unmarshal(body, &envelope)
	result.ResponseModel = envelope.Model
	result.ResponseID = envelope.ID
	result.ReportedEffort = envelope.Reasoning.Effort
	if len(envelope.Error) > 0 && string(envelope.Error) != "null" {
		return result, errors.New("upstream_error_envelope")
	}
	result.Complete = completeJSONResponse(protocol, body)
	if !result.Complete {
		return result, errors.New("upstream_incomplete_response")
	}
	return result, nil
}

func (client *HTTPUpstreamClient) endpoint(provider, protocol string) (ProviderEndpoint, bool) {
	canonical := canonicalProtocol(protocol)
	for _, endpoint := range client.Endpoints {
		if strings.EqualFold(endpoint.Provider, provider) && canonicalProtocol(endpoint.Protocol) == canonical {
			return endpoint, true
		}
	}
	for _, endpoint := range client.Endpoints {
		if (endpoint.Provider == "" || strings.EqualFold(endpoint.Provider, "default") || endpoint.Provider == "*") && canonicalProtocol(endpoint.Protocol) == canonical {
			return endpoint, true
		}
	}
	return ProviderEndpoint{}, false
}

func extractUsage(body []byte) map[string]any {
	var payload map[string]any
	if json.Unmarshal(body, &payload) != nil {
		return nil
	}
	usage, ok := payload["usage"].(map[string]any)
	if !ok {
		return nil
	}
	return usage
}

func copyAuthHeaders(destination, source http.Header) {
	copyTrustedClientIP(destination, source)
	copyClientUserAgent(destination, source)
	for _, key := range []string{"Authorization", "X-API-Key", "anthropic-version", "anthropic-beta"} {
		for _, value := range source.Values(key) {
			destination.Add(key, value)
		}
	}
}

func copyClientUserAgent(destination, source http.Header) {
	// An explicit empty value suppresses net/http's synthetic Go user agent.
	// Preserve the caller's identity; do not invent a browser or CLI identity.
	destination.Set("User-Agent", source.Get("User-Agent"))
}
