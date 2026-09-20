package capture

import "sync"

// Observe must take ownership of a copy because the proxy reuses its read
// buffer. Reusing the common read-buffer sizes keeps that ownership copy from
// becoming short-lived garbage on every streamed chunk.
var captureChunkPools = [...]struct {
	size int
	pool sync.Pool
}{
	{size: 4096},
	{size: 32768},
	{size: 131072},
	{size: 1048576},
}

func cloneCaptureChunk(p []byte) []byte {
	for i := range captureChunkPools {
		if len(p) > captureChunkPools[i].size {
			continue
		}
		if b, ok := captureChunkPools[i].pool.Get().([]byte); ok && cap(b) >= captureChunkPools[i].size {
			b = b[:len(p)]
			copy(b, p)
			return b
		}
		b := make([]byte, captureChunkPools[i].size)
		b = b[:len(p)]
		copy(b, p)
		return b
	}
	b := make([]byte, len(p))
	copy(b, p)
	return b
}

func releaseCaptureChunks(chunks [][]byte) {
	for _, b := range chunks {
		capB := cap(b)
		for i := range captureChunkPools {
			if capB == captureChunkPools[i].size {
				captureChunkPools[i].pool.Put(b[:captureChunkPools[i].size])
				break
			}
		}
	}
}
