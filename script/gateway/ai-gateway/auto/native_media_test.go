package autogateway

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func nativeTestGuard(t *testing.T, mutate func(string) string) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		var in struct {
			ProviderPayload string `json:"provider_payload"`
		}
		if json.NewDecoder(r.Body).Decode(&in) != nil {
			t.Error("bad Guard input")
		}
		if strings.Contains(in.ProviderPayload, base64.StdEncoding.EncodeToString([]byte("private attachment contents"))) {
			t.Error("attachment bytes sent to text Guard")
		}
		digest := sha256.Sum256([]byte(in.ProviderPayload))
		sanitized := in.ProviderPayload
		if mutate != nil {
			sanitized = mutate(sanitized)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"decision": "allow", "redaction_version": "credential-redaction-v1", "input_sha256": hex.EncodeToString(digest[:]), "sanitized_payload": sanitized})
	}))
}

func TestNativeAttachmentsPreservedAcrossProtocolsAndToolResults(t *testing.T) {
	b64 := base64.StdEncoding.EncodeToString([]byte("private attachment contents"))
	cases := []struct {
		name, protocol, body string
		images, files, audio int
	}{
		{"chat_image", "chat", `{"messages":[{"role":"user","content":[{"type":"text","text":"describe it"},{"type":"image_url","image_url":{"url":"data:image/png;base64,` + b64 + `"}}]}]}`, 1, 0, 0},
		{"responses_file", "responses", `{"input":[{"role":"user","content":[{"type":"input_text","text":"summarize"},{"type":"input_file","filename":"report.pdf","file_data":"` + b64 + `"}]}]}`, 0, 1, 0},
		{"messages_document", "anthropic", `{"messages":[{"role":"user","content":[{"type":"text","text":"read it"},{"type":"document","source":{"type":"base64","media_type":"application/pdf","data":"` + b64 + `"}}]}]}`, 0, 1, 0},
		{"messages_tool_image", "anthropic", `{"messages":[{"role":"user","content":"inspect screenshot"},{"role":"user","content":[{"type":"tool_result","tool_use_id":"a","content":[{"type":"text","text":"screenshot"},{"type":"image","source":{"type":"base64","media_type":"image/png","data":"` + b64 + `"}}]}]}]}`, 1, 0, 0},
		{"responses_tool_image", "responses", `{"input":[{"role":"user","content":"inspect screenshot"},{"type":"function_call_output","call_id":"a","output":[{"type":"input_image","image_url":"https://example.com/shot.png"}]}]}`, 1, 0, 0},
		{"chat_audio", "chat", `{"messages":[{"role":"user","content":[{"type":"text","text":"transcribe"},{"type":"input_audio","input_audio":{"data":"` + b64 + `","format":"wav"}}]}]}`, 0, 0, 1},
	}
	guard := nativeTestGuard(t, nil)
	defer guard.Close()
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			r, err := NormalizeProtocolRequest(tc.protocol, []byte(tc.body))
			if err != nil {
				t.Fatal(err)
			}
			result, err := (&HTTPPreflightChecker{Endpoint: guard.URL}).Evaluate(context.Background(), r)
			if err != nil || result.Decision != PreflightAllow || result.SanitizedRequest == nil {
				t.Fatalf("%+v %v", result, err)
			}
			out := result.SanitizedRequest
			if !bytesEqualJSON(out.RawPayload, r.RawPayload) {
				t.Fatal("native request content changed")
			}
			if out.Native == nil || out.Native.Images != tc.images || out.Native.Files != tc.files || out.Native.Audio != tc.audio {
				t.Fatalf("media=%+v", out.Native)
			}
			if _, err := splitSemanticInput(*out); err != nil {
				t.Fatal(err)
			}
			classification := classificationFromAssessment(*out, assessment("quick_qa", "simple"))
			if tc.files > 0 {
				for _, m := range FilterCapableModels(classification, DefaultCatalog) {
					if m.Provider != "openai" {
						t.Fatal("file routed to unsupported provider")
					}
				}
			}
		})
	}
}

