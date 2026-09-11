#!/usr/bin/env python3
"""One-time bootstrap into the persistent custom update channel (run on a node).

Only sub2api is recreated. Existing PostgreSQL, Redis and proxy containers stay
running. A failed health check restores the previous custom binary automatically.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
import uuid

DEPLOY=Path('/opt/sub2api-deploy')
ROOT=DEPLOY/'data/policy-updates'
STAGING=DEPLOY/'policy-releases'
STATE=DEPLOY/'policy-upgrade-bootstrap.json'
COMPOSE=DEPLOY/'docker-compose.yml'
RUNTIME=ROOT/'runtime/sub2api'


def run(args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def output(args):
    return run(args,stdout=subprocess.PIPE,universal_newlines=True).stdout.strip()


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()


def active_hash():
    return output(['docker','exec','-u','1000:1000','sub2api','sha256sum','/proc/1/exe']).split()[0]


def install_runtime(source):
    """Anchor every directory and operate on FDs; never follow app symlinks as root."""
    directory=os.open(DEPLOY,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in ('data','policy-updates','runtime'):
            try:os.mkdir(part,0o755,dir_fd=directory)
            except FileExistsError:pass
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory)
            os.close(directory);directory=child
        os.fchown(directory,1000,1000)
        temporary='.bootstrap-'+uuid.uuid4().hex
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=directory)
        try:
            with os.fdopen(fd,'wb') as out,source.open('rb') as src:
                shutil.copyfileobj(src,out);out.flush()
                os.fchmod(out.fileno(),0o755);os.fchown(out.fileno(),1000,1000);os.fsync(out.fileno())
            os.rename(temporary,'sub2api',src_dir_fd=directory,dst_dir_fd=directory)
            os.fsync(directory)
        finally:
            try:os.unlink(temporary,dir_fd=directory)
            except FileNotFoundError:pass
    finally:os.close(directory)


def save_state(state):
    temporary=STATE.with_suffix('.pending')
    temporary.write_text(json.dumps(state));temporary.chmod(0o600)
    with temporary.open('rb') as f:os.fsync(f.fileno())
    os.replace(temporary,STATE)


def healthy(expected,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=4) as r:
                ok=json.load(r).get('status')=='ok'
            state=json.loads(output(['docker','inspect','--format','{{json .State}}','sub2api']))
            if ok and state.get('Health',{}).get('Status')=='healthy' and active_hash()==expected:return
        except Exception:pass
        time.sleep(3)
    raise RuntimeError('Application failed health/process verification')


def replacement_compose(text,image,retry=False):
    matches=list(re.finditer(r'^  sub2api:[ \t]*\n',text,re.M))
    if len(matches)!=1:raise RuntimeError('Unexpected compose layout')
    match=matches[0];marker=match.group(0)
    prefix,tail=text[:match.start()],text[match.end():]
    boundary=re.search(r'^  [a-zA-Z0-9_-]+:\s*$',tail,re.M)
    block=tail[:boundary.start()] if boundary else tail
    rest=tail[boundary.start():] if boundary else ''
    if retry:
        block=block.replace('    command: ["/app/data/policy-updates/runtime/sub2api"]\n','')
        block=block.replace('      - ./policy-releases:/app/policy-releases:ro\n','')
    if re.search(r'^    (command|entrypoint):',block,re.M):raise RuntimeError('Existing custom entrypoint needs review')
    block,count=re.subn(r'^    image:.*$',f'    image: {image}',block,count=1,flags=re.M)
    if count!=1:raise RuntimeError('Missing application image')
    if block.count('    volumes:\n')!=1:raise RuntimeError('Unexpected application mounts')
    block=block.replace('    volumes:\n','    volumes:\n      - ./policy-releases:/app/policy-releases:ro\n')
    return prefix+marker+'    command: ["/app/data/policy-updates/runtime/sub2api"]\n'+block+rest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--expected-current-sha',required=True)
    parser.add_argument('--version',required=True)
    parser.add_argument('--expected-release-sha',required=True)
    parser.add_argument('--check-only',action='store_true',help='Validate binary and actual compose without backups or activation')
    args=parser.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Run as root')
    state=json.loads(STATE.read_text()) if STATE.exists() else {}
    incomplete=state.get('status') in ('prepared','activating','rolled_back') and state.get('from_sha256')==args.expected_current_sha
    if args.check_only and incomplete:raise RuntimeError('An incomplete bootstrap must be reconciled before preflight')
    try:active=active_hash()
    except subprocess.CalledProcessError:
        if not incomplete:raise
        active=None
    if incomplete and state.get('target_sha256')==args.expected_release_sha and active in (None,args.expected_release_sha):
        try:
            if active is None:raise RuntimeError('Interrupted activation left application unavailable')
            healthy(args.expected_release_sha)
        except Exception:
            previous=Path(state['backup'])/'sub2api'
            if digest(previous)!=args.expected_current_sha:raise RuntimeError('Recovery backup integrity check failed')
            saved_compose=Path(state['backup'])/'activation-compose.yml'
            if not saved_compose.is_file():raise RuntimeError('Missing protected activation configuration')
            pending=DEPLOY/'docker-compose.policy-pending.yml'
            pending.write_bytes(saved_compose.read_bytes());pending.chmod(0o600)
            run(['docker','compose','--project-directory',str(DEPLOY),'-f',str(pending),'config','--quiet'])
            install_runtime(previous);os.replace(pending,COMPOSE)
            run(['docker','compose','--project-directory',str(DEPLOY),'-f',str(COMPOSE),'up','-d','--no-deps','--pull','never','--force-recreate','sub2api'])
            healthy(args.expected_current_sha)
            state['status']='rolled_back';save_state(state)
            raise RuntimeError('Interrupted activation recovered to the verified previous custom version')
        state['status']='complete';save_state(state)
        print(json.dumps({'health':'healthy','recovered':True,'version':args.version,'sha256':active}));return
    if active!=args.expected_current_sha:raise RuntimeError('Running version changed; bootstrap stopped')
    retry=incomplete
    if RUNTIME.exists() and not retry:raise RuntimeError('Persistent runtime already exists; use the admin updater')
    catalog=json.loads((STAGING/'catalog.json').read_text())
    release=next(r for r in catalog['releases'] if r['version']==args.version)
    if release['sha256']!=args.expected_release_sha:raise RuntimeError('Catalog does not match independently pinned release SHA')
    candidate=STAGING/'releases'/release['sha256']/'sub2api'
    if digest(candidate)!=args.expected_release_sha:raise RuntimeError('Staged checksum mismatch')
    image_id=output(['docker','inspect','--format','{{.Image}}','sub2api'])
    result=run(['docker','run','--rm','--user','1000:1000','--network','none','--read-only','--cap-drop','ALL',
                '--security-opt','no-new-privileges','--pids-limit','32','--memory','256m','--entrypoint','/candidate',
                '--mount',f'type=bind,src={candidate},dst=/candidate,readonly',image_id,'-version'],
               stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
    if args.version not in result.stdout:raise RuntimeError('Staged version mismatch')
    digests=json.loads(output(['docker','image','inspect','--format','{{json .RepoDigests}}',image_id]))
    image=digests[0] if digests else image_id
    original_compose=COMPOSE.read_text()
    new_compose=replacement_compose(original_compose,image,retry)
    with tempfile.NamedTemporaryFile(mode='w',prefix='.policy-compose-check-',suffix='.yml',dir=str(DEPLOY)) as check:
        check.write(new_compose);check.flush()
        run(['docker','compose','--project-directory',str(DEPLOY),'-f',check.name,'config','--quiet'])
    if args.check_only:
        print('BOOTSTRAP_PREFLIGHT_OK');return
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=DEPLOY/'backups'/f'policy-upgrade-bootstrap-{stamp}'
    backup.mkdir(mode=0o700,parents=True)
    shutil.copy2(COMPOSE,backup/'docker-compose.yml')
    (backup/'docker-compose.yml').chmod(0o600)
    config=DEPLOY/'data/policy-request-log.json'
    shutil.copy2(config,backup/'policy-request-log.json')
    (backup/'policy-request-log.json').chmod(0o600)
    if retry:shutil.copy2(Path(state['backup'])/'sub2api',backup/'sub2api')
    else:run(['docker','cp','sub2api:/app/sub2api',str(backup/'sub2api')])
    if digest(backup/'sub2api')!=args.expected_current_sha:raise RuntimeError('Backup differs from running binary')
    database_size=int(output(['docker','exec','sub2api-postgres','psql','-U','sub2api','-d','sub2api','-Atc','SELECT pg_database_size(current_database())']))
    if shutil.disk_usage(DEPLOY).free < database_size+2*1024**3:raise RuntimeError('Insufficient space for DB backup')
    with (backup/'database.dump').open('xb') as dump:
        os.chmod(dump.name,0o600)
        run(['docker','exec','sub2api-postgres','pg_dump','-U','sub2api','-d','sub2api','-Fc'],stdout=dump)
    # Verify the backup's TOC is readable before switching anything.
    with (backup/'database.dump').open('rb') as dump:
        run(['docker','exec','-i','sub2api-postgres','pg_restore','--list'],stdin=dump,stdout=subprocess.DEVNULL)
    (backup/'activation-compose.yml').write_text(new_compose)
    (backup/'activation-compose.yml').chmod(0o600)
    pending=DEPLOY/'docker-compose.policy-pending.yml'
    pending.write_text(new_compose);pending.chmod(0o600)
    run(['docker','compose','--project-directory',str(DEPLOY),'-f',str(pending),'config','--quiet'])
    if active_hash()!=args.expected_current_sha:raise RuntimeError('Running version changed during preparation')
    if COMPOSE.read_text()!=original_compose:raise RuntimeError('Compose changed during preparation; activation stopped')
    state={'status':'prepared','backup':str(backup),'from_sha256':args.expected_current_sha,'target_sha256':args.expected_release_sha}
    save_state(state)
    compose=['docker','compose','--project-directory',str(DEPLOY),'-f',str(COMPOSE),'up','-d','--no-deps','--pull','never','--force-recreate','sub2api']
    try:
        install_runtime(candidate)
        os.replace(pending,COMPOSE)
        state['status']='activating';save_state(state)
        run(compose)
        healthy(release['sha256'])
        if digest(config)!=digest(backup/'policy-request-log.json'):raise RuntimeError('Recorder config unexpectedly changed')
    except Exception:
        install_runtime(backup/'sub2api')
        # Even if activation stopped before compose replacement, start the old
        # custom binary through the persistent command, never the official image binary.
        if pending.exists():os.replace(pending,COMPOSE)
        run(compose)
        healthy(args.expected_current_sha)
        state['status']='rolled_back';save_state(state)
        raise
    state['status']='complete';save_state(state)
    print(json.dumps({'version':args.version,'sha256':active_hash(),'backup':str(backup),'compose_command':'/app/data/policy-updates/runtime/sub2api','image':image,'health':'healthy'}))


if __name__=='__main__':main()
