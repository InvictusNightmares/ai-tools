package service

import (
	"bytes"
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	coderws "github.com/coder/websocket"
	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestPolicyObservationChatForwardIntegration(t *testing.T) {
	for _, stream := range []bool{false, true} {
		t.Run(map[bool]string{false: "buffered", true: "stream"}[stream], func(t *testing.T) {
			c, _ := gin.CreateTestContext(httptest.NewRecorder())
			body := []byte(`{"model":"gpt-5.5","messages":[{"role":"user","content":"harmless fixture"}],"stream":` + map[bool]string{false: "false", true: "true"}[stream] + `}`)
			c.Request = httptest.NewRequest("POST", "/v1/chat/completions", bytes.NewReader(body))
			upstreamBody := "data: {\"type\":\"response.failed\",\"response\":{\"id\":\"fixture-response\",\"status\":\"failed\",\"error\":{\"code\":\"invalid_prompt\",\"message\":\"Your prompt was flagged as potentially violating our usage policy.\"}}}\n\n"
			svc := &OpenAIGatewayService{policyObservationEnabled: func() bool { return true }, httpUpstream: &httpUpstreamRecorder{resp: &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{"text/event-stream"}, "X-Request-Id": []string{"fixture-upstream"}}, Body: io.NopCloser(strings.NewReader(upstreamBody))}}}
			account := &Account{ID: 51, Platform: PlatformOpenAI, Type: AccountTypeOAuth, Concurrency: 1, Credentials: map[string]any{"access_token": "fixture-token", "chatgpt_account_id": "fixture-account"}}
			_, _ = svc.ForwardAsChatCompletions(context.Background(), c, account, body, "", "gpt-5.5")
			mark := GetOpenAIPolicyObservation(c)
			require.NotNil(t, mark)
			require.Equal(t, "invalid_prompt", mark.Code)
			require.Equal(t, "fixture-response", mark.UpstreamResponseID)
			require.Equal(t, "fixture-upstream", mark.UpstreamRequestID)
			require.Nil(t, GetOpsCyberPolicy(c), "the new observation must not mark a non-cyber request as cyber")
		})
	}
}

func TestPolicyObservationWebSocketTransportBeforeAfterTurn(t *testing.T) {
	for _, tc := range []struct {
		name   string
		events []string
		code   string
	}{
		{"policy", []string{`{"type":"response.failed","response":{"id":"fixture-response","status":"failed","error":{"code":"content_policy","message":"fixture"}}}`}, "content_policy"},
		{"refusal", []string{`{"type":"response.refusal.delta","delta":"Harmless fixture refusal"}`, `{"type":"response.completed","response":{"id":"fixture-response","status":"completed","output":[],"usage":{"input_tokens":2,"output_tokens":1}}}`}, "structured_refusal"},
	} {
		t.Run(tc.name, func(t *testing.T) {
			ctx, cancel := context.WithCancelCause(context.Background())
			defer cancel(context.Canceled)
			upstream := newStagedPassthroughConn()
			for _, event := range tc.events {
				upstream.Send(event)
			}
			seen := make(chan OpenAIPolicyObservation, 1)
			server, serverErr := startPassthroughLifecycleServerWithHooks(t, ctx, policyObservationTestService(upstream), passthroughLifecycleAccount(), func(c *gin.Context) *OpenAIWSIngressHooks {
				return &OpenAIWSIngressHooks{AfterTurn: func(_ int, _ *OpenAIForwardResult, _ error) {
					if mark := GetOpenAIPolicyObservation(c); mark != nil {
						select {
						case seen <- *mark:
						default:
						}
					}
					ClearOpenAIPolicyObservation(c)
				}}
			})
			defer server.Close()
			client := dialPassthroughLifecycleClient(t, server)
			defer client.CloseNow()
			for range tc.events {
				_, err := readPassthroughLifecycleFrame(t, client, 3*time.Second)
				require.NoError(t, err)
			}
			select {
			case mark := <-seen:
				require.Equal(t, tc.code, mark.Code)
				require.Equal(t, 200, mark.UpstreamStatus)
			case <-time.After(3 * time.Second):
				t.Fatal("policy evidence not visible to AfterTurn")
			}
			require.NoError(t, client.Close(coderws.StatusNormalClosure, "done"))
			select {
			case <-serverErr:
			case <-time.After(3 * time.Second):
				t.Fatal("fixture server did not exit")
			}
		})
	}
}

