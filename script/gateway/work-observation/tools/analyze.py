#!/usr/bin/env python3
"""Local-only rolling metadata analysis. Accept a restricted collection export on stdin.

No network/model/tool execution; no request/response bodies stored in analysis DB.
This index is independent of gateway routing, guard quarantine and billing state.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

SCHEMA = 'work-observation-v1'


def utc(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.astimezone(timezone.utc).isoformat()


def number(value):
    # Unknown remains null, including booleans and malformed billing fields.
    return value if type(value) in (int, float) and value >= 0 else None


def partition(event):
    """Keep a verified conversation in one split; leave uncertain links unsplit."""
    if event.get('association') not in ('verified_session', 'verified_conversation'):
        return 'unassigned'
    session = event.get('root_session_hash') or event.get('session_hash')
    if not session or not event.get('key_hash'):
        return 'unassigned'
    identity = '\0'.join([event['region'], event['key_hash'], session])
    return 'holdout' if hashlib.sha256(identity.encode()).digest()[0] < 51 else 'development'


def usage(response):
    if isinstance(response, dict):
        if response.get('_capture_transport')=='sse':
            return usage(response.get('data'))
        # Support canonical response and a completed Responses envelope.
        if isinstance(response.get('response'), dict):
            response = response['response']
        elif isinstance(response.get('message'), dict):
            response = response['message']
        value = response.get('usage')
        if isinstance(value, dict):
            return number(value.get('input_tokens', value.get('prompt_tokens'))), number(value.get('output_tokens', value.get('completion_tokens')))
    if isinstance(response, list):
        # Latest evidence only; do not sum cumulative streaming snapshots.
        result = [None, None]
        for event in reversed(response):
            values = usage(event)
            for index in (0, 1):
                if result[index] is None: result[index] = values[index]
            if all(v is not None for v in result): break
        return tuple(result)
    return None, None



def api_failure(response):
    """Only API envelopes, never a quoted tool/document field called error."""
    if isinstance(response,list):
        for item in reversed(response):
            status=api_failure(item)
            if status:return status
    elif isinstance(response,dict):
        if response.get('_capture_transport')=='sse':return api_failure(response.get('data'))
        if response.get('type') in ('error','response.failed'):return 'model_error'
        if response.get('type')=='response.incomplete':return 'model_incomplete'
        if isinstance(response.get('error'),dict) and response['error']:return 'model_error'
        if isinstance(response.get('response'),dict):return api_failure(response['response'])
        if response.get('status')=='failed':return 'model_error'
        if response.get('status')=='incomplete':return 'model_incomplete'
    return None


def response_metadata(value):
    if isinstance(value, list):
        result = [None, None]
        for item in reversed(value):
            fields = response_metadata(item)
            for index in (0, 1):
                if result[index] is None: result[index] = fields[index]
        return tuple(result)
    if isinstance(value, dict):
        if value.get('_capture_transport') == 'sse': return response_metadata(value.get('data'))
        for key in ('response', 'message'):
            if isinstance(value.get(key), dict): return response_metadata(value[key])
        if value.get('object') in ('response', 'response.compaction', 'chat.completion', 'chat.completion.chunk') or value.get('type') == 'message':
            return tuple(value.get(key) if isinstance(value.get(key), str) else None for key in ('id', 'model'))
    return None, None

def connect(path):
    os.umask(0o077)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('analysis DB must not be a symlink')
    db = sqlite3.connect(path, timeout=2)
    os.chmod(path, 0o600)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=2000')
    db.execute('PRAGMA cache_size=-8192')
    db.execute('PRAGMA temp_store=FILE')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS events (
            region TEXT NOT NULL, id TEXT NOT NULL, at TEXT NOT NULL,
            ingress TEXT NOT NULL, key_hash TEXT, session_hash TEXT,
            client TEXT NOT NULL, kind TEXT NOT NULL, protocol TEXT NOT NULL,
            model TEXT, outcome TEXT NOT NULL, status INTEGER,
            first_ms REAL, total_ms REAL, input_tokens INTEGER, output_tokens INTEGER,
            billed_cost REAL, billing_matched INTEGER NOT NULL,
            association TEXT NOT NULL, partition TEXT NOT NULL,
            missing_count INTEGER NOT NULL, quality TEXT NOT NULL,
            version TEXT NOT NULL, PRIMARY KEY(region,id)
        );
        CREATE INDEX IF NOT EXISTS events_at ON events(at);
        CREATE INDEX IF NOT EXISTS events_session ON events(region,key_hash,session_hash);
    ''')
    columns = {row[1] for row in db.execute('PRAGMA table_info(events)')}
    for name in ('agent_hash', 'connection_id', 'direction', 'upstream_request_id', 'response_id', 'requested_model', 'reported_model'):
        if name not in columns:
            db.execute('ALTER TABLE events ADD COLUMN '+name+' TEXT')
    db.execute('CREATE INDEX IF NOT EXISTS events_agent ON events(region,key_hash,session_hash,agent_hash)')
    return db


def ingest(db, event):
    if event.get('schema') != SCHEMA:
        raise ValueError('unsupported schema')
    if event.get('plane', 'actual') != 'actual':
        raise ValueError('simulations require a separate dataset')
    for required in ('id', 'at', 'region', 'ingress', 'kind', 'protocol', 'outcome', 'version'):
        if not isinstance(event.get(required), str) or not event[required]:
            raise ValueError('missing required event metadata: '+required)
    request = event.get('request')
    if isinstance(request, dict) and request.get('type') == 'response.create' and isinstance(request.get('response'), dict):
        request = request['response']
    requested_model = request.get('model') if isinstance(request, dict) else None
    model = event.get('model') or requested_model
    response = event.get('response')
    response_id, reported_model = response_metadata(response)
    input_tokens, output_tokens = usage(response)
    if event['kind'] == 'websocket_message' and isinstance(response, dict):
        if response.get('type') not in ('response.completed', 'response.failed', 'response.incomplete'):
            # Individual WS messages are records, not separate billed calls.
            # Provisional usage belongs in the raw evidence, not a second total.
            input_tokens, output_tokens = None, None
    bill = event.get('billing', {})
    matched = bill.get('match') == 'verified' and bill.get('currency') == 'USD'
    cost = number(bill.get('cost_usd')) if matched else None
    # HTTP success and model text cannot prove a task was completed correctly.
    quality = 'unknown'
    evidence = event.get('completion_evidence', {})
    if evidence.get('verified') is True and evidence.get('kind') in ('artifact_test', 'human_review'):
        if evidence.get('result') in ('success', 'failure'):
            quality = evidence['result']
    outcome=event['outcome']
    if outcome in ('completed','observed'):
        outcome=api_failure(event.get('response')) or outcome
    row = (event['region'],event['id'],utc(event['at']),event['ingress'],event.get('key_hash'),
           event.get('root_session_hash') or event.get('session_hash'),event.get('client','unknown'),event['kind'],
           event['protocol'],str(model)[:256] if model else None,outcome,number(event.get('status')),
           number(event.get('first_byte_ms')),number(event.get('duration_ms')),input_tokens,output_tokens,cost,
           int(matched and cost is not None),event.get('association','unknown'),partition(event),
           len(event.get('missing',[])),quality,event['version'],event.get('agent_hash'),event.get('connection_id'),
           event.get('direction'),event.get('upstream_request_id'),event.get('response_id') or response_id,
           str(requested_model)[:256] if requested_model else None,str(reported_model)[:256] if reported_model else None)
    # Replay/export overlap is idempotent. A later verified billing join can enrich it.
    cols = 'region,id,at,ingress,key_hash,session_hash,client,kind,protocol,model,outcome,status,first_ms,total_ms,input_tokens,output_tokens,billed_cost,billing_matched,association,partition,missing_count,quality,version,agent_hash,connection_id,direction,upstream_request_id,response_id,requested_model,reported_model'
    changes = db.total_changes
    db.execute(f'''INSERT INTO events ({cols}) VALUES ({','.join('?' for _ in row)})
        ON CONFLICT(region,id) DO UPDATE SET
        billed_cost=CASE WHEN excluded.billing_matched=1 THEN excluded.billed_cost ELSE events.billed_cost END,
        billing_matched=MAX(events.billing_matched,excluded.billing_matched),
        quality=CASE WHEN excluded.quality!='unknown' THEN excluded.quality ELSE events.quality END
        WHERE (excluded.billing_matched=1 AND (events.billing_matched=0 OR events.billed_cost!=excluded.billed_cost))
           OR (excluded.quality!='unknown' AND events.quality!=excluded.quality)''',row)
    return db.total_changes - changes


def report(db, now=None, hours=24):
    now=now or datetime.now(timezone.utc)
    since=(now-timedelta(hours=hours)).isoformat()
    db.row_factory=sqlite3.Row
    bounds=(since,now.isoformat())
    window='at>=? AND at<=?'
    # Aggregate inside SQLite: a 30-day report must not materialize every event
    # in Python. SQLite's bounded page cache and file-backed sort hold the data.
    totals=dict(db.execute(f'''SELECT COUNT(*) AS events,
        COALESCE(SUM(association NOT IN ('verified_session','verified_conversation')),0) AS unlinked,
        COALESCE(SUM(billed_cost),0) AS cost, COALESCE(SUM(billing_matched),0) AS cost_known,
        COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(output_tokens),0) AS output_tokens,
        COALESCE(SUM(input_tokens IS NULL OR output_tokens IS NULL),0) AS usage_unknown,
        COALESCE(SUM(missing_count>0),0) AS missing FROM events WHERE {window}''',bounds).fetchone())
    # A verified session remains an association unit, not a completed task.
    linked=db.execute(f'''SELECT COUNT(*) FROM (SELECT 1 FROM events WHERE {window}
        AND session_hash IS NOT NULL AND session_hash!=''
        AND association IN ('verified_session','verified_conversation')
        GROUP BY region,key_hash,session_hash)''',bounds).fetchone()[0]
    fields={'client','model','ingress','requested_model','reported_model','protocol','kind','outcome','quality','partition'}
    distribution_omitted={}
    def counts(field):
        if field not in fields:raise ValueError('unsupported_report_field')
        result={r[0]:r[1] for r in db.execute(f"SELECT COALESCE(NULLIF({field},''),'unknown'),COUNT(*) FROM events WHERE {window} GROUP BY 1 ORDER BY 2 DESC,1 LIMIT 100",bounds)}
        omitted=totals['events']-sum(result.values())
        if omitted:distribution_omitted[field]=omitted
        return result
    def latency(kind):
        result={}
        for field,label in (('first_ms','first_byte_p95_ms'),('total_ms','total_p95_ms')):
            where=f'{window} AND kind=? AND {field} IS NOT NULL'
            params=(*bounds,kind)
            n=db.execute(f'SELECT COUNT(*) FROM events WHERE {where}',params).fetchone()[0]
            offset=max(0,(95*n+99)//100-1) # Exact nearest rank, including small samples.
            result[label]=db.execute(f'SELECT {field} FROM events WHERE {where} ORDER BY {field} LIMIT 1 OFFSET ?',(*params,offset)).fetchone()[0] if n else None
            if field=='total_ms':result['samples']=n
        return result
    kinds=counts('kind')
    latency_by_kind={kind:latency(kind) for kind in kinds}
    http=latency_by_kind.get('http_exchange',{'samples':0,'first_byte_p95_ms':None,'total_p95_ms':None})
    faults=[dict(r) for r in db.execute(f'''SELECT region,id,at,outcome,missing_count AS capture_gaps FROM events
        WHERE {window} AND (outcome NOT IN ('completed','success','observed','websocket_closed') OR missing_count>0)
        ORDER BY at DESC,id DESC LIMIT 100''',bounds)]
    return {'plane':'actual','report_version':2,'percentile_method':'nearest_rank',
        'window_hours':hours,'since':since,'until':now.isoformat(),
        'events':totals['events'],'verified_conversations':linked,
        'unlinked_events':totals['unlinked'],
        'clients':counts('client'),'models':counts('model'),'ingresses':counts('ingress'),
        'requested_models':counts('requested_model'),'reported_models':counts('reported_model'),
        'protocols':counts('protocol'),'event_kinds':kinds,'outcomes':counts('outcome'),
        'evidence_quality':counts('quality'),'splits':counts('partition'),
        'first_byte_p95_ms':http['first_byte_p95_ms'],
        'total_p95_ms':http['total_p95_ms'],
        'latency_samples':http['samples'],
        'headline_latency_scope':'http_exchange','latency_by_event_kind':latency_by_kind,
        'known_cost_usd':totals['cost'],
        'cost_known_events':totals['cost_known'],
        'cost_unknown_events':totals['events']-totals['cost_known'],
        'input_tokens_known':totals['input_tokens'],
        'output_tokens_known':totals['output_tokens'],
        'usage_unknown_events':totals['usage_unknown'],
        'events_with_missing_capture':totals['missing'],
        'investigation_candidates':list(reversed(faults)),
        'distribution_limit':100,'distribution_omitted_events':distribution_omitted,
        'limitations':['HTTP成功不等于任务完成','未关联到事件的全局采集丢失须由健康报告单独加入',
                      '原入口没有候选Guard/Auto实际决策','尚无任务类型语义标注；不能由模型占比推定选型合理']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('ingest')
    r=sub.add_parser('report');r.add_argument('--hours',type=int,default=24)
    p=sub.add_parser('prune');p.add_argument('--days',type=int,default=30)
    args=parser.parse_args();db=connect(args.db)
    try:
        if args.command=='ingest':
            seen=changed=0
            while True:
                line=sys.stdin.readline(64*1024*1024+1)
                if not line:break
                if len(line)>64*1024*1024: raise ValueError('oversized export record')
                changed+=ingest(db,json.loads(line));seen+=1
                if seen%100==0:db.commit()
            db.commit();result={'seen':seen,'inserted_or_enriched':changed}
        elif args.command=='report':
            if not 1<=args.hours<=720:raise ValueError('report window must be 1..720 hours')
            result=report(db,hours=args.hours)
        else:
            if args.days!=30:raise ValueError('approved retention is 30 days')
            cutoff=(datetime.now(timezone.utc)-timedelta(days=30)).isoformat()
            count=db.execute('DELETE FROM events WHERE at<?',(cutoff,)).rowcount;db.commit()
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)');result={'pruned':count,'cutoff':cutoff}
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:db.close()


if __name__=='__main__':
    main()
