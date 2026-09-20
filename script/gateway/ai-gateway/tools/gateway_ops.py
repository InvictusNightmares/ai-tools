#!/usr/bin/env python3
"""Regional maintenance: durable usage sync, private health alerts and bounded logs."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.request

import usage_sync

PORTS={'tokyo':(8093,8013),'us':(8094,8014)}


def atomic_json(path,value):
    path=Path(path);temporary=path.with_name(path.name+'.new')
    fd=os.open(temporary,os.O_CREAT|os.O_TRUNC|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as output:
        json.dump(value,output);output.flush();os.fsync(output.fileno())
    os.replace(temporary,path)


def histogram_p95(current,previous,prefix):
    count=current.get(prefix+'_count',0)-previous.get(prefix+'_count',0)
    if count<=0:return None
    bounds=[]
    for key,value in current.items():
        match=re.fullmatch(re.escape(prefix)+r'_bucket\{le="([0-9]+)"\}',key)
        if match:bounds.append((int(match[1]),value-previous.get(key,0)))
    for bound,value in sorted(bounds):
        if value>=count*.95:return bound
    return 30001


def rotate(path,limit,apply=False,reopen=None):
    path=Path(path)
    if path.is_symlink():raise ValueError('log symlink rejected')
    stat=path.stat()
    if stat.st_size<limit:return False
    if not apply:return True
    lock_fd=os.open(str(path)+'.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(lock_fd,'a') as lock:
        os.fchown(lock.fileno(),stat.st_uid,stat.st_gid)
        deadline=time.monotonic()+3
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline:raise TimeoutError('log_rotation_lock_timeout')
                time.sleep(.02)
        if path.stat().st_size<limit:return False
        archived=path.with_name(path.name+'.'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')+'.'+str(time.time_ns()))
        os.rename(path,archived)
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
        try:os.fchown(fd,stat.st_uid,stat.st_gid);os.fsync(fd)
        finally:os.close(fd)
        directory=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(directory)
        finally:os.close(directory)
        if reopen:reopen()
        return True


def log_maintenance(root,region,apply,retention_days=None,limit=32<<20):
    rotated=expired=deleted=0
    now=time.time()
    for folder,names in [('auto',['usage.jsonl','route-audit.jsonl']),('guard',['security-usage.jsonl','security-decisions.jsonl','guard-security.jsonl']),('nginx',['access.jsonl','error.log'])]:
        directory=root/'logs'/folder
        if directory.is_symlink():raise ValueError('log directory symlink rejected')
        if not directory.exists():continue
        if apply:directory.chmod(0o700)
        for name in names:
            path=directory/name
            if not path.exists():continue
            if path.is_symlink():raise ValueError('log symlink rejected')
            if apply:path.chmod(0o600)
            reopen=None
            if folder=='nginx':
                def reopen():
                    subprocess.run(['docker','exec','nginx-acceptance-'+region,'nginx','-s','reopen'],check=True,capture_output=True,timeout=10)
            rotated+=int(rotate(path,limit,apply,reopen))
            if retention_days is None:continue
            for archived in directory.glob(name+'.*'):
                if not re.fullmatch(re.escape(name)+r'\.\d{8}T\d{6}\.\d+',archived.name):continue
                if archived.is_symlink():raise ValueError('archive symlink rejected')
                if now-archived.stat().st_mtime<retention_days*86400:continue
                expired+=1
                # Usage removal is gated on successful remote export and a
                # complete local cursor. An outage retains data beyond its TTL.
                if 'usage' in name or name=='security-decisions.jsonl':
                    ledger=usage_sync.Ledger(root/'ops/usage-ledger.sqlite')
                    try:
                        stat=archived.stat();identity=str(stat.st_dev)+':'+str(stat.st_ino)
                        cursor=ledger.db.execute('SELECT byte_offset FROM spool_offsets WHERE file_id=?',(identity,)).fetchone()
                        pending=ledger.db.execute('SELECT COUNT(*) FROM events WHERE exported=0').fetchone()[0]
                        if pending or not cursor or cursor[0]!=stat.st_size:continue
                    finally:ledger.close()
                if apply:archived.unlink();deleted+=1
    return dict(rotated=rotated,expired=expired,deleted=deleted,retention_days=retention_days,applied=apply)


def inspect(root,region,previous):
    secret=(root/'secrets/cache-secret').read_text().strip()
    http=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    alerts=[];components={};metrics={}
    for component,port in zip(('auto','guard'),PORTS[region]):
        request=urllib.request.Request('http://127.0.0.1:'+str(port)+'/_gateway/status',headers={'X-Gateway-Admin':secret})
        try:
            with http.open(request,timeout=3) as response:components[component]=json.load(response)
        except Exception:
            alerts.append(dict(code=component+'_unavailable',severity='critical'))
    draining=components.get('auto',{}).get('draining',False)
    if draining:alerts=[row for row in alerts if row['code']!='auto_unavailable']
    try:
        with http.open('http://127.0.0.1:'+str(PORTS[region][1])+'/metrics',timeout=3) as response:
            for line in response.read(1<<20).decode().splitlines():
                if line and not line.startswith('#'):
                    key,value=line.rsplit(' ',1);metrics[key]=float(value)
    except Exception:alerts.append(dict(code='guard_metrics_unavailable',severity='warning'))
    before=previous.get('metrics',{})
    current_version=components.get('guard',{}).get('version',{})
    old_version=previous.get('components',{}).get('guard',{}).get('version',{})
    latency=queue=None
    if before and current_version==old_version:
        latency=histogram_p95(metrics,before,'preflight_latency_ms')
        queue=histogram_p95(metrics,before,'preflight_queue_wait_ms')
        if latency is not None and latency>300:alerts.append(dict(code='guard_p95_above_300ms',severity='warning',value_ms=latency))
        if queue is not None and queue>=1000:alerts.append(dict(code='guard_queue_wait_high',severity='warning',value_ms=queue))
        key='preflight_decisions_total{decision="unavailable"}'
        unavailable=metrics.get(key,0)-before.get(key,0)
        if unavailable>0:alerts.append(dict(code='guard_fail_closed',severity='critical',requests=int(unavailable)))
    capacity=metrics.get('preflight_queue_capacity',0)
    if capacity and metrics.get('preflight_queue_active',0)>=capacity*.8:alerts.append(dict(code='guard_queue_pressure',severity='warning'))
    disk=shutil.disk_usage(root);free_ratio=disk.free/disk.total
    if disk.free<1<<30 or free_ratio<.05:alerts.append(dict(code='disk_space_critical',severity='critical'))
    elif disk.free<5<<30 or free_ratio<.15:alerts.append(dict(code='disk_space_low',severity='warning'))
    ledger_path=root/'ops/usage-ledger.sqlite'
    if ledger_path.exists():
        ledger=usage_sync.Ledger(ledger_path)
        try:
            since=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(minutes=5)).isoformat()
            rows=ledger.db.execute("SELECT model,key_hash,COUNT(*),SUM(NOT json_extract(payload,'$.success')) FROM events WHERE purpose IN ('business','classification','action_review') AND json_extract(payload,'$.attempt')=1 AND json_extract(payload,'$.at')>=? GROUP BY model,key_hash",(since,)).fetchall()
            for model,key_hash,attempts,failures in rows:
                if failures>=3 and failures/attempts>=.2:
                    alerts.append(dict(code='model_key_failure_rate',severity='warning',model=model,key_hash=key_hash,attempts=attempts,failures=failures))
        finally:ledger.close()
    return dict(region=region,at=datetime.datetime.now(datetime.timezone.utc).isoformat(),components=components,metrics=metrics,
                guard_p95_upper_bound_ms=latency,queue_p95_upper_bound_ms=queue,disk_free_bytes=disk.free,alerts=alerts)


def run_usage(root,region):
    root=Path(root);ops=root/'ops';ops.mkdir(mode=0o700,exist_ok=True)
    with (ops/'usage-export.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=ops/'usage-status.json'
        try:previous=json.loads(path.read_text())
        except (OSError,ValueError):previous={}
        if not isinstance(previous,dict):previous={}
        stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        running={'status':'running','at':stamp,'last_completed_at':previous.get('last_completed_at')}
        atomic_json(path,running)
        try:
            result=usage_sync.run(region,root)
            result.update(status='completed',last_completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        except Exception as error:
            result=dict(status='failed',error_type=type(error).__name__,last_completed_at=previous.get('last_completed_at'))
        result['at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        atomic_json(path,result)
        print(json.dumps({'region':region,'usage_sync':result}))
        return result


def read_usage_status(ops):
    path=ops/'usage-status.json'
    try:result=json.loads(path.read_text())
    except (OSError,ValueError):return {'status':'unavailable'},True
    if not isinstance(result,dict):return {'status':'unavailable'},True
    pending=result.get('status') in ('failed','unavailable') or result.get('remaining',0)>0
    try:
        completed=datetime.datetime.fromisoformat(result['last_completed_at'])
        pending=pending or (datetime.datetime.now(datetime.timezone.utc)-completed).total_seconds()>180
    except (KeyError,TypeError,ValueError):pending=True
    return result,pending


def run(root,region,apply=False,retention_days=None):
    root=Path(root);ops=root/'ops';ops.mkdir(mode=0o700,exist_ok=True)
    with (ops/'maintenance.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        path=ops/'status.json';previous=json.loads(path.read_text()) if path.exists() else {}
        # A regional SSH/database outage must never delay Guard health checks.
        # The independently scheduled exporter owns its durable status file.
        sync_result,pending=read_usage_status(ops)
        status=inspect(root,region,previous);status['usage_sync']=sync_result
        if pending:status['alerts'].append(dict(code='usage_export_pending',severity='warning'))
        try:
            if apply:
                release=json.loads((root/'current-release.json').read_text())
                metadata=json.loads((Path(release['path'])/'release.json').read_text())
                if metadata.get('log_append_contract')!='locked-reopen-jsonl-v1':
                    raise ValueError('running_release_does_not_support_rotation')
            maintain=apply and not status['components'].get('auto',{}).get('draining',False)
            status['logs']=log_maintenance(root,region,maintain,retention_days)
        except Exception as error:
            status['logs']={'status':'failed','error_type':type(error).__name__};status['alerts'].append(dict(code='log_maintenance_failed',severity='critical'))
        atomic_json(path,status)
        # Private, machine-readable alert state and journald are the default
        # destinations. No email/chat recipient is configured implicitly.
        atomic_json(ops/'alerts.json',status['alerts'])
        print(json.dumps({'region':region,'alerts':status['alerts'],'usage_sync':sync_result,'logs':status.get('logs')}))
        return status


if __name__=='__main__':
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    parser.add_argument('--region',choices=tuple(PORTS),required=True)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--apply-log-maintenance',action='store_true')
    parser.add_argument('--usage-only',action='store_true')
    parser.add_argument('--retention-days',type=int,choices=(30,90))
    args=parser.parse_args()
    if args.usage_only:
        result=run_usage(args.root,args.region)
        raise SystemExit(1 if result.get('status')=='failed' else 0)
    result=run(args.root,args.region,args.apply_log_maintenance,args.retention_days)
    if any(row['severity']=='critical' for row in result['alerts']):raise SystemExit(2)
