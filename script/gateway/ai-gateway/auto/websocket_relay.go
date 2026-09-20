package autogateway

import (
	"context"
	"errors"
	"io"
	"sync"
)

// DuplexConn is the minimal seam required by a WebSocket adapter. The actual
// websocket library remains at the edge so this core module has no vendor or
// protocol-specific dependency.
type DuplexConn interface {
	io.ReadWriteCloser
}

// RelayDuplex copies frames represented by the adapter's Read/Write methods in
// both directions. Either side ending or the request context being cancelled
// closes both connections, preventing a half-open model turn from surviving
// after the client disconnects. Model selection must happen before this call.
func RelayDuplex(ctx context.Context, client, upstream DuplexConn) error {
	if client == nil || upstream == nil {
		return errors.New("duplex_connection_missing")
	}
	result := make(chan error, 2)
	var once sync.Once
	closeBoth := func() {
		once.Do(func() {
			_ = client.Close()
			_ = upstream.Close()
		})
	}
	copyDirection := func(destination io.Writer, source io.Reader) {
		_, err := io.Copy(destination, source)
		result <- err
		closeBoth()
	}
	go copyDirection(upstream, client)
	go copyDirection(client, upstream)
	select {
	case err := <-result:
		closeBoth()
		if err != nil && !errors.Is(err, io.ErrClosedPipe) {
			return err
		}
		return nil
	case <-ctx.Done():
		closeBoth()
		return ctx.Err()
	}
}
