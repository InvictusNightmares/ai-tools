#!/usr/bin/env python3
"""Private JSON RPC for gated formal-chain acceptance; stdout may contain keys.

Invoke only through cutover_accept.py which captures the private transport.
"""
from decimal import Decimal
import json
import os
import sys
import time

from cutover_merge import ROOT,OPS,check,sql,value
from cutover_control import state,inspect,report


def q(query):return value('sub2api_next',query)


def context():
    groups=q("SELECT json_agg(t) FROM (SELECT g.id,g.name,(SELECT a.id FROM account_groups ag JOIN accounts a ON a.id=ag.account_id WHERE ag.group_id=g.id AND a.deleted_at IS NULL AND a.platform='openai' AND a.type='oauth') account_id FROM groups g WHERE g.deleted_at IS NULL ORDER BY g.id)t")
    check(len(groups)==8,'final active group inventory differs')
    customers=q("SELECT json_agg(t) FROM (SELECT k.id key_id,k.key,k.user_id,k.group_id,u.email FROM api_keys k JOIN users u ON u.id=k.user_id WHERE u.deleted_at IS NULL AND u.role='user' AND k.deleted_at IS NULL AND k.status='active' ORDER BY k.id)t")
    samples=[]
    for group in groups:
        person=next(c for c in customers if c['group_id']==group['id'])
        samples.append(dict(person,group_name=group['name'],account_id=group['account_id']))
    return {'samples':samples,'gate_secret':state()['gate_secret'],'initial_usage_max':q('SELECT to_json(max(id)) FROM usage_logs')}


def ledger(uid,kid):
    return q("""SELECT json_build_object('balance',u.balance::text,'weekly',q.weekly_usage_usd::text,
      'week',q.weekly_window_start,'daily',q.daily_usage_usd::text,'monthly',q.monthly_usage_usd::text,
      'usage_max',(SELECT coalesce(max(id),0) FROM usage_logs WHERE api_key_id={kid}))
      FROM users u JOIN user_platform_quotas q ON q.user_id=u.id
      WHERE u.id={uid} AND q.platform='openai' AND q.deleted_at IS NULL""".format(uid=uid,kid=kid))


def confirm_call(data):
    uid,kid=int(data['user_id']),int(data['key_id']);before=data['before'];rows=[]
    for _ in range(40):
        rows=q("""SELECT coalesce(json_agg(t),'[]') FROM (SELECT l.id,l.request_id,l.user_id,l.api_key_id,l.account_id,
        l.group_id,a.platform,l.model,l.actual_cost::text,l.total_cost::text,l.input_tokens,l.output_tokens
        FROM usage_logs l JOIN accounts a ON a.id=l.account_id WHERE l.api_key_id={kid} AND l.id>{maxid} ORDER BY l.id)t""".format(kid=kid,maxid=int(before['usage_max'])))
        after=ledger(uid,kid)
        if len(rows)==1 and Decimal(before['balance'])-Decimal(after['balance'])>0:
            expected=Decimal(rows[0]['actual_cost']) if rows[0]['platform']=='openai' else Decimal(0)
            if abs((Decimal(after['weekly'])-Decimal(before['weekly']))-expected)<Decimal('0.00000001'):break
        time.sleep(1)
    check(len(rows)==1,'formal request did not produce exactly one usage row')
    row=rows[0];cost=Decimal(row['actual_cost'])
    check(row['user_id']==uid and row['group_id']==int(data['group_id']) and row['account_id']==int(data['account_id']),'formal request routed or attributed incorrectly')
    check(cost>0 and abs(Decimal(before['balance'])-Decimal(after['balance'])-cost)<Decimal('0.00000001'),'wallet deduction differs from actual cost')
    check(abs(Decimal(after['weekly'])-Decimal(before['weekly'])-(cost if row['platform']=='openai' else Decimal(0)))<Decimal('0.00000001'),'GPT weekly usage differs from platform cost')
    check(before['week']==after['week'],'unexpected quota window transition')
    return dict(row,wallet_and_weekly_reconciled=True)


def quota_block(uid):
    path=OPS/'quota-acceptance-before.json';check(not path.exists(),'quota acceptance already prepared')
    current=quota_row(uid)
    check(current['weekly_limit_usd']==300,'unexpected current weekly limit')
    check(Decimal(current['weekly_usage_usd'])<300,'customer already at weekly limit')
    current['_usage_max']=q('SELECT to_json(max(id)) FROM usage_logs')
    current['_freeze_id']=state()['freeze_id']
    current['_stage']='prepared'
    path.write_text(json.dumps(current))
    sql('sub2api_next',"UPDATE user_platform_quotas SET weekly_usage_usd=300 WHERE user_id={} AND platform='openai' AND deleted_at IS NULL;".format(uid))
    current['_stage']='applied';path.write_text(json.dumps(current))
    from cutover_control import redis
    redis('b',['DEL','billing:user_platform_quota:{}:openai'.format(uid)])
    return {'quota_temporarily_full':True}


