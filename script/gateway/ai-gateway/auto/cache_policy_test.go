package autogateway

import "testing"

func TestResponseCachePolicyKeepsOnlyReusableAllowedResponses(t *testing.T) {
	policy := DefaultResponseCachePolicy()
	plain := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	if ok, reason := policy.Eligible(plain, PreflightAllow, 100); !ok || reason != "eligible" {
		t.Fatalf("plain = %v %s", ok, reason)
	}
	for _, test := range []struct {
		name, reason string
		request      Request
		decision     PreflightDecision
		bytes        int
	}{
		{name: "stream", reason: "streaming_response", request: Request{Stream: true}},
		{name: "tools", reason: "tool_call_response", request: Request{Tools: []Tool{{Name: "lookup"}}}},
		{name: "image", reason: "image_input", request: Request{Messages: []Message{{Parts: []ContentPart{{Type: "image_url"}}}}}},
		{name: "blocked", reason: "preflight_not_allowed", request: plain, decision: PreflightBlock},
		{name: "large", reason: "response_too_large", request: plain, bytes: 5 << 20},
	} {
		t.Run(test.name, func(t *testing.T) {
			decision := test.decision
			if decision == "" {
				decision = PreflightAllow
			}
			if ok, reason := policy.Eligible(test.request, decision, test.bytes); ok || reason != test.reason {
				t.Fatalf("result = %v %s", ok, reason)
			}
		})
	}
}
