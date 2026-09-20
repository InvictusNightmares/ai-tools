package main

import (
	"net"
	"sync"
)

// Track actual sockets, including hijacked WebSockets, for bounded shutdown.
type trackedListener struct {
	net.Listener
	mu          sync.Mutex
	connections map[*trackedConn]struct{}
}
type trackedConn struct {
	net.Conn
	owner *trackedListener
	once  sync.Once
}

func (l *trackedListener) Accept() (net.Conn, error) {
	c, err := l.Listener.Accept()
	if err != nil {
		return nil, err
	}
	tracked := &trackedConn{Conn: c, owner: l}
	l.mu.Lock()
	l.connections[tracked] = struct{}{}
	l.mu.Unlock()
	return tracked, nil
}
func (c *trackedConn) Close() error {
	err := c.Conn.Close()
	c.once.Do(func() { c.owner.mu.Lock(); delete(c.owner.connections, c); c.owner.mu.Unlock() })
	return err
}
func (l *trackedListener) closeConnections() {
	l.mu.Lock()
	list := make([]*trackedConn, 0, len(l.connections))
	for c := range l.connections {
		list = append(list, c)
	}
	l.mu.Unlock()
	for _, c := range list {
		_ = c.Close()
	}
}

func (l *trackedListener) count() int { l.mu.Lock(); defer l.mu.Unlock(); return len(l.connections) }
