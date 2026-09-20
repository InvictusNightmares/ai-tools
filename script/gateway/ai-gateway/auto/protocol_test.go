package autogateway

import "testing"

func TestNormalizeChatCompletions(t *testing.T) {
	request, err := NormalizeProtocolRequest("chat", []byte(`{"model":"auto","reasoning_effort":"xhigh","stream":true,"messages":[{"role":"user","content":[{"type":"text","text":"translate hello"},{"type":"image_url","image_url":{"url":"data:image/png;base64,x"}}]}],"tools":[{"type":"function","function":{"name":"lookup","parameters":{"type":"object"}}}],"response_format":{"type":"json_object"}}`))
	if err != nil {
		t.Fatal(err)
	}
	if len(request.Messages) != 1 || !request.ResponseFormat || !request.Stream || len(request.Tools) != 1 {
		t.Fatalf("normalized request = %+v", request)
	}
	classification := ExtractFeatures(request)
	if classification.Intent != "agent" || !classification.HasImage || classification.EffectiveReasoningEffort != ReasoningMedium {
		t.Fatalf("classification = %+v", classification)
	}
}

func TestNormalizeResponsesIgnoresClientReasoning(t *testing.T) {
	request, err := NormalizeProtocolRequest("responses", []byte(`{"model":"auto","reasoning":{"effort":"xhigh"},"input":"hello"}`))
	if err != nil {
		t.Fatal(err)
	}
	classification := ExtractFeatures(request)
	if classification.EffectiveReasoningEffort != ReasoningNone {
		t.Fatalf("client reasoning leaked into route: %+v", classification)
	}
}

func TestNormalizeAnthropicMessagesAndTools(t *testing.T) {
	request, err := NormalizeProtocolRequest("anthropic", []byte(`{"system":"You are helpful","messages":[{"role":"user","content":[{"type":"text","text":"debug this failure"}]}],"tools":[{"name":"run_tests","input_schema":{"type":"object"}}]}`))
	if err != nil {
		t.Fatal(err)
	}
	if len(request.Messages) != 2 || request.Messages[0].Role != "system" || len(request.Tools) != 1 {
		t.Fatalf("normalized request = %+v", request)
	}
	classification := ExtractFeatures(request)
	if classification.Intent != "agent" || classification.ToolCount != 1 {
		t.Fatalf("classification = %+v", classification)
	}
}

func TestNormalizeRejectsMalformedAndUnknownProtocol(t *testing.T) {
	if _, err := NormalizeProtocolRequest("unknown", []byte(`{}`)); err == nil {
		t.Fatal("unknown protocol accepted")
	}
	if _, err := NormalizeProtocolRequest("chat", []byte(`{"messages":`)); err == nil {
		t.Fatal("malformed body accepted")
	}
}

func TestStreamCapabilityIsRequired(t *testing.T) {
	request, err := NormalizeProtocolRequest("chat", []byte(`{"stream":true,"messages":[{"role":"user","content":"hello"}]}`))
	if err != nil {
		t.Fatal(err)
	}
	classification := ExtractFeatures(request)
	if !request.Stream || len(classification.RequiredCapabilities) != 2 {
		t.Fatalf("stream features = %+v", classification)
	}
	withoutStream := append([]Model(nil), DefaultCatalog...)
	withoutStream[0].Capabilities = []Capability{CapabilityText, CapabilityCode}
	capable := FilterCapableModels(classification, withoutStream)
	for _, model := range capable {
		if model.Name == "deepseek-flash" {
			t.Fatal("non-stream model passed capability filter")
		}
	}
}
