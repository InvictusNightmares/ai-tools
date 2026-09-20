#!/usr/bin/env python3
"""Build once from verified source; validate immutable Linux release artifacts."""
import argparse
import datetime
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import shutil
import subprocess

from source_manifest import digest, manifest

BINARIES = ('auto-server', 'preflight-api')
SCHEMA = 'gateway-release-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def component_digest(sources, name):
    package = 'auto' if name == 'auto-server' else 'guard'
    prefixes = (package + '/', 'service/', 'vendor/', 'cmd/' + name + '/')
    files = [row for row in sources['files'] if
             (row['path'] in ('go.mod', 'go.sum') or row['path'].startswith(prefixes))
             and not row['path'].endswith('_test.go')
             and ('/testdata/' not in row['path'])
             and (row['path'].endswith('.go') or row['path'] in ('go.mod', 'go.sum', 'auto/codex_prompt.md', 'vendor/modules.txt'))]
    return digest({'files': files})


def binary_version(data, name):
    return data.get('binary_versions', {}).get(name, {'release_id': data['release_id'], 'source_sha256': data['source_sha256']})


def validate(root):
    data = json.loads((root / 'release.json').read_text())
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}', data.get('release_id', '')):
        raise ValueError('invalid release ID')
    if data.get('schema') != SCHEMA or data.get('platform') != 'linux/amd64':
        raise ValueError('unsupported release schema or platform')
    if data.get('config_schema') != 'gateway-config-v1' or data.get('state_schema') != 'session-json-v1':
        raise ValueError('unsupported configuration or state schema')
    if data.get('guard_contract') != 'credential-redaction-v1' or 'session-json-v1' not in data.get('compatible_state_schemas', []):
        raise ValueError('incompatible Guard contract or rollback state schema')
    listed = set()
    for line in (root / 'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts or name in listed:
            raise ValueError('invalid checksum path')
        listed.add(name)
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or sha(path) != expected:
            raise ValueError('release checksum mismatch: ' + name)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if listed != actual - {'SHA256SUMS'} or 'release.json' not in listed:
        raise ValueError('release contains unlisted or missing files')
    for name in BINARIES:
        path = root / 'bin' / name
        header = path.read_bytes()[:20]
        if header[:5] != b'\x7fELF\x02' or header[18:20] != b'\x3e\x00' or sha(path) != data['binaries'][name]:
            raise ValueError('binary platform or checksum mismatch')
        if platform.system() == 'Linux' and platform.machine() in ('x86_64', 'amd64'):
            version = json.loads(subprocess.check_output([str(path), '--version'], text=True))
            expected = binary_version(data, name)
            if version['release_id'] != expected['release_id'] or version['source_sha256'] != expected['source_sha256']:
                raise ValueError('embedded version mismatch')
    return data


def build(args):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}', args.release_id):
        raise ValueError('invalid release ID')
    source, verification, output = args.source.resolve(), args.verification.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError('release output must be new')
    verified = json.loads((verification / 'source-manifest.json').read_text())
    if manifest(source) != verified:
        raise ValueError('source differs from tested manifest')
    summary = json.loads((verification / 'verification.json').read_text())
    if summary.get('status') != 'passed' or summary.get('source_sha256') != digest(verified):
        raise ValueError('verification was not completed for this source')
    rows = [json.loads(line) for line in (verification / 'go-race.jsonl').read_text().splitlines()]
    if any(row.get('Action') == 'fail' for row in rows) or not any(row.get('Action') == 'pass' for row in rows):
        raise ValueError('failed or missing tests')
    git_commit, dirty = None, True
    try:
        git_commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--', '.'], text=True))
    except subprocess.CalledProcessError:
        pass
    if dirty and not args.candidate:
        raise ValueError('formal release rejects dirty/untracked source')
    output.mkdir(parents=True, mode=0o700)
    (output / 'bin').mkdir()
    revision = digest(verified)
    previous = validate(args.previous_release) if args.previous_release else None
    previous_sources = json.loads((args.previous_release / 'source-manifest.json').read_text()) if previous else None
    versions = {}
    component_sources = {}
    flags = '-X local/ai-gateway/service.ReleaseID=' + args.release_id + ' -X local/ai-gateway/service.SourceSHA256=' + revision
    for name in BINARIES:
        component_sources[name] = component_digest(verified, name)
        same_toolchain = previous and previous.get('toolchain_image') == args.build_image
        if same_toolchain and component_digest(previous_sources, name) == component_sources[name]:
            shutil.copy2(args.previous_release / 'bin' / name, output / 'bin' / name)
            versions[name] = binary_version(previous, name)
            continue
        versions[name] = {'release_id': args.release_id, 'source_sha256': revision}
        subprocess.run(['docker', 'run', '--rm', '--pull', 'never', '-v', str(source) + ':/src:ro',
                        '-v', str(output / 'bin') + ':/out', '-w', '/src', '-e', 'GOTOOLCHAIN=local',
                        '-e', 'GOPROXY=off', '-e', 'GOSUMDB=off', '-e', 'CGO_ENABLED=0',
                        args.build_image, 'go', 'build', '-trimpath', '-ldflags', flags,
                        '-o', '/out/' + name, './cmd/' + name], check=True)
    if manifest(source) != verified:
        raise ValueError('source changed while building')
    shutil.copytree(source / 'deploy' / 'acceptance', output / 'deployment', ignore=shutil.ignore_patterns('__pycache__'))
    (output / 'tools').mkdir()
    for name in ('release.py', 'source_manifest.py', 'deploy-release.py', 'usage_ledger.py', 'usage_sync.py', 'usage_schema.sql', 'gateway_ops.py'):
        shutil.copy2(source / 'tools' / name, output / 'tools' / name)
    shutil.copy2(verification / 'source-manifest.json', output / 'source-manifest.json')
    shutil.copy2(verification / 'verification.json', output / 'verification.json')
    data = {'schema': SCHEMA, 'release_id': args.release_id, 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'platform': 'linux/amd64', 'toolchain_image': args.build_image, 'git_commit': git_commit,
            'dirty': dirty, 'candidate_only': args.candidate, 'source_sha256': revision,
            'config_schema': 'gateway-config-v1', 'state_schema': 'session-json-v1', 'log_append_contract': 'locked-reopen-jsonl-v1',
            'compatible_state_schemas': ['session-json-v1'], 'guard_contract': 'credential-redaction-v1',
            'operations_contract': 'independent-usage-health-v1',
            'guard_rule_version': 'preflight-r19', 'guard_model_version': 'qwen3guard-gen-8b',
            'classifier_policy': 'semantic-v10-task-routing-r4', 'business_revision': 'guard-r19-semantic-v10-native-v31',
            'binaries': {name: sha(output / 'bin' / name) for name in BINARIES},
            'binary_versions': versions, 'component_source_sha256': component_sources,
            'tests_including_subtests': sum(row.get('Action') == 'pass' and bool(row.get('Test')) for row in rows)}
    (output / 'release.json').write_text(json.dumps(data, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(sha(p) + '  ' + p.relative_to(output).as_posix() + '\n' for p in sorted(output.rglob('*')) if p.is_file()))
    validate(output)
    print(json.dumps(data))


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build')
    for field in ('source', 'verification', 'output'): b.add_argument('--' + field, type=Path, required=True)
    b.add_argument('--release-id', required=True)
    b.add_argument('--build-image', default='golang:1.27.1-bookworm')
    b.add_argument('--candidate', action='store_true')
    b.add_argument('--previous-release', type=Path)
    v = sub.add_parser('verify'); v.add_argument('release', type=Path)
    args = parser.parse_args()
    if args.command == 'build': build(args)
    else: print(json.dumps(validate(args.release)))
