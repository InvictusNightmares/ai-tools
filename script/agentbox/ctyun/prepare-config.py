#!/usr/bin/env python3
"""Read only explicit CtYun credential fields; write an ignored, mode-0600 config."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import yaml

root = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--secrets', type=Path, default=root / 'pas.yaml')
parser.add_argument('--desktop-id', required=True)
args = parser.parse_args()
if not re.fullmatch(r'[0-9]{1,20}', args.desktop_id):
    parser.error('desktop-id must be numeric')
try:
    secrets = yaml.safe_load(args.secrets.read_text())
    user, password = secrets.get('ctyun_user'), secrets.get('ctyun_pass')
    if not isinstance(user, (str, int)) or not str(user).strip() or not isinstance(password, str) or not password:
        raise ValueError('Missing explicit CtYun credentials')
    directory = root / '.agentbox-staging' / 'ctyun'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if directory.is_symlink() or directory.parent.is_symlink():
        raise ValueError('Private directory must not be a symlink')
    directory.chmod(0o700)
    path = directory / 'accounts.json'
    if path.is_symlink():
        raise ValueError('Private output must not be a symlink')
    fd, name = tempfile.mkstemp(dir=directory, prefix='.config-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump({'User': str(user).strip(), 'Password': password, 'DesktopId': args.desktop_id, 'KeepAliveSeconds': 60}, stream)
            stream.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    print('PRIVATE_CONFIG_READY: .agentbox-staging/ctyun/accounts.json (0600)')
except Exception as error:
    # YAML parser errors can contain password text. Never print the exception body.
    raise SystemExit('Private configuration unavailable: check ctyun_user and ctyun_pass in the local secrets file.') from None
