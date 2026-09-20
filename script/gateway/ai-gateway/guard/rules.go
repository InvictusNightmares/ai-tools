package gocheck

import (
	"regexp"
	"strings"
)

var (
	secretMarker      = regexp.MustCompile(`(?i)(api[_ -]?key|access[_ -]?token|bearer\s+[a-z0-9._-]+|client_secret|password)`)                                            // signal only
	cyberActionMarker = regexp.MustCompile(`(?i)(exfiltrat|steal|dump|persistence|ransomware|credential\s+(?:theft|dump)|bypass\s+(?:edr|av|detection)|破坏|窃取凭据|绕过检测|持久化)`) // signal only
	cyberTargetMarker = regexp.MustCompile(`(?i)(production|真实站点|线上服务器|目标主机|specific host|外网主机|真实账号)`)                                                                     // signal only
	executableMarker  = regexp.MustCompile("(?i)(```|curl\\s|wget\\s|powershell|bash\\s|python\\s+-c|chmod\\s+\\+x|tool call|function call|工具调用)")                         // signal only
	evasionMarker     = regexp.MustCompile(`(?i)(without detection|hide|obfuscat|绕过|隐藏行为|规避审计)`)                                                                           // signal only
)

func evaluateSafetyRules(input SafetyInput, secretPresent, secretUse bool) SafetyDecisionResult {
	text := normalizedSafetyText(input)
	result := SafetyDecisionResult{Decision: SafetyAllow, RiskLevel: RiskLow, Confidence: 0.99}
	if secretPresent && secretUse {
		result.Decision, result.RiskLevel, result.Confidence = SafetyBlock, RiskHigh, 0.99
		result.Categories = []string{"credential"}
		result.ReasonCodes = append(result.ReasonCodes, "secret_input_not_allowed")
		return result
	}
	if secretMarker.MatchString(text) && (cyberActionMarker.MatchString(text) || executableMarker.MatchString(text)) {
		result.ReasonCodes = append(result.ReasonCodes, "credential_context_review")
	}
	cyberSignals := 0
	for _, marker := range []*regexp.Regexp{cyberActionMarker, cyberTargetMarker, executableMarker, evasionMarker} {
		if marker.MatchString(text) {
			cyberSignals++
		}
	}
	// These are ambiguous context markers, not a determination of intent.
	// Ordinary logout/release code contains persistence, production and code
	// fences. Always obtain Guard's verdict; its unsafe/controversial verdict
	// and unavailability still block before any external model is called.
	if cyberSignals >= 2 {
		result.ReasonCodes = append(result.ReasonCodes, "cyber_context_review")
	}
	if strings.Contains(strings.ToLower(text), "ignore previous instructions") || strings.Contains(text, "忽略之前的指令") {
		result.ReasonCodes = append(result.ReasonCodes, "prompt_injection_signal")
	}
	return result
}

func maxRisk(left, right RiskLevel) RiskLevel {
	if riskRank(right) > riskRank(left) {
		return right
	}
	return left
}

func riskRank(level RiskLevel) int {
	switch level {
	case RiskHigh:
		return 3
	case RiskMedium:
		return 2
	case RiskLow:
		return 1
	default:
		return 0
	}
}

func appendUnique(values []string, additions ...string) []string {
	seen := make(map[string]struct{}, len(values)+len(additions))
	result := make([]string, 0, len(values)+len(additions))
	for _, value := range append(values, additions...) {
		if value == "" {
			continue
		}
		if _, ok := seen[value]; ok {
			continue
		}
		seen[value] = struct{}{}
		result = append(result, value)
	}
	return result
}
