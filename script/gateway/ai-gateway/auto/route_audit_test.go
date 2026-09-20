package autogateway

import (
	"testing"
	"time"
)

func TestBuildRouteAuditExplainsGeneratedEffort(t *testing.T) {
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}}
	classification := ExtractFeatures(request)
	decision, _, err := NewAutoGateway().Route(request, 1, time.Unix(1, 0), false, false, false)
	if err != nil || decision.SelectedModel == nil {
		t.Fatalf("route = %+v err=%v", decision, err)
	}
	audit := BuildRouteAudit(time.Unix(1, 0), "auto", "deepseek", "chat", request, decision, classification)
	if audit.RequestedModel != "auto" || audit.EffectiveModel != "deepseek-flash" || audit.EffectiveReasoning != ReasoningNone || audit.EffortStatus != EffortApplied || audit.EffortParameter != "reasoning_effort" {
		t.Fatalf("audit = %+v", audit)
	}
}
