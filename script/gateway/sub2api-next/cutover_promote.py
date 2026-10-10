#!/usr/bin/env python3
"""Promote only a certified final database while both original writers are stopped."""
import argparse
import json
import os
import time

from cutover_merge import ROOT,OPS,CONTAINER,SOURCE_ROLE,SOURCE_NETWORK,check,guard,run,sql,value,assert_sql,table_certificate
from cutover_control import state,save,inspect,compose,redis,iptables,CHAIN,report

AUTH_FIELDS=('email','id_token','client_id','plan_type','expires_at','access_token','refresh_token',
             '_token_version','chatgpt_user_id','organization_id','chatgpt_account_id','subscription_expires_at')


def stopped():
    check(all(not inspect(name)['State']['Running'] for name in ('sub2api','sub2api-next')),'both writers must be stopped')


def customize():
    stopped();x=state();check(x['stage']=='frozen','expected frozen state')
    check(value('cutover_final',"SELECT to_json(bool_and(complete)) FROM cutover_audit.build_state") is True,'final merge not fully certified')
    for name in ('final-a-dump.json','final-b-dump.json','final-restore.json','final-core.json','final-v2.json'):
        check(json.loads((OPS/name).read_text()).get('freeze_id')==x['freeze_id'],'readiness belongs to another freeze '+name)
    for side in ('a','b'):
        record=json.loads((OPS/('final-'+side+'-dump.json')).read_text())
        check(record['phase']=='local_snapshot_completed','fresh frozen backup missing')
    ids=value('cutover_final',"SELECT json_agg(a.id ORDER BY a.id) FROM accounts a WHERE a.deleted_at IS NULL AND a.platform='openai' AND a.type='oauth' AND EXISTS(SELECT 1 FROM account_groups ag JOIN groups g ON g.id=ag.group_id WHERE ag.account_id=a.id AND g.deleted_at IS NULL)")
    check(len(ids)==8,'expected eight current B OAuth accounts')
    sources=json.loads(sql('sub2api',"SELECT json_agg(json_build_object('id',id,'credentials',credentials)) FROM accounts WHERE id IN ({})".format(','.join(map(str,ids))),True))
    current=value('cutover_final',"SELECT json_agg(json_build_object('id',id,'account_identity',credentials->>'chatgpt_account_id')) FROM accounts WHERE id IN ({})".format(','.join(map(str,ids))))
    identity={a['id']:a['account_identity'] for a in current}
    check({a['id'] for a in sources}==set(ids) and all(identity.values()),'complete nonempty OAuth identity inventory required')
    payload=[]
    for account in sources:
        credentials=account['credentials']
        check(credentials.get('access_token') and credentials.get('refresh_token'),'fresh OAuth token pair missing')
        check(identity[account['id']]==credentials.get('chatgpt_account_id'),'upstream identity differs from B assignment')
        payload.append({'id':account['id'],'credentials':{k:credentials[k] for k in AUTH_FIELDS if k in credentials}})
    encoded=json.dumps(payload).encode().hex()
    fields='ARRAY['+','.join("'"+k+"'" for k in AUTH_FIELDS)+']::text[]'
    query="""BEGIN; SET LOCAL TIME ZONE 'Asia/Shanghai';
      CREATE FUNCTION pg_temp.check_true(ok boolean,msg text) RETURNS void LANGUAGE plpgsql AS
        $$ BEGIN IF ok IS DISTINCT FROM TRUE THEN RAISE EXCEPTION '%%',msg; END IF; END $$;
      CREATE TABLE cutover_audit.activation_accounts_before AS SELECT * FROM accounts;
      CREATE TABLE cutover_audit.activation_quotas_before AS SELECT * FROM user_platform_quotas;
      CREATE TEMP TABLE current_tokens AS SELECT * FROM jsonb_to_recordset(convert_from(decode('%s','hex'),'UTF8')::jsonb) AS t(id bigint,credentials jsonb);
      UPDATE accounts a SET credentials=(a.credentials-%s)||t.credentials,updated_at=now() FROM current_tokens t WHERE a.id=t.id;
      UPDATE user_platform_quotas q SET weekly_usage_usd=0,weekly_window_start=date_trunc('week',now()),updated_at=now()
        FROM users u WHERE q.user_id=u.id AND u.role='user' AND u.deleted_at IS NULL AND q.deleted_at IS NULL AND q.platform='openai';
      """%(encoded,fields)
    query+=assert_sql("(SELECT count(*) FROM user_platform_quotas q JOIN users u ON u.id=q.user_id WHERE u.role='user' AND u.deleted_at IS NULL AND q.platform='openai' AND q.deleted_at IS NULL AND q.weekly_usage_usd=0 AND q.weekly_limit_usd=300 AND q.weekly_window_start=date_trunc('week',now()))=74",'activation weekly policy differs')
    query+=assert_sql("(SELECT count(*) FROM current_tokens)=8 AND (SELECT count(*) FROM accounts a JOIN current_tokens t USING(id) WHERE a.credentials @> t.credentials)=8",'not all eight OAuth token pairs were synchronized')
    query+=assert_sql("NOT EXISTS(SELECT 1 FROM accounts a JOIN cutover_audit.activation_accounts_before b USING(id) WHERE (to_jsonb(a)-'credentials'-'updated_at')<>(to_jsonb(b)-'credentials'-'updated_at') OR a.credentials-{}<>b.credentials-{})".format(fields,fields),'B account configuration changed beyond OAuth')
    query+=assert_sql("NOT EXISTS(SELECT 1 FROM user_platform_quotas a JOIN cutover_audit.activation_quotas_before b USING(id) WHERE (to_jsonb(a)-'weekly_usage_usd'-'weekly_window_start'-'updated_at')<>(to_jsonb(b)-'weekly_usage_usd'-'weekly_window_start'-'updated_at'))",'quota changed beyond authorized weekly activation')
    query+='COMMIT;';sql('cutover_final',query)
    sql('cutover_final',"DROP SCHEMA source_a_facts CASCADE; DROP SCHEMA source_a CASCADE; DROP SCHEMA source_b CASCADE; DROP SERVER source_a CASCADE; DROP SERVER source_b CASCADE; DROP EXTENSION postgres_fdw;")
    sql('sub2api',"DROP SCHEMA cutover_read_20261009 CASCADE; REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM {r}; REVOKE USAGE ON SCHEMA public FROM {r}; REVOKE CONNECT ON DATABASE sub2api FROM {r}; DROP ROLE {r};".format(r=SOURCE_ROLE),True)
    run(['docker','network','disconnect',SOURCE_NETWORK,CONTAINER])
    # Exact final-history boundary replaces the preview baseline containing QA.
    baseline=value('cutover_final',"""SELECT json_build_object('usage_max_id',(SELECT max(id) FROM usage_logs),
      'usage_totals',(SELECT json_agg(t) FROM (SELECT api_key_id,count(*) requests,sum(input_tokens)::text input_tokens,
      sum(output_tokens)::text output_tokens,sum(cache_creation_tokens)::text cache_creation_tokens,
      sum(cache_read_tokens)::text cache_read_tokens,sum(total_cost)::text total_cost,sum(actual_cost)::text actual_cost
      FROM usage_logs GROUP BY api_key_id ORDER BY api_key_id)t))""")
    (ROOT/'ops'/'production-history-baseline.json').write_text(json.dumps(baseline,indent=2))
    x.update(stage='customized',customized_at_epoch=int(time.time()));save(x)
    report('activation_data_ready',oauth_accounts=len(ids),weekly_accounts=74,history_cutoff=baseline['usage_max_id'],balances_unchanged=True)


