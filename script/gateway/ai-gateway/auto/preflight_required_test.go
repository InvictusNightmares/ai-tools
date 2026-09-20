package autogateway

import (
	"context"
	"testing"
)

func TestMissingPreflightStopsAllRouting(t *testing.T) {
	for _, streaming := range []bool{false, true} {
		calls := 0
		upstream := &recordingUpstream{}
		p := &Pipeline{Gateway: NewAutoGateway(), Upstream: upstream, Classifier: taskClassifierFunc(func(context.Context, Request, PipelineMeta) (Classification, error) {
			calls++
			return Classification{}, nil
		})}
		r := Request{Messages: []Message{{Role: "user", Content: "ordinary task"}}}
		var out PipelineResult
		var err error
		if streaming {
			out, err = p.Plan(context.Background(), "chat", "", "auto", r, 0, false, false, false, false, PipelineMeta{})
		} else {
			out, err = p.Execute(context.Background(), "chat", "", "auto", r, 0, false, false, false, false)
		}
		if err == nil || err.Error() != "preflight_unavailable" || out.Preflight.Decision != PreflightUnavailable || calls != 0 || upstream.calls != 0 {
			t.Fatalf("missing Guard reached routing: stream=%t classification=%d upstream=%d err=%v", streaming, calls, upstream.calls, err)
		}
	}
}
