package autogateway

import (
	"context"
	"io"
	"sync"
	"testing"
)

type memoryDuplex struct {
	mu     sync.Mutex
	data   []byte
	offset int
	closed bool
}

func (d *memoryDuplex) Read(output []byte) (int, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	if d.offset >= len(d.data) {
		return 0, io.EOF
	}
	n := copy(output, d.data[d.offset:])
	d.offset += n
	return n, nil
}

func (d *memoryDuplex) Write(input []byte) (int, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.data = append(d.data, input...)
	return len(input), nil
}

func (d *memoryDuplex) Close() error { d.mu.Lock(); d.closed = true; d.mu.Unlock(); return nil }

func (d *memoryDuplex) isClosed() bool { d.mu.Lock(); defer d.mu.Unlock(); return d.closed }

func TestRelayDuplexClosesBothSidesAtTurnEnd(t *testing.T) {
	client := &memoryDuplex{}
	upstream := &memoryDuplex{}
	upstream.data = []byte("provider-frame")
	if err := RelayDuplex(context.Background(), client, upstream); err != nil {
		t.Fatal(err)
	}
	if !client.isClosed() || !upstream.isClosed() {
		t.Fatal("relay did not close both connections")
	}
}

func TestRelayDuplexRejectsMissingConnection(t *testing.T) {
	if err := RelayDuplex(context.Background(), nil, &memoryDuplex{}); err == nil {
		t.Fatal("missing client accepted")
	}
}
