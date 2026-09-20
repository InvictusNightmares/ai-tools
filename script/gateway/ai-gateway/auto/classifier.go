package autogateway

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

type Message struct {
	Role       string
	Content    string
	Parts      []ContentPart
	ToolCalls  json.RawMessage `json:"tool_calls,omitempty"`
	ToolCallID string          `json:"tool_call_id,omitempty"`
}

type ContentPart struct {
	Type string
	Text string
	Raw  []byte
}

type Tool struct {
	Name        string
	Schema      string
	Description string
}

type Request struct {
	CompactionTrigger bool         `json:"compaction_trigger,omitempty"`
	CompactionState   bool         `json:"compaction_state,omitempty"`
	Native            *NativeMedia `json:"native_media,omitempty"`
	Messages          []Message
	Tools             []Tool
	ResponseFormat    bool
	OutputFormat      string `json:"output_format,omitempty"`
	Stream            bool
	// Canonical provider body with client routing parameters removed. It is
	// included in response-cache digests but never in telemetry.
	RawPayload json.RawMessage `json:"provider_payload,omitempty"`
	Protocol   string          `json:"protocol,omitempty"`
}

type ClassifierTrace struct {
	ToolBindingReused         bool   `json:"tool_binding_reused,omitempty"`
	ReviewerChangedComplexity bool   `json:"reviewer_changed_complexity,omitempty"`
	PrimaryModel              string `json:"primary_model,omitempty"`
	PrimaryValid              bool   `json:"primary_valid"`
	ReviewerModel             string `json:"reviewer_model,omitempty"`
	Reviewed                  bool   `json:"reviewed"`
	DecisionModel             string `json:"decision_model,omitempty"`
	PrimaryComplexityRetained bool   `json:"primary_complexity_retained,omitempty"`
	CacheHit                  bool   `json:"cache_hit"`
}

type Classification struct {
	ContextBudget            ContextBudget
	Trace                    ClassifierTrace
	Source                   string
	Assessment               *TaskAssessment
	Intent                   string
	InputTokens              int
	MessageCount             int
	ToolCount                int
	HasImage                 bool
	HasStructuredOutput      bool
	LongContext              bool
	RequiredCapabilities     []Capability
	Score                    int
	Confidence               float64
	ReasonCodes              []string
	EffectiveReasoningEffort ReasoningEffort
}

var (
	codeMarker         = regexp.MustCompile("(?i)(```|stack trace|traceback|compile error|typescript|javascript|golang|python|sql|diff|patch|unit test|regression)")
	debugMarker        = regexp.MustCompile(`(?i)(error|exception|failed|failure|bug|crash|timeout|502|503|429|日志|报错|故障|回归)`)
	architectureMarker = regexp.MustCompile(`(?i)(architecture|system design|migration|trade-?off|scalab|架构|迁移|方案|设计)`)
	agentMarker        = regexp.MustCompile(`(?i)(tool call|function call|workflow|agent|multi-?step|工具调用|工作流|多步)`)
)

