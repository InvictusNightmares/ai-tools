#!/usr/bin/env python3
"""GPU-side spool replay and SSH export to an isolated regional PostgreSQL DB.

Uses existing SSH aliases; credentials and Key values never enter arguments,
files or reports. The regional helper reads Key values locally and returns HMAC
identifiers only. Sub2API tables are read-only; gateway_usage holds our tables.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys

from usage_ledger import Ledger

HOSTS = {'tokyo': 'qiyuan-tokyo', 'us': 'qiyuan-us'}
DB = 'gateway_usage'

# This code runs at the regional host. Key values stay in that host's memory.
KEYMAP_HELPER = '''import sys,json,subprocess,hmac,hashlib
request=json.load(sys.stdin)
sql="SELECT COALESCE(json_agg(json_build_object('id',id,'key',key)),'[]'::json) FROM api_keys;"
p=subprocess.run(['docker','exec','-i','sub2api-postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','sub2api','-d','sub2api','-At'],input=sql,universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if p.returncode: raise SystemExit('regional_key_mapping_query_failed')
rows=json.loads(p.stdout)
out=[]
for row in rows:
 value=('sub2api-identity-v1\\x00'+request['region']+'\\x00'+row['key']).encode()
 digest=hmac.new(request['secret'].encode(),value,hashlib.sha256).hexdigest()
 out.append({'region':request['region'],'key_hash':'key-hmac-v1:'+digest,'api_key_id':row['id']})
print(json.dumps(out))
'''


def ssh(region, command, data, timeout=90):
    wrapped=command+'; gateway_command_status=$?; printf \"\\n__GATEWAY_REMOTE_EXIT__:%s\\n\" \"$gateway_command_status\"'
    remote='sh -c '+shlex.quote(wrapped)
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'UpdateHostKeys=no', HOSTS[region], remote],
                            input=data, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # stderr may contain a rejected SQL row. Do not propagate it to logs.
        raise RuntimeError('regional_operation_failed_exit_' + str(result.returncode))
    match=re.search(r'\n__GATEWAY_REMOTE_EXIT__:(\d+)\r?\n?$',result.stdout)
    if not match:
        raise RuntimeError('regional_exit_status_missing')
    if match[1]!='0':
        raise RuntimeError('regional_command_failed_exit_'+match[1])
    return result.stdout[:match.start()]


def psql(region, script, database=DB):
    if database not in (DB, 'postgres'):
        raise ValueError('business database writes forbidden')
    command = shlex.join(['docker', 'exec', '-i', 'sub2api-postgres', 'psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1',
                          '-U', 'sub2api', '-d', database, '-At'])
    return ssh(region, command, script)


def initialize(region):
    existing=psql(region, "SELECT count(*) FROM pg_database WHERE datname='gateway_usage';", 'postgres').strip()
    if existing=='1':
        unknown=psql(region, "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name NOT IN ('gateway_usage_schema','gateway_key_mapping','gateway_usage_events','model_usage_daily','security_model_usage_daily');").strip()
        if unknown:
            raise ValueError('existing database contains unrecognized tables')
        version=psql(region, "SELECT to_regclass('public.gateway_usage_schema');").strip()
        if version and psql(region, 'SELECT version FROM gateway_usage_schema;').strip()!='1':
            raise ValueError('unsupported regional usage schema')
    # CREATE DATABASE cannot run in a transaction. Existing DBs are retained.
    psql(region, "SELECT 'CREATE DATABASE gateway_usage' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='gateway_usage');\n\\gexec\n", 'postgres')
    psql(region, Path(__file__).with_name('usage_schema.sql').read_text())


def csv_rows(rows):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    for row in rows:
        writer.writerow([json.dumps(row, separators=(',', ':'))])
    return output.getvalue()


def aggregate_sql(table, security):
    if table not in ('model_usage_daily', 'security_model_usage_daily'):
        raise ValueError('invalid aggregate table')
    condition = "IN ('security','security_check')" if security else "NOT IN ('security','security_check')"
    counters = ['input_tokens','cache_hit_tokens','cache_miss_tokens','output_tokens']
    flags = [('response_cache_hit','response_cache_hits'), ('classification_cache_hit','classification_cache_hits')]
    expressions = ["COUNT(DISTINCT COALESCE(NULLIF(e.payload->>'request_id',''),e.event_id)) AS requests", 'COUNT(*) AS events',
                   "SUM((e.payload->>'attempt')::boolean::integer) AS attempts",
                   "SUM((e.payload->>'success')::boolean::integer) AS successes",
                   "SUM((NOT (e.payload->>'success')::boolean)::integer) AS failures"]
    expressions += [f"SUM((e.payload->>'{name}')::bigint) AS {name}" for name in counters]
    expressions += [f"SUM((e.payload->>'{source}')::boolean::integer) AS {dest}" for source,dest in flags]
    expressions += ["SUM(((e.payload->>'attempt')::boolean AND NOT (e.payload->>'usage_reported')::boolean)::integer) AS unknown_usage_attempts",
                    "SUM((COALESCE(e.payload->>'decision','')='unavailable')::integer) AS unavailable", "SUM((e.payload->>'upgrade')::boolean::integer) AS upgrades", "SUM((e.payload->>'downgrade')::boolean::integer) AS downgrades"]
    names = ['requests','events','attempts','successes','failures'] + counters + [dest for _,dest in flags] + ['unknown_usage_attempts','unavailable','upgrades','downgrades']
    return f'''
      INSERT INTO {table}
      SELECT (e.payload->>'date')::date,e.payload->>'region',e.payload->>'api_key_id',k.api_key_id,
             e.payload->>'purpose',e.payload->>'effective_model',e.payload->>'effective_reasoning_effort',
             {','.join(expressions)}
      FROM gateway_usage_events e
      JOIN affected a ON (e.payload->>'date',e.payload->>'region',e.payload->>'api_key_id',e.payload->>'purpose',e.payload->>'effective_model',e.payload->>'effective_reasoning_effort')
                       =(a.date,a.region,a.key_hash,a.purpose,a.model,a.effort)
      LEFT JOIN gateway_key_mapping k ON k.region=e.payload->>'region' AND k.key_hash=e.payload->>'api_key_id'
      WHERE e.payload->>'purpose' {condition}
      GROUP BY 1,2,3,4,5,6,7
      ON CONFLICT(date,region,api_key_hash,purpose,effective_model,effective_reasoning_effort)
      DO UPDATE SET api_key_id=EXCLUDED.api_key_id,{','.join(name+'=EXCLUDED.'+name for name in names)};
    '''


def export_batch(region, ledger, mapping, limit=500):
    rows = ledger.db.execute('SELECT event_id,payload FROM events WHERE exported=0 AND region=? ORDER BY date,event_id LIMIT ?', (region,limit)).fetchall()
    events = [json.loads(raw) for _,raw in rows]
    script = '''BEGIN;
      CREATE TEMP TABLE incoming_mapping(payload jsonb) ON COMMIT DROP;
      COPY incoming_mapping FROM STDIN WITH (FORMAT csv);
    '''.rstrip() + '\n' + csv_rows(mapping) + '\\.\n'
    script += '''
      DO $$ BEGIN
        IF EXISTS(SELECT 1 FROM incoming_mapping i JOIN gateway_key_mapping k ON k.region=i.payload->>'region' AND k.key_hash=i.payload->>'key_hash'
                  WHERE k.api_key_id<>(i.payload->>'api_key_id')::bigint) THEN RAISE EXCEPTION 'Key mapping conflict'; END IF;
      END $$;
      INSERT INTO gateway_key_mapping SELECT payload->>'region',payload->>'key_hash',(payload->>'api_key_id')::bigint FROM incoming_mapping ON CONFLICT DO NOTHING;
      CREATE TEMP TABLE incoming_events(payload jsonb) ON COMMIT DROP;
      COPY incoming_events FROM STDIN WITH (FORMAT csv);
    '''.rstrip() + '\n' + csv_rows(events) + '\\.\n'
    script += '''
      INSERT INTO gateway_usage_events(event_id,payload) SELECT payload->>'event_id',payload FROM incoming_events ON CONFLICT DO NOTHING;
      CREATE TEMP TABLE affected ON COMMIT DROP AS
        SELECT DISTINCT payload->>'date' AS date,payload->>'region' AS region,payload->>'api_key_id' AS key_hash,payload->>'purpose' AS purpose,
                        payload->>'effective_model' AS model,payload->>'effective_reasoning_effort' AS effort FROM incoming_events;
    '''
    script += aggregate_sql('model_usage_daily', False) + aggregate_sql('security_model_usage_daily', True)
    for table in ('model_usage_daily','security_model_usage_daily'):
        script += f'UPDATE {table} d SET api_key_id=k.api_key_id FROM gateway_key_mapping k WHERE d.region=k.region AND d.api_key_hash=k.key_hash AND d.api_key_id IS DISTINCT FROM k.api_key_id;\n'
    script += 'COMMIT;\n'
    psql(region, script)
    # The remote transaction may have committed even if its acknowledgement was
    # lost. Repeating the same event IDs rebuilds affected totals without adding.
    with ledger.db:
        ledger.db.executemany('UPDATE events SET exported=1 WHERE event_id=?', [(identifier,) for identifier,_ in rows])
    return len(rows)


def run(region, root, initialize_db=False):
    root = Path(root)
    secret = (root/'secrets/cache-secret').read_text().strip()
    mapping = json.loads(ssh(region, 'python3 -c ' + shlex.quote(KEYMAP_HELPER), json.dumps({'region':region,'secret':secret})))
    if initialize_db:
        initialize(region)
    ledger = Ledger(root/'ops/usage-ledger.sqlite')
    try:
        ledger.map_keys(mapping)
        imported = []
        for folder, filename in [('auto','usage.jsonl'),('guard','security-usage.jsonl'),('guard','security-decisions.jsonl')]:
            for path in sorted((root/'logs'/folder).glob(filename+'*')):
                if path.name.endswith('.lock') or path.suffix=='.gz' or not path.is_file():
                    continue
                imported.append(ledger.ingest(path))
        exported = 0
        for _ in range(20):
            amount = export_batch(region, ledger, mapping)
            exported += amount
            if amount < 500:
                break
        remaining = ledger.db.execute('SELECT COUNT(*) FROM events WHERE exported=0').fetchone()[0]
        return {'region':region,'imported':sum(row['inserted'] for row in imported),'exported':exported,'remaining':remaining,
                'key_mappings':len(mapping),'partial_spools':sum(row['partial_tail'] for row in imported)}
    finally:
        ledger.close()


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', choices=tuple(HOSTS), required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--initialize', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.region,args.root,args.initialize)))
    except Exception as error:
        print(json.dumps({'region':args.region,'status':'failed','error_type':type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
