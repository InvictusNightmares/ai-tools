package autogateway

import (
	"encoding/json"
	"errors"
	"reflect"
	"sort"
)

func mergeStreamDelta(target, delta map[string]any) error {
	for key, value := range delta {
		if value == nil {
			continue
		}
		switch v := value.(type) {
		case string:
			if key == "id" || key == "type" || key == "role" {
				if old := textField(target, key); old != "" && old != v {
					return errors.New("upstream_stream_identity_changed")
				}
				target[key] = v
			} else {
				target[key] = textField(target, key) + v
			}
		case []any:
			old, _ := target[key].([]any)
			target[key] = append(old, v...)
		case map[string]any:
			old, _ := target[key].(map[string]any)
			if old == nil {
				old = map[string]any{}
				target[key] = old
			}
			if err := mergeStreamDelta(old, v); err != nil {
				return err
			}
		default:
			if old := target[key]; old != nil && !reflect.DeepEqual(old, value) {
				return errors.New("upstream_stream_conflicting_delta")
			}
			target[key] = value
		}
	}
	return nil
}
func textField(m map[string]any, key string) string { value, _ := m[key].(string); return value }
func eventIndex(m map[string]any) (int, error) {
	n, ok := m["index"].(json.Number)
	if !ok {
		return 0, errors.New("upstream_stream_missing_index")
	}
	i, err := n.Int64()
	if err != nil || i < 0 || i > 1024 {
		return 0, errors.New("upstream_stream_invalid_index")
	}
	return int(i), nil
}
func sortedIndexes[T any](m map[int]T) []int {
	keys := make([]int, 0, len(m))
	for key := range m {
		keys = append(keys, key)
	}
	sort.Ints(keys)
	return keys
}