func policyObservationTestService(upstream *stagedPassthroughConn) *OpenAIGatewayService {
	s := newPassthroughLifecycleService(passthroughLifecycleConfig(), upstream)
	s.policyObservationEnabled = func() bool { return true }
	return s
}

func TestPolicyObservationWebSocketTurnsRemainSeparated(t *testing.T) {
	ctx, cancel := context.WithCancelCause(context.Background())
	defer cancel(context.Canceled)
	upstream := newStagedPassthroughConn()
	upstream.Send(`{"type":"response.completed","response":{"id":"fixture-A","status":"completed","output":[],"usage":{"input_tokens":2,"output_tokens":1}}}`)
	type turnEvidence struct {
		turn int
		code string
	}
	seen := make(chan turnEvidence, 3)
	server, serverErr := startPassthroughLifecycleServerWithHooks(t, ctx, policyObservationTestService(upstream), passthroughLifecycleAccount(), func(c *gin.Context) *OpenAIWSIngressHooks {
		return &OpenAIWSIngressHooks{AfterTurn: func(turn int, _ *OpenAIForwardResult, _ error) {
			e := turnEvidence{turn: turn}
			if m := GetOpenAIPolicyObservation(c); m != nil {
				e.code = m.Code
			}
			seen <- e
			ClearOpenAIPolicyObservation(c)
			ClearOpsCyberPolicy(c)
		}}
	})
	defer server.Close()
	client := dialPassthroughLifecycleClient(t, server)
	defer client.CloseNow()
	_, err := readPassthroughLifecycleFrame(t, client, 3*time.Second)
	require.NoError(t, err)
	// A completes before the client submits B; the existing overlap guard rejects earlier admission.
	<-upstream.writes
	require.NoError(t, client.Write(ctx, coderws.MessageText, []byte(`{"type":"response.create","model":"gpt-5.5","input":"harmless second fixture"}`)))
	select {
	case <-upstream.writes:
	case <-time.After(3 * time.Second):
		t.Fatal("second request not forwarded")
	}
	upstream.Send(`{"type":"response.refusal.delta","delta":"Harmless second-turn fixture delta"}`)
	_, err = readPassthroughLifecycleFrame(t, client, 3*time.Second)
	require.NoError(t, err)
	upstream.Send(`{"type":"response.completed","response":{"id":"fixture-B","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"refusal","refusal":"Harmless test refusal"}]}],"usage":{"input_tokens":2,"output_tokens":1}}}`)
	_, err = readPassthroughLifecycleFrame(t, client, 3*time.Second)
	require.NoError(t, err)
	for _, expected := range []turnEvidence{{1, ""}, {2, "structured_refusal"}} {
		select {
		case got := <-seen:
			require.Equal(t, expected, got)
		case <-time.After(3 * time.Second):
			t.Fatal("turn evidence missing")
		}
	}
	require.NoError(t, client.Close(coderws.StatusNormalClosure, "done"))
	select {
	case <-serverErr:
	case <-time.After(3 * time.Second):
		t.Fatal("fixture server did not exit")
	}
}

func TestPolicyObservationDisabledLeavesResponseUnwrapped(t *testing.T) {
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	body := io.NopCloser(strings.NewReader(`{"error":{"code":"content_policy"}}`))
	s := &OpenAIGatewayService{policyObservationEnabled: func() bool { return false }, httpUpstream: &httpUpstreamRecorder{resp: &http.Response{StatusCode: 400, Header: http.Header{}, Body: body}}}
	req := httptest.NewRequest("POST", "http://fixture.invalid/v1/responses", nil)
	resp, err := s.doOpenAIUpstream(req, "", &Account{ID: 51, Platform: PlatformOpenAI}, c)
	require.NoError(t, err)
	require.Equal(t, body, resp.Body)
	_, err = io.Copy(io.Discard, resp.Body)
	require.NoError(t, err)
	require.NoError(t, resp.Body.Close())
	require.Nil(t, GetOpenAIPolicyObservation(c))
}
