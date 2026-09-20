package autogateway

type Capability string

const (
	CapabilityText             Capability = "text"
	CapabilityCode             Capability = "code"
	CapabilityTools            Capability = "tools"
	CapabilityStream           Capability = "stream"
	CapabilityVision           Capability = "vision"
	CapabilityStructured       Capability = "structured"
	CapabilityLongContext      Capability = "long_context"
	CapabilityFiles            Capability = "files"
	CapabilityAudio            Capability = "audio"
	CapabilityImageGeneration  Capability = "image_generation"
	CapabilityCompaction       Capability = "compaction"
	CapabilityLocalToolHistory Capability = "local_tool_history"
)

type Model struct {
	Name                string
	Provider            string
	Tier                int
	Capabilities        []Capability
	Intents             []string
	ReasoningEfforts    []ReasoningEffort
	ContextWindowTokens int
	MaxInputTokens      int
	MaxOutputTokens     int
}

// DeepSeek's native levels; compatibility aliases are mapped explicitly.
var deepseekReasoningEfforts = []ReasoningEffort{ReasoningNone, ReasoningLow, ReasoningHigh, ReasoningMax}

// Verified 2026-09-15 against official model pages. Regional proxy
// acceptance is additionally checked by the real API capability probe.
var gpt56ReasoningEfforts = []ReasoningEffort{ReasoningNone, ReasoningLow, ReasoningMedium, ReasoningHigh, ReasoningXHigh, ReasoningMax}
var astraReasoningEfforts = []ReasoningEffort{ReasoningLow, ReasoningMedium, ReasoningHigh, ReasoningXHigh, ReasoningMax}

var DefaultCatalog = []Model{
	{Name: "deepseek-flash", Provider: "deepseek", Tier: 0, Capabilities: []Capability{CapabilityText, CapabilityCode, CapabilityTools, CapabilityStream, CapabilityVision}, Intents: []string{"quick_qa", "translation", "formatting", "coding", "debugging"}, ReasoningEfforts: deepseekReasoningEfforts, ContextWindowTokens: 1000000, MaxInputTokens: 1000000, MaxOutputTokens: 384000},
	{Name: "gpt-5.6-luna", Provider: "openai", Tier: 1, Capabilities: []Capability{CapabilityText, CapabilityCode, CapabilityTools, CapabilityStream, CapabilityVision, CapabilityFiles, CapabilityCompaction, CapabilityImageGeneration, CapabilityStructured, CapabilityLocalToolHistory}, Intents: []string{"quick_qa", "translation", "formatting", "coding", "debugging"}, ReasoningEfforts: gpt56ReasoningEfforts, ContextWindowTokens: 1050000, MaxInputTokens: 922000, MaxOutputTokens: 128000},
	{Name: "gpt-5.6-terra", Provider: "openai", Tier: 2, Capabilities: []Capability{CapabilityText, CapabilityCode, CapabilityTools, CapabilityStream, CapabilityVision, CapabilityFiles, CapabilityCompaction, CapabilityImageGeneration, CapabilityStructured, CapabilityLongContext, CapabilityLocalToolHistory}, Intents: []string{"coding", "debugging", "architecture", "agent"}, ReasoningEfforts: gpt56ReasoningEfforts, ContextWindowTokens: 1050000, MaxInputTokens: 922000, MaxOutputTokens: 128000},
	{Name: "gpt-5.6-sol", Provider: "openai", Tier: 3, Capabilities: []Capability{CapabilityText, CapabilityCode, CapabilityTools, CapabilityStream, CapabilityVision, CapabilityFiles, CapabilityCompaction, CapabilityImageGeneration, CapabilityStructured, CapabilityLongContext, CapabilityLocalToolHistory}, Intents: []string{"coding", "debugging", "architecture", "agent", "reasoning"}, ReasoningEfforts: gpt56ReasoningEfforts, ContextWindowTokens: 1050000, MaxInputTokens: 922000, MaxOutputTokens: 128000},
	{Name: "gpt-6-astra", Provider: "openai", Tier: 4, Capabilities: []Capability{CapabilityText, CapabilityCode, CapabilityTools, CapabilityStream, CapabilityVision, CapabilityFiles, CapabilityCompaction, CapabilityImageGeneration, CapabilityStructured, CapabilityLongContext, CapabilityLocalToolHistory}, Intents: []string{"coding", "debugging", "architecture", "agent", "reasoning"}, ReasoningEfforts: astraReasoningEfforts, ContextWindowTokens: 1050000, MaxInputTokens: 922000, MaxOutputTokens: 128000},
}

func ModelByName(name string, catalog []Model) *Model {
	for i := range catalog {
		if catalog[i].Name == name {
			return &catalog[i]
		}
	}
	return nil
}
