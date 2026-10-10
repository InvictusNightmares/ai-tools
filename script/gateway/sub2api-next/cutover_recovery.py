#!/usr/bin/env python3
"""Prove recovery of merged B plus simulated subsequent writes, clone only."""
import argparse
import json
import os
from pathlib import Path
import secrets
import time

from cutover_merge import OPS,check,guard,sql,value,table_certificate
from cutover_local import snapshot,restore,drop_rehearsal

DB='cutover_rehearsal'


def certificates():
    tables=value(DB,"SELECT json_agg(json_build_array(schemaname,tablename) ORDER BY schemaname,tablename) FROM pg_tables WHERE schemaname IN('public','cutover_audit')")
    parts=["BEGIN; SET LOCAL TIME ZONE 'UTC'; SET LOCAL work_mem='16MB'; SET LOCAL temp_file_limit='512MB';"]
    for schema,table in tables:
        parts.append("SELECT json_build_object('table','{}.{}','certificate',({}));".format(schema,table,table_certificate(table,schema=schema)))
    parts.append("SELECT jsonb_build_object('sequences',(SELECT jsonb_agg(to_jsonb(t) ORDER BY schemaname,sequencename) FROM (SELECT schemaname,sequencename,last_value,increment_by,min_value,max_value,cycle,cache_size FROM pg_sequences WHERE schemaname IN('public','cutover_audit'))t)); COMMIT;")
    rows=[json.loads(x) for x in sql(DB,'\n'.join(parts)).splitlines() if x.startswith('{')]
    return {'tables':{r['table']:r['certificate'] for r in rows if 'table' in r},'sequences':next(r['sequences'] for r in rows if 'sequences' in r)}


def prepare():
    check(value(DB,"SELECT to_json(bool_and(complete)) FROM cutover_audit.build_state") is True,'merged core and V2 must pass first')
    check(not (OPS/'rehearsal-recovery-before.json').exists(),'recovery test already prepared')
    # Remove foreign credentials and references before taking any recovery dump.
    sql(DB,"DROP SCHEMA IF EXISTS source_a_facts CASCADE; DROP SCHEMA IF EXISTS source_a CASCADE; DROP SCHEMA IF EXISTS source_b CASCADE; DROP SERVER IF EXISTS source_a CASCADE; DROP SERVER IF EXISTS source_b CASCADE; DROP EXTENSION IF EXISTS postgres_fdw;")
    marker=secrets.token_hex(16)
    query="""BEGIN;
      CREATE TABLE cutover_audit.recovery_case AS SELECT k.id key_id,k.user_id,
        (SELECT max(id) FROM usage_logs)+1 usage_id FROM api_keys k JOIN users u ON u.id=k.user_id
        WHERE u.role='user' AND u.deleted_at IS NULL AND k.deleted_at IS NULL AND k.status='active' ORDER BY k.id LIMIT 1;
      INSERT INTO usage_logs SELECT (jsonb_populate_record(NULL::public.usage_logs,to_jsonb(l)||jsonb_build_object(
        'id',c.usage_id,'api_key_id',c.key_id,'user_id',c.user_id,'request_id','recovery-%s',
        'created_at',now(),'total_cost',0.123456789,'actual_cost',0.123456789))).*
        FROM cutover_audit.recovery_case c CROSS JOIN LATERAL (SELECT * FROM usage_logs WHERE api_key_id=c.key_id ORDER BY id DESC LIMIT 1) l;
      UPDATE users SET balance=balance-0.123456789,password_hash=password_hash||'-recovery' WHERE id=(SELECT user_id FROM cutover_audit.recovery_case);
      UPDATE api_keys SET key='sk-recovery-%s',name='isolated recovery rehearsal' WHERE id=(SELECT key_id FROM cutover_audit.recovery_case);
      UPDATE user_platform_quotas SET weekly_usage_usd=weekly_usage_usd+0.123456789 WHERE user_id=(SELECT user_id FROM cutover_audit.recovery_case) AND platform='openai' AND deleted_at IS NULL;
      UPDATE accounts SET credentials=credentials||jsonb_build_object('access_token','recovery-%s','refresh_token','recovery-%s') WHERE id=51;
      SELECT setval('usage_logs_id_seq',(SELECT max(id) FROM usage_logs)); COMMIT;"""%(marker,marker,marker,marker)
    sql(DB,query)
    checkpoint()


def checkpoint():
    check(not (OPS/'rehearsal-recovery-before.json').exists(),'recovery checkpoint already exists')
    check(value(DB,"SELECT to_json(count(*)=1) FROM cutover_audit.recovery_case") is True,'owned simulated case missing')
    check(value(DB,"SELECT to_json(count(*)=1) FROM usage_logs WHERE id=(SELECT usage_id FROM cutover_audit.recovery_case)") is True,'simulated subsequent request missing')
    record=certificates();record['marker_hash_only']=True
    (OPS/'rehearsal-recovery-before.json').write_text(json.dumps(record,indent=2))
    snapshot('rehearsal','merged')
    print(json.dumps({'recovery_snapshot_ready':True,'certified_tables':len(record['tables']),'simulated_changes':['usage','balance','password','key','quota','OAuth']}),flush=True)


def recover():
    before=json.loads((OPS/'rehearsal-recovery-before.json').read_text())
    drop_rehearsal();restore('rehearsal','merged')
    after=certificates()
    check(before['tables']==after['tables'] and before['sequences']==after['sequences'],'recovered database certificate differs')
    result={'recovery_passed':True,'method':'official B logical backup and restore','all_merged_history_preserved':True,
        'simulated_subsequent_writes_preserved':True,'tables':len(after['tables']),'sequences':len(after['sequences']),
        'old_binary_not_used':True,'verified_at_epoch':int(time.time())}
    (OPS/'rehearsal-recovery.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


def main():
    os.umask(0o077);guard()
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','checkpoint','recover']);args=p.parse_args()
    {'prepare':prepare,'checkpoint':checkpoint,'recover':recover}[args.action]()

if __name__=='__main__':main()
