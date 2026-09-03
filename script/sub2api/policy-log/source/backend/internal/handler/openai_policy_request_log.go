package handler

import (
	"strings"

	"github.com/Wei-Shaw/sub2api/internal/pkg/ctxkey"
	"github.com/Wei-Shaw/sub2api/internal/requestcontent"
	"github.com/Wei-Shaw/sub2api/internal/service"
	"github.com/gin-gonic/gin"
	"github.com/tidwall/gjson"
)

// This hook only writes evidence, independently of native risk control. It is
// called after each HTTP attempt or WS turn, before its request buffers expire.
func (h *OpenAIGatewayHandler) recordPolicyRequestIfMarked(c *gin.Context, key *service.APIKey, account *service.Account, model string, body []byte) {
	if c == nil || key == nil || len(body) == 0 {
		return
	}
	m := service.GetOpenAIPolicyObservation(c)
	if m != nil {
		service.ClearOpenAIPolicyObservation(c)
	} else if cyber := service.GetOpsCyberPolicy(c); cyber != nil && !c.GetBool(cyberPolicyRecordedKey) {
		m = &service.OpenAIPolicyObservation{Code: "cyber_policy", UpstreamStatus: cyber.UpstreamStatus, SignalPath: "native_cyber_policy_mark", Reason: "explicit_upstream_policy_error"}
		if account != nil {
			m.AccountID = account.ID
		}
	}
	if m == nil {
		return
	}
	e := requestcontent.Entry{
		RequestID: c.Writer.Header().Get("X-Request-Id"),
		UserID:    key.UserID, APIKeyID: key.ID, APIKeyName: key.Name,
		GroupID: key.GroupID, AccountID: m.AccountID,
		Provider: service.PlatformOpenAI, Protocol: "http", Model: clientRequestedModel(c, model),
		Stage: "upstream_policy_signal", ErrorCode: m.Code, ErrorType: m.ErrorType,
		SignalPath: m.SignalPath, Reason: m.Reason, UpstreamStatus: m.UpstreamStatus,
		UpstreamRequestID: m.UpstreamRequestID, UpstreamResponseID: m.UpstreamResponseID, Body: body,
	}
	if key.User != nil {
		e.UserID = key.User.ID
	}
	if key.Group != nil {
		e.GroupName = key.Group.Name
	}
	if c.GetBool(opsStreamKey) {
		e.Protocol = "sse"
	}
	if c.Request != nil {
		e.ClientRequestID, _ = c.Request.Context().Value(ctxkey.ClientRequestID).(string)
		if c.Request.URL != nil {
			e.Endpoint = c.Request.URL.Path
		}
		if strings.EqualFold(c.GetHeader("Upgrade"), "websocket") {
			e.Protocol = "websocket"
		}
	}
	record := h.policyRequestRecorder
	if record == nil {
		record = requestcontent.Capture
	}
	record(e)
}

// A refusal may precede a disconnect with no terminal event. Only the one
// unconsumed request can be safely attributed; ambiguous leftovers are skipped.
func (h *OpenAIGatewayHandler) recordUnfinishedPolicyRequest(c *gin.Context, key *service.APIKey, account *service.Account, model string, bodies map[int][]byte) {
	if service.GetOpenAIPolicyObservation(c) == nil {
		return
	}
	if len(bodies) != 1 {
		service.ClearOpenAIPolicyObservation(c)
		return
	}
	for turn, body := range bodies {
		if requested := gjson.GetBytes(body, "model").String(); requested != "" {
			model = requested
		}
		h.recordPolicyRequestIfMarked(c, key, account, model, body)
		delete(bodies, turn)
	}
}
