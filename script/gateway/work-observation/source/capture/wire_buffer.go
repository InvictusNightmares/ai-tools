package capture

import "sync"

type wireBuffer struct {
	data []byte
	pool int
}
type wirePool struct {
	size int
	pool sync.Pool
}

var wirePools = []wirePool{{size: 1024}, {size: 4096}, {size: 32768}, {size: 65536}}

func wireBufferSize(n int) (int, int) {
	for i := range wirePools {
		if n <= wirePools[i].size {
			return wirePools[i].size, i
		}
	}
	return n, -1
}

func copyWireBuffer(p []byte, size, index int) *wireBuffer {
	var result *wireBuffer
	if index >= 0 {
		result, _ = wirePools[index].pool.Get().(*wireBuffer)
	}
	if result == nil {
		result = &wireBuffer{data: make([]byte, size), pool: index}
	}
	copy(result.data, p)
	return result
}

func releaseWireBuffer(buffer *wireBuffer) {
	if buffer != nil && buffer.pool >= 0 {
		wirePools[buffer.pool].pool.Put(buffer)
	}
}
