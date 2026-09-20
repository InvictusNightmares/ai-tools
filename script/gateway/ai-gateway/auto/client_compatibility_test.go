package autogateway

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestClaudeCodeAliasesEnterAuto(t *testing.T) {
	g := NewAutoGateway()
	for _, alias := range []string{"claude-opus-5", "claude-sonnet-5", "claude-haiku-4", "claude-haiku-4-5-20251001"} {
		if g.ValidatePublicModel(alias) != nil {
			t.Errorf("rejected client agent alias %s", alias)
		}
	}
	if g.ValidatePublicModel("claude-unknown") == nil || g.ValidatePublicModel("gpt-unknown") == nil {
		t.Fatal("arbitrary forced business model accepted")
	}
}

func TestClaudeCodeSystemAndToolRoundPreserved(t *testing.T) {
	body := []byte(`{"model":"claude-opus-5","max_tokens":4096,"system":[{"type":"text","text":"代码必须有测试","cache_control":{"type":"ephemeral"}}],"messages":[{"role":"user","content":"修复并发刷新 / fix refresh race"},{"role":"assistant","content":[{"type":"tool_use","id":"call-1","name":"Read","input":{"path":"main.go"}}]},{"role":"user","content":[{"type":"tool_result","tool_use_id":"call-1","content":"race detected / 检测到竞争","is_error":true}]}],"thinking":{"type":"adaptive"},"output_config":{"effort":"low","format":{"type":"json_schema","schema":{"type":"object"}}},"tools":[{"name":"Read","input_schema":{"type":"object"}}]}`)
	r, err := NormalizeProtocolRequest("anthropic", body)
	if err != nil {
		t.Fatal(err)
	}
	in, err := splitSemanticInput(r)
	if err != nil || len(in.Instructions) != 1 || !strings.Contains(in.Current.Content, "fix refresh race") || len(in.After) != 2 || !requestToolContinuation(r) {
		t.Fatalf("lost system or tool context: %+v %v", in, err)
	}
	p := BuildProviderParameters("openai", "anthropic", DefaultCatalog[3], ReasoningHigh, true)
	out, err := BuildProviderPayload("anthropic", r, p)
	if err != nil {
		t.Fatal(err)
	}
	var wire map[string]any
	json.Unmarshal(out, &wire)
	config, _ := wire["output_config"].(map[string]any)
	if config["effort"] != "high" || config["format"] == nil || wire["reasoning_effort"] != nil || !strings.Contains(string(out), "tool_use_id") || !strings.Contains(string(out), "cache_control") {
		t.Fatalf("bad Anthropic wire: %s", out)
	}
}