func TestNativeAttachmentBindingAndTextRedaction(t *testing.T) {
	r, _ := NormalizeProtocolRequest("chat", []byte(`{"messages":[{"role":"user","content":[{"type":"text","text":"password=fixture-secret"},{"type":"image_url","image_url":{"url":"https://example.com/image.png"}}]}]}`))
	guard := nativeTestGuard(t, func(s string) string { return strings.ReplaceAll(s, "fixture-secret", "[REDACTED]") })
	defer guard.Close()
	out, err := (&HTTPPreflightChecker{Endpoint: guard.URL}).Evaluate(context.Background(), r)
	if err != nil || out.Decision != PreflightAllow || strings.Contains(string(out.SanitizedRequest.RawPayload), "fixture-secret") || !strings.Contains(string(out.SanitizedRequest.RawPayload), "https://example.com/image.png") {
		t.Fatal("text redaction or attachment preservation failed")
	}
	tamper := nativeTestGuard(t, func(s string) string { return strings.ReplaceAll(s, "contents excluded", "contents changed") })
	defer tamper.Close()
	out, err = (&HTTPPreflightChecker{Endpoint: tamper.URL}).Evaluate(context.Background(), r)
	if err != nil || out.Decision != PreflightBlock || out.SanitizedRequest != nil {
		t.Fatal("modified native binding accepted")
	}
}

func TestNativeImageModelsAndFileUploadRemainSDKCompatible(t *testing.T) {
	guard := nativeTestGuard(t, nil)
	defer guard.Close()
	calls := 0
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.UserAgent() != "native-sdk-fixture/1" || r.Header.Get("Authorization") != "Bearer fixture" {
			t.Error("identity or UA lost")
		}
		if r.URL.Path == "/v1/files" {
			if err := r.ParseMultipartForm(1 << 20); err != nil {
				t.Error(err)
				return
			}
			file, header, err := r.FormFile("file")
			if err != nil {
				t.Error(err)
				return
			}
			defer file.Close()
			b, _ := io.ReadAll(file)
			if string(b) != "private attachment contents" || header.Filename != "fixture.txt" || r.FormValue("purpose") != "user_data" {
				t.Error("native upload changed")
			}
			io.WriteString(w, `{"id":"file-fixture","object":"file"}`)
			return
		}
		var body map[string]any
		_ = json.NewDecoder(r.Body).Decode(&body)
		if body["model"] != ImageFlare || body["reasoning_effort"] != nil {
			t.Error("wrong image model or text effort leaked")
		}
		w.Header().Set("X-Request-ID", "image-provider-fixture")
		w.Header().Set("X-Client-Request-ID", "billing-attempt-fixture")
		io.WriteString(w, `{"created":1,"data":[{"b64_json":"fixture"}],"usage":{"input_tokens":2,"input_tokens_details":{"cached_tokens":0},"output_tokens":3}}`)
	}))
	defer upstream.Close()
	gateway := NewAutoGateway()
	pipeline := &Pipeline{Gateway: gateway, Preflight: &HTTPPreflightChecker{Endpoint: guard.URL}}
	usagePath := filepath.Join(t.TempDir(), "usage.jsonl")
	usageSink, err := NewJSONLUsageSink(usagePath)
	if err != nil {
		t.Fatal(err)
	}
	pipeline.UsageSink = usageSink
	server := &HTTPServer{Gateway: gateway, Pipeline: pipeline, NativeAPI: &NativeAPI{BaseURL: upstream.URL}}
	makeRequest := func(path, kind string, body io.Reader) *httptest.ResponseRecorder {
		r := httptest.NewRequest("POST", path, body)
		r.Header.Set("Content-Type", kind)
		r.Header.Set("Authorization", "Bearer fixture")
		r.Header.Set("User-Agent", "native-sdk-fixture/1")
		w := httptest.NewRecorder()
		server.ServeHTTP(w, r)
		return w
	}
	w := makeRequest("/v1/images/generations", "application/json", strings.NewReader(`{"prompt":"a blue square","model":"auto","reasoning_effort":"high"}`))
	if w.Code != 200 {
		t.Fatalf("%d %s", w.Code, w.Body.String())
	}
	usageRaw, err := os.ReadFile(usagePath)
	if err != nil {
		t.Fatal(err)
	}
	var event UsageEvent
	if json.Unmarshal(usageRaw, &event) != nil || event.UpstreamRequestID != "image-provider-fixture" || event.UpstreamClientRequestID != "billing-attempt-fixture" || event.InputTokens != 2 || event.CacheMissTokens != 2 || event.OutputTokens != 3 || !event.UsageReported {
		t.Fatalf("image reconciliation metadata missing: %+v", event)
	}
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	_ = writer.WriteField("purpose", "user_data")
	file, _ := writer.CreateFormFile("file", "fixture.txt")
	_, _ = io.WriteString(file, "private attachment contents")
	writer.Close()
	w = makeRequest("/v1/files", writer.FormDataContentType(), &body)
	if w.Code != 200 {
		t.Fatalf("%d %s", w.Code, w.Body.String())
	}
	w = makeRequest("/v1/images/generations", "application/json", strings.NewReader(`{"prompt":"a square","model":"unapproved-image-model"}`))
	if w.Code != 400 || calls != 2 {
		t.Fatal("unapproved image model reached upstream")
	}
}

