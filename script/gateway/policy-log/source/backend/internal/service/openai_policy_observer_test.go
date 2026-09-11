package service

import (
	"bytes"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/require"
)

func TestPolicyObservationExactSignals(t *testing.T) {
	cases := []struct{ name, payload, code string }{
		{"cyber", `{"error":{"code":"cyber_policy"}}`, "cyber_policy"},
		{"content type", `{"error":{"type":"content_policy"}}`, "content_policy"},
		{"violation", `{"error":{"code":"content_policy_violation"}}`, "content_policy_violation"},
		{"policy invalid prompt", `{"type":"response.failed","response":{"error":{"code":"invalid_prompt","message":"Your prompt was flagged as potentially violating our usage policy. Please try again with a different prompt."}}}`, "invalid_prompt"},
		{"generic invalid prompt", `{"error":{"code":"invalid_prompt","message":"Missing input"}}`, ""},
		{"unrelated flagged", `{"error":{"code":"invalid_prompt","message":"flagged as invalid JSON"}}`, ""},
		{"local tier", `{"error":{"code":"policy_violation","message":"Fast tier not allowed"}}`, ""},
		{"empty output", `{"error":{"code":"openai_silent_refusal"}}`, ""},
		{"quota", `{"error":{"code":"insufficient_quota"}}`, ""},
		{"blocked identifier", `{"error":{"code":"safety_identifier_blocked"}}`, ""},
		{"response filter", `{"type":"response.incomplete","response":{"id":"resp-test","incomplete_details":{"reason":"content_filter"}}}`, "content_filter"},
		{"token limit", `{"response":{"incomplete_details":{"reason":"max_output_tokens"}}}`, ""},
		{"chat filter", `{"choices":[{"finish_reason":"content_filter"}]}`, "content_filter"},
		{"chat refusal", `{"choices":[{"message":{"role":"assistant","refusal":"Harmless test refusal"}}]}`, "structured_refusal"},
		{"chat refusal delta", `{"choices":[{"delta":{"refusal":"Harmless test"}}]}`, "structured_refusal"},
		{"empty refusal", `{"choices":[{"message":{"refusal":null}}]}`, ""},
		{"delta", `{"type":"response.refusal.delta","delta":"Harmless test"}`, "structured_refusal"},
		{"done", `{"type":"response.refusal.done","refusal":"Harmless test"}`, "structured_refusal"},
		{"response output", `{"object":"response","id":"resp-test","output":[{"type":"message","role":"assistant","content":[{"type":"refusal","refusal":"Harmless test"}]}]}`, "structured_refusal"},
		{"event part", `{"type":"response.content_part.done","part":{"type":"refusal","refusal":"Harmless test"}}`, "structured_refusal"},
		{"event item", `{"type":"response.output_item.done","item":{"type":"message","role":"assistant","content":[{"type":"refusal","refusal":"Harmless test"}]}}`, "structured_refusal"},
		{"keywords in output", `{"output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"cyber_policy content_policy invalid_prompt refusal content_filter"}]}]}`, ""},
		{"quoted JSON output", `{"choices":[{"message":{"content":"{\"error\":{\"code\":\"content_policy\"}}"},"finish_reason":"stop"}]}`, ""},
		{"user input ignored", `{"input":[{"role":"user","content":"cyber_policy"}],"tools":[{"error":{"code":"content_policy"}}]}`, ""},
		{"malformed", `{"error":{"code":"cyber_policy"}`, ""},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := detectOpenAIPolicyObservation([]byte(tc.payload))
			if tc.code == "" {
				require.Nil(t, got)
				return
			}
			require.NotNil(t, got)
			require.Equal(t, tc.code, got.Code)
			require.NotEmpty(t, got.SignalPath)
		})
	}
}

