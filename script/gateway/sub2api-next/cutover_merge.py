#!/usr/bin/env python3
"""Merge A history into a compact B clone, entirely on the US-West host.

No app runs against the clone. All A reads, mutations and verification share
one PostgreSQL transaction/FDW snapshot. Final promotion is a separate step.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

ROOT = Path('/opt/sub2api-next')
OPS = ROOT / 'ops' / 'cutover'
CONTAINER = 'sub2api-next-postgres'
SOURCE_CONTAINER = 'sub2api-postgres'
SOURCE_NETWORK = 'sub2api-deploy_sub2api-network'
SOURCE_ROLE = 'cutover_reader_20261009'
BASE_USAGE_MAX = 2007519
BASE_USAGE_ROWS = 1549460
QA_PREDICATE = "((id BETWEEN 2007520 AND 2007558 AND user_id=79 AND api_key_id BETWEEN 92 AND 100) OR (api_key_id=90 AND id IN (2007559,2007560,2007561)))"
APPEND_TABLES = ('usage_logs', 'usage_billing_dedup', 'audit_logs', 'ops_error_logs', 'deleted_api_key_audits')
EMPTY_LEDGERS = ('billing_usage_entries', 'payment_orders', 'payment_audit_logs',
                 'user_affiliate_ledger', 'batch_image_jobs', 'batch_image_items',
                 'batch_image_events', 'user_subscriptions', 'usage_billing_dedup_archive',
                 'promo_code_usages', 'prompt_audit_jobs', 'prompt_audit_events',
                 'content_moderation_logs', 'scheduled_test_results', 'usage_cleanup_tasks')
DERIVED = ('usage_dashboard_hourly', 'usage_dashboard_daily', 'usage_dashboard_hourly_users',
           'usage_dashboard_daily_users', 'usage_dashboard_aggregation_watermark',
           'usage_group_daily_rollups', 'usage_group_rollup_state')
DATABASES = ('postgres', 'sub2api_next', 'cutover_rehearsal', 'cutover_final')


def check(value, message):
    if not value:
        raise RuntimeError(message)


def run(args, data=None, timeout=1800):
    p = subprocess.run(args, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       universal_newlines=True, timeout=timeout)
    if p.returncode:
        OPS.mkdir(exist_ok=True)
        (OPS / 'merge-error.log').write_text(p.stderr)
        raise RuntimeError('cutover command failed; details in private merge-error.log')
    return p.stdout.strip()


def sql(database, query, source=False):
    check(database in DATABASES or (source and database == 'sub2api'), 'database outside cutover scope')
    return run(['docker', 'exec', '-i', SOURCE_CONTAINER if source else CONTAINER,
                'psql', '-XqAt', '-v', 'ON_ERROR_STOP=1', '-U', 'sub2api', '-d', database], query)


def value(database, query):
    return json.loads(sql(database, query))


def guard():
    check(ROOT.is_dir() and (ROOT / 'ops' / 'migration-baseline.json').is_file(), 'wrong host or candidate directory')
    info = json.loads(run(['docker', 'inspect', CONTAINER]))[0]
    check(any(m['Source'] == str(ROOT / 'postgres_data') and m['Destination'] == '/var/lib/postgresql'
              for m in info['Mounts']), 'unexpected PostgreSQL data mount')
    check(not info['HostConfig'].get('PortBindings'), 'candidate PostgreSQL has published ports')
    OPS.mkdir(exist_ok=True)


def connect_source():
    """Temporary least-privilege role; no original application data is changed."""
    private = OPS / 'source-reader.json'
    if private.exists():
        auth = json.loads(private.read_text())
    else:
        check(sql('sub2api', "SELECT count(*) FROM pg_roles WHERE rolname='{}'".format(SOURCE_ROLE), True) == '0',
              'unowned source role already exists')
        auth = {'password': secrets.token_hex(24)}
        private.write_text(json.dumps(auth))
        os.chmod(str(private), 0o600)
        sql('sub2api', """CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
          NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD '{password}';
          GRANT CONNECT ON DATABASE sub2api TO {role};
          GRANT USAGE ON SCHEMA public TO {role};
          GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role};
          ALTER ROLE {role} SET default_transaction_read_only=on;
          """.format(role=SOURCE_ROLE, password=auth['password']), True)
    sql('sub2api', """CREATE SCHEMA IF NOT EXISTS cutover_read_20261009;
      CREATE OR REPLACE VIEW cutover_read_20261009.usage_facts AS
        SELECT id,api_key_id,encode(sha256(convert_to((to_jsonb(t)-'id'-'user_id')::text,'UTF8')),'hex') facts_hash
        FROM public.usage_logs t;
      GRANT USAGE ON SCHEMA cutover_read_20261009 TO cutover_reader_20261009;
      GRANT SELECT ON cutover_read_20261009.usage_facts TO cutover_reader_20261009;""",True)
    info = json.loads(run(['docker', 'inspect', CONTAINER]))[0]
    if SOURCE_NETWORK not in info['NetworkSettings']['Networks']:
        run(['docker', 'network', 'connect', '--alias', 'cutover-b-postgres', SOURCE_NETWORK, CONTAINER])
    source = json.loads(run(['docker', 'inspect', SOURCE_CONTAINER]))[0]
    auth['host'] = source['NetworkSettings']['Networks'][SOURCE_NETWORK]['IPAddress']
    private.write_text(json.dumps(auth))
    print(json.dumps({'temporary_source_read_access': True}), flush=True)


def attach(database, final=False):
    auth = json.loads((OPS / 'source-reader.json').read_text())
    check(re.fullmatch(r'[0-9.]+', auth['host']) and re.fullmatch(r'[0-9a-f]{48}', auth['password']), 'invalid private source mapping')
    sql(database, """CREATE EXTENSION IF NOT EXISTS postgres_fdw;
    CREATE SERVER source_a FOREIGN DATA WRAPPER postgres_fdw OPTIONS(
      host '{host}',dbname 'sub2api',fetch_size '5000',updatable 'false',truncatable 'false');
    CREATE USER MAPPING FOR CURRENT_USER SERVER source_a OPTIONS(user '{role}',password '{password}');
    CREATE SCHEMA source_a;
    IMPORT FOREIGN SCHEMA public FROM SERVER source_a INTO source_a;
    """.format(role=SOURCE_ROLE, **auth))
    sql(database,"CREATE SCHEMA IF NOT EXISTS source_a_facts; IMPORT FOREIGN SCHEMA cutover_read_20261009 FROM SERVER source_a INTO source_a_facts;")
    if final:
        sql(database, """CREATE SERVER source_b FOREIGN DATA WRAPPER postgres_fdw
          OPTIONS(host '/var/run/postgresql',dbname 'sub2api_next',fetch_size '5000',updatable 'false',truncatable 'false');
          CREATE USER MAPPING FOR CURRENT_USER SERVER source_b OPTIONS(user 'sub2api');
          CREATE SCHEMA source_b;
          IMPORT FOREIGN SCHEMA public FROM SERVER source_b INTO source_b;""")


def assert_sql(condition, message):
    check("'" not in message, 'invalid diagnostic')
    return "SELECT pg_temp.check_true(({}),'{}');\n".format(condition, message)


def table_certificate(table, where='TRUE', schema='public'):
    # A sorted stream of cryptographic row hashes preserves multiplicity, works
    # for tables without a primary key, and never emits credentials/payloads.
    return """WITH hashed AS MATERIALIZED (
      SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') row_hash
      FROM {schema}.{table} t WHERE {where})
      SELECT jsonb_build_object('rows',count(*),'sha256',
        encode(sha256(convert_to(coalesce(string_agg(row_hash,'' ORDER BY row_hash),''),'UTF8')),'hex'))
      FROM hashed""".format(table=table, where=where, schema=schema)


def dashboard_sql():
    # Old dashboards can retain totals beyond raw-log retention. Only rebuild
    # buckets touched by imported A rows or the exact excluded QA requests.
    parts = ["""CREATE TEMP TABLE affected_hours AS SELECT DISTINCT date_trunc('hour',created_at) bucket_start
      FROM (SELECT created_at FROM incoming_usage_logs UNION ALL SELECT created_at FROM cutover_audit.excluded_qa)x;
      CREATE TEMP TABLE affected_days AS SELECT DISTINCT (created_at AT TIME ZONE 'Asia/Shanghai')::date bucket_date
      FROM (SELECT created_at FROM incoming_usage_logs UNION ALL SELECT created_at FROM cutover_audit.excluded_qa)x;
      CREATE TEMP TABLE unchanged_derived_certs(table_name text PRIMARY KEY,certificate jsonb);
      """]
    parts.append(assert_sql("NOT EXISTS(SELECT 1 FROM affected_days WHERE bucket_date<=(SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date FROM cutover_audit.b_raw_boundary))", 'affected day intersects incomplete raw retention boundary'))
    parts.append(assert_sql("NOT EXISTS(SELECT 1 FROM affected_hours WHERE bucket_start<=(SELECT date_trunc('hour',created_at) FROM cutover_audit.b_raw_boundary))", 'affected hour intersects incomplete raw retention boundary'))
    buckets = [('hourly', "date_trunc('hour',created_at)", 'bucket_start','affected_hours'),
               ('daily', "(created_at AT TIME ZONE 'Asia/Shanghai')::date", 'bucket_date','affected_days')]
    for period, expression, column, touched in buckets:
        tables = ('usage_dashboard_'+period, 'usage_dashboard_'+period+'_users')
        predicate = '{c} NOT IN(SELECT {c} FROM {a})'.format(c=column,a=touched)
        for table in tables:
            parts.append("INSERT INTO unchanged_derived_certs SELECT '{}',({});".format(table,table_certificate(table,predicate)))
            parts.append('DELETE FROM {t} WHERE {c} IN(SELECT {c} FROM {a});'.format(t=table,c=column,a=touched))
        expected = """SELECT {bucket} AS {column},count(*)::bigint total_requests,
          sum(input_tokens)::bigint input_tokens,sum(output_tokens)::bigint output_tokens,
          sum(cache_creation_tokens)::bigint cache_creation_tokens,sum(cache_read_tokens)::bigint cache_read_tokens,
          sum(total_cost) total_cost,sum(actual_cost) actual_cost,
          sum(coalesce(account_stats_cost,total_cost)*coalesce(account_rate_multiplier,1)) account_cost,
          sum(coalesce(duration_ms,0))::bigint total_duration_ms,count(DISTINCT user_id)::bigint active_users
          FROM usage_logs WHERE {bucket} IN(SELECT {column} FROM {touched}) GROUP BY 1""".format(bucket=expression,column=column,touched=touched)
        columns = column + ',total_requests,input_tokens,output_tokens,cache_creation_tokens,cache_read_tokens,total_cost,actual_cost,account_cost,total_duration_ms,active_users'
        parts.append('CREATE TEMP TABLE expected_{p} (LIKE usage_dashboard_{p} INCLUDING DEFAULTS); INSERT INTO expected_{p}({cols}) {query};'.format(p=period,cols=columns,query=expected))
        parts.append('INSERT INTO usage_dashboard_{0}({1}) SELECT {1} FROM expected_{0};'.format(period,columns))
        parts.append('INSERT INTO usage_dashboard_{p}_users SELECT DISTINCT {e},user_id FROM usage_logs WHERE {e} IN(SELECT {c} FROM {a});'.format(p=period,e=expression,c=column,a=touched))
        actual='SELECT {cols} FROM usage_dashboard_{p} WHERE {c} IN(SELECT {c} FROM {a})'.format(cols=columns,p=period,c=column,a=touched)
        want='SELECT {cols} FROM expected_{p}'.format(cols=columns,p=period)
        parts.append(assert_sql('NOT EXISTS(({} EXCEPT ALL {}) UNION ALL ({} EXCEPT ALL {}))'.format(actual,want,want,actual),'dashboard full affected bucket mismatch '+period))
        actual='SELECT {c},user_id FROM usage_dashboard_{p}_users WHERE {c} IN(SELECT {c} FROM {a})'.format(c=column,p=period,a=touched)
        want='SELECT DISTINCT {e},user_id FROM usage_logs WHERE {e} IN(SELECT {c} FROM {a})'.format(e=expression,c=column,a=touched)
        parts.append(assert_sql('NOT EXISTS(({} EXCEPT ALL {}) UNION ALL ({} EXCEPT ALL {}))'.format(actual,want,want,actual),'dashboard affected membership mismatch '+period))
        for table in tables:
            parts.append(assert_sql("({})=(SELECT certificate FROM unchanged_derived_certs WHERE table_name='{}')".format(table_certificate(table,predicate),table),'untouched historical aggregate changed '+table))
    predicate='bucket_date NOT IN(SELECT bucket_date FROM affected_days)'
    parts.append("INSERT INTO unchanged_derived_certs SELECT 'usage_group_daily_rollups',({});".format(table_certificate('usage_group_daily_rollups',predicate)))
    parts.append("""DELETE FROM usage_group_daily_rollups WHERE bucket_date IN(SELECT bucket_date FROM affected_days);
      CREATE TEMP TABLE expected_group (LIKE usage_group_daily_rollups INCLUDING DEFAULTS);
      INSERT INTO expected_group(bucket_date,group_id,actual_cost) SELECT (created_at AT TIME ZONE 'Asia/Shanghai')::date bucket_date,
        group_id,sum(actual_cost) actual_cost FROM usage_logs WHERE group_id IS NOT NULL
        AND (created_at AT TIME ZONE 'Asia/Shanghai')::date IN(SELECT bucket_date FROM affected_days) GROUP BY 1,2;
      INSERT INTO usage_group_daily_rollups SELECT * FROM expected_group;
      DELETE FROM usage_group_rollup_state;
      INSERT INTO usage_group_rollup_state SELECT * FROM group_state_before;""")
    parts.append(assert_sql("NOT EXISTS((SELECT * FROM usage_group_daily_rollups WHERE bucket_date IN(SELECT bucket_date FROM affected_days) EXCEPT ALL SELECT * FROM expected_group) UNION ALL (SELECT * FROM expected_group EXCEPT ALL SELECT * FROM usage_group_daily_rollups WHERE bucket_date IN(SELECT bucket_date FROM affected_days)))",'affected group daily totals differ'))
    parts.append(assert_sql("({})=(SELECT certificate FROM unchanged_derived_certs WHERE table_name='usage_group_daily_rollups')".format(table_certificate('usage_group_daily_rollups',predicate)),'untouched group daily history changed'))
    parts.append(assert_sql("NOT EXISTS((TABLE usage_group_rollup_state EXCEPT ALL TABLE group_state_before) UNION ALL (TABLE group_state_before EXCEPT ALL TABLE usage_group_rollup_state))",'group retention state changed'))
    parts.append(assert_sql("NOT EXISTS((TABLE usage_dashboard_aggregation_watermark EXCEPT ALL TABLE dashboard_watermark_before) UNION ALL (TABLE dashboard_watermark_before EXCEPT ALL TABLE usage_dashboard_aggregation_watermark))",'dashboard watermark changed'))
    return '\n'.join(parts)


def build_sql(tables, baseline, final=False):
    check(len(baseline) == 91 and len({k['id'] for k in baseline}) == 91, 'original key identity inventory differs')
    for k in baseline:
        check(isinstance(k['id'], int) and re.fullmatch('[0-9a-f]{32}', k['key_digest']), 'invalid original key identity')
    identities = ','.join("({},'{}')".format(k['id'],k['key_digest']) for k in baseline)
    parts = ["""BEGIN ISOLATION LEVEL REPEATABLE READ;
      SET LOCAL statement_timeout='40min'; SET LOCAL lock_timeout='5s';
      SET LOCAL TIME ZONE 'UTC'; SET LOCAL DateStyle='ISO,YMD';
      SET LOCAL work_mem='16MB'; SET LOCAL temp_file_limit='768MB'; SET LOCAL max_parallel_workers_per_gather=0;
      CREATE FUNCTION pg_temp.check_true(ok boolean,msg text) RETURNS void LANGUAGE plpgsql AS
        $$ BEGIN IF ok IS DISTINCT FROM TRUE THEN RAISE EXCEPTION '%',msg; END IF; END $$;
      CREATE SCHEMA cutover_audit;
      CREATE TABLE cutover_audit.build_state(name text PRIMARY KEY,complete boolean NOT NULL);
      INSERT INTO cutover_audit.build_state VALUES('core',false),('v2',false);
      CREATE TABLE cutover_audit.b_certificates(table_name text PRIMARY KEY,certificate jsonb);
      CREATE TABLE cutover_audit.source_map(source_table text,source_id bigint,target_id bigint,source_hash text,
        PRIMARY KEY(source_table,source_id),UNIQUE(source_table,target_id));
      CREATE TABLE cutover_audit.excluded_qa AS SELECT * FROM usage_logs WHERE {qa}; CREATE TABLE cutover_audit.b_raw_boundary AS SELECT min(created_at) created_at FROM usage_logs;
      CREATE TEMP TABLE group_state_before AS SELECT * FROM usage_group_rollup_state;
      CREATE TEMP TABLE dashboard_watermark_before AS SELECT * FROM usage_dashboard_aggregation_watermark;
      """.format(qa=QA_PREDICATE)]
    parts += [assert_sql('(SELECT count(*) FROM cutover_audit.excluded_qa)=42','QA inventory differs'),
              assert_sql('(SELECT count(*) FROM usage_logs WHERE id<=2007519)=1549460','original B history differs'),
              assert_sql("NOT EXISTS(SELECT 1 FROM source_a.api_keys a LEFT JOIN (VALUES {}) original(id,digest) ON original.id=a.id WHERE original.id IS NULL OR md5(a.key)<>original.digest)".format(identities),'source key identity changed')]
    if final:
        parts.append(assert_sql("(SELECT array_agg(relname ORDER BY relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r')=(SELECT array_agg(relname ORDER BY relname) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='source_b' AND c.relkind='f')", 'frozen B table inventory differs'))
        parts.append(assert_sql("(SELECT jsonb_agg(jsonb_build_array(c.relname,a.attname,a.atttypid,a.atttypmod,a.attnotnull) ORDER BY c.relname,a.attnum) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped)=(SELECT jsonb_agg(jsonb_build_array(c.relname,a.attname,a.atttypid,a.atttypmod,a.attnotnull) ORDER BY c.relname,a.attnum) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='source_b' AND c.relkind='f' AND a.attnum>0 AND NOT a.attisdropped)", 'frozen B column inventory differs'))
    for table in EMPTY_LEDGERS:
        parts.append(assert_sql('(SELECT count(*) FROM source_a.{0})+(SELECT count(*) FROM public.{0})=0'.format(table), 'unexpected business ledger ' + table))
    for table in ('users','api_keys','groups','accounts'):
        parts.append(assert_sql('NOT EXISTS(SELECT 1 FROM source_a.{0} a LEFT JOIN public.{0} b USING(id) WHERE b.id IS NULL OR a.created_at IS DISTINCT FROM b.created_at)'.format(table), 'unmapped source entity ' + table))
    parts.append(assert_sql('NOT EXISTS(SELECT 1 FROM source_a.redeem_codes a LEFT JOIN public.redeem_codes b USING(id) WHERE b.id IS NULL OR to_jsonb(a)<>to_jsonb(b))','source redemption state differs'))
    for table in APPEND_TABLES:
        parts.append(assert_sql("(SELECT jsonb_agg(jsonb_build_array(attname,atttypid,atttypmod) ORDER BY attnum) FROM pg_attribute WHERE attrelid='public.{t}'::regclass AND attnum>0 AND NOT attisdropped)=(SELECT jsonb_agg(jsonb_build_array(attname,atttypid,atttypmod) ORDER BY attnum) FROM pg_attribute WHERE attrelid='source_a.{t}'::regclass AND attnum>0 AND NOT attisdropped)".format(t=table), 'source column mismatch ' + table))
    for table in tables:
        if table in DERIVED:
            if final:
                comparison='(SELECT to_jsonb(t) FROM public.{t} t EXCEPT ALL SELECT to_jsonb(t) FROM source_b.{t} t) UNION ALL (SELECT to_jsonb(t) FROM source_b.{t} t EXCEPT ALL SELECT to_jsonb(t) FROM public.{t} t)'.format(t=table)
                parts.append(assert_sql('NOT EXISTS('+comparison+')','initial frozen B aggregate differs '+table))
            continue
        predicate = 'NOT '+QA_PREDICATE if table=='usage_logs' else 'TRUE'
        parts.append("SELECT json_build_object('progress','B_certificate','table','{}');".format(table))
        parts.append("INSERT INTO cutover_audit.b_certificates SELECT '{}',({});".format(table,table_certificate(table,predicate)))
    parts.append("CREATE TEMP TABLE a_usage_facts AS SELECT * FROM source_a_facts.usage_facts; CREATE UNIQUE INDEX ON a_usage_facts(id); ANALYZE a_usage_facts; CREATE TEMP TABLE b_usage_facts AS SELECT id,api_key_id,user_id,encode(sha256(convert_to((to_jsonb(t)-'id'-'user_id')::text,'UTF8')),'hex') facts_hash FROM usage_logs t; CREATE UNIQUE INDEX ON b_usage_facts(id); ANALYZE b_usage_facts;")
    parts.append(assert_sql("NOT EXISTS(SELECT 1 FROM a_usage_facts a JOIN b_usage_facts b USING(id) WHERE b.id<=2007519 AND a.facts_hash<>b.facts_hash)",'common usage facts changed'))
    parts.append("CREATE TABLE cutover_audit.b_only_original AS SELECT b.id,b.facts_hash FROM b_usage_facts b LEFT JOIN a_usage_facts a USING(id) WHERE b.id<=2007519 AND a.id IS NULL;")
    parts.append("""CREATE TEMP TABLE incoming_usage_logs (LIKE public.usage_logs);
      DO $$ DECLARE ids text; BEGIN
        SELECT string_agg(a.id::text,',') INTO ids FROM a_usage_facts a
          LEFT JOIN usage_logs b ON b.id=a.id AND b.id<=2007519 WHERE b.id IS NULL;
        IF ids IS NOT NULL THEN
          EXECUTE 'INSERT INTO incoming_usage_logs SELECT * FROM source_a.usage_logs WHERE id=ANY(ARRAY['||ids||']::bigint[])';
        END IF;
      END $$;
      INSERT INTO cutover_audit.source_map SELECT 'usage_logs',id,
        (SELECT max(id) FROM usage_logs)+row_number() OVER(ORDER BY id),md5(to_jsonb(a)::text) FROM incoming_usage_logs a;
      INSERT INTO usage_logs SELECT (jsonb_populate_record(NULL::public.usage_logs,to_jsonb(a)||
        jsonb_build_object('id',m.target_id,'user_id',k.user_id))).*
        FROM incoming_usage_logs a JOIN cutover_audit.source_map m ON m.source_table='usage_logs' AND m.source_id=a.id
        JOIN api_keys k ON k.id=a.api_key_id;
      DELETE FROM usage_logs WHERE id IN (SELECT id FROM cutover_audit.excluded_qa);
      SELECT setval('usage_logs_id_seq',(SELECT max(id) FROM usage_logs));""")
    parts.append(assert_sql('NOT EXISTS(SELECT 1 FROM source_a.usage_billing_dedup a JOIN usage_billing_dedup b USING(request_id,api_key_id) WHERE a.request_fingerprint<>b.request_fingerprint)','billing dedup conflict'))
    for table in APPEND_TABLES[1:]:
        predicate = 'a.request_id=b.request_id AND a.api_key_id=b.api_key_id' if table=='usage_billing_dedup' else 'a.id=b.id AND to_jsonb(a)=to_jsonb(b)'
        parts.append("""CREATE TEMP TABLE incoming_{t} AS SELECT a.* FROM source_a.{t} a LEFT JOIN public.{t} b ON {predicate} WHERE b.id IS NULL;
          INSERT INTO cutover_audit.source_map SELECT '{t}',id,
            coalesce((SELECT max(id) FROM public.{t}),0)+row_number() OVER(ORDER BY id),md5(to_jsonb(a)::text) FROM incoming_{t} a;
          INSERT INTO public.{t} SELECT (jsonb_populate_record(NULL::public.{t},to_jsonb(a)||jsonb_build_object('id',m.target_id))).*
            FROM incoming_{t} a JOIN cutover_audit.source_map m ON m.source_table='{t}' AND m.source_id=a.id;
          SELECT setval(pg_get_serial_sequence('public.{t}','id'),greatest(coalesce((SELECT max(id) FROM public.{t}),0),1),(SELECT count(*)>0 FROM public.{t}));
          """.format(t=table,predicate=predicate))
    parts.append(dashboard_sql())
    # The following certificates prove all original B rows/config survived.
    # Imported A target IDs are outside the B identity domain, recorded exactly.
    for table in tables:
        if table in DERIVED:
            continue
        predicate = "NOT EXISTS(SELECT 1 FROM cutover_audit.source_map m WHERE m.source_table='{}' AND m.target_id=t.id)".format(table) if table in APPEND_TABLES else 'TRUE'
        parts.append(assert_sql("({})=(SELECT certificate FROM cutover_audit.b_certificates WHERE table_name='{}')".format(table_certificate(table,predicate),table), 'B certificate mismatch ' + table))
        if final:
            if table in APPEND_TABLES:
                bpredicate = 'NOT '+QA_PREDICATE if table=='usage_logs' else 'TRUE'
                parts.append(assert_sql("({})=(SELECT certificate FROM cutover_audit.b_certificates WHERE table_name='{}')".format(table_certificate(table,bpredicate,'source_b'),table), 'frozen B complete row certificate differs ' + table))
                continue
            else:
                comparison = '(SELECT to_jsonb(t) FROM public.{t} t EXCEPT ALL SELECT to_jsonb(t) FROM source_b.{t} t) UNION ALL (SELECT to_jsonb(t) FROM source_b.{t} t EXCEPT ALL SELECT to_jsonb(t) FROM public.{t} t)'.format(t=table)
            parts.append(assert_sql('NOT EXISTS('+comparison+')','frozen B exact comparison differs ' + table))
    parts.append("DELETE FROM b_usage_facts WHERE id IN(SELECT id FROM cutover_audit.excluded_qa); INSERT INTO b_usage_facts SELECT t.id,t.api_key_id,t.user_id,encode(sha256(convert_to((to_jsonb(t)-'id'-'user_id')::text,'UTF8')),'hex') FROM usage_logs t JOIN cutover_audit.source_map m ON m.source_table='usage_logs' AND m.target_id=t.id; ANALYZE b_usage_facts;")
    for table in APPEND_TABLES:
        predicate = 'm.request_id=a.request_id AND m.api_key_id=a.api_key_id' if table=='usage_billing_dedup' else 'm.id=coalesce(s.target_id,a.id)'
        fields = "-'id'-'user_id'" if table=='usage_logs' else "-'id'"
        owner = ' OR m.user_id<>(SELECT user_id FROM api_keys WHERE id=a.api_key_id)' if table=='usage_logs' else ''
        if table=='usage_logs':
            parts.append(assert_sql("NOT EXISTS(SELECT 1 FROM a_usage_facts a LEFT JOIN cutover_audit.source_map s ON s.source_table='usage_logs' AND s.source_id=a.id LEFT JOIN b_usage_facts m ON m.id=coalesce(s.target_id,a.id) WHERE m.id IS NULL OR a.facts_hash<>m.facts_hash OR m.user_id<>(SELECT user_id FROM api_keys WHERE id=a.api_key_id))",'A full row coverage differs usage_logs'))
        else:
            parts.append(assert_sql("NOT EXISTS(SELECT 1 FROM source_a.{t} a LEFT JOIN cutover_audit.source_map s ON s.source_table='{t}' AND s.source_id=a.id LEFT JOIN public.{t} m ON {p} WHERE m.id IS NULL OR (to_jsonb(m){f})<>(to_jsonb(a){f}){owner})".format(t=table,p=predicate,f=fields,owner=owner),'A full row coverage differs ' + table))
        # usage baseline certificate already excludes QA, so do not subtract it.
        parts.append(assert_sql("(SELECT count(*) FROM public.{t})=(SELECT (certificate->>'rows')::bigint FROM cutover_audit.b_certificates WHERE table_name='{t}')+(SELECT count(*) FROM cutover_audit.source_map WHERE source_table='{t}')".format(t=table),'merged row count differs ' + table))
    parts.append("""UPDATE cutover_audit.build_state SET complete=true WHERE name='core';
      SELECT json_build_object('core_passed',true,'ready_for_promotion',false,
        'source_snapshot_consistent',true,'merged_requests',(SELECT count(*) FROM usage_logs),
        'excluded_qa',(SELECT count(*) FROM cutover_audit.excluded_qa),
        'B_tables_certified',(SELECT count(*) FROM cutover_audit.b_certificates),
        'B_original_rows_no_longer_in_A',(SELECT count(*) FROM cutover_audit.b_only_original),
        'untouched_aggregate_history_preserved',true,'recomputed_days',(SELECT json_agg(bucket_date ORDER BY bucket_date) FROM affected_days),
        'imported',(SELECT json_object_agg(source_table,n) FROM (SELECT source_table,count(*) n FROM cutover_audit.source_map GROUP BY source_table)x));
      COMMIT;""")
    return '\n'.join(parts)


def build(phase):
    database = 'cutover_' + phase
    check(sql(database,"SELECT count(*) FROM pg_namespace WHERE nspname='cutover_audit'")=='0','merge already attempted; inspect before retry')
    if phase=='final':
        for name in ('sub2api','sub2api-next'):
            check(not json.loads(run(['docker','inspect',name]))[0]['State']['Running'], 'final merge requires stopped writers')
    if sql(database,"SELECT count(*) FROM pg_namespace WHERE nspname='source_a'")=='0':
        attach(database,phase=='final')
    elif sql(database,"SELECT count(*) FROM pg_namespace WHERE nspname='source_a_facts'")=='0':
        sql(database,"CREATE SCHEMA source_a_facts; IMPORT FOREIGN SCHEMA cutover_read_20261009 FROM SERVER source_a INTO source_a_facts;")
    tables = value(database,"SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='public'")
    check(all(re.fullmatch('[a-z0-9_]+',t) for t in tables),'unexpected table name')
    receipt = json.loads((OPS/(phase+'-restore.json')).read_text())
    check(receipt.get('phase') == 'local_restore_completed', 'successful restore receipt missing')
    if phase=='final':check(receipt.get('freeze_id')==json.loads((OPS/'control.json').read_text())['freeze_id'],'restored clone belongs to another freeze')
    listing = run(['docker','exec',CONTAINER,'pg_restore','--list','/backup/cutover-'+phase+'-b.dump'])
    expected_tables = sorted(re.findall(r'^\d+; \d+ \d+ TABLE public ([a-z0-9_]+) \S+$',listing,re.M))
    check(expected_tables == tables, 'restored table inventory differs from full B archive')
    baseline = json.loads((ROOT/'ops'/'migration-baseline.json').read_text())['keys']
    query=build_sql(tables,baseline,phase=='final')
    (OPS/(phase+'-merge.sql')).write_text(query)
    started=time.monotonic()
    with (OPS/(phase+'-merge.sql')).open('r') as inp, (OPS/(phase+'-merge.stdout')).open('w') as out, (OPS/'merge-error.log').open('w') as err:
        process=subprocess.Popen(['docker','exec','-i',CONTAINER,'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','sub2api','-d',database],stdin=inp,stdout=out,stderr=err)
        while process.poll() is None:
            if shutil.disk_usage(str(ROOT)).free < 4.5*1024**3:
                sql('postgres',"SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE datname='{}'".format(database))
                process.wait(timeout=30)
                raise RuntimeError('merge canceled at 4.5 GiB reserve; transaction rolled back')
            time.sleep(2)
        check(process.returncode==0,'merge failed; inspect private merge-error.log')
    result=(OPS/(phase+'-merge.stdout')).read_text()
    reports=[json.loads(line) for line in result.splitlines() if line.startswith('{') and json.loads(line).get('core_passed')]
    check(len(reports)==1 and reports[0]['core_passed'],'core report missing')
    reports[0].update(seconds=round(time.monotonic()-started,1),database=database,
                      free_gib=round(shutil.disk_usage(str(ROOT)).free/1024**3,2))
    if phase=='final':reports[0]['freeze_id']=receipt['freeze_id']
    (OPS/(phase+'-core.json')).write_text(json.dumps(reports[0],indent=2))
    print(json.dumps(reports[0]),flush=True)


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['connect-source','build'])
    parser.add_argument('--phase',choices=['rehearsal','final'],default='rehearsal')
    args=parser.parse_args();guard()
    if args.action=='connect-source':connect_source()
    else:build(args.phase)


if __name__=='__main__':main()
