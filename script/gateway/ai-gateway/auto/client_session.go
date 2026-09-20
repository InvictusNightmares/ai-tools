package autogateway

import (
	"encoding/json"
	"net/http"
	"strings"
)

// Only explicit session signals are usable for stickiness. A user/account ID,
// prompt-cache key or a shared first prompt is not a session identifier.
func clientSessionID(headers http.Header, protocol string, body []byte) (string, string) {
	if value, source := clientSessionHeader(headers, protocol); value != "" {
		return scopedClientSession(headers, value), source
	}
	if canonicalProtocol(protocol) == "anthropic" {
		var payload struct {
			Metadata struct {
				UserID string `json:"user_id"`
			} `json:"metadata"`
		}
		if json.Unmarshal(body, &payload) == nil {
			var metadata struct {
				SessionID string `json:"session_id"`
			}
			if json.Unmarshal([]byte(payload.Metadata.UserID), &metadata) == nil {
				if value := boundedSessionID(metadata.SessionID); value != "" {
					return scopedClientSession(headers, value), "metadata.user_id.session_id"
				}
			}
		}
	}
	return "", "request_only"
}

// Return the raw session signal so WebSocket lanes can add their scope before
// the HTTP pipeline applies a child-agent scope exactly once.
func clientSessionHeader(headers http.Header, protocol string) (string, string) {
	names := []string{"X-Gateway-Session-ID"}
	if canonicalProtocol(protocol) == "anthropic" {
		names = append(names, "X-Claude-Code-Session-Id")
	}
	names = append(names, "session-id", "x-session-id", "session_id", "conversation_id")
	for _, name := range names {
		if value := boundedSessionID(headers.Get(name)); value != "" {
			return value, strings.ToLower(name)
		}
	}
	return "", "request_only"
}

func boundedSessionID(value string) string {
	value = strings.TrimSpace(value)
	if len(value) == 0 || len(value) > 256 {
		return ""
	}
	for _, r := range value {
		if r < 33 || r > 126 {
			return ""
		}
	}
	return value
}

func scopedClientSession(headers http.Header, session string) string {
	// Claude's native agents share the parent's session header and supply their
	// own agent ID. Explicit integration identity retains precedence. Parent-agent
	// references never identify the current child.
	for _, name := range []string{"X-Gateway-Agent-ID", "x-claude-code-agent-id"} {
		if agent := boundedSessionID(headers.Get(name)); agent != "" {
			value, _ := json.Marshal([]string{session, agent})
			return RequestDigest(value)
		}
	}
	return session
}
