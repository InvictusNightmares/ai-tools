#!/usr/bin/env python3
"""Prepare a NEW acceptance directory. Does not start/stop any service.

Run on the GPU as root, with a verified manifest; no user Key file is stored.
The ingress port is required and must be confirmed before deployment.
"""
import argparse
import hashlib
import ipaddress
import json
import os
import pathlib
import secrets
import shutil
import socket
import subprocess

def deployment_profile(region):
    profiles = {'tokyo': (4004, 8093, 8013, 9881), 'us': (4005, 8094, 8014, 9880)}
    ingress, auto, guard, upstream = profiles[region]
    return {'region': region, 'port': ingress, 'auto_port': auto, 'guard_port': guard,
            'root': pathlib.Path('/data/ai-gateway/acceptance-' + region),
            'upstream': f'106.14.254.110:{upstream}'}


def render_nginx(template, address, profile):
    for key, value in {'BIND_ADDRESS': address, 'PORT': profile['port'], 'AUTO_PORT': profile['auto_port'], 'UPSTREAM_AUTHORITY': profile['upstream']}.items():
        template = template.replace('@' + key + '@', str(value))
    return template


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--verified-root', type=pathlib.Path, required=True)
    p.add_argument('--manifest', type=pathlib.Path, required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--region', choices=('tokyo', 'us'), default='tokyo')
    p.add_argument('--bind-address', default='192.168.64.16')
    p.add_argument('--runtime-image', required=True)
    p.add_argument('--nginx-image', required=True)
    args = p.parse_args()
    profile = deployment_profile(args.region)
    ROOT = profile['root']
    SERVICES = tuple(name + '-acceptance-' + args.region for name in ('guard', 'auto', 'nginx'))
    if os.geteuid() != 0 or ROOT.exists():
        p.error('requires root and a new acceptance directory; existing data is never overwritten')
    if args.port != profile['port']:
        p.error('ingress port must match the selected regional profile')
    address = ipaddress.ip_address(args.bind_address)
    if not address.is_private or address.is_unspecified or address.is_loopback or address.version != 4:
        p.error('a specific private IPv4 address is required')
    for host, port in [(str(address), args.port), ('127.0.0.1', profile['guard_port']), ('127.0.0.1', profile['auto_port'])]:
        with socket.socket() as probe:
            probe.bind((host, port))
    existing = set(subprocess.check_output(['docker', 'ps', '-a', '--format', '{{.Names}}'], text=True).splitlines())
    if existing.intersection(SERVICES):
        p.error('acceptance container name already exists; inspect before changing it')
    for image in (args.runtime_image, args.nginx_image):
        if '@sha256:' not in image or any(c.isspace() for c in image):
            p.error('images must be pinned by digest')
        subprocess.run(['docker', 'image', 'inspect', image], check=True, stdout=subprocess.DEVNULL)
    manifest = json.loads(args.manifest.read_text())
    verified = args.verified_root.resolve()
    for entry in manifest['files']:
        rel = pathlib.PurePosixPath(entry['path'])
        if rel.is_absolute() or '..' in rel.parts or not rel.parts or (rel.parts[0] not in ('auto', 'guard', 'cmd', 'service', 'vendor', 'tools', 'deploy', 'config') and str(rel) not in ('go.mod', 'go.sum', 'README.md', 'AGENTS.md', 'verify.sh', 'verify-on-linux.sh')):
            p.error('invalid source manifest path')
        source = (verified / rel).resolve()
        if not source.is_relative_to(verified) or hashlib.sha256(source.read_bytes()).hexdigest() != entry['sha256']:
            p.error('source manifest does not match verified checkout')
    # Combined deployment files are verified alongside both module sources.
    deployment_files = ('compose.yaml', 'run-auto.sh', 'deploy.sh', 'prepare.py', 'README.md', 'nginx.conf.template')
    manifest_paths = {entry['path'] for entry in manifest['files']}
    if any('deploy/acceptance/' + name not in manifest_paths for name in deployment_files):
        p.error('manifest must include all deploy/acceptance files')
    os.umask(0o077)
    ROOT.mkdir(mode=0o700)
    for name in ('source', 'bin', 'deployment', 'secrets', 'logs/auto', 'logs/guard', 'logs/nginx', 'state'):
        (ROOT / name).mkdir(mode=0o700, parents=True, exist_ok=True)
    for entry in manifest['files']:
        target = ROOT / 'source' / entry['path']
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copyfile(verified / entry['path'], target)
    (ROOT / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    here = verified / 'deploy' / 'acceptance'
    for name in deployment_files:
        shutil.copyfile(here / name, ROOT / 'deployment' / name)
    nginx = render_nginx((here / 'nginx.conf.template').read_text(), str(address), profile)
    (ROOT / 'deployment/nginx.conf').write_text(nginx)
    (ROOT / 'deployment/runtime.env').write_text(
        f'SUB2API_ORIGIN=http://{profile["upstream"]}\nACCEPTANCE_REGION={args.region}\nACCEPTANCE_AUTO_PORT={profile["auto_port"]}\nACCEPTANCE_GUARD_PORT={profile["guard_port"]}\nACCEPTANCE_ROOT={ROOT}\nACCEPTANCE_RUNTIME_IMAGE={args.runtime_image}\nACCEPTANCE_NGINX_IMAGE={args.nginx_image}\n')
    for name, value in [('cache-secret', secrets.token_hex(32).encode())]:
        path = ROOT / 'secrets' / name
        path.write_bytes(value)
        path.chmod(0o400)
        os.chown(path, 10001, 10001)
    for name in ('logs/auto', 'logs/guard', 'logs/nginx', 'state'):
        os.chown(ROOT / name, 10001, 10001)
    for name in ('nginx.conf', 'run-auto.sh'):
        (ROOT / 'deployment' / name).chmod(0o444)
    (ROOT / 'deployment/endpoint.json').write_text(json.dumps({'bind_address': str(address), 'port': args.port, 'auto_port': profile['auto_port'], 'guard_port': profile['guard_port'], 'region': args.region, 'auth': 'sub2api-caller-key', 'identity_namespace': 'key-hmac-v1', 'business_response_cache': False}, indent=2) + '\n')
    print(json.dumps({'prepared': str(ROOT), 'source_files_verified': len(manifest['files']), 'port': args.port, 'services_started': False}))


if __name__ == '__main__':
    main()
