package guarddeployment

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"unicode/utf8"

	goCheck "local/ai-gateway/guard"
)

func TestReadableFieldsKeepJSONOrderUnknownValuesAndPrecision(t *testing.T) {
	input := goCheck.SafetyInput{ProviderPayload: `{"z":"first\nline","n":9007199254740993,"a":[true,null,{},[],"中间风险"],"z":"duplicate-key"}`,
		Metadata: map[string]string{"custom": "metadata marker"}, Tools: []goCheck.SafetyTool{{Name: "tool", Schema: "schema marker"}}}
	fields, err := readableInputFields(input)
	if err != nil {
		t.Fatal(err)
	}
	if fields[0].text != "first\nline" || fields[1].text != "9007199254740993" || fields[7].text != "duplicate-key" {
		t.Fatal("JSON order, decoded strings, duplicate fields or integer precision changed", fields)
	}
	var values []string
	for _, field := range fields {
		values = append(values, field.text)
	}
	for _, want := range []string{"true", "null", "{}", "[]", "中间风险", "metadata marker", "schema marker"} {
		if !strings.Contains(strings.Join(values, "\n"), want) {
			t.Fatal("missing field", want)
		}
	}
	for _, raw := range []string{`{"x":`, `{} {}`, strings.Repeat(`{"x":`, 258) + `0` + strings.Repeat(`}`, 258)} {
		if _, err := readableInputFields(goCheck.SafetyInput{ProviderPayload: raw}); err == nil {
			t.Fatal("invalid or excessive structure accepted")
		}
	}
}

func TestTokenBudgetKeepsCompleteInputAndChecksEveryOversizedPart(t *testing.T) {
	for _, large := range []bool{false, true} {
		t.Run(map[bool]string{false: "complete_context", true: "split_context"}[large], func(t *testing.T) {
			var inspected []string
			var counted []string
			modelLen := 32768
			if large {
				modelLen = 4096
			}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var body struct {
					Messages []chatMessage `json:"messages"`
				}
				if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
					t.Error(err)
					return
				}
				content := body.Messages[0].Content
				if !utf8.ValidString(content) {
					t.Error("split damaged Unicode")
				}
				if r.URL.Path == "/tokenize" {
					counted = append(counted, content)
					count := len([]rune(content))
					if !large {
						count /= 4
					}
					json.NewEncoder(w).Encode(map[string]int{"count": count + 32, "max_model_len": modelLen})
					return
				}
				inspected = append(inspected, content)
				label := "Safety: Safe\nCategories: None"
				if strings.Contains(content, "UNSAFE-MIDDLE-SENTINEL") {
					label = "Safety: Unsafe\nCategories: Non-violent Illegal Acts"
				}
				json.NewEncoder(w).Encode(map[string]any{"choices": []any{map[string]any{"message": chatMessage{Role: "assistant", Content: label}}}})
			}))
			defer server.Close()
			text := "BEGIN" + strings.Repeat("合成内容", 5000) + "UNSAFE-MIDDLE-SENTINEL" + strings.Repeat("More", 5000) + "END"
			input := goCheck.SafetyInput{Messages: []goCheck.SafetyMessage{{Role: "user", Content: text}}}
			client := HTTPModelClient{Endpoint: server.URL + "/v1/chat/completions", TokenizerEndpoint: server.URL + "/tokenize", Model: "qwen"}
			verdict, err := client.Classify(context.Background(), input)
			if err != nil || verdict.Decision != goCheck.SafetyBlock {
				t.Fatal("unsafe middle lost", verdict, err)
			}
			if !large && len(inspected) != 1 {
				t.Fatal("input within actual token limit was prematurely split")
			}
			if large && len(inspected) < 2 {
				t.Fatal("oversized input not split")
			}
			var recovered strings.Builder
			for _, content := range inspected {
				if large && len([]rune(content))+32 > modelLen-320 {
					t.Fatal("model token budget exceeded")
				}
				if _, value, ok := strings.Cut(content, `$["messages"][0]["content"]:`+"\n"); ok {
					recovered.WriteString(strings.TrimSuffix(value, "\n"))
				}
			}
			if !large && recovered.String() != text {
				t.Fatal("full original string not covered exactly")
			}
			if large && (len(recovered.String()) < len(text) || !strings.HasPrefix(recovered.String(), "BEGIN") || !strings.HasSuffix(recovered.String(), "END")) {
				t.Fatal("overlapping fragments lost input boundaries or coverage")
			}
			if len(counted) == 0 {
				t.Fatal("tokenizer not used")
			}
		})
	}
}

func TestTokenizerFailuresNeverCallSafetyModel(t *testing.T) {
	for _, response := range []string{"unavailable", `{}`, `{"count":0,"max_model_len":32768}`, `{"count":2,"max_model_len":128}`, `{"count":2,"max_model_len":9999999}`} {
		t.Run(response, func(t *testing.T) {
			modelCalls := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/tokenize" {
					modelCalls++
					return
				}
				if response == "unavailable" {
					w.WriteHeader(503)
				}
				w.Write([]byte(response))
			}))
			defer server.Close()
			client := HTTPModelClient{Endpoint: server.URL + "/v1/chat/completions", TokenizerEndpoint: server.URL + "/tokenize", Model: "qwen"}
			_, err := client.Classify(context.Background(), goCheck.SafetyInput{Messages: []goCheck.SafetyMessage{{Role: "user", Content: "normal fixture"}}})
			if err == nil || modelCalls != 0 {
				t.Fatal("tokenizer failure did not fail closed")
			}
		})
	}
}