func ExtractFeatures(request Request) Classification {
	var builder strings.Builder
	hasImage := false
	for _, message := range request.Messages {
		builder.WriteString(message.Content)
		builder.WriteByte('\n')
		for _, part := range message.Parts {
			builder.WriteString(part.Text)
			if part.Type == "image_url" || part.Type == "input_image" {
				hasImage = true
			}
		}
	}
	text := builder.String()
	inputTokens := (len([]rune(text)) + 3) / 4
	hasCode := codeMarker.MatchString(text)
	hasDebug := debugMarker.MatchString(text)
	hasArchitecture := architectureMarker.MatchString(text)
	hasAgent := agentMarker.MatchString(text) || len(request.Tools) > 0
	hasTranslation := strings.Contains(strings.ToLower(text), "translate") || strings.Contains(text, "翻译")
	longContext := inputTokens >= 8000 || len(request.Messages) >= 12

	intent := "quick_qa"
	switch {
	case hasAgent:
		intent = "agent"
	case hasArchitecture:
		intent = "architecture"
	case hasDebug:
		intent = "debugging"
	case hasCode:
		intent = "coding"
	case hasTranslation:
		intent = "translation"
	case request.ResponseFormat:
		intent = "formatting"
	}

	capabilities := []Capability{CapabilityText}
	if request.CompactionTrigger || request.CompactionState {
		capabilities = append(capabilities, CapabilityCompaction)
	}
	addCapability := func(capability Capability) {
		for _, existing := range capabilities {
			if existing == capability {
				return
			}
		}
		capabilities = append(capabilities, capability)
	}
	if hasCode || hasDebug || hasArchitecture {
		addCapability(CapabilityCode)
	}
	if len(request.Tools) > 0 {
		addCapability(CapabilityTools)
	}
	if hasImage {
		addCapability(CapabilityVision)
	}
	if request.ResponseFormat {
		addCapability(CapabilityStructured)
	}
	if request.Stream {
		addCapability(CapabilityStream)
	}
	if longContext {
		addCapability(CapabilityLongContext)
	}

	score := inputTokens/250 + len(request.Messages)*3/2
	if hasCode {
		score += 18
	}
	if hasDebug {
		score += 12
	}
	if hasArchitecture {
		score += 20
	}
	if hasAgent {
		score += 20
	}
	if longContext {
		score += 20
	}
	if request.ResponseFormat {
		score += 8
	}
	if hasImage {
		score += 10
	}
	if hasTranslation {
		score += 15
	}
	if score > 100 {
		score = 100
	}

	reasons := []string{}
	if hasCode {
		reasons = append(reasons, "code_signal")
	}
	if hasDebug {
		reasons = append(reasons, "debug_signal")
	}
	if hasArchitecture {
		reasons = append(reasons, "architecture_signal")
	}
	if hasAgent {
		reasons = append(reasons, "tool_or_agent_signal")
	}
	if longContext {
		reasons = append(reasons, "long_context")
	}
	if hasImage {
		reasons = append(reasons, "image_input")
	}
	if hasTranslation {
		reasons = append(reasons, "translation_signal")
	}
	if request.ResponseFormat {
		reasons = append(reasons, "structured_output")
	}
	confidence := 0.7
	if score < 20 || score > 90 {
		confidence = 0.9
	}
	effort := InferReasoningEffort(score)
	reasons = append(reasons, "auto_reasoning_effort_"+string(effort))
	return Classification{Intent: intent, InputTokens: inputTokens, MessageCount: len(request.Messages), ToolCount: len(request.Tools), HasImage: hasImage, HasStructuredOutput: request.ResponseFormat, LongContext: longContext, RequiredCapabilities: capabilities, Score: score, Confidence: confidence, ReasonCodes: reasons, EffectiveReasoningEffort: effort}
}

func FilterCapableModels(classification Classification, catalog []Model) []Model {
	result := make([]Model, 0, len(catalog))
	for _, model := range catalog {
		capable := true
		for _, required := range classification.RequiredCapabilities {
			found := false
			for _, available := range model.Capabilities {
				if required == available {
					found = true
					break
				}
			}
			if !found {
				capable = false
				break
			}
		}
		if !modelSupportsReasoningEffort(model, classification.EffectiveReasoningEffort) || !modelFitsContext(classification, model) {
			capable = false
		}
		if capable {
			result = append(result, model)
		}
	}
	return result
}

func RankModels(classification Classification, models []Model, health map[string]float64) []Model {
	if classification.Source == semanticPolicyVersion && classification.Assessment != nil {
		return rankTaskModels(classification, models, health)
	}
	result := append([]Model(nil), models...)
	intentFit := func(model Model) float64 {
		for _, intent := range model.Intents {
			if intent == classification.Intent {
				return 1
			}
		}
		return 0.6
	}
	quality := func(model Model) float64 {
		tierTarget := float64(classification.Score) / 25
		tierFit := 1 - 0.08*absFloat(float64(model.Tier)-tierTarget)
		if tierFit < 0 {
			tierFit = 0
		}
		healthScore, ok := health[model.Name]
		if !ok {
			healthScore = 1
		}
		return intentFit(model)*0.55 + tierFit*0.25 + healthScore*0.2
	}
	for i := 0; i < len(result); i++ {
		for j := i + 1; j < len(result); j++ {
			if quality(result[j]) > quality(result[i]) || (quality(result[j]) == quality(result[i]) && result[j].Tier < result[i].Tier) {
				result[i], result[j] = result[j], result[i]
			}
		}
	}
	return result
}

func absFloat(value float64) float64 {
	if value < 0 {
		return -value
	}
	return value
}

func (c Classification) String() string {
	return fmt.Sprintf("%s score=%d confidence=%.2f", c.Intent, c.Score, c.Confidence)
}
