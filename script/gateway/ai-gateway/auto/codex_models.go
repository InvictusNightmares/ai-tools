package autogateway

import _ "embed"

// Keep the default instructions identical to Codex CLI 0.154.0's unknown-model
// fallback. Serving a descriptor without them would replace the client's
// native agent instructions with an empty string. See third_party/README.md.
//
//go:embed codex_prompt.md
var codexDefaultInstructions string

// Codex's /models wrapper differs from the standard OpenAI /v1/models list.
// Return both wrappers; existing SDKs continue to read data. Guardian policy is
// deliberately absent so local/admin approval controls retain their authority.
func codexModelDescriptors(publicModel string) []map[string]any {
	result := []map[string]any{}
	for _, name := range []string{publicModel, ActionReviewModel} {
		item := map[string]any{
			"slug": name, "display_name": name, "description": "Automatic model selection with input Guard",
			"default_reasoning_level": "low", "supported_reasoning_levels": []map[string]string{{"effort": "low", "description": "Auto selects the effective reasoning level for each task."}},
			"shell_type": "unified_exec", "visibility": "list", "supported_in_api": true, "priority": 0,
			"availability_nux": nil, "upgrade": nil, "support_verbosity": false, "default_verbosity": nil,
			"apply_patch_tool_type": nil, "truncation_policy": map[string]any{"mode": "bytes", "limit": 10000},
			"context_window": 1000000, "max_context_window": 1000000, "effective_context_window_percent": 90,
			"experimental_supported_tools": []string{}, "input_modalities": []string{"text", "image"},
			"include_apps_usage_instructions": false, "base_instructions": codexDefaultInstructions,
		}
		if name == ActionReviewModel {
			item["visibility"] = "hide"
			item["shell_type"] = "disabled"
			item["description"] = "Dedicated Codex action review"
			item["priority"] = 1
		}
		result = append(result, item)
	}
	return result
}
