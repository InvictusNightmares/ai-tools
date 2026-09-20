package autogateway

type NormalizedUsage struct {
	PromptTokens      int
	CacheHitTokens    int
	CacheMissTokens   int
	CompletionTokens  int
	CacheStatus       string
	HasPromptTokens   bool
	HasCacheHitTokens bool
}

type Pricing struct{ InputMiss, InputHit, Output float64 }

func number(value any) (int, bool) {
	switch item := value.(type) {
	case int:
		return item, true
	case int64:
		return int(item), true
	case float64:
		return int(item), true
	default:
		return 0, false
	}
}

func NormalizeUsage(usage map[string]any) NormalizedUsage {
	result := NormalizedUsage{CacheStatus: "unknown"}
	if value, ok := number(usage["input_tokens"]); ok {
		result.PromptTokens = value
		result.HasPromptTokens = true
	}
	if value, ok := number(usage["output_tokens"]); ok {
		result.CompletionTokens = value
	}
	if value, ok := number(usage["cache_read_input_tokens"]); ok {
		result.CacheHitTokens = value
		result.PromptTokens += value
		if write, ok := number(usage["cache_creation_input_tokens"]); ok {
			result.PromptTokens += write
		}
		result.HasCacheHitTokens = true
	}
	if details, ok := usage["input_tokens_details"].(map[string]any); ok {
		if value, ok := number(details["cached_tokens"]); ok {
			result.CacheHitTokens = value
			result.HasCacheHitTokens = true
		}
	}
	if value, ok := number(usage["prompt_tokens"]); ok {
		result.PromptTokens, result.HasPromptTokens = value, true
	}
	if value, ok := number(usage["completion_tokens"]); ok {
		result.CompletionTokens = value
	}
	if value, ok := number(usage["prompt_cache_hit_tokens"]); ok {
		result.CacheHitTokens, result.HasCacheHitTokens = value, true
	}
	if value, ok := number(usage["cached_tokens"]); ok {
		result.CacheHitTokens, result.HasCacheHitTokens = value, true
	}
	if details, ok := usage["prompt_tokens_details"].(map[string]any); ok {
		if value, exists := number(details["cached_tokens"]); exists {
			result.CacheHitTokens, result.HasCacheHitTokens = value, true
		}
	}
	if value, ok := number(usage["prompt_cache_miss_tokens"]); ok {
		result.CacheMissTokens = value
	} else if result.HasPromptTokens && result.HasCacheHitTokens {
		result.CacheMissTokens = result.PromptTokens - result.CacheHitTokens
	}
	if result.CacheMissTokens < 0 {
		result.CacheMissTokens = 0
	}
	if result.HasCacheHitTokens {
		if result.CacheHitTokens > 0 {
			result.CacheStatus = "hit"
		} else {
			result.CacheStatus = "miss"
		}
	}
	return result
}

func EstimateCost(usage map[string]any, pricing Pricing) (NormalizedUsage, float64, string) {
	normalized := NormalizeUsage(usage)
	if pricing.InputMiss == 0 && pricing.InputHit == 0 && pricing.Output == 0 {
		return normalized, 0, "unknown_pricing"
	}
	miss := normalized.CacheMissTokens
	if !normalized.HasCacheHitTokens && normalized.HasPromptTokens {
		miss = normalized.PromptTokens
	}
	cost := (float64(miss)*pricing.InputMiss + float64(normalized.CacheHitTokens)*pricing.InputHit + float64(normalized.CompletionTokens)*pricing.Output) / 1_000_000
	status := "observed"
	if normalized.CacheStatus == "unknown" {
		status = "conservative"
	}
	return normalized, cost, status
}
