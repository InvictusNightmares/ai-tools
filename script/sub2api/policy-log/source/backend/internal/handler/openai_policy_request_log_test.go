package handler

import (
	"net/http/httptest"
	"testing"

	"github.com/Wei-Shaw/sub2api/internal/requestcontent"
	"github.com/Wei-Shaw/sub2api/internal/service"
	"github.com/stretchr/testify/require"
)

func TestPolicyRequestRecorderBroaderSignalsRemainIndependentOfCyberControl(t *testing.T) {
	c := newTestGinContext()
	c.Request = httptest.NewRequest("POST", "/v1/responses", nil)
	var entries []requestcontent.Entry
	h := &OpenAIGatewayHandler{policyRequestRecorder: func(e requestcontent.Entry) { entries = append(entries, e) }}
	key := &service.APIKey{ID: 65, UserID: 9, Name: "fixture-owner"}
	account := &service.Account{ID: 51, Platform: service.PlatformOpenAI}
	body := []byte(`{"input":"harmless fixture"}`)
	for _, code := range []string{"content_policy", "content_policy_violation", "content_filter", "invalid_prompt", "structured_refusal"} {
		payload := `{"error":{"code":"` + code + `","message":"Your prompt was flagged as potentially violating our usage policy."}}`
		if code == "structured_refusal" {
			payload = `{"type":"response.refusal.delta","delta":"Harmless fixture"}`
		}
		service.ObserveOpenAIPolicyPayload(c, account, []byte(payload), 200, "upstream-"+code)
		h.recordCyberPolicyIfMarked(c, key, account, nil, "gpt-5", false, body, service.ChannelUsageFields{}, "")
		require.Nil(t, service.GetOpsCyberPolicy(c), "logging must not enable cyber enforcement")
		require.False(t, c.GetBool(cyberPolicyRecordedKey))
	}
	require.Len(t, entries, 5)
	for _, entry := range entries {
		require.Equal(t, int64(65), entry.APIKeyID)
		require.Equal(t, int64(9), entry.UserID)
		require.Equal(t, int64(51), entry.AccountID)
		require.Equal(t, string(body), string(entry.Body))
		require.NotEmpty(t, entry.UpstreamRequestID)
	}
	h.recordPolicyRequestIfMarked(c, key, account, "gpt-5", body)
	require.Len(t, entries, 5, "consumed signals must not duplicate")
	c.Request.Header.Set("Upgrade", "websocket")
	clearCyberPolicyTurnState(c)
	h.recordPolicyRequestIfMarked(c, key, account, "gpt-5", []byte(`{"input":"normal next turn"}`))
	require.Len(t, entries, 5)
	service.ObserveOpenAIPolicyPayload(c, account, []byte(`{"error":{"code":"content_policy"}}`), 200, "next-turn")
	h.recordPolicyRequestIfMarked(c, key, account, "gpt-5", []byte(`{"input":"next rejected turn"}`))
	require.Len(t, entries, 6)
	require.Equal(t, "websocket", entries[5].Protocol)
	require.Equal(t, `{"input":"next rejected turn"}`, string(entries[5].Body))
}

func TestPolicyRequestRecorderRetainsOnlyUnambiguousUnfinishedTurn(t *testing.T) {
	c := newTestGinContext()
	c.Request = httptest.NewRequest("GET", "/v1/responses", nil)
	c.Request.Header.Set("Upgrade", "websocket")
	var entries []requestcontent.Entry
	h := &OpenAIGatewayHandler{policyRequestRecorder: func(e requestcontent.Entry) { entries = append(entries, e) }}
	key := &service.APIKey{ID: 65}
	account := &service.Account{ID: 51, Platform: service.PlatformOpenAI}
	bodies := map[int][]byte{2: []byte(`{"model":"gpt-5.5","input":"harmless interrupted second turn"}`)}
	service.ObserveOpenAIPolicyPayload(c, account, []byte(`{"type":"response.refusal.delta","delta":"Harmless fixture"}`), 200, "")
	h.recordUnfinishedPolicyRequest(c, key, account, "gpt-5", bodies)
	require.Len(t, entries, 1)
	require.Equal(t, "gpt-5.5", entries[0].Model)
	require.Contains(t, string(entries[0].Body), "second turn")
	require.Empty(t, bodies)
	h.recordUnfinishedPolicyRequest(c, key, account, "gpt-5", bodies)
	require.Len(t, entries, 1)
	service.ObserveOpenAIPolicyPayload(c, account, []byte(`{"type":"response.refusal.delta","delta":"Harmless fixture"}`), 200, "")
	h.recordUnfinishedPolicyRequest(c, key, account, "gpt-5", map[int][]byte{3: []byte(`{}`), 4: []byte(`{}`)})
	require.Len(t, entries, 1, "ambiguous turn bodies must not be retained")
}
