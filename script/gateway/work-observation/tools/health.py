#!/usr/bin/env python3
"""Read collector counters without touching forwarding/Guard/Auto state."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile

COUNTERS=('captured','written','dropped','truncated','write_errors','projection_errors','pruned','unavailable_bypassed_requests')


def evaluate(current,previous,now,free_bytes):
    start=current.get('started_at')
    same_boot=bool(previous) and previous.get('started_at')==start
    delta={key:max(0,int(current.get(key,0))-(int(previous.get(key,0)) if same_boot else 0)) for key in COUNTERS}
    issues=[]
    if current.get('capture_unavailable'):
        issues.append({'reason':'capture_unavailable','failure':current['capture_unavailable'],
                       'new_bypassed_requests':delta['unavailable_bypassed_requests']})
    for key in ('dropped','truncated','write_errors','projection_errors'):
        if delta[key]:issues.append({'reason':key,'new_count':delta[key]})
    timestamp=current.get('updated_at')
    stale_seconds=None
    if timestamp:
        updated=datetime.fromisoformat(timestamp.replace('Z','+00:00'))
        if updated.tzinfo is None:raise ValueError('timestamp requires timezone')
        stale_seconds=(now-updated).total_seconds()
        if stale_seconds>330:issues.append({'reason':'stale_status','seconds':stale_seconds})
        elif stale_seconds < -30:issues.append({'reason':'clock_skew','seconds':stale_seconds})
    else:issues.append({'reason':'missing_status_timestamp'})
    queue=int(current.get('queued_bytes',0));limit=int(current.get('queue_limit_bytes',0))
    if limit and queue>=limit*.8:issues.append({'reason':'queue_pressure','bytes':queue,'limit':limit})
    disk=int(current.get('stored_bytes',0));disk_limit=int(current.get('storage_limit_bytes',200<<30))
    if disk>=disk_limit*.9:issues.append({'reason':'retention_capacity_pressure','bytes':disk,'limit':disk_limit})
    if free_bytes<1<<30:issues.append({'reason':'filesystem_low_space','free_bytes':free_bytes})
    missing=int(current.get('association_unknown',0))
    return {'at':now.isoformat(),'status':'degraded' if issues else 'ok','issues':issues,
        'counter_scope':'same_process_interval' if same_boot else 'since_process_start',
        'process_changed':bool(previous) and not same_boot,'delta':delta,
        'queued_bytes':queue,'stored_bytes':disk,'filesystem_free_bytes':free_bytes,
        'association_unknown_total':missing,'status_age_seconds':stale_seconds,
        'capture_enabled':current.get('capture_enabled',False),
        'complete_capture_claim':False if issues or not current.get('capture_enabled') else None}


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,temporary=tempfile.mkstemp(prefix='.health-',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--status',required=True)
    p.add_argument('--state',required=True);p.add_argument('--storage-dir',required=True)
    p.add_argument('--report',required=True);args=p.parse_args();os.umask(0o077)
    if len({Path(p).resolve() for p in (args.status,args.state,args.report)})!=3:
        raise SystemExit('status, state and report must be distinct paths')
    previous={}
    invalid_previous=False
    try:
        previous=json.loads(Path(args.state).read_text()) if Path(args.state).exists() else {}
    except (OSError,ValueError):invalid_previous=True
    try:
        current=json.loads(Path(args.status).read_text())
        report=evaluate(current,previous,datetime.now(timezone.utc),shutil.disk_usage(args.storage_dir).free)
        if invalid_previous:
            report['issues'].append({'reason':'health_baseline_unavailable'});report['status']='degraded'
            report['complete_capture_claim']=False
        allowed=('started_at','updated_at','capture_enabled',*COUNTERS)
        atomic_json(args.state,{k:current[k] for k in allowed if k in current})
    except (OSError,ValueError,TypeError):
        # Never print an exception that may contain source content or private paths.
        report={'at':datetime.now(timezone.utc).isoformat(),'status':'degraded',
                'issues':[{'reason':'status_unavailable'}],'complete_capture_claim':False}
    atomic_json(args.report,report);print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
