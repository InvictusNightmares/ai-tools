//go:build !linux && !darwin

package requestcontent

import "errors"

func availableBytes(string) (uint64, error) { return 0, errors.New("free space check unsupported") }
