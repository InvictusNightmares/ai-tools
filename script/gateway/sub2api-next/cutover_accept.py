#!/usr/bin/env python3
"""Run private formal-chain HTTP/SSE requests via GPU; never write keys there."""
import json
import subprocess
import tempfile
import time
import uuid

SERVER='/opt/sub2api-next/ops/cutover/cutover_accept_server.py'
CONTROL_PATH=None


def ssh(host,*command):
    options=[] if CONTROL_PATH is None else ['-oControlMaster=auto','-oControlPersist=180','-oControlPath='+CONTROL_PATH]
    return ['ssh']+options+[host]+list(command)


def run(args,text,timeout=240):
    result=subprocess.run(args,input=text,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=timeout)
    if result.returncode:raise RuntimeError('private acceptance transport failed; no credential output emitted')
    lines=[line for line in result.stdout.splitlines() if line.startswith('{')]
    if not lines:raise RuntimeError('private acceptance response missing')
    return json.loads(lines[-1])


def rpc(action,**data):
    return run(ssh('qiyuan-us','sudo','-n','python3',SERVER),json.dumps(dict(data,action=action)))


def gpu_request(person,secret,model):
    gpt=model.startswith('gpt-');nonce='cutover-'+uuid.uuid4().hex
    body={'model':model,'stream':True,'store':False,'instructions':'Reply briefly.',
          'input':[{'role':'user','content':[{'type':'input_text','text':'Reply with exactly OK. '+nonce}]}]} if gpt else {
          'model':model,'stream':False,'max_tokens':64,'messages':[{'role':'user','content':'Reply with exactly OK. '+nonce}]}
    package={'url':'http://192.168.64.16:4001'+('/v1/responses' if gpt else '/v1/chat/completions'),
      'body':body,'headers':{'Authorization':'Bearer '+person['key'],'Content-Type':'application/json','X-Sub2API-Cutover':secret,'X-Request-ID':nonce},'gpt':gpt}
    # Data exists only in SSH stdin and process memory on GPU, never in a file or argv.
    code="""import json,urllib.request,urllib.error,time
p=json.loads(%r)
request=urllib.request.Request(p['url'],data=json.dumps(p['body']).encode(),headers=p['headers'],method='POST')
started=time.monotonic()
try: response=urllib.request.urlopen(request,timeout=150)
except urllib.error.HTTPError as exc: response=exc
raw=response.read(8*1024*1024)
try: body=json.loads(raw)
except ValueError:body={}
error=body.get('error',{}) if isinstance(body,dict) else {}
if not isinstance(error,dict):error={}
completed=(b'event: response.completed' in raw or b'"type":"response.completed"' in raw or b'"type": "response.completed"' in raw) if p['gpt'] else bool(body.get('choices'))
print(json.dumps({'status':response.code,'completed':completed,'response_bytes':len(raw),'seconds':round(time.monotonic()-started,3),'request_id':response.headers.get('X-Request-ID'),'error_type':error.get('type'),'error_code':error.get('code'),'weekly_quota_error':error.get('message')=='Weekly usage quota exhausted for this platform.'}))
"""%json.dumps(package)
    return run(ssh('qiyuan-gpu','python3','-'),code,timeout=180)


def call(person,secret,model,account):
    before=rpc('ledger',user_id=person['user_id'],key_id=person['key_id'])
    transport=gpu_request(person,secret,model)
    if transport['status']!=200 or not transport['completed']:raise RuntimeError('formal request failed: '+json.dumps(transport))
    settled=rpc('confirm',user_id=person['user_id'],key_id=person['key_id'],group_id=person['group_id'],account_id=account,before=before)
    result=dict(settled,transport=transport)
    print(json.dumps({'tested_group':person['group_name'],'model':model,'http_status':200,'account_id':account,'usage_id':settled['id'],'billing_reconciled':True}),flush=True)
    return result


def acceptance():
    context=rpc('context');secret=context['gate_secret'];samples=context['samples']
    report={'gpt':[],'deepseek':[]}
    for person in samples:report['gpt'].append(call(person,secret,'gpt-5.6-luna',person['account_id']))
    person=samples[0]
    for model,aid in [('deepseek-flash',76),('deepseek-v4-pro',77)]:
        report['deepseek'].append(call(person,secret,model,aid))
    limit_test_started=False
    try:
        rpc('quota-block',user_id=person['user_id'])
        limit_test_started=True
        blocked=gpu_request(person,secret,'gpt-5.6-luna');report['quota_http_status']=blocked['status']
        report['weekly_quota_error']=blocked['weekly_quota_error']
        if blocked['status']!=429 or not blocked['weekly_quota_error']:raise RuntimeError('GPT did not return the native personal weekly-limit error')
        report['deepseek_at_gpt_limit']=call(person,secret,'deepseek-flash',76)
    finally:
        report['quota_restoration']=rpc('quota-restore',user_id=person['user_id'],limit_test_started=limit_test_started)
    report['portal']=rpc('portal')
    result=rpc('finish',report=report)
    print(json.dumps({'formal_chain_passed':result['passed'],'entry':result['entry'],'gpt_routes':len(result['gpt']),
      'deepseek_routes':len(result['deepseek']),'gpt_limit_status':result['quota_http_status'],'customers_group_isolated':len(result['portal']['samples']),
      'old_source_usage_unchanged':result['old_source_usage_unchanged']}),flush=True)

def main():
    global CONTROL_PATH
    # Reuse only this run's private SSH sockets; do not change global SSH config.
    with tempfile.TemporaryDirectory(prefix='cutover-ssh-',dir='/private/tmp') as directory:
        CONTROL_PATH=directory+'/%C'
        try:
            acceptance()
        finally:
            for host in ('qiyuan-us','qiyuan-gpu'):
                try:
                    subprocess.run(['ssh','-oControlPath='+CONTROL_PATH,'-O','exit',host],
                                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
                except subprocess.TimeoutExpired:
                    pass
            CONTROL_PATH=None


if __name__=='__main__':main()
