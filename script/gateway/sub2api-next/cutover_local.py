#!/usr/bin/env python3
"""Scoped local snapshot/restore operations for the US-West cutover."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from cutover_merge import ROOT, OPS, CONTAINER, check, guard, run, sql


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def frozen():
    for name in ('sub2api','sub2api-next'):
        check(not json.loads(run(['docker','inspect',name]))[0]['State']['Running'],'final operation requires stopped apps')


def snapshot(phase,side):
    if phase=='final':frozen()
    names={'a':('sub2api-postgres','sub2api'),'b':(CONTAINER,'sub2api_next'),
           'merged':(CONTAINER,'cutover_'+phase)}
    container,database=names[side]
    path=ROOT/'backups'/('cutover-'+phase+'-'+side+'.dump')
    part=path.with_suffix('.dump.part')
    check(not path.exists() and not part.exists(),'refusing to overwrite existing snapshot')
    started=time.monotonic();minimum=shutil.disk_usage(str(ROOT)).free
    with part.open('xb') as out,(OPS/(phase+'-'+side+'-dump.stderr')).open('wb') as err:
        p=subprocess.Popen(['docker','exec',container,'nice','-n','10','pg_dump','-U','sub2api','-d',database,'-Fc','-Z1','--lock-wait-timeout=5s'],stdout=out,stderr=err)
        while p.poll() is None:
            free=shutil.disk_usage(str(ROOT)).free;minimum=min(minimum,free)
            if free<4.5*1024**3:
                p.terminate();p.wait(timeout=30);raise RuntimeError('snapshot stopped at 4.5 GiB reserve')
            time.sleep(2)
        check(p.returncode==0,'snapshot failed; private diagnostic retained')
    listing=run(['docker','exec',CONTAINER,'pg_restore','--list','/backup/'+part.name])
    check('TABLE DATA public usage_logs ' in listing and 'TABLE DATA public users ' in listing,'incomplete archive TOC')
    record={'phase':'local_snapshot_completed','source_database':database,'bytes':part.stat().st_size,
            'sha256':digest(part),'seconds':round(time.monotonic()-started,1),'min_free_gib':round(minimum/1024**3,2)}
    if phase=='final':record['freeze_id']=json.loads((OPS/'control.json').read_text())['freeze_id']
    part.rename(path);(OPS/(phase+'-'+side+'-dump.json')).write_text(json.dumps(record,indent=2))
    print(json.dumps(record),flush=True)


def restore(phase,side):
    check(side in ('b','merged'),'only B or merged snapshots can initialize a clone')
    if phase=='final':frozen()
    database='cutover_'+phase
    path=ROOT/'backups'/('cutover-'+phase+'-'+side+'.dump')
    record=json.loads((OPS/(phase+'-'+side+'-dump.json')).read_text())
    if phase=='final':check(record.get('freeze_id')==json.loads((OPS/'control.json').read_text())['freeze_id'],'archive belongs to a different freeze')
    check(record['sha256']==digest(path) and record['bytes']==path.stat().st_size,'snapshot bytes/hash differ')
    check(sql('postgres',"SELECT count(*) FROM pg_database WHERE datname='{}'".format(database))=='0','clone already exists')
    check(shutil.disk_usage(str(ROOT)).free>7.2*1024**3,'insufficient space for measured compact restore')
    sql('postgres','CREATE DATABASE '+database+' OWNER sub2api')
    started=time.monotonic();minimum=shutil.disk_usage(str(ROOT)).free
    with (OPS/(phase+'-restore.stdout')).open('wb') as out,(OPS/(phase+'-restore.stderr')).open('wb') as err:
        p=subprocess.Popen(['docker','exec',CONTAINER,'pg_restore','--exit-on-error','--single-transaction','--no-owner','--no-acl','-U','sub2api','-d',database,'/backup/'+path.name],stdout=out,stderr=err)
        while p.poll() is None:
            free=shutil.disk_usage(str(ROOT)).free;minimum=min(minimum,free)
            if free<4.5*1024**3:
                sql('postgres',"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{}'".format(database))
                p.wait(timeout=30)
                raise RuntimeError('restore stopped at disk reserve; original databases preserved')
            time.sleep(2)
        check(p.returncode==0,'restore failed; private diagnostic retained')
    result={'phase':'local_restore_completed','source_side':side,'seconds':round(time.monotonic()-started,1),
            'database_bytes':int(sql('postgres',"SELECT pg_database_size('{}')".format(database))),
            'min_free_gib':round(minimum/1024**3,2),'free_gib':round(shutil.disk_usage(str(ROOT)).free/1024**3,2)}
    if phase=='final':result['freeze_id']=record['freeze_id']
    (OPS/(phase+'-restore.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


def drop_rehearsal():
    # The sole destructive DB target is a task-owned rehearsal clone, never A/B.
    check((OPS/'rehearsal-restore.json').is_file(),'owned restore receipt missing')
    compose=json.loads((ROOT/'compose.json').read_text())
    check(compose['services']['app']['environment']['DATABASE_DBNAME']=='sub2api_next','unexpected active app DB')
    check(sql('postgres',"SELECT count(*) FROM pg_stat_activity WHERE datname='cutover_rehearsal'")=='0','rehearsal still has sessions')
    sql('postgres','DROP DATABASE cutover_rehearsal')
    print(json.dumps({'rehearsal_database_removed':True}),flush=True)


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['snapshot','restore','drop-rehearsal'])
    p.add_argument('--phase',choices=['rehearsal','final'],default='rehearsal')
    p.add_argument('--side',choices=['a','b','merged'],default='b')
    args=p.parse_args();guard()
    if args.action=='snapshot':snapshot(args.phase,args.side)
    elif args.action=='restore':restore(args.phase,args.side)
    else:check(args.phase=='rehearsal','only rehearsal can be dropped');drop_rehearsal()


if __name__=='__main__':main()
