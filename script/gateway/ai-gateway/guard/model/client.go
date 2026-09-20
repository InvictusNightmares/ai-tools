package guarddeployment

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"sort"
	"strings"
	"time"

	goCheck "local/ai-gateway/guard"
)

// HTTPModelClient calls the private Qwen3Guard endpoint. It sends only the
// sanitized input and never forwards credentials or the raw audit body.
type HTTPModelClient struct {
	OnUsage  func(goCheck.ModelUsage) error
	Endpoint string
	Model    string
	Client   *http.Client
	// MaxChunkChars is a conservative bound below the model token limit. Long
	// inputs are checked in every chunk and their verdicts are aggregated.
	MaxChunkChars int
	// TokenizerEndpoint enables the deployed model's exact chat-template budget.
	// A configured tokenizer failure is an unavailable Guard, never a bypass.
	TokenizerEndpoint string
}

type chatCompletionRequest struct {
	Model       string        `json:"model"`
	Messages    []chatMessage `json:"messages"`
	Temperature float64       `json:"temperature"`
	MaxTokens   int           `json:"max_tokens"`
	Stream      bool          `json:"stream"`
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatCompletionResponse struct {
	Usage struct {
		PromptTokens     *int `json:"prompt_tokens"`
		CompletionTokens int  `json:"completion_tokens"`
		Details          struct {
			CachedTokens int `json:"cached_tokens"`
		} `json:"prompt_tokens_details"`
	} `json:"usage"`
	Choices []struct {
		Message chatMessage `json:"message"`
	} `json:"choices"`
}

func (c *HTTPModelClient) Classify(ctx context.Context, input goCheck.SafetyInput) (goCheck.ModelVerdict, error) {
	if strings.TrimSpace(c.Endpoint) == "" {
		return goCheck.ModelVerdict{}, errors.New("safety model endpoint is required")
	}
	if strings.TrimSpace(c.Model) == "" {
		return goCheck.ModelVerdict{}, errors.New("safety model name is required")
	}
	payload := goCheck.SanitizeInputForModel(input)
	payload.RawBody = nil
	maxChars := c.MaxChunkChars
	if maxChars <= 0 {
		maxChars = 20000
	}
	text := modelInputText(payload)
	if text == "" {
		text = "(empty input)"
	}
	chunks := contextualInputChunks(text, payload.ProviderPayload, maxChars)
	if payload.ProviderPayload == "" && len(chunks) == 1 && len(payload.Messages) == 1 && len(payload.Tools) == 0 && len(payload.Attachments) == 0 && len(payload.Metadata) == 0 {
		chunks = []string{payload.Messages[0].Content}
	}
	if c.TokenizerEndpoint != "" {
		var err error
		chunks, err = c.tokenBoundChunks(ctx, payload)
		if err != nil {
			return goCheck.ModelVerdict{}, err
		}
	}
	combined := goCheck.ModelVerdict{Decision: goCheck.SafetyAllow, RiskLevel: goCheck.RiskLow, Confidence: 1}
	for _, chunk := range chunks {
		verdict, err := c.classifyChunk(ctx, chunk, input)
		if err != nil {
			return goCheck.ModelVerdict{}, err
		}
		if verdict.Decision == goCheck.SafetyBlock {
			combined.Decision = goCheck.SafetyBlock
		}
		if verdict.RiskLevel == goCheck.RiskHigh {
			combined.RiskLevel = goCheck.RiskHigh
		} else if verdict.RiskLevel == goCheck.RiskMedium && combined.RiskLevel == goCheck.RiskLow {
			combined.RiskLevel = goCheck.RiskMedium
		}
		if verdict.Confidence < combined.Confidence {
			combined.Confidence = verdict.Confidence
		}
		combined.Categories = appendUnique(combined.Categories, verdict.Categories...)
		combined.ReasonCodes = appendUnique(combined.ReasonCodes, verdict.ReasonCodes...)
	}
	return combined, nil
}

func (c *HTTPModelClient) classifyChunk(ctx context.Context, content string, input goCheck.SafetyInput) (verdict goCheck.ModelVerdict, resultErr error) {
	event := goCheck.ModelUsage{At: time.Now(), Purpose: "security", RequestID: input.RequestID, Region: input.Region, APIKeyID: input.AccountID, EffectiveModel: c.Model}
	defer func() {
		if !event.Attempt {
			return
		}
		event.Success = resultErr == nil
		if resultErr != nil {
			event.ErrorType = "security_model_failed"
		}
		if c.OnUsage != nil {
			if err := c.OnUsage(event); err != nil {
				verdict = goCheck.ModelVerdict{}
				resultErr = errors.New("security_usage_unavailable")
			}
		}
	}()

	requestBody := chatCompletionRequest{
		Model: c.Model, Temperature: 0, MaxTokens: 256, Stream: false,
		Messages: []chatMessage{{Role: "user", Content: content}},
	}
	body, err := json.Marshal(requestBody)
	if err != nil {
		return goCheck.ModelVerdict{}, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.Endpoint, bytes.NewReader(body))
	if err != nil {
		return goCheck.ModelVerdict{}, err
	}
	req.Header.Set("Content-Type", "application/json")
	client := c.Client
	if client == nil {
		client = http.DefaultClient
	}
	event.Attempt = true
	resp, err := client.Do(req)
	if err != nil {
		return goCheck.ModelVerdict{}, err
	}
	defer resp.Body.Close()
	event.HTTPStatus = resp.StatusCode
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return goCheck.ModelVerdict{}, errors.New("safety model returned non-2xx")
	}
	var completion chatCompletionResponse
	if err := json.NewDecoder(io.LimitReader(resp.Body, 1<<20)).Decode(&completion); err != nil {
		return goCheck.ModelVerdict{}, err
	}
	if completion.Usage.PromptTokens != nil {
		event.InputTokens = *completion.Usage.PromptTokens
		event.UsageReported = true
	}
	event.OutputTokens = completion.Usage.CompletionTokens
	event.CacheHitTokens = completion.Usage.Details.CachedTokens
	event.CacheMissTokens = event.InputTokens - event.CacheHitTokens
	if event.CacheMissTokens < 0 {
		event.CacheMissTokens = 0
	}
	if len(completion.Choices) == 0 {
		return goCheck.ModelVerdict{}, errors.New("safety model returned no choices")
	}
	responseContent := strings.TrimSpace(completion.Choices[0].Message.Content)
	responseContent = strings.TrimPrefix(responseContent, "```json")
	responseContent = strings.TrimPrefix(responseContent, "```")
	responseContent = strings.TrimSuffix(strings.TrimSpace(responseContent), "```")
	return parseGuardVerdict(responseContent)
}

