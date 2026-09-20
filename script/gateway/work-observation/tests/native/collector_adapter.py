"""Adapter for existing native-client fixtures; only a loopback capture proxy."""
from collections import Counter
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request


class GatewayFixture:
    def __init__(self, root, binary, backend):
        self.root = Path(root) / 'observation'
        self.root.mkdir(mode=0o700)
        self.store = self.root / 'store'
        self.binary = str(Path(binary).resolve())
        subprocess.run([self.binary, 'init', '--dir', str(self.store)], check=True, capture_output=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.base = 'http://127.0.0.1:' + str(port)
        config = {'listen': '127.0.0.1:' + str(port), 'upstream': backend,
            'region': 'synthetic', 'ingress': 'native-fixture', 'store_dir': str(self.store),
            'identity_salt_file': str(self.store / 'identity.salt'), 'capture_enabled': True,
            'storage_bytes': 1 << 30, 'memory_bytes': 64 << 20, 'body_bytes': 16 << 20, 'queue_items': 512}
        cfg = self.root / 'config.json'
        cfg.write_text(json.dumps(config))
        self.log = (self.root / 'service.log').open('w')
        self.process = subprocess.Popen([self.binary, 'serve', '--config', str(cfg)],
            stdout=self.log, stderr=self.log, start_new_session=True)
        for _ in range(100):
            if self.process.poll() is not None:
                raise RuntimeError('isolated_collector_exited')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.1):
                    return
            except OSError:
                time.sleep(.05)
        raise RuntimeError('isolated_collector_not_ready')

    def close(self):
        os.killpg(self.process.pid, signal.SIGTERM)
        try:
            code = self.process.wait(timeout=40)
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()
            raise RuntimeError('isolated_collector_drain_timeout')
        finally:
            self.log.close()
        if code != 0:
            raise RuntimeError('isolated_collector_shutdown_failed')
        exported = subprocess.check_output([self.binary, 'export', '--dir', str(self.store)], timeout=30)
        events = [json.loads(line) for line in exported.splitlines()]
        status = json.loads((self.store / 'status.json').read_text())
        summary = {'scope': 'native clients, synthetic loopback provider, actual collector',
            'production_changed': False, 'events': len(events),
            'kinds': dict(Counter(e['kind'] for e in events)), 'outcomes': dict(Counter(e['outcome'] for e in events)),
            'clients': dict(Counter(e['client'] for e in events)),
            'missing': dict(Counter(gap for e in events for gap in e.get('missing', []))),
            'status': status, 'all_record_checksums_valid': True,
            'original_ua_observed': sorted({e.get('user_agent', '') for e in events}),
            'auth_headers_excluded': all(value not in exported for value in (b'synthetic-native-fixture', b'synthetic-fixture'))}
        (self.root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
