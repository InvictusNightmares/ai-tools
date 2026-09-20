#!/usr/bin/env python3
"""Install private, per-region maintenance from a verified active release."""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode=True


def render_unit(content, executable, version):
    if version<(3,9):raise ValueError('operations require Python 3.9 or newer')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+',executable):raise ValueError('unsupported Python executable path')
    return content.replace(b'@GATEWAY_PYTHON@',executable.encode())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--region',choices=('tokyo','us'),required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:raise SystemExit('root required')
    render_unit(b'',sys.executable,sys.version_info[:2])
    os.umask(0o077)
    root=Path('/data/ai-gateway/acceptance-'+args.region)
    pointer=json.loads((root/'current-release.json').read_text())
    release=Path(pointer['path']).resolve()
    if not release.is_relative_to('/data/ai-gateway/releases'):raise SystemExit('invalid release path')
    sys.path.insert(0,str(release/'tools'))
    from release import validate
    metadata=validate(release)
    if metadata.get('log_append_contract')!='locked-reopen-jsonl-v1':raise SystemExit('active release does not support rotation')
    operations=Path('/data/ai-gateway/operations');operations.mkdir(mode=0o700,exist_ok=True)
    ops=root/'ops';ops.mkdir(mode=0o700,exist_ok=True);ops.chmod(0o700)
    backup=root/'backups'/('operations-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(mode=0o700,parents=True)
    copies=[(release/'deployment/run-current.py',operations/'run-current.py')]
    copies += [(release/'deployment'/name,Path('/etc/systemd/system')/name) for name in ('gateway-ops@.service','gateway-ops@.timer','gateway-usage@.service','gateway-usage@.timer')]
    for source,target in copies:
        if target.is_symlink():raise SystemExit('operation target symlink rejected')
        if target.exists():shutil.copy2(target,backup/target.name)
        temporary=target.with_name(target.name+'.gateway-new')
        if temporary.exists():raise SystemExit('unfinished operations install exists')
        with temporary.open('xb') as output:
            content=render_unit(source.read_bytes(),sys.executable,sys.version_info[:2])
            output.write(content);output.flush();os.fsync(output.fileno())
        temporary.chmod(0o644 if target.suffix in ('.service','.timer') else 0o700)
        os.replace(temporary,target)
    config=ops/'config.json'
    if not config.exists():
        with config.open('x') as output:json.dump({'retention_days':None},output)
    # Installation never changes a previously selected retention policy.
    config.chmod(0o600)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','gateway-ops@'+args.region+'.timer'],check=True,capture_output=True)
    subprocess.run(['systemctl','enable','--now','gateway-usage@'+args.region+'.timer'],check=True,capture_output=True)
    print(json.dumps({'region':args.region,'status':'installed','release_id':metadata['release_id'],'backup':str(backup),
                      'retention_days':json.loads(config.read_text()).get('retention_days'),'python':sys.executable}))


if __name__=='__main__':main()
