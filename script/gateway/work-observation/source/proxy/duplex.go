package proxy

import (
	"io"
	"local/work-observation/source/capture"
)

type duplex struct {
	io.ReadWriteCloser
	x *capture.Exchange
}

func newDuplex(r io.ReadWriteCloser, x *capture.Exchange, extensions string) io.ReadWriteCloser {
	x.Update(func(e *capture.Event) { e.Kind = "websocket_connection"; e.WebsocketExtensions = extensions })
	return &duplex{r, x}
}
func (d *duplex) Read(p []byte) (int, error) {
	n, err := d.ReadWriteCloser.Read(p)
	d.x.ObserveWire(true, p[:n])
	return n, err
}
func (d *duplex) Write(p []byte) (int, error) {
	n, err := d.ReadWriteCloser.Write(p)
	d.x.ObserveWire(false, p[:n])
	return n, err
}
