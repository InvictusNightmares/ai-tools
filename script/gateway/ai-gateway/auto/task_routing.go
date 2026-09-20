package autogateway

import "sort"

const taskRoutingPolicy = "task-capability-floor-v2"

func routinePhaseDownshift(c Classification) bool {
	if c.Source != semanticPolicyVersion || c.Assessment == nil {
		return false
	}
	a := *c.Assessment
	if a.TaskType == "quick_qa" && a.Complexity == "simple" && a.Scope == "local" {
		// Apply the same uncertainty/failure/mixed-intent checks as summaries.
		a.TaskType = "summary"
	}
	return routineInformationTask(a)
}

// Model output is validated before this policy runs. A routine label alone is
// insufficient: uncertainty, failures and real reasoning dependencies matter.
func routineInformationTask(a TaskAssessment) bool {
	for _, label := range a.TaskLabels {
		if !oneOf(label, "summary", "extraction", "translation", "formatting", "quick_qa") {
			return false
		}
	}
	return oneOf(a.TaskType, "summary", "extraction", "translation", "formatting") &&
		oneOf(a.Complexity, "simple", "bounded") &&
		oneOf(a.Stage, "understand", "verify", "continue") &&
		a.Uncertainty == "low" && oneOf(a.Verification, "none", "inspection") &&
		a.ReasoningDependencies <= 1 && a.FailedAttempts == 0 && a.Confidence >= 0.9
}

func taskModelFloor(c Classification) int {
	if c.Assessment == nil {
		return 0
	}
	if routineInformationTask(*c.Assessment) {
		return 0
	}
	switch c.Assessment.Complexity {
	case "bounded":
		return 1
	case "multi_step":
		return 2
	case "complex":
		return 3
	case "exceptional":
		return 4
	default:
		return 0
	}
}

// Capability/effort/context filtering precedes this function. Explicit quality
// floors replace the score/25 similarity heuristic. Within the acceptable set,
// prefer a healthy lower-cost tier; never silently fall below the task floor.
// Tier order is the configured candidate preference, not a live price quote.
func rankTaskModels(c Classification, models []Model, health map[string]float64) []Model {
	result := make([]Model, 0, len(models))
	for _, model := range models {
		if model.Tier >= taskModelFloor(c) {
			result = append(result, model)
		}
	}
	state := func(model Model) float64 {
		if value, ok := health[model.Name]; ok {
			return value
		}
		return 1
	}
	sort.SliceStable(result, func(i, j int) bool {
		hi, hj := state(result[i]), state(result[j])
		if (hi >= 0.5) != (hj >= 0.5) {
			return hi >= 0.5
		}
		if result[i].Tier != result[j].Tier {
			return result[i].Tier < result[j].Tier
		}
		return hi > hj
	})
	return result
}
