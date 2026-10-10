#!/usr/bin/env python3
"""Rebuild the already published V2 interval with exact official v0.2.15 SQL."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

TABLES = ('channel_monitor_v2_metrics_1m', 'channel_monitor_v2_user_metrics_1m',
          'channel_monitor_v2_latency_histograms_1m', 'channel_monitor_v2_error_metrics_1m')
ROLLUPS = tuple(t.replace('_1m', '_rollup') for t in TABLES)


def extract(source):
    files = [Path(source)/'channel_monitor_v2_aggregation.go', Path(source)/'usage_log_repo.go']
    text = '\n'.join(p.read_text() for p in files)
    cache = {}

    def expression(pos, env=None):
        env = env or {}
        def atom(at):
            while text[at].isspace(): at += 1
            if text[at] == '`':
                end = text.index('`', at+1)
                return text[at+1:end], end+1
            if text[at] == '"':
                value, length = json.JSONDecoder().raw_decode(text[at:])
                return value, at+length
            match = re.match(r'[A-Za-z_][A-Za-z0-9_]*', text[at:])
            if not match: raise ValueError('unsupported Go SQL expression')
            name = match.group(0)
            return env[name] if name in env else constant(name), at+len(name)
        result,pos = atom(pos)
        while True:
            end=pos
            while end<len(text) and text[end].isspace():end+=1
            if end>=len(text) or text[end]!='+':return result,pos
            term,pos=atom(end+1);result+=term

    def constant(name):
        if name not in cache:
            match=re.search(r'\bconst\s+'+re.escape(name)+r'\s*=\s*',text)
            if not match:raise ValueError('SQL constant not found: '+name)
            cache[name]=expression(match.end())[0]
        return cache[name]

    def c(name):return constant('channelMonitorV2'+name)
    match=re.search(r'func channelMonitorV2HistogramBoundSQL\(column string\) string \{\s*return\s*',text)
    histogram=expression(match.end(),{'column':'latency.value_ms'})[0]
    queries={
        'usage':c('UsageMetricsSQL')%(c('PlatformSQL'),c('ModelSQL')),
        'users':c('UserMetricsSQL')%(c('PlatformSQL'),c('ModelSQL')),
        'histogram':c('HistogramSQL')%(c('PlatformSQL'),c('ModelSQL'),histogram),
        'errors':c('ErrorAggregationSQL'),
    }
    for suffix,table in zip(('Metrics','UserMetrics','Histogram','Error'),ROLLUPS):
        queries[table]=c(suffix+'RollupSQL')
    return {'version':'v0.2.15','sources':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'queries':queries}


def rebuild_sql(bundle,start,end):
    from cutover_merge import assert_sql
    # Bounds are server-produced ISO timestamps, checked before SQL quoting.
    assert re.fullmatch(r'[0-9T :+.\-]+',start) and re.fullmatch(r'[0-9T :+.\-]+',end)
    queries=bundle['queries'];assert bundle['version']=='v0.2.15'
    parts=["""BEGIN; SET LOCAL TIME ZONE 'UTC'; SET LOCAL statement_timeout='30min';
      SET LOCAL work_mem='16MB'; SET LOCAL temp_file_limit='512MB';
      CREATE FUNCTION pg_temp.check_true(ok boolean,msg text) RETURNS void LANGUAGE plpgsql AS
        $$ BEGIN IF ok IS DISTINCT FROM TRUE THEN RAISE EXCEPTION '%',msg; END IF; END $$;
      CREATE TEMP TABLE watermark_before AS SELECT * FROM public.channel_monitor_v2_watermarks;
      """]
    # Build expected results into shadow temporary tables. Official queries keep
    # their names; search_path selects pg_temp first without rewriting formulas.
    for table in TABLES+ROLLUPS:
        parts.append('CREATE TEMP TABLE {t} (LIKE public.{t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES);'.format(t=table))
    for name in ('usage','users','histogram','errors'):
        parts.append('PREPARE v2_{0}(timestamptz,timestamptz) AS {1};'.format(name,queries[name]))
        parts.append("EXECUTE v2_{}('{}','{}');".format(name,start,end))
    for i,table in enumerate(ROLLUPS):
        parts.append('PREPARE v2_roll_{0}(interval,integer,timestamptz,timestamptz) AS {1};'.format(i,queries[table]))
        for seconds in (300,3600,43200,86400):
            parts.append("EXECUTE v2_roll_{i}('{seconds} seconds',{seconds},'{start}','{end}');".format(i=i,seconds=seconds,start=start,end=end))
    for table in TABLES+ROLLUPS:
        parts.append("DELETE FROM public.{t} WHERE bucket_start>='{start}'::timestamptz AND bucket_start<'{end}'::timestamptz;".format(t=table,start=start,end=end))
        parts.append('INSERT INTO public.{t} SELECT * FROM pg_temp.{t};'.format(t=table))
        left="SELECT to_jsonb(t)-'computed_at' FROM public.{t} t WHERE bucket_start>='{start}'::timestamptz AND bucket_start<'{end}'::timestamptz".format(t=table,start=start,end=end)
        right="SELECT to_jsonb(t)-'computed_at' FROM pg_temp.{} t".format(table)
        parts.append(assert_sql('NOT EXISTS(({} EXCEPT ALL {}) UNION ALL ({} EXCEPT ALL {}))'.format(left,right,right,left),'V2 exact aggregate mismatch '+table))
    parts.append("""UPDATE public.channel_monitor_v2_watermarks SET data_through=greatest(data_through,'{end}'::timestamptz),
      last_successful_at=now(),updated_at=now() WHERE id=1;""".format(end=end))
    parts.append(assert_sql("(SELECT to_jsonb(t)-'data_through'-'last_successful_at'-'updated_at' FROM public.channel_monitor_v2_watermarks t)=(SELECT to_jsonb(t)-'data_through'-'last_successful_at'-'updated_at' FROM watermark_before t)",'V2 historical coverage/cursor changed'))
    parts.append("UPDATE cutover_audit.build_state SET complete=true WHERE name='v2'; COMMIT;")
    return '\n'.join(parts)


def rebuild(phase):
    from cutover_merge import ROOT,OPS,CONTAINER,check,guard,sql,value
    guard();db='cutover_'+phase
    if phase=='final':
        from cutover_local import frozen
        frozen()
        check(json.loads((OPS/'final-core.json').read_text()).get('freeze_id')==json.loads((OPS/'control.json').read_text())['freeze_id'],'core report belongs to another freeze')
    check(value(db,"SELECT to_json(coalesce(bool_and(complete),false)) FROM cutover_audit.build_state WHERE name='core'") is True,'core merge incomplete')
    bundle=json.loads((OPS/'official-v2-queries.json').read_text())
    bounds=value(db,"""SELECT json_build_object('start',to_char(date_trunc('day',
      least(usage_coverage_start,error_coverage_start,backfill_cursor) AT TIME ZONE 'UTC') AT TIME ZONE 'UTC',
      'YYYY-MM-DD HH24:MI:SSOF'),'end',to_char(date_trunc('minute',now()),'YYYY-MM-DD HH24:MI:SSOF'))
      FROM channel_monitor_v2_watermarks WHERE id=1""")
    check(bounds and bounds['start'] and bounds['end'],'published V2 coverage missing')
    started=time.monotonic()
    query=OPS/(phase+'-v2.sql');query.write_text(rebuild_sql(bundle,bounds['start'],bounds['end']))
    with query.open('r') as inp,(OPS/(phase+'-v2.stdout')).open('w') as out,(OPS/(phase+'-v2.stderr')).open('w') as err:
        process=subprocess.Popen(['docker','exec','-i',CONTAINER,'psql','-XqAt','-v','ON_ERROR_STOP=1','-U','sub2api','-d',db],stdin=inp,stdout=out,stderr=err)
        while process.poll() is None:
            if shutil.disk_usage(str(ROOT)).free<4.5*1024**3:
                sql('postgres',"SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE datname='{}'".format(db))
                process.wait(timeout=30)
                raise RuntimeError('V2 rebuild canceled at disk reserve; transaction rolled back')
            time.sleep(2)
        check(process.returncode==0,'V2 rebuild failed; inspect private diagnostic')
    result={'v2_passed':True,'database':db,'range':bounds,'history_backfill_cursor_preserved':True,
            'seconds':round(time.monotonic()-started,1),'all_build_stages_complete':value(db,"SELECT to_json(bool_and(complete)) FROM cutover_audit.build_state")}
    if phase=='final':result['freeze_id']=json.loads((OPS/'control.json').read_text())['freeze_id']
    (OPS/(phase+'-v2.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['extract','rebuild'])
    parser.add_argument('--source');parser.add_argument('--output');parser.add_argument('--phase',choices=['rehearsal','final'],default='rehearsal')
    args=parser.parse_args()
    if args.action=='extract':
        if not args.source or not args.output:parser.error('extract requires --source and --output')
        bundle=extract(args.source);Path(args.output).write_text(json.dumps(bundle,indent=2))
        print(json.dumps({'version':bundle['version'],'source_hashes':bundle['sources'],'query_lengths':{k:len(v) for k,v in bundle['queries'].items()}}))
    else:rebuild(args.phase)


if __name__=='__main__':main()