func TestPolicyObservationReaderPreservesBytesAndHandlesFragments(t *testing.T) {
	cases := []struct{ name, contentType, body, code string }{
		{"HTTP400", "application/json", `{"error":{"code":"content_policy_violation"}}`, "content_policy_violation"},
		{"SSE200", "text/event-stream", "event: response.failed\r\ndata: {\"type\":\"response.failed\",\"response\":{\"error\":{\"code\":\"content_policy\"}}}\r\n\r\n", "content_policy"},
		{"SSE missing header", "", "data: {\"type\":\"response.refusal.delta\",\"delta\":\"Harmless fixture\"}\n\n", "structured_refusal"},
		{"SSE multiline", "text/event-stream", "data: {\"error\":\ndata: {\"code\":\"cyber_policy\"}}\n\n", "cyber_policy"},
		{"SSE no trailing newline", "text/event-stream", "data: {\"error\":{\"code\":\"content_filter\"}}", "content_filter"},
		{"normal", "text/event-stream", "data: {\"type\":\"response.output_text.delta\",\"delta\":\"refusal content_policy\"}\n\ndata: [DONE]\n\n", ""},
	}
	for _, tc := range cases {
		for _, size := range []int{1, 7, 4096} {
			t.Run(tc.name+"/"+string(rune(size)), func(t *testing.T) {
				c, _ := gin.CreateTestContext(httptest.NewRecorder())
				resp := &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{tc.contentType}, "X-Request-Id": []string{"upstream-fixture"}}, Body: io.NopCloser(strings.NewReader(tc.body))}
				observeOpenAIPolicyResponse(c, &Account{ID: 51, Platform: PlatformOpenAI}, resp)
				var got bytes.Buffer
				_, err := io.CopyBuffer(&got, struct{ io.Reader }{resp.Body}, make([]byte, size))
				require.NoError(t, err)
				require.NoError(t, resp.Body.Close())
				require.Equal(t, tc.body, got.String())
				mark := GetOpenAIPolicyObservation(c)
				if tc.code == "" {
					require.Nil(t, mark)
				} else {
					require.NotNil(t, mark)
					require.Equal(t, tc.code, mark.Code)
					require.Equal(t, int64(51), mark.AccountID)
					require.Equal(t, "upstream-fixture", mark.UpstreamRequestID)
				}
			})
		}
	}
}

func TestPolicyObservationDeduplicatesAndClearsBetweenAttempts(t *testing.T) {
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	a := &Account{ID: 51, Platform: PlatformOpenAI}
	ObserveOpenAIPolicyPayload(c, a, []byte(`{"error":{"code":"content_policy"}}`), 200, "request-a")
	ObserveOpenAIPolicyPayload(c, a, []byte(`{"error":{"code":"cyber_policy"}}`), 200, "request-b")
	require.Equal(t, "request-a", GetOpenAIPolicyObservation(c).UpstreamRequestID)
	ClearOpenAIPolicyObservation(c)
	ObserveOpenAIPolicyPayload(c, a, []byte(`{"type":"response.completed","response":{"status":"completed"}}`), 200, "request-c")
	require.Nil(t, GetOpenAIPolicyObservation(c))
	ObserveOpenAIPolicyPayload(c, &Account{ID: 99, Platform: PlatformAnthropic}, []byte(`{"error":{"code":"content_policy"}}`), 400, "request-d")
	require.Nil(t, GetOpenAIPolicyObservation(c))
}

func TestPolicyObservationOversizedLineDoesNotBreakFollowingEvents(t *testing.T) {
	c, _ := gin.CreateTestContext(httptest.NewRecorder())
	body := "data: " + strings.Repeat("x", maxPolicyObservationBytes+1) + "\n\ndata: {\"error\":{\"code\":\"content_filter\"}}\n\n"
	resp := &http.Response{StatusCode: 200, Header: http.Header{"Content-Type": []string{"text/event-stream"}}, Body: io.NopCloser(strings.NewReader(body))}
	observeOpenAIPolicyResponse(c, &Account{ID: 51, Platform: PlatformOpenAI}, resp)
	n, err := io.Copy(io.Discard, resp.Body)
	require.NoError(t, err)
	require.Equal(t, int64(len(body)), n)
	require.NoError(t, resp.Body.Close())
	require.Equal(t, "content_filter", GetOpenAIPolicyObservation(c).Code)
}
