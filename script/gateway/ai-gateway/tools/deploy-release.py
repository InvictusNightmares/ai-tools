#!/usr/bin/env python3
"""Install, upgrade, inspect and roll back only the authorized 4004/4005 instances."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from release import validate, binary_version

PROFILES = {'tokyo': (4004, 8093, 8013), 'us': (4005, 8094, 8014)}


def run(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component_config(config, name):
    value = json.loads(json.dumps(config['services'][name]))
    for volume in value.get('volumes', []):
        if isinstance(volume, dict) and volume.get('target') in ('/app/auto-server', '/app/preflight-api'):
            volume['source'] = '<versioned-binary>'
    return value


def render_ingress(release, root, region):
    endpoint = json.loads((root / 'deployment/endpoint.json').read_text())
    expected = PROFILES[region]
    environment = dict(line.split('=', 1) for line in (root / 'deployment/runtime.env').read_text().splitlines() if '=' in line and not line.startswith('#'))
    # Initial Tokyo instances predate the two internal-port metadata fields.
    auto_port = endpoint.get('auto_port', int(environment.get('ACCEPTANCE_AUTO_PORT', str(expected[1]))))
    guard_port = endpoint.get('guard_port', int(environment.get('ACCEPTANCE_GUARD_PORT', str(expected[2]))))
    if (endpoint.get('region'), endpoint.get('port'), auto_port, guard_port) != (region, *expected):
        raise ValueError('ingress_profile_mismatch')
    import ipaddress
    address = ipaddress.ip_address(endpoint['bind_address'])
    if address.version != 4 or not address.is_private or address.is_unspecified or address.is_loopback:
        raise ValueError('invalid_ingress_address')
    text = (release / 'deployment/nginx.conf.template').read_text()
    values = {'BIND_ADDRESS': str(address), 'PORT': expected[0], 'AUTO_PORT': expected[1],
              'UPSTREAM_AUTHORITY': '106.14.254.110:' + ('9881' if region == 'tokyo' else '9880')}
    for key, value in values.items(): text = text.replace('@' + key + '@', str(value))
    if '@' in text: raise ValueError('unresolved_ingress_template')
    return text


class Deployment:
    def __init__(self, region, drain_seconds):
        self.region, self.ports = region, PROFILES[region]
        self.root = Path('/data/ai-gateway/acceptance-' + region)
        self.drain_seconds = drain_seconds
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.compose = ['docker', 'compose', '--env-file', str(self.root / 'deployment/runtime.env'), '-f', str(self.root / 'deployment/compose.yaml')]

    def request(self, port, path, data=None, admin=False):
        headers = {'Content-Type': 'application/json'}
        if admin: headers['X-Gateway-Admin'] = (self.root / 'secrets/cache-secret').read_text().strip()
        request = urllib.request.Request('http://127.0.0.1:' + str(port) + path,
                                         data=None if data is None else json.dumps(data).encode(), headers=headers)
        with self.http.open(request, timeout=3) as response:
            return json.load(response)

    def ready(self):
        for _ in range(40):
            try:
                self.request(self.ports[1], '/healthz')
                self.request(self.ports[2], '/readyz')
                return
            except Exception:
                time.sleep(.5)
        raise RuntimeError('readiness_failed')

    def status(self):
        result = {'region': self.region, 'ports': self.ports}
        path = self.root / 'current-release.json'
        result['release'] = json.loads(path.read_text()) if path.exists() else {'release_id': 'legacy-unversioned'}
        for name, port in [('auto', self.ports[1]), ('guard', self.ports[2])]:
            try: result[name] = self.request(port, '/_gateway/status', admin=True)
            except Exception: result[name] = {'version_endpoint': 'unavailable'}
        return result

    def rewrite_ingress(self, text):
        # Preserve the inode: nginx bind-mounts this file.
        (self.root / 'deployment/nginx.conf').write_text(text)
        run(['docker', 'exec', 'nginx-acceptance-' + self.region, 'nginx', '-t'])
        run(['docker', 'exec', 'nginx-acceptance-' + self.region, 'nginx', '-s', 'reload'])

    def protected(self):
        result = {}
        for name in run(['docker', 'ps', '--format', '{{.Names}}']).splitlines():
            if name in ('auto-acceptance-' + self.region, 'guard-acceptance-' + self.region): continue
            item = json.loads(run(['docker', 'inspect', name]))[0]
            result[name] = (item['Id'], item['State']['StartedAt'], item['RestartCount'])
        return result

    def drain(self):
        deadline = time.monotonic() + self.drain_seconds
        modern = True
        try: self.request(self.ports[1], '/_gateway/drain', {'draining': True}, admin=True)
        except urllib.error.HTTPError as error:
            if error.code not in (401, 404): raise
            modern = False
        while time.monotonic() < deadline:
            if modern:
                if self.request(self.ports[1], '/_gateway/status', admin=True)['active_requests'] == 0: return
            else:
                active = run(['ss', '-Htn', 'state', 'established', '( sport = :' + str(self.ports[1]) + ' )']).strip()
                if not active: return
            time.sleep(.25)
        raise RuntimeError('drain_timeout_old_instance_preserved')

    def activate_components(self, changed):
        if changed:
            run(self.compose + ['up', '-d', '--no-deps', '--force-recreate'] + changed)
        if 'auto' not in changed:
            # Ingress is still closed. An unchanged Auto retains its drain flag;
            # release it before its health endpoint participates in readiness.
            self.request(self.ports[1], '/_gateway/drain', {'draining': False}, admin=True)
        self.ready()

    def activate(self, release, inject_failure=False):
        metadata = validate(release)
        if self.root.is_symlink() or not (self.root / 'deployment/runtime.env').is_file():
            raise ValueError('existing isolated instance required; use acceptance prepare/deploy for first creation')
        disk = shutil.disk_usage(self.root)
        state_bytes = sum(p.stat().st_size for p in (self.root / 'state').rglob('*') if p.is_file())
        if disk.free < state_bytes + 512 * 1024 * 1024: raise RuntimeError('insufficient_disk_space')
        secret_before = sha(self.root / 'secrets/cache-secret')
        self.ready()
        protected = self.protected()
        stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        backup = self.root / 'backups' / ('release-' + stamp)
        backup.mkdir(parents=True, mode=0o700)
        shutil.copytree(self.root / 'deployment', backup / 'deployment')
        current = self.root / 'current-release.json'
        if current.exists(): shutil.copy2(current, backup / 'current-release.json')
        ingress = (self.root / 'deployment/nginx.conf').read_text()
        if ingress.count('server_name _;') != 1: raise RuntimeError('unexpected_ingress_shape')
        previous_metadata = validate(Path(json.loads(current.read_text())['path'])) if current.exists() else None
        next_ingress = render_ingress(release, self.root, self.region)
        if current.exists() and ingress != render_ingress(Path(json.loads(current.read_text())['path']), self.root, self.region):
            raise RuntimeError('ingress_configuration_drift')
        old_config = json.loads(run(self.compose + ['config', '--format', 'json']))
        own_before = {name: json.loads(run(['docker', 'inspect', name + '-acceptance-' + self.region]))[0]['Id'] for name in ('auto', 'guard')}
        changed = ['guard', 'auto']
        switched = False
        result = {'release_id': metadata['release_id'], 'region': self.region, 'backup': str(backup)}
        try:
            self.rewrite_ingress(ingress.replace('server_name _;', 'server_name _;\n        return 503;', 1))
            self.drain()
            shutil.copytree(self.root / 'state', backup / 'state')
            state_before = {p.relative_to(self.root / 'state').as_posix(): sha(p) for p in (self.root / 'state').rglob('*') if p.is_file()}
            template = (release / 'deployment/compose.yaml').read_text()
            template = template.replace('${ACCEPTANCE_ROOT}/bin/', str(release / 'bin') + '/')
            (self.root / 'deployment/compose.yaml').write_text(template)
            # Validate the complete expanded config before stopping any process.
            new_config = json.loads(run(self.compose + ['config', '--format', 'json']))
            if old_config['services']['ingress'] != new_config['services']['ingress']:
                raise RuntimeError('ingress_configuration_change_requires_separate_activation')
            if previous_metadata:
                changed = [name for name, binary in [('guard', 'preflight-api'), ('auto', 'auto-server')]
                           if previous_metadata['binaries'][binary] != metadata['binaries'][binary]
                           or component_config(old_config, name) != component_config(new_config, name)]
            switched = bool(changed)
            self.activate_components(changed)
            if inject_failure: raise RuntimeError('injected_post_activation_failure')
            for port, binary in zip(self.ports[1:], ('auto-server', 'preflight-api')):
                status = self.request(port, '/_gateway/status', admin=True)
                expected = binary_version(metadata, binary)
                if any(status['version'][field] != expected[field] for field in ('release_id', 'source_sha256')): raise RuntimeError('live_release_mismatch')
            if sha(self.root / 'secrets/cache-secret') != secret_before: raise RuntimeError('internal_secret_changed')
            if self.protected() != protected: raise RuntimeError('unrelated_service_changed')
            for name in ('guard', 'auto'):
                if name not in changed and json.loads(run(['docker', 'inspect', name + '-acceptance-' + self.region]))[0]['Id'] != own_before[name]: raise RuntimeError('unchanged_component_restarted')
            if state_before != {p.relative_to(self.root / 'state').as_posix(): sha(p) for p in (self.root / 'state').rglob('*') if p.is_file()}: raise RuntimeError('state_changed_during_closed_upgrade')
            current.write_text(json.dumps({'release_id': metadata['release_id'], 'path': str(release), 'state_schema': metadata['state_schema'], 'backup': str(backup)}, indent=2) + '\n')
            self.request(self.ports[1], '/_gateway/drain', {'draining': False}, admin=True)
            self.rewrite_ingress(next_ingress)
            result.update(changed_services=changed, status='updated', secret_preserved=True, state_preserved=True, protected_services_unchanged=True)
        except Exception as error:
            result.update(status='failed', reason=str(error), rollback='not_required')
            try:
                shutil.copy2(backup / 'deployment/compose.yaml', self.root / 'deployment/compose.yaml')
                if switched:
                    run(self.compose + ['up', '-d', '--no-deps', '--force-recreate'] + changed)
                    # Guard-only failure leaves the existing Auto drained.
                    # Ingress is still closed, so release that flag before
                    # testing readiness of the restored pair.
                    self.request(self.ports[1], '/_gateway/drain', {'draining': False}, admin=True)
                    self.ready()
                    result['rollback'] = 'restored'
                else:
                    # An aborted drain must not leave the old service gated.
                    try: self.request(self.ports[1], '/_gateway/drain', {'draining': False}, admin=True)
                    except urllib.error.HTTPError as failure:
                        if failure.code not in (401, 404): raise
                self.request(self.ports[1], '/_gateway/drain', {'draining': False}, admin=True)
                if (backup / 'current-release.json').exists(): shutil.copy2(backup / 'current-release.json', current)
                elif current.exists(): current.unlink()
                self.rewrite_ingress(ingress)
            except Exception as rollback_error:
                result['rollback'] = 'failed'
                result['rollback_reason'] = str(rollback_error)
                # Ingress remains closed; no unsafe fail-open recovery.
            # Never restore a state snapshot over possible new writes.
        (backup / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result), flush=True)
        if result['status'] != 'updated': raise SystemExit(1)


def install(source, destination):
    metadata = validate(source)
    destination = destination / metadata['release_id']
    if destination.exists():
        if (destination / 'SHA256SUMS').read_bytes() != (source / 'SHA256SUMS').read_bytes(): raise ValueError('release ID collision')
        validate(destination)
    else:
        if shutil.disk_usage(destination.parent).free < sum(p.stat().st_size for p in source.rglob('*') if p.is_file()) + 256 * 1024 * 1024: raise RuntimeError('insufficient_disk_space')
        staging = destination.with_name(destination.name + '.installing')
        if staging.exists(): raise ValueError('incomplete installation exists; inspect it first')
        shutil.copytree(source, staging)
        validate(staging)
        os.rename(staging, destination)
    return destination


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('install', 'upgrade', 'rollback', 'status'))
    parser.add_argument('--region', choices=tuple(PROFILES), default='tokyo')
    parser.add_argument('--release', type=Path)
    parser.add_argument('--drain-seconds', type=int, default=120)
    parser.add_argument('--inject-post-activation-failure', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0: parser.error('root required')
    app = Deployment(args.region, args.drain_seconds)
    if args.command == 'status': print(json.dumps(app.status())); raise SystemExit(0)
    lock = (app.root / 'upgrade.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.release is None: parser.error('--release is required; rollback names the compatible previous release')
    releases = Path('/data/ai-gateway/releases'); releases.mkdir(mode=0o755, exist_ok=True)
    installed = install(args.release.resolve(), releases)
    if args.command == 'install': print(json.dumps({'installed': str(installed)}))
    else: app.activate(installed, args.inject_post_activation_failure)
