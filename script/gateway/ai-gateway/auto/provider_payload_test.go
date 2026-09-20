package autogateway

import (
	"bytes"
	"encoding/json"
	"testing"
)

func TestBuildProviderPayloadUsesGeneratedParameters(t *testing.T) {
	request := Request{Messages: []Message{{Role: "user", Content: "hello"}}, Stream: true}
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		t.Run(protocol, func(t *testing.T) {
			params := BuildProviderParameters("openai", protocol, DefaultCatalog[1], ReasoningHigh, true)
			body, err := BuildProviderPayload(protocol, request, params)
			if err != nil {
				t.Fatal(err)
			}
			var payload map[string]any
			if err := json.Unmarshal(body, &payload); err != nil {
				t.Fatal(err)
			}
			if payload["model"] != "gpt-5.6-luna" || payload["stream"] != true {
				t.Fatalf("payload=%s", body)
			}
			if protocol == "responses" {
				reasoning, ok := payload["reasoning"].(map[string]any)
				if !ok || reasoning["effort"] != "high" {
					t.Fatalf("reasoning=%s", body)
				}
			} else if protocol == "anthropic" {
				config, ok := payload["output_config"].(map[string]any)
				if !ok || config["effort"] != "high" {
					t.Fatalf("output_config=%s", body)
				}
			} else if payload["reasoning_effort"] != "high" {
				t.Fatalf("reasoning=%s", body)
			}
			if _, exists := payload["effort"]; exists {
				t.Fatalf("client or unscoped effort leaked: %s", body)
			}
		})
	}
}

func TestBuildProviderPayloadPreservesRawPartsAndTools(t *testing.T) {
	request := Request{Messages: []Message{{Role: "user", Parts: []ContentPart{{Type: "input_image", Raw: []byte(`{"type":"input_image","image_url":"https://example.invalid/image"}`)}}}}, Tools: []Tool{{Name: "lookup", Schema: `{"type":"object","properties":{"q":{"type":"string"}}}`}}}
	params := BuildProviderParameters("openai", "chat", DefaultCatalog[0], ReasoningNone, false)
	body, err := BuildProviderPayload("chat", request, params)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Contains(body, []byte("image_url")) || !bytes.Contains(body, []byte("lookup")) {
		t.Fatalf("payload dropped raw content/tool: %s", body)
	}
}

func TestProviderPayloadPreservesLargeNumbersAndStreamOptions(t *testing.T) {
	for _, protocol := range []string{"chat", "responses", "anthropic"} {
		body := []byte(`{"messages":[{"role":"user","content":"hello"}],"input":"hello","metadata":{"record_id":9007199254740993},"stream":true,"stream_options":{"include_obfuscation":false}}`)
		request, err := NormalizeProtocolRequest(protocol, body)
		if err != nil {
			t.Fatal(err)
		}
		model := *ModelByName("gpt-5.6-luna", DefaultCatalog)
		payload, err := BuildProviderPayload(protocol, request, BuildProviderParameters(model.Provider, protocol, model, ReasoningLow, true))
		if err != nil || !bytes.Contains(payload, []byte(`9007199254740993`)) {
			t.Fatalf("%s lost numeric precision", protocol)
		}
		if protocol == "chat" && !bytes.Contains(payload, []byte(`"include_obfuscation":false`)) {
			t.Fatal("stream options were dropped")
		}
	}
}