def quota_row(uid):
    return q("SELECT to_jsonb(t)||jsonb_build_object('daily_usage_usd',daily_usage_usd::text,'weekly_usage_usd',weekly_usage_usd::text,'monthly_usage_usd',monthly_usage_usd::text) FROM user_platform_quotas t WHERE user_id={} AND platform='openai' AND deleted_at IS NULL".format(uid))


def quota_restore(uid,limit_test_started):
    path=OPS/'quota-acceptance-before.json'
    if not path.exists():return {'quota_restored':True,'temporary_snapshot_absent':True}
    before=json.loads(path.read_text());check(before['user_id']==uid and before.get('_freeze_id')==state()['freeze_id'],'quota restore user or freeze differs')
    from cutover_control import redis,active,quota_settled,run
    current=quota_row(uid)
    if before['_stage']=='prepared' and current['weekly_usage_usd']==before['weekly_usage_usd']:
        path.rename(OPS/'quota-acceptance-restored.json')
        return {'quota_restored':True,'temporary_limit_not_applied':True}
    if before['_stage']=='restored':
        redis('b',['DEL','billing:user_platform_quota:{}:openai'.format(uid)])
        if not inspect('sub2api-next')['State']['Running']:run(['docker','start','sub2api-next'])
        deadline=time.monotonic()+120
        while inspect('sub2api-next')['State'].get('Health',{}).get('Status')!='healthy':
            check(time.monotonic()<deadline,'B unhealthy after retried restoration');time.sleep(2)
        path.rename(OPS/'quota-acceptance-restored.json')
        return {'quota_restored':True,'retried_completed_restore':True}
    deadline=time.monotonic()+120
    while True:
        activity=active('b')
        if activity['slots']==0 and activity['waits']==0 and activity['inflight']==0 and (not limit_test_started or quota_settled('b')):break
        check(time.monotonic()<deadline,'quota-test billing did not settle');time.sleep(2)
    # Stop the sole app before lowering the counter: no flusher snapshot or
    # detached DB increment may race this maintenance-only restoration.
    run(['docker','stop','--time','60','sub2api-next'],timeout=90)
    info=inspect('sub2api-next');check(not info['State']['Running'] and info['State']['ExitCode']==0 and not info['State']['OOMKilled'],'quota-test app shutdown was not clean')
    current=quota_row(uid)
    check(current['weekly_window_start']==before['weekly_window_start'],'quota window changed during test')
    extra=Decimal(q("SELECT to_json(coalesce(sum(l.actual_cost),0)::text) FROM usage_logs l JOIN accounts a ON a.id=l.account_id WHERE l.user_id={} AND l.id>{} AND a.platform='openai'".format(uid,int(before['_usage_max']))))
    if not limit_test_started:
        check(extra==0 and Decimal(current['weekly_usage_usd']) in (Decimal(300),Decimal(before['weekly_usage_usd'])),'partial quota setup has unexpected consumption')
    else:
        check(abs(Decimal(str(current['weekly_usage_usd']))-Decimal(300)-extra)<Decimal('0.00000001'),'temporary quota does not reconcile with subsequent GPT usage')
    if extra==0:
        for field in ('daily_usage_usd','monthly_usage_usd','daily_window_start','monthly_window_start'):
            check(current[field]==before[field],'DeepSeek changed GPT '+field)
    restored=Decimal(str(before['weekly_usage_usd']))+extra
    sql('sub2api_next',"UPDATE user_platform_quotas SET weekly_usage_usd={} WHERE user_id={} AND platform='openai' AND deleted_at IS NULL;".format(restored,uid))
    before['_stage']='restored';path.write_text(json.dumps(before))
    redis('b',['DEL','billing:user_platform_quota:{}:openai'.format(uid)])
    run(['docker','start','sub2api-next'])
    deadline=time.monotonic()+120
    while inspect('sub2api-next')['State'].get('Health',{}).get('Status')!='healthy':
        check(time.monotonic()<deadline,'B did not recover after quota restoration');time.sleep(2)
    path.rename(OPS/'quota-acceptance-restored.json')
    return {'quota_restored':True,'week_preserved':True,'daily_monthly_preserved':True,'additional_GPT_cost_preserved':str(extra)}


def portal():
    sys.path.insert(0,str(ROOT/'ops'))
    from candidate_accept import login,native,request
    from customer_passwords import customer_password
    samples=context()['samples'];results=[]
    for person in samples:
        gid=person['group_id'];token=None
        candidates=q("SELECT json_agg(t) FROM (SELECT DISTINCT u.id user_id,u.email FROM users u JOIN user_allowed_groups g ON g.user_id=u.id WHERE u.deleted_at IS NULL AND u.role='user' AND g.group_id={} ORDER BY u.id LIMIT 3)t".format(gid))
        for candidate in candidates:
            try:
                token=login(candidate['email'],customer_password(candidate['email']))
                person=dict(person,user_id=candidate['user_id']);break
            except RuntimeError as exc:
                if 'returned 401' not in str(exc):raise
        check(token is not None,'no authorized initial-login sample available in group; no passwords changed')
        profile=native('GET','/api/v1/user/profile',token=token)
        check(profile['id']==person['user_id'] and profile['role']=='user','customer login identity differs')
        dimensions=native('GET','/api/v1/channel-monitor-v2/dimensions?range=90m',token=token)
        check({g['id'] for g in dimensions['groups']}=={gid},'monitor dimensions reveal another group')
        check({p['value'] for p in dimensions['platforms']}=={'openai','deepseek'},'platform catalog differs')
        other=next(p['group_id'] for p in samples if p['group_id']!=gid)
        matrix=native('GET','/api/v1/channel-monitor-v2/matrix?range=90m&group_by=platform_group&group_id='+str(other),token=token)
        check(not matrix['items'],'foreign group monitor request returned data')
        check(request('GET','/api/v1/admin/users',token=token)[0]==403,'customer can access admin users')
        groups=native('GET','/api/v1/groups/available',token=token)
        check({g['id'] for g in groups}=={gid},'available group scope differs')
        results.append({'group_id':gid,'customer_id':person['user_id'],'login':True,'group_isolation':True,'admin_denied':True})
    return {'passed':True,'samples':results}