def promote():
    stopped();x=state();check(x['stage']=='customized','customization incomplete')
    check(sql('postgres',"SELECT count(*) FROM pg_stat_activity WHERE datname IN('sub2api_next','cutover_final')")=='0','database still has sessions')
    check(sql('postgres',"SELECT count(*) FROM pg_database WHERE datname='cutover_previous'")=='0','unexpected previous DB')
    x['stage']='promoting';save(x)
    sql('postgres','BEGIN; ALTER DATABASE sub2api_next RENAME TO cutover_previous; ALTER DATABASE cutover_final RENAME TO sub2api_next; COMMIT;')
    # Invalidate derived caches only. Authentication/session key spaces survive.
    prefixes=['apikey:auth:*','billing:balance:*','billing:sub:*','billing:user_platform_quota:*','billing:upq:dirty','sched:*','oauth:token:*','temp_unsched:account:*']
    lua="""local removed=0; for _,pattern in ipairs(ARGV) do local cursor='0'; repeat
      local r=redis.call('SCAN',cursor,'MATCH',pattern,'COUNT',1000); cursor=r[1];
      for _,key in ipairs(r[2]) do removed=removed+redis.call('UNLINK',key) end until cursor=='0' end;return removed"""
    deleted=int(redis('b',['EVAL',lua,'0']+prefixes))
    config=json.loads((ROOT/'compose.json').read_text());config['services']['app']['environment']['TOKEN_REFRESH_ENABLED']='true'
    (ROOT/'compose.json').write_text(json.dumps(config,indent=2));compose('up','-d','--no-deps','app')
    deadline=time.monotonic()+120
    while inspect('sub2api-next')['State'].get('Health',{}).get('Status')!='healthy':
        check(time.monotonic()<deadline,'promoted B is not healthy');time.sleep(2)
    new_ip=inspect('sub2api-next')['NetworkSettings']['Networks']['sub2api-next_candidate']['IPAddress']
    # Cover a possible changed container address before starting the formal proxy.
    if new_ip!=x['ips']['b']:
        iptables('-I',CHAIN,'1','-d',new_ip,'-p','tcp','--dport','8080','-j','REJECT','--reject-with','tcp-reset')
        iptables('-D',CHAIN,'-d',x['ips']['b'],'-p','tcp','--dport','8080','-j','REJECT','--reject-with','tcp-reset')
        iptables('-D',CHAIN,'-d',x['ips']['b'],'-p','tcp','--dport','8080','-m','conntrack','--ctstate','NEW','-j','REJECT','--reject-with','tcp-reset')
    run(['docker','stop','--time','30','sub2api-proxy'])
    compose('up','-d','--no-deps','gateway')
    proxy_ip=inspect('sub2api-next-proxy')['NetworkSettings']['Networks']['sub2api-next_candidate']['IPAddress']
    iptables('-I',CHAIN,'1','-s',proxy_ip,'-d',new_ip,'-p','tcp','--dport','8080','-j','RETURN')
    x.update(stage='promoted_gated',promoted_at_epoch=int(time.time()),new_ip=new_ip);save(x)
    report('promoted_under_maintenance',only_new_app_running=True,derived_caches_removed=deleted,formal_port=8080,preview_port=18080)


def open_service():
    x=state();check(x['stage']=='promoted_gated','expected gated promoted service')
    accepted=json.loads((OPS/'final-acceptance.json').read_text())
    check(accepted.get('passed') is True and accepted.get('freeze_id')==x['freeze_id'],'current formal-chain acceptance incomplete')
    path=ROOT/'gateway'/'nginx.conf'
    with path.open('w') as stream:stream.write((OPS/'nginx-final-open.conf').read_text());stream.flush();os.fsync(stream.fileno())
    run(['docker','exec','sub2api-next-proxy','nginx','-t']);run(['docker','exec','sub2api-next-proxy','nginx','-s','reload'])
    iptables('-D','DOCKER-USER','-j',CHAIN);iptables('-F',CHAIN);iptables('-X',CHAIN)
    x.update(stage='open',opened_at_epoch=int(time.time()));save(x)
    report('formal_service_open',preview_same_instance=True,formal_chain_tested=True)


def main():
    os.umask(0o077);guard();p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['customize','promote','open']);a=p.parse_args()
    {'customize':customize,'promote':promote,'open':open_service}[a.action]()

if __name__=='__main__':main()
