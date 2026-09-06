#!/usr/bin/env python3
"""Exercise real UDP and TCP DNS without an external Python dependency."""
import secrets
import socket
import struct
import sys

host, port = sys.argv[1], int(sys.argv[2])
name = sys.argv[3] if len(sys.argv) > 3 else f"agentbox-{secrets.token_hex(8)}.example.com"
for kind in (socket.SOCK_DGRAM, socket.SOCK_STREAM):
    ident = secrets.randbelow(65536)
    packet = struct.pack('!6H', ident, 0x100, 1, 0, 0, 0)
    packet += b''.join(bytes([len(label)]) + label.encode('ascii') for label in name.split('.'))
    packet += b'\x00\x00\x01\x00\x01'
    with socket.socket(socket.AF_INET, kind) as sock:
        sock.settimeout(15)
        sock.connect((host, port))
        if kind == socket.SOCK_DGRAM:
            sock.send(packet)
            reply = sock.recv(65535)
        else:
            sock.sendall(struct.pack('!H', len(packet)) + packet)
            def read_exact(size):
                data = b''
                while len(data) < size:
                    chunk = sock.recv(size - len(data))
                    if not chunk:
                        raise RuntimeError('DNS TCP response truncated')
                    data += chunk
                return data
            size = struct.unpack('!H', read_exact(2))[0]
            reply = read_exact(size)
    rid, flags, questions, answers, _, _ = struct.unpack('!6H', reply[:12])
    rcode = flags & 15
    if rid != ident or not flags & 0x8000 or questions != 1 or rcode not in (0, 3):
        raise RuntimeError(f'DNS response invalid: rcode={rcode}')
    if len(sys.argv) > 3 and (rcode != 0 or answers == 0):
        raise RuntimeError('Expected DNS answer missing')
    print(f'DNS_{"UDP" if kind == socket.SOCK_DGRAM else "TCP"}_OK {host}:{port} rcode={rcode} answers={answers}')