func TestNativeEndpointsFailClosedBeforeUpstream(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { t.Error("Guard failure reached upstream") }))
	defer upstream.Close()
	gateway := NewAutoGateway()
	s := &HTTPServer{Gateway: gateway, Pipeline: &Pipeline{Gateway: gateway}, NativeAPI: &NativeAPI{BaseURL: upstream.URL}}
	r := httptest.NewRequest("POST", "/v1/images/generations", strings.NewReader(`{"prompt":"fixture"}`))
	r.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	s.ServeHTTP(w, r)
	if w.Code != 503 {
		t.Fatalf("status=%d", w.Code)
	}
}

func TestClassifierReceivesNativeMediaOnlyAfterBoundTextGuard(t *testing.T) {
	guard := nativeTestGuard(t, nil)
	defer guard.Close()
	r, _ := NormalizeProtocolRequest("responses", []byte(`{"input":[{"role":"user","content":[{"type":"input_text","text":"describe"},{"type":"input_image","image_url":"https://example.com/image.png"}]}]}`))
	preflight, err := (&HTTPPreflightChecker{Endpoint: guard.URL}).Evaluate(context.Background(), r)
	if err != nil {
		t.Fatal(err)
	}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		b, _ := io.ReadAll(r.Body)
		if r.URL.Path != "/responses" || !strings.Contains(string(b), `"type":"input_image"`) || !strings.Contains(string(b), "https://example.com/image.png") {
			t.Error("classifier lost native attachment")
		}
		value, _ := json.Marshal(assessment("quick_qa", "simple"))
		_ = json.NewEncoder(w).Encode(map[string]any{"id": "fixture", "model": "gpt-5.6-luna", "status": "completed", "output": []any{map[string]any{"content": []any{map[string]any{"type": "output_text", "text": string(value)}}}}, "usage": map[string]any{"input_tokens": 12, "output_tokens": 20}})
	}))
	defer server.Close()
	c := &SemanticClassifier{Endpoint: server.URL + "/chat/completions", Model: "gpt-5.6-luna", ReviewerModel: "gpt-5.6-sol"}
	classification, err := c.Classify(context.Background(), *preflight.SanitizedRequest, PipelineMeta{})
	if err != nil || !classification.HasImage {
		t.Fatal("native classifier failed", err)
	}
}

func TestResponsesLargeImageSSECompletesWithoutDroppingBytes(t *testing.T) {
	image := strings.Repeat("A", 2<<20)
	data := "data: {\"type\":\"response.completed\",\"response\":{\"id\":\"fixture\",\"model\":\"gpt-5.6-luna\",\"output\":[{\"type\":\"image_generation_call\",\"result\":\"" + image + "\"}]}}\n\n"
	observer := &observedSSEBody{ReadCloser: io.NopCloser(strings.NewReader(data)), MaxEventBytes: 128 << 20}
	got, err := io.ReadAll(observer)
	if err != nil || string(got) != data || !observer.Complete || observer.Invalid {
		t.Fatal("large native image stream lost completion")
	}
}

func TestResponsesImageToolSelectsOpenAIAndPreservesResult(t *testing.T) {
	r, err := NormalizeProtocolRequest("responses", []byte(`{"input":"draw a blue square","tools":[{"type":"image_generation"}]}`))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(r.RawPayload), ImageFlare) {
		t.Fatal("image tool missing default")
	}
	c := classificationFromAssessment(r, assessment("quick_qa", "simple"))
	for _, m := range FilterCapableModels(c, DefaultCatalog) {
		if m.Provider != "openai" {
			t.Fatal("image tool routed to non-OpenAI model")
		}
	}
	_, err = NormalizeProtocolRequest("responses", []byte(`{"input":"draw","tools":[{"type":"image_generation","model":"unknown"}]}`))
	if err == nil {
		t.Fatal("unapproved image tool model accepted")
	}
	stream := "data: {\"type\":\"response.completed\",\"response\":{\"id\":\"r\",\"model\":\"gpt-5.6-luna\",\"status\":\"completed\",\"output\":[{\"type\":\"image_generation_call\",\"id\":\"img\",\"status\":\"completed\",\"result\":\"native-base64\"}]}}\n\n"
	b, err := aggregateSSE(context.Background(), "responses", strings.NewReader(stream), 1<<20)
	if err != nil || !strings.Contains(string(b), "native-base64") {
		t.Fatal("image output lost", err)
	}
}
