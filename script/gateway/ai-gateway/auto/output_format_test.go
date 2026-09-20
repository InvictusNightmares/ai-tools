package autogateway

import (
	"encoding/json"
	"testing"
	"time"
)

func TestOutputFormatCapabilityMatchesActualFormat(t *testing.T) {
	for _, tc := range []struct {
		name, protocol, fields string
		structured             bool
	}{
		{"chat_default", "chat", ``, false},
		{"chat_text", "chat", `,"response_format":{"type":"text"}`, false},
		{"chat_null", "chat", `,"response_format":null`, false},
		{"chat_json", "chat", `,"response_format":{"type":"json_object"}`, true},
		{"chat_schema", "chat", `,"response_format":{"type":"json_schema","json_schema":{"name":"x","schema":{"type":"object"}}}`, true},
		{"responses_verbosity", "responses", `,"text":{"verbosity":"low"}`, false},
		{"responses_empty", "responses", `,"text":{}`, false},
		{"responses_null", "responses", `,"text":null`, false},
		{"responses_text", "responses", `,"text":{"format":{"type":"text"}}`, false},
		{"responses_null_format", "responses", `,"text":{"format":null,"verbosity":"high"}`, false},
		{"responses_schema", "responses", `,"text":{"format":{"type":"json_schema","name":"x","schema":{"type":"object"}}}`, true},
		{"responses_legacy_json", "responses", `,"text":{"verbosity":"low"},"response_format":{"type":"json_object"}`, true},
		{"messages_effort", "anthropic", `,"output_config":{"effort":"high"}`, false},
		{"messages_schema", "anthropic", `,"output_config":{"format":{"type":"json_schema","schema":{"type":"object"}}}`, true},
		{"unknown_format", "responses", `,"text":{"format":{"type":"future_format"}}`, true},
		{"malformed_format", "responses", `,"text":{"format":[]}`, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			raw := []byte(`{"model":"auto","input":"hello","messages":[{"role":"user","content":"hello"}]` + tc.fields + `}`)
			r, err := NormalizeProtocolRequest(tc.protocol, raw)
			if err != nil {
				t.Fatal(err)
			}
			if r.ResponseFormat != tc.structured {
				t.Fatalf("structured=%v want %v", r.ResponseFormat, tc.structured)
			}
			a := assessment("quick_qa", "simple")
			a.Stage, a.Verification = "understand", "none"
			c := classificationFromAssessment(r, a)
			d := DecideRoute(NewRouteState(), c, DefaultCatalog, nil, 1, time.Now(), false, false, false)
			if d.SelectedModel == nil {
				t.Fatal("no model")
			}
			if (d.SelectedModel.Name == "deepseek-flash") == tc.structured {
				t.Fatalf("wrong capability route %s", d.SelectedModel.Name)
			}
			var before, after map[string]json.RawMessage
			json.Unmarshal(raw, &before)
			json.Unmarshal(r.RawPayload, &after)
			for _, k := range []string{"text", "response_format"} {
				if len(before[k]) > 0 && !bytesEqualJSON(before[k], after[k]) {
					t.Fatalf("client output config changed: %s", k)
				}
			}
		})
	}
}