def finish(data):
    check(len(data['gpt'])==8 and {r['account_id'] for r in data['gpt']}=={p['account_id'] for p in context()['samples']},'eight GPT routes not proven')
    check({r['account_id'] for r in data['deepseek']}=={76,77} and data['quota_http_status']==429 and data['weekly_quota_error'] and data['portal']['passed'],'formal-chain acceptance incomplete')
    check(all(r['wallet_and_weekly_reconciled'] for r in data['gpt']+data['deepseek']+[data['deepseek_at_gpt_limit']]),'billing reconciliation incomplete')
    check((OPS/'quota-acceptance-restored.json').exists(),'temporary quota not restored')
    check(json.loads((OPS/'quota-acceptance-restored.json').read_text()).get('_freeze_id')==state()['freeze_id'],'quota restoration belongs to another freeze')
    check(not inspect('sub2api')['State']['Running'],'old app restarted')
    unchanged=json.loads(sql('sub2api',"SELECT json_build_object('usage_max',(SELECT max(id) FROM usage_logs),'usage_count',(SELECT count(*) FROM usage_logs))",True))
    old=state()['frozen_signatures']['a'];check(all(unchanged[k]==old[k] for k in unchanged),'old source accepted new usage')
    sys.path.insert(0,str(ROOT/'ops'))
    from candidate_monitor_v2 import verify
    verify()
    from candidate_migrate import api, sql_json
    settings=api('GET','/api/v1/admin/settings')
    check(all(settings.get(k) is True for k in ('ops_monitoring_enabled','ops_realtime_monitoring_enabled','channel_monitor_enabled')),'official monitoring feature disabled')
    advanced=api('GET','/api/v1/admin/ops/advanced-settings')
    check(advanced['aggregation']['aggregation_enabled'] and advanced['data_retention']['cleanup_enabled'] and advanced['auto_refresh_enabled'],'official monitoring background configuration differs')
    check(api('GET','/api/v1/admin/ops/runtime/logging')['request_retention_days']==0,'historical usage retention changed')
    endpoints=('dashboard/overview','dashboard/throughput-trend','concurrency','realtime-traffic','account-availability','alert-rules','alert-events','request-errors','upstream-errors','system-logs','system-logs/health')
    for endpoint in endpoints:api('GET','/api/v1/admin/ops/'+endpoint)
    check(sql_json("SELECT count(*) FROM ops_system_metrics WHERE created_at>now()-interval '5 minutes'")>0,'official metrics collector has not persisted recent data')
    env=dict(s.split('=',1) for s in inspect('sub2api-next')['Config']['Env'] if '=' in s)
    check(all(env.get(k)=='true' for k in ('OPS_ENABLED','DASHBOARD_AGGREGATION_ENABLED','USAGE_CLEANUP_ENABLED')),'official worker environment disabled')
    check(env['TOKEN_REFRESH_ENABLED']=='true' and env['GATEWAY_OPENAI_WS_ENABLED']=='false' and env['GATEWAY_OPENAI_WS_FORCE_HTTP']=='true','OAuth/HTTP-only runtime differs')
    result=dict(data,passed=True,freeze_id=state()['freeze_id'],old_source_usage_unchanged=True,official_version='v0.2.15',entry='http://192.168.64.16:4001',oauth_refresh_single_instance=True,websocket_disabled=True,official_ops_endpoints_passed=len(endpoints),recent_ops_metrics_persisted=True)
    (OPS/'final-acceptance.json').write_text(json.dumps(result,indent=2));return result


def main():
    os.umask(0o077);data=json.load(sys.stdin);check(state()['stage']=='promoted_gated','acceptance requires gated final service')
    action=data['action']
    if action=='context':result=context()
    elif action=='ledger':result=ledger(int(data['user_id']),int(data['key_id']))
    elif action=='confirm':result=confirm_call(data)
    elif action=='quota-block':result=quota_block(int(data['user_id']))
    elif action=='quota-restore':result=quota_restore(int(data['user_id']),bool(data['limit_test_started']))
    elif action=='portal':result=portal()
    elif action=='finish':result=finish(data['report'])
    else:raise RuntimeError('unknown private RPC')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
