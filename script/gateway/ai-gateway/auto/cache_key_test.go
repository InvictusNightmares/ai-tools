package autogateway

import "testing"

func TestResponseCacheKeySeparatesEffectiveModelEffortAndRequest(t *testing.T) {
	base := []string{"secret", "tokyo", "openai", "deepseek-flash", "rev-1", "key-1", "client-a", RequestDigest([]byte(`{"messages":[{"content":"hello"}]}`))}
	first, err := ResponseCacheKey(base[0], base[1], base[2], base[3], ReasoningNone, base[4], base[5], base[6], base[7])
	if err != nil {
		t.Fatal(err)
	}
	same, _ := ResponseCacheKey(base[0], base[1], base[2], base[3], ReasoningNone, base[4], base[5], base[6], base[7])
	otherModel, _ := ResponseCacheKey(base[0], base[1], base[2], "gpt-6-astra", ReasoningNone, base[4], base[5], base[6], base[7])
	otherEffort, _ := ResponseCacheKey(base[0], base[1], base[2], base[3], ReasoningHigh, base[4], base[5], base[6], base[7])
	otherRequest, _ := ResponseCacheKey(base[0], base[1], base[2], base[3], ReasoningNone, base[4], base[5], base[6], RequestDigest([]byte(`{"messages":[{"content":"goodbye"}]}`)))
	if first != same || first == otherModel || first == otherEffort || first == otherRequest {
		t.Fatal("response cache key isolation failed")
	}
}
