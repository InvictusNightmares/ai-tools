#!/usr/bin/env python3
"""Scoped maintenance and promotion control; never starts the old binary on new data."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time

from cutover_merge import ROOT,OPS,CONTAINER,SOURCE_ROLE,SOURCE_NETWORK,check,guard,run,sql,value,table_certificate

STATE=OPS/'control.json'
NGINX=Path('/opt/sub2api-deploy/gateway/nginx.conf')
CHAIN='SUB2API_CUTOVER_1009'
IMAGE='nginx@sha256:2f07d83bf561b506400dc183b1b2003803e39efbd22451f848adaba14d28c7c7'


def state():return json.loads(STATE.read_text())
def save(x):STATE.write_text(json.dumps(x,indent=2))
def inspect(name):return json.loads(run(['docker','inspect',name]))[0]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def report(name,**data):
    result=dict(event=name,at_epoch=int(time.time()),**data)
    (OPS/(name+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)


def compose(*args):
    return run(['docker','compose','-p','sub2api-next','-f',str(ROOT/'compose.json')]+list(args),timeout=180)


def redis(side,args):
    name='sub2api' if side=='a' else 'sub2api-next'
    env=dict(e.split('=',1) for e in inspect(name)['Config']['Env'] if '=' in e)
    process_env=os.environ.copy();process_env['REDISCLI_AUTH']=env.get('REDIS_PASSWORD','')
    command=['docker','exec','-e','REDISCLI_AUTH',name+'-redis','redis-cli','--raw']+args
    try:
        result=subprocess.run(command,env=process_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=30)
    except subprocess.TimeoutExpired:
        raise RuntimeError('private Redis operation timed out') from None
    check(result.returncode==0,'private Redis operation failed')
    return result.stdout.strip()


def active(side):
    # Scores are lease timestamps, not expiry times. Conservatively count all
    # members, including stale leases, rather than miss active requests.
    lua="""local cursor='0'; local slots=0; local waits=0; local leases=0; local inflight=0; repeat
      local result=redis.call('SCAN',cursor,'MATCH','concurrency:*','COUNT',1000); cursor=result[1];
      for _,key in ipairs(result[2]) do
        local kind=redis.call('TYPE',key).ok;
        if not string.find(key,'active_index',1,true) and not string.find(key,'startup:',1,true) then
          if kind=='zset' then local n=redis.call('ZCARD',key); if string.find(key,'openai_ws_ingress',1,true) then leases=leases+n else slots=slots+n end
          elseif kind=='string' and string.find(key,'concurrency:wait:',1,true) then waits=waits+tonumber(redis.call('GET',key) or '0') end
        end
      end until cursor=='0'; cursor='0'; repeat local r=redis.call('SCAN',cursor,'MATCH','wait:account:*','COUNT',1000); cursor=r[1];for _,k in ipairs(r[2]) do waits=waits+tonumber(redis.call('GET',k) or '0') end until cursor=='0';
      cursor='0'; repeat local r=redis.call('SCAN',cursor,'MATCH','billing:inflight:*','COUNT',1000); cursor=r[1];for _,k in ipairs(r[2]) do if redis.call('TYPE',k).ok=='zset' then inflight=inflight+redis.call('ZCARD',k) end end until cursor=='0';
      return cjson.encode({slots=slots,waits=waits,leases=leases,inflight=inflight})"""
    return json.loads(redis(side,['EVAL',lua,'0']))


def quota_settled(side):
    db='sub2api' if side=='a' else 'sub2api_next'
    query="""SELECT coalesce(json_agg(json_build_object('user_id',user_id,'platform',platform,
      'daily_usage',daily_usage_usd::text,'weekly_usage',weekly_usage_usd::text,'monthly_usage',monthly_usage_usd::text,
      'daily_limited',daily_limit_usd IS NOT NULL,'weekly_limited',weekly_limit_usd IS NOT NULL,'monthly_limited',monthly_limit_usd IS NOT NULL,
      'daily_window_start',floor(extract(epoch from daily_window_start))::bigint,
      'weekly_window_start',floor(extract(epoch from weekly_window_start))::bigint,
      'monthly_window_start',floor(extract(epoch from monthly_window_start))::bigint)),'[]'::json)
      FROM user_platform_quotas WHERE deleted_at IS NULL AND
      (daily_limit_usd IS NOT NULL OR weekly_limit_usd IS NOT NULL OR monthly_limit_usd IS NOT NULL)"""
    rows=json.loads(sql(db,query,side=='a'))
    keys=['billing:user_platform_quota:{}:{}'.format(row['user_id'],row['platform']) for row in rows]
    lookup=json.loads(redis(side,['EVAL',"local out={};for _,k in ipairs(ARGV) do local v=redis.call('HGETALL',k);if #v>0 then out[k]=v end end;return cjson.encode(out)",'0']+keys))
    for row,key in zip(rows,keys):
        if key not in lookup:continue
        raw=lookup[key];cached=dict(zip(raw[::2],raw[1::2]))
        for period in ('daily','weekly','monthly'):
            window=period+'_window_start';usage=period+'_usage'
            if row[period+'_limited'] and str(row[window] or '')!=cached.get(window,''):return False
            if abs(Decimal(row[usage])-Decimal(cached.get(usage,'0')))>Decimal('0.00000001'):return False
    return True


def billing_logs_clean(since):
    pattern=re.compile(r'ALERT: (?:panic in user platform quota|incr user platform quota DB failed)|usage_record\.task_panic|usage_record_task_panic_recovered|record_usage_failed|Create usage log.*failed|(?:billing|usage).*(?:persist|deduct|record).*(?:failed|panic)',re.I)
    for name in ('sub2api','sub2api-next'):
        result=subprocess.run(['docker','logs','--since',str(since),name],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
        check(result.returncode==0,'cannot read shutdown billing diagnostics')
        check(not any(pattern.search(line) for line in result.stdout.splitlines()),'billing persistence error since maintenance began')


def gate_config(original,secret=None):
    insertion='        return 503;\n' if secret is None else '        if ($http_x_sub2api_cutover != "'+secret+'") { return 503; }\n'
    check(original.count('        server_name _;')==1,'proxy server anchor differs')
    return original.replace('        server_name _;','        server_name _;\n'+insertion)


def reload_old(text):
    # Preserve the inode of the existing single-file bind mount.
    with NGINX.open('w') as stream:stream.write(text);stream.flush();os.fsync(stream.fileno())
    run(['docker','exec','sub2api-proxy','nginx','-t']);run(['docker','exec','sub2api-proxy','nginx','-s','reload'])


def prepare():
    check(not STATE.exists(),'control preparation already exists')
    for filename,flag in [('rehearsal-core.json','core_passed'),('rehearsal-v2.json','v2_passed'),('rehearsal-recovery.json','recovery_passed')]:
        check(json.loads((OPS/filename).read_text()).get(flag) is True,'rehearsal gate incomplete '+filename)
    original=NGINX.read_text();check('set $sub2api_upstream http://sub2api:8080;' in original,'formal upstream changed')
    (OPS/'nginx-before.conf').write_text(original)
    shutil.copy2(str(ROOT/'compose.json'),str(OPS/'compose-before.json'))
    gw=ROOT/'gateway';gw.mkdir(mode=0o700,exist_ok=True)
    shutil.copy2(str(NGINX.parent/'all-hours-api-keys.conf'),str(gw/'all-hours-api-keys.conf'))
    final=original.replace('http://sub2api:8080','http://app:8080')
    (OPS/'nginx-final-open.conf').write_text(final)
    secret=secrets.token_hex(24)
    (gw/'nginx.conf').write_text(gate_config(final,secret))
    run(['docker','run','--rm','--network','none','--name','sub2api-cutover-nginx-check','-v',str(gw/'nginx.conf')+':/etc/nginx/nginx.conf:ro','-v',str(gw/'all-hours-api-keys.conf')+':/etc/nginx/all-hours-api-keys.conf:ro',IMAGE,'nginx','-t'])
    config=json.loads((ROOT/'compose.json').read_text())
    check(set(config['services'])=={'app','postgres','redis'},'unexpected B service inventory')
    config['services']['gateway']={'image':IMAGE,'container_name':'sub2api-next-proxy','restart':'unless-stopped',
        'environment':{'TZ':'Asia/Shanghai'},'networks':['candidate'],'ports':['0.0.0.0:8080:8080'],
        'volumes':[str(gw/'nginx.conf')+':/etc/nginx/nginx.conf:ro,Z',str(gw/'all-hours-api-keys.conf')+':/etc/nginx/all-hours-api-keys.conf:ro,Z'],
        'mem_limit':'128m','cpus':0.25,'logging':{'driver':'json-file','options':{'max-size':'10m','max-file':'3'}},
        'healthcheck':{'test':['CMD','nginx','-t'],'interval':'10s','timeout':'5s','retries':3}}
    (ROOT/'compose.json').write_text(json.dumps(config,indent=2));compose('config','--quiet')
    x={'stage':'prepared','gate_secret':secret,'original_nginx_sha256':sha(OPS/'nginx-before.conf'),'prepared_at_epoch':int(time.time())}
    save(x);report('control_prepared',original_services_running=True)


def iptables(*args):return run(['iptables','-w','5']+list(args))


def freeze():
    x=state();check(x['stage']=='prepared','freeze state differs')
    check(sha(NGINX)==x['original_nginx_sha256'],'formal proxy config changed after preparation')
    ips={}
    for side,name,network in [('a','sub2api',SOURCE_NETWORK),('b','sub2api-next','sub2api-next_candidate')]:
        info=inspect(name);check(info['State']['Running'],'app already stopped')
        ips[side]=info['NetworkSettings']['Networks'][network]['IPAddress']
        check(re.fullmatch(r'[0-9.]+',ips[side]) is not None,'unexpected app address')
    x.update(stage='gating',ips=ips,freeze_started_epoch=int(time.time()),freeze_id=secrets.token_hex(16));save(x)
    reload_old(gate_config((OPS/'nginx-before.conf').read_text()))
    iptables('-N',CHAIN)
    for address in ips.values():iptables('-A',CHAIN,'-d',address,'-p','tcp','--dport','8080','-m','conntrack','--ctstate','NEW','-j','REJECT','--reject-with','tcp-reset')
    iptables('-I','DOCKER-USER','1','-j',CHAIN)
    # First allow active calls to drain with no new TCP connections.
    deadline=time.monotonic()+600
    while True:
        counts={s:active(s) for s in ('a','b')};report('drain_progress',**counts)
        # Idle WS connections may hold a billing reservation until closed.
        # The second phase requires those reservations to drain as well.
        if all(c['slots']==0 and c['waits']==0 for c in counts.values()):break
        check(time.monotonic()<deadline,'drain timeout; maintenance gate retained for inspection')
        time.sleep(5)
    # Existing keep-alive/WS connections must also be unable to submit new work.
    for address in ips.values():iptables('-I',CHAIN,'1','-d',address,'-p','tcp','--dport','8080','-j','REJECT','--reject-with','tcp-reset')
    # Also cover a later app recreation changing its address inside B's network.
    network=json.loads(run(['docker','network','inspect','sub2api-next_candidate']))[0]
    subnet=network['IPAM']['Config'][0]['Subnet']
    check(re.fullmatch(r'[0-9./]+',subnet) is not None,'unexpected candidate subnet')
    iptables('-I',CHAIN,'1','-d',subnet,'-p','tcp','-m','conntrack','--ctorigdstport','18080','-j','REJECT','--reject-with','tcp-reset')
    for name in ('sub2api','sub2api-next'):
        pid=inspect(name)['State']['Pid']
        run(['nsenter','-t',str(pid),'-n','ss','-K','state','established','sport = :8080'])
    # Recheck after closing idle transports, allowing detached billing to finish.
    stable=None;passes=0;deadline=time.monotonic()+180
    while passes<4:
        counts={s:active(s) for s in ('a','b')}
        signatures={}
        for side,db in [('a','sub2api'),('b','sub2api_next')]:
            query="SELECT json_build_object('usage_max',(SELECT max(id) FROM usage_logs),'usage_count',(SELECT count(*) FROM usage_logs),'users',(SELECT md5(string_agg(to_jsonb(t)::text,'' ORDER BY id)) FROM users t),'quotas',(SELECT md5(string_agg(to_jsonb(t)::text,'' ORDER BY id)) FROM user_platform_quotas t))"
            signatures[side]=json.loads(sql(db,query,side=='a'))
        if all(c['slots']==0 and c['waits']==0 and c['inflight']==0 for c in counts.values()) and signatures==stable and all(quota_settled(side) for side in ('a','b')):passes+=1
        else:passes=0
        stable=signatures
        check(time.monotonic()<deadline,'billing did not settle; gates retained')
        time.sleep(5)
    for name in ('sub2api','sub2api-next'):
        run(['docker','stop','--time','60',name],timeout=90)
        info=inspect(name);check(not info['State']['Running'] and not info['State']['OOMKilled'] and info['State']['ExitCode']==0,'app did not shut down cleanly')
    check(all(quota_settled(side) for side in ('a','b')),'quota cache/DB differ after application shutdown')
    billing_logs_clean(x['freeze_started_epoch'])
    x.update(stage='frozen',frozen_at_epoch=int(time.time()),frozen_signatures=stable);save(x)
    # Preserve B sessions and native authentication state separately from DB.
    redis('b',['SAVE'])
    run(['docker','cp','sub2api-next-redis:/data/dump.rdb',str(ROOT/'backups'/'cutover-final-b-redis.rdb')])
    report('writers_frozen',both_apps_stopped=True,transports_closed=True,stable_checks=passes,signatures=stable)


def unfreeze_before_promotion():
    x=state();check(x['stage'] in ('gating','frozen'),'cannot restore old service after promotion')
    for name in ('sub2api','sub2api-next'):
        if not inspect(name)['State']['Running']:run(['docker','start',name])
    # A resumes sole token refresh; B compose still has refresh disabled here.
    iptables('-D','DOCKER-USER','-j',CHAIN);iptables('-F',CHAIN);iptables('-X',CHAIN)
    reload_old((OPS/'nginx-before.conf').read_text())
    x['stage']='prepared';save(x);report('prepromotion_service_restored',final_cutover=False)


def main():
    os.umask(0o077);guard()
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','freeze','unfreeze']);args=p.parse_args()
    {'prepare':prepare,'freeze':freeze,'unfreeze':unfreeze_before_promotion}[args.action]()

if __name__=='__main__':main()
