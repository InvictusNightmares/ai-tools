package capture

import (
	"bytes"
	"testing"
)

func TestWSDecoderRetainsPartialFrameIndependentlyOfReadBuffer(t *testing.T) {
	body := []byte(`{"type":"response.create","input":"retained literal"}`)
	frame := append([]byte{0x81, byte(len(body))}, body...)
	first := bytes.Clone(frame[:8])
	tail := bytes.Clone(frame[8:])
	decoder := newWSDecoder("", false, 1024)
	var observed []byte
	emit := func(value []byte, _ bool) error { observed = bytes.Clone(value); return nil }
	if err := decoder.feed(first, emit); err != nil {
		t.Fatal(err)
	}
	for i := range first {
		first[i] = 0xff
	}
	if err := decoder.feed(tail, emit); err != nil {
		t.Fatal(err)
	}
	for i := range tail {
		tail[i] = 0xff
	}
	if !bytes.Equal(observed, body) || decoder.held() != 0 {
		t.Fatal("decoder retained reusable transport buffer")
	}
}

func TestWireBufferBudgetUsesCapacityAndCopyIsIndependent(t *testing.T) {
	for _, n := range []int{1, 1025, 4097, 32769, 65537} {
		size, index := wireBufferSize(n)
		if size < n {
			t.Fatal("capacity under-accounted")
		}
		input := bytes.Repeat([]byte{'x'}, n)
		buffer := copyWireBuffer(input, size, index)
		input[0] = 'y'
		if len(buffer.data) != size || buffer.data[0] != 'x' {
			t.Fatal("buffer ownership or size mismatch")
		}
		releaseWireBuffer(buffer)
	}
}
