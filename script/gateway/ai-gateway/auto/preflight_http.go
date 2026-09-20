package autogateway

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// HTTPPreflightChecker is the phase-D client for the Guard API. It sends the
// complete input body to the private Guard for credential scanning. Transport
// authentication headers are never forwarded to Guard.
type HTTPPreflightChecker struct {
	Endpoint  string
	Client    *http.Client
	Provider  string
	Region    string
	SessionID string
}

type guardMessage struct {
	Role    string `json:"role"`
	Content string `json:"content,omitempty"`
}

type guardTool struct {
	Name   string `json:"name,omitempty"`
	Schema string `json:"schema,omitempty"`
}

func (checker *HTTPPreflightChecker) Evaluate(ctx context.Context, request Request) (PreflightResult, error) {
	return checker.EvaluateWithMeta(ctx, request, PipelineMeta{})
}

func (checker *HTTPPreflightChecker) EvaluateWithMeta(ctx context.Context, request Request, meta PipelineMeta) (PreflightResult, error) {
	if checker == nil || strings.TrimSpace(checker.Endpoint) == "" {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_endpoint_unconfigured"}}, errors.New("guard_endpoint_unconfigured")
	}
	inspection, view, mediaErr := inspectNativeMedia(request)
	if mediaErr != nil {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{mediaErr.Error()}}, mediaErr
	}
	request = view
	messages := make([]guardMessage, 0, len(request.Messages))
	for _, message := range request.Messages {
		messages = append(messages, guardMessage{Role: message.Role, Content: message.Content})
		if len(message.ToolCalls) > 0 {
			messages[len(messages)-1].Content += "\n" + string(message.ToolCalls)
		}
		if len(message.Parts) > 0 {
			messages[len(messages)-1].Content = ""
		}
		for _, part := range message.Parts {
			if part.Text != "" {
				messages[len(messages)-1].Content += part.Text
			}
		}
	}
	// Include the complete provider body so fields absent from the semantic view
	// (for example tool arguments or metadata) cannot bypass the input scan.
	if len(request.RawPayload) > 0 {
		messages = nil
	}
	tools := make([]guardTool, 0, len(request.Tools))
	for _, tool := range request.Tools {
		tools = append(tools, guardTool{Name: tool.Name, Schema: tool.Schema})
	}
	region, session := checker.Region, hashIdentifier(checker.SessionID)
	if meta.Region != "" {
		region = meta.Region
	}
	if meta.SessionID != "" {
		session = hashIdentifier(sessionStoreKey(meta))
	}
	payload := struct {
		ProviderPayload string         `json:"provider_payload,omitempty"`
		RequestID       string         `json:"request_id,omitempty"`
		Protocol        string         `json:"protocol"`
		Provider        string         `json:"provider"`
		Model           string         `json:"model"`
		Region          string         `json:"region,omitempty"`
		SessionHash     string         `json:"session_hash,omitempty"`
		AccountID       string         `json:"account_id,omitempty"`
		Messages        []guardMessage `json:"messages"`
		Tools           []guardTool    `json:"tools,omitempty"`
	}{ProviderPayload: string(request.RawPayload), RequestID: meta.RequestID, Protocol: "normalized", Provider: checker.Provider, Model: "auto", Region: region, SessionHash: session, AccountID: meta.APIKeyID, Messages: messages, Tools: tools}
	encoded, err := json.Marshal(payload)
	if err != nil {
		return PreflightResult{Decision: PreflightUnavailable}, err
	}
	httpRequest, err := http.NewRequestWithContext(ctx, http.MethodPost, checker.Endpoint, bytes.NewReader(encoded))
	if err != nil {
		return PreflightResult{Decision: PreflightUnavailable}, err
	}
	httpRequest.Header.Set("Content-Type", "application/json")
	if meta.RequestID != "" {
		httpRequest.Header.Set("X-Request-ID", meta.RequestID)
	}
	client := checker.Client
	if client == nil {
		client = &http.Client{Timeout: 5 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	}
	response, err := client.Do(httpRequest)
	if err != nil {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_transport_error"}}, fmt.Errorf("guard_transport: %w", err)
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, (32<<20)+1))
	if err != nil || len(body) > 32<<20 {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_response_read_error"}}, errors.New("guard_response_read_error")
	}
	var result struct {
		SanitizedPayload string            `json:"sanitized_payload"`
		InputSHA256      string            `json:"input_sha256"`
		RedactionVersion string            `json:"redaction_version"`
		Decision         PreflightDecision `json:"decision"`
		ReasonCodes      []string          `json:"reason_codes"`
	}
	if json.Unmarshal(body, &result) != nil {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_invalid_response"}}, errors.New("guard_invalid_response")
	}
	if response.StatusCode < 200 || response.StatusCode >= 300 || result.Decision == PreflightUnavailable || result.Decision == "" {
		if len(result.ReasonCodes) == 0 {
			result.ReasonCodes = []string{"guard_unavailable"}
		}
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: result.ReasonCodes}, errors.New("preflight_unavailable")
	}
	if result.Decision != PreflightAllow && result.Decision != PreflightBlock {
		return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_invalid_decision"}}, errors.New("guard_invalid_decision")
	}
	out := PreflightResult{Decision: result.Decision, ReasonCodes: result.ReasonCodes}
	if result.Decision == PreflightAllow && len(request.RawPayload) > 0 {
		digest := sha256.Sum256(request.RawPayload)
		if result.RedactionVersion != "credential-redaction-v1" || result.InputSHA256 != hex.EncodeToString(digest[:]) || !json.Valid([]byte(result.SanitizedPayload)) {
			return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_payload_contract_invalid"}}, errors.New("guard_payload_contract_invalid")
		}
		sanitized, normalizeErr := NormalizeProtocolRequest(request.Protocol, []byte(result.SanitizedPayload))
		if normalizeErr != nil || sanitized.Stream != request.Stream {
			return PreflightResult{Decision: PreflightUnavailable, ReasonCodes: []string{"guard_payload_contract_invalid"}}, errors.New("guard_payload_contract_invalid")
		}
		restored, restoreErr := inspection.restore(sanitized)
		if restoreErr != nil {
			return PreflightResult{Decision: PreflightBlock, ReasonCodes: []string{"attachment_metadata_rejected"}}, nil
		}
		out.SanitizedRequest = &restored
		if restored.Native != nil {
			out.ReasonCodes = append(out.ReasonCodes, "attachment_contents_not_inspected")
		}
	}
	return out, nil
}

func hashIdentifier(value string) string {
	if strings.TrimSpace(value) == "" {
		return ""
	}
	digest := sha256.Sum256([]byte(value))
	return hex.EncodeToString(digest[:])
}