func modelInputText(input goCheck.SafetyInput) string {
	var builder strings.Builder
	builder.WriteString(input.ProviderPayload)
	builder.WriteByte('\n')
	for _, message := range input.Messages {
		builder.WriteString(message.Role)
		builder.WriteString(": ")
		builder.WriteString(message.Content)
		builder.WriteByte('\n')
	}
	for _, tool := range input.Tools {
		builder.WriteString("tool ")
		builder.WriteString(tool.Name)
		builder.WriteString(": ")
		builder.WriteString(tool.Schema)
		builder.WriteByte('\n')
	}
	for _, attachment := range input.Attachments {
		builder.WriteString("attachment ")
		builder.WriteString(attachment.Type)
		builder.WriteString(": ")
		builder.WriteString(attachment.Source)
		builder.WriteByte('\n')
	}
	keys := make([]string, 0, len(input.Metadata))
	for key := range input.Metadata {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		builder.WriteString("metadata ")
		builder.WriteString(key)
		builder.WriteString(": ")
		builder.WriteString(input.Metadata[key])
		builder.WriteByte('\n')
	}
	return strings.TrimSpace(builder.String())
}

func splitRunes(text string, maxChars int) []string {
	runes := []rune(text)
	if len(runes) == 0 {
		return []string{""}
	}
	chunks := make([]string, 0, (len(runes)+maxChars-1)/maxChars)
	for start := 0; start < len(runes); start += maxChars {
		end := start + maxChars
		if end > len(runes) {
			end = len(runes)
		}
		chunks = append(chunks, string(runes[start:end]))
	}
	return chunks
}

func appendUnique(values []string, additions ...string) []string {
	seen := make(map[string]struct{}, len(values)+len(additions))
	for _, value := range values {
		seen[value] = struct{}{}
	}
	for _, value := range additions {
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		values = append(values, value)
	}
	return values
}

func parseGuardVerdict(content string) (goCheck.ModelVerdict, error) {
	lines := strings.Split(content, "\n")
	decisionLine, categoriesLine := "", ""
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(strings.ToLower(line), "safety:") {
			decisionLine = line
		}
		if strings.HasPrefix(strings.ToLower(line), "categories:") {
			categoriesLine = line
		}
	}
	if decisionLine == "" || categoriesLine == "" {
		return goCheck.ModelVerdict{}, errors.New("safety model returned invalid label format")
	}
	label := strings.TrimSpace(decisionLine[strings.Index(decisionLine, ":")+1:])
	verdict := goCheck.ModelVerdict{Confidence: 0.8}
	switch strings.ToLower(label) {
	case "safe":
		verdict.Decision, verdict.RiskLevel, verdict.Confidence = goCheck.SafetyAllow, goCheck.RiskLow, 0.8
	case "unsafe":
		verdict.Decision, verdict.RiskLevel, verdict.Confidence = goCheck.SafetyBlock, goCheck.RiskHigh, 0.9
	case "controversial":
		verdict.Decision, verdict.RiskLevel, verdict.Confidence = goCheck.SafetyBlock, goCheck.RiskMedium, 0.7
	default:
		return goCheck.ModelVerdict{}, errors.New("safety model returned unknown safety label")
	}
	categoryText := strings.TrimSpace(categoriesLine[strings.Index(categoriesLine, ":")+1:])
	if !strings.EqualFold(categoryText, "none") && categoryText != "" {
		for _, category := range strings.Split(categoryText, ",") {
			if category = strings.TrimSpace(category); category != "" {
				verdict.Categories = append(verdict.Categories, category)
			}
		}
	}
	return verdict, nil
}
