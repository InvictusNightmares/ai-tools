package autogateway

import (
	"net/http"
	"strings"
	"testing"
)

func TestClientSessionSignalsAndIsolation(t *testing.T) {
	for _, tc := range []struct{ protocol, name string }{{"anthropic", "X-Claude-Code-Session-Id"}, {"responses", "session_id"}, {"chat", "conversation_id"}, {"anthropic", "X-Gateway-Session-ID"}} {
		h := http.Header{}
		h.Set(tc.name, "same-session")
		id, source := clientSessionID(h, tc.protocol, nil)
		if id != "same-session" || source != strings.ToLower(tc.name) {
			t.Fatalf("session signal lost: %s", tc.name)
		}
		a, b := PipelineMeta{Region: "tokyo", APIKeyID: "a", SessionID: id}, PipelineMeta{Region: "tokyo", APIKeyID: "b", SessionID: id}
		if sessionStoreKey(a) == sessionStoreKey(b) {
			t.Fatal("cross-key session collision")
		}
		h.Set("X-Gateway-Agent-ID", "child-one")
		child, _ := clientSessionID(h, tc.protocol, nil)
		h.Set("X-Gateway-Agent-ID", "child-two")
		sibling, _ := clientSessionID(h, tc.protocol, nil)
		if child == sibling || child == id {
			t.Fatal("explicit child session collision")
		}
	}
	for _, body := range []string{`{"metadata":{"user_id":"same-account"}}`, `{"prompt_cache_key":"same-prefix"}`} {
		if id, _ := clientSessionID(nil, "anthropic", []byte(body)); id != "" {
			t.Fatal("account/cache key mistaken for session")
		}
	}
	id, _ := clientSessionID(nil, "anthropic", []byte(`{"metadata":{"user_id":"{\"session_id\":\"s1\",\"account_uuid\":\"a1\"}"}}`))
	if id != "s1" {
		t.Fatal("structured Claude session missing")
	}
}

func TestNativeClientSessionHeaders(t *testing.T) {
	for _, name := range []string{"x-session-id", "session-id"} {
		t.Run(name, func(t *testing.T) {
			for _, protocol := range []string{"responses", "chat", "anthropic"} {
				headers := http.Header{}
				headers.Set(name, "native-parent")
				parent, source := clientSessionID(headers, protocol, nil)
				if parent != "native-parent" || source != name {
					t.Fatalf("native session not recognized for %s: %q %q", protocol, parent, source)
				}
				headers.Set(name, "native-child")
				headers.Set("x-codex-parent-thread-id", parent)
				headers.Set("x-session-affinity", parent)
				child, _ := clientSessionID(headers, protocol, nil)
				if child != "native-child" || child == parent {
					t.Fatal("child identity collapsed into parent")
				}
				headers.Set("X-Gateway-Session-ID", "explicit-override")
				if id, _ := clientSessionID(headers, protocol, nil); id != "explicit-override" {
					t.Fatal("explicit integration session precedence changed")
				}
			}
		})
	}
	for _, name := range []string{"x-session-affinity", "x-codex-parent-thread-id", "user-agent"} {
		headers := http.Header{}
		headers.Set(name, "shared-value")
		if id, _ := clientSessionID(headers, "responses", nil); id != "" {
			t.Fatalf("non-session header accepted: %s", name)
		}
	}
}

func TestNativeClaudeAgentIsolation(t *testing.T) {
	for _, fromMetadata := range []bool{false, true} {
		headers := http.Header{}
		var body []byte
		if fromMetadata {
			body = []byte(`{"metadata":{"user_id":"{\"session_id\":\"native-claude-session\"}"}}`)
		} else {
			headers.Set("X-Claude-Code-Session-Id", "native-claude-session")
		}
		parent, _ := clientSessionID(headers, "anthropic", body)
		headers.Set("x-claude-code-parent-agent-id", "shared-parent")
		if id, _ := clientSessionID(headers, "anthropic", body); id != parent {
			t.Fatal("parent agent reference changed own session")
		}
		headers.Set("x-claude-code-agent-id", "native-child-one")
		child, _ := clientSessionID(headers, "anthropic", body)
		headers.Set("x-claude-code-agent-id", "native-child-two")
		sibling, _ := clientSessionID(headers, "anthropic", body)
		if child == parent || sibling == parent || child == sibling {
			t.Fatal("native Claude agents share routing and classification state")
		}
		headers.Set("X-Gateway-Agent-ID", "explicit-child")
		explicit, _ := clientSessionID(headers, "anthropic", body)
		headers.Del("x-claude-code-agent-id")
		if id, _ := clientSessionID(headers, "anthropic", body); id != explicit {
			t.Fatal("explicit child scope precedence changed")
		}
	}
}
