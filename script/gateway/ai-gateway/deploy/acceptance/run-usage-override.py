#!/usr/bin/env python3
"""Run a verified US usage hotfix without changing the regional API release.

An API upgrade invalidates this override; revalidate or remove its systemd
drop-in rather than silently keeping old operations code after an upgrade.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

FILES = {'run-usage-override.py', 'tools/gateway_ops.py', 'tools/usage_sync.py',
         'tools/usage_ledger.py', 'tools/usage_schema.sql'}
RELEASES = Path('/data/ai-gateway/releases')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(root, bundle):
    manifest = json.loads((bundle/'manifest.json').read_text())
    if manifest.get('schema') != 'gateway-usage-override-v1' or manifest.get('region') != 'us':
        raise ValueError('invalid usage override manifest')
    if set(manifest['files']) != FILES:
        raise ValueError('invalid usage override file list')
    actual = {p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    if actual != FILES | {'manifest.json'}:
        raise ValueError('unlisted usage override file')
    for name, expected in manifest['files'].items():
        path = bundle/name
        if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()) or digest(path) != expected:
            raise ValueError('usage override checksum mismatch')
    pointer = json.loads((root/'current-release.json').read_text())
    release = Path(pointer['path']).resolve()
    if not release.is_relative_to(RELEASES.resolve()):
        raise ValueError('invalid API release path')
    metadata = json.loads((release/'release.json').read_text())
    if (pointer.get('release_id') != manifest['base_release_id']
            or metadata.get('release_id') != manifest['base_release_id']
            or metadata.get('source_sha256') != manifest['base_source_sha256']
            or metadata.get('operations_contract') != 'independent-usage-health-v1'):
        raise ValueError('API release changed; remove or revalidate usage override')
    for name in ('gateway_ops.py', 'usage_ledger.py', 'usage_schema.sql'):
        if digest(release/'tools'/name) != manifest['files']['tools/'+name]:
            raise ValueError('usage override changed an unapproved component')
    return [sys.executable, '-B', str(bundle/'tools/gateway_ops.py'), '--region', 'us',
            '--root', str(root), '--usage-only']


if __name__ == '__main__':
    os.umask(0o077)
    try:
        args = command(Path('/data/ai-gateway/acceptance-us'), Path(__file__).resolve().parent)
        os.execv(sys.executable, args)
    except Exception as error:
        print(json.dumps({'region':'us', 'status':'failed', 'error_type':type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
