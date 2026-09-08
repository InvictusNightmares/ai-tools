#!/usr/bin/env python3
"""On CTYun, read credential JSON from stdin; validate CPA before replacing .env."""
import datetime
import json
import os
import re
import shlex
import sys
import urllib.request
from pathlib import Path

BASE = Path('/srv/agentbox/hermes')
allowed = {'CPA_API_KEY', 'FEISHU_APP_ID', 'FEISHU_APP_SECRET', 'FEISHU_ALLOWED_USERS'}


def main():
    assert os.geteuid() == 0
    incoming = json.load(sys.stdin)
    assert isinstance(incoming, dict) and not incoming.keys() - allowed
    assert incoming.get('CPA_API_KEY')
    assert incoming.get('FEISHU_APP_ID') == 'cli_aa15cd2181b81cff'
    assert incoming.get('FEISHU_APP_SECRET')
    for key, value in incoming.items():
        assert isinstance(value, str) and not any(c in value for c in "\n\r'"), 'Unsupported credential format'
    request = urllib.request.Request(
        'https://179.253.245.229:8317/v1/models',
        headers={'Authorization': 'Bearer ' + incoming['CPA_API_KEY']},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        models = sorted(item['id'] for item in json.load(response).get('data', []))
    assert 'deepseek-v4-pro' in models
    env = BASE / 'data/.env'
    assert env.is_file() and not env.is_symlink()
    raw = env.read_text()
    values = {}
    for line in raw.splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            parsed = shlex.split(value, comments=False)
            values[key] = parsed[0] if parsed else ''
    backup = BASE / 'verification' / ('credentials-before-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.env')
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(raw)
    # Enabling the bot waits for an owner allowlist; keep pending Feishu
    # credentials outside the container's mounts until that gate is complete.
    values['CPA_API_KEY'] = incoming['CPA_API_KEY']
    pending = BASE / 'feishu.pending.env'
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        for key in ('FEISHU_APP_ID', 'FEISHU_APP_SECRET', 'FEISHU_ALLOWED_USERS'):
            handle.write(key + "='" + incoming.get(key, '') + "'\n")
    staged = env.with_name('.env.next')
    assert not staged.exists()
    fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        for key, value in values.items():
            assert re.fullmatch('[A-Z][A-Z0-9_]*', key)
            handle.write(key + "='" + value + "'\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chown(staged, 10000, 10000)
    os.replace(staged, env)
    print(json.dumps({'cpa_key': 'user-provided key validated and installed', 'feishu_credentials': 'staged privately pending owner allowlist', 'available_models': models}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'configured': False, 'error_type': type(exc).__name__}))
        raise SystemExit(1)
