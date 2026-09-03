package requestcontent

// invalid_prompt is admitted here only after the upstream observer confirms
// the explicit usage-policy flag; a generic parameter error never reaches us.
func isPolicySignal(code string) bool {
	switch code {
	case "cyber_policy", "content_policy", "content_policy_violation", "invalid_prompt", "content_filter", "structured_refusal":
		return true
	}
	return false
}
