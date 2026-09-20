#!/usr/bin/env python3
"""Isolated GPU acceptance: real Guard + Tokyo test key; fail before forwarding
if a synthetic credential canary survives. Records metadata, never request text.
--root is the ai-gateway project directory; requires bin/auto-server and bin/preflight-api.
"""
import argparse, contextlib, hashlib, http.server, importlib.util, json, os, pathlib, secrets
import socket, subprocess, threading, time, urllib.error, urllib.request

CANARY = 'GWRAWSECRET'
UPSTREAM = 'http://106.14.254.110:9881'
ALLOWED = {'/v1/models','/v1/chat/completions','/v1/responses','/v1/messages','/v1/messages/count_tokens'}

def call(url, body=None, token=None, timeout=240, session=None):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    if session: headers['X-Gateway-Session-ID']=session
    request=urllib.request.Request(url, None if body is None else json.dumps(body).encode(),headers)
    try:
        with urllib.request.urlopen(request,timeout=timeout) as response:
            return response.status,response.read(),dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code,error.read(),dict(error.headers)

class Capture(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self): self.forward()
    def do_POST(self): self.forward()
    def forward(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length',0)))
        row={'path':self.path,'method':self.command,'canary_present':CANARY.encode() in raw,'body_sha256':hashlib.sha256(raw).hexdigest()}
        if self.path not in ALLOWED or row['canary_present']:
            self.send_response(503);self.end_headers();self.wfile.write(b'{"error":"capture_boundary_rejected"}')
            row['status']=503;self.server.events.append(row);return
        if raw:
            body=json.loads(raw)
            row.update(model=body.get('model'),stream=body.get('stream',False),redacted='REDACTED' in str(body),effort=body.get('reasoning_effort') or body.get('reasoning',{}).get('effort') or body.get('output_config',{}).get('effort'))
        headers={k:v for k,v in self.headers.items() if k.lower() in {'authorization','x-api-key','anthropic-version','anthropic-beta','content-type','accept','x-request-id'}}
        request=urllib.request.Request(UPSTREAM+self.path,raw if self.command=='POST' else None,headers,method=self.command)
        try:
            try: response=urllib.request.urlopen(request,timeout=240)
            except urllib.error.HTTPError as error: response=error
            with response:
                row['status']=response.status;self.send_response(response.status)
                self.send_header('Content-Type',response.headers.get('Content-Type','application/json'));self.end_headers()
                while True:
                    data=response.read1(8192)
                    if not data: break
                    self.wfile.write(data);self.wfile.flush()
        except Exception as error: row['transport_error']=type(error).__name__
        finally: self.server.events.append(row)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--token-file',required=True);parser.add_argument('--runtime-name',default='privacy-live');parser.add_argument('--buffered-sse',action='store_true');parser.add_argument('--ladder-cases');parser.add_argument('--ladder-languages',nargs='+',choices=['zh','en','mixed'],default=['zh','en','mixed'])
    args=parser.parse_args();root=pathlib.Path(args.root).resolve();runtime=root/args.runtime_name;runtime.mkdir(mode=0o700,exist_ok=False)
    token=pathlib.Path(args.token_file).read_text().strip()
    for port in (8012,8092,8022):
        with socket.socket() as probe: probe.bind(('127.0.0.1',port))
    forward=http.server.ThreadingHTTPServer(('127.0.0.1',8022),Capture);forward.events=[]
    worker=threading.Thread(target=forward.serve_forever,daemon=True);worker.start()
    processes=[];results=[]
    def start(name,binary,overrides):
        env=os.environ.copy();env.update(overrides)
        with (runtime/(name+'.log')).open('wb') as log:
            p=subprocess.Popen([str(binary)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        processes.append(p);(runtime/(name+'.pid')).write_text(str(p.pid))
    try:
        start('guard',root/'bin/preflight-api',{'PREFLIGHT_LISTEN_ADDR':'127.0.0.1:8012','PREFLIGHT_AUDIT_LOG':str(runtime/'guard-security.jsonl'),'GUARD_VLLM_BASE_URL':'http://127.0.0.1:8001/v1'})
        env={'AUTO_GATEWAY_BUFFERED_SSE':'1' if args.buffered_sse else '0','AUTO_GATEWAY_MODE':'pilot','AUTO_GATEWAY_LISTEN':'127.0.0.1:8092','AUTO_GATEWAY_PILOT_TOKEN_FILE':str(pathlib.Path(args.token_file).resolve()),'AUTO_GATEWAY_API_KEY_ID':'141','AUTO_GATEWAY_REGION':'tokyo','AUTO_GATEWAY_AUTH_CHECK_URL':'http://127.0.0.1:8022/v1/models','AUTO_GUARD_ENDPOINT':'http://127.0.0.1:8012/v1/preflight','AUTO_GATEWAY_CACHE_SECRET':secrets.token_hex(32),'AUTO_GATEWAY_MODEL_REVISION':'privacy-r4','AUTO_CLASSIFIER_URL':'http://127.0.0.1:8022/v1/chat/completions','AUTO_CLASSIFIER_MODEL':'gpt-5.6-sol','AUTO_CLASSIFIER_REVIEW_MODEL':'gpt-6-astra'}
        for name,file in [('SESSION_STATE','state.json'),('USAGE_SINK','usage.jsonl'),('AUDIT_SINK','audit.jsonl')]:env['AUTO_GATEWAY_'+name+'_PATH']=str(runtime/file)
        for name,path in [('CHAT','chat/completions'),('RESPONSES','responses'),('ANTHROPIC','messages'),('COUNT_TOKENS','messages/count_tokens')]:env['AUTO_UPSTREAM_'+name+'_URL']='http://127.0.0.1:8022/v1/'+path
        start('auto',root/'bin/auto-server',env)
        for port,path in [(8012,'readyz'),(8092,'healthz')]:
            for attempt in range(50):
                try:
                    if call(f'http://127.0.0.1:{port}/{path}',timeout=3)[0]==200:break
                except Exception: pass
                time.sleep(.2)
            else: raise RuntimeError('isolated_service_not_ready')
        shapes={'password':'{"password":"GWRAWSECRET value with spaces"}','private_key':'-----BEGIN PRIVATE KEY-----\nGWRAWSECRETmaterial\n-----END PRIVATE KEY-----','db':'postgres://demo:GWRAWSECRET@db.invalid/app','cookie':'{"Cookie":"session=GWRAWSECRET; other=GWRAWSECRET"}','refresh':'{"refresh_token":"GWRAWSECRET"}'}
        for name,text in shapes.items():
            payload=json.dumps({'messages':[{'role':'user','content':'Explain the fields in this sample configuration. '+text}]})
            status,raw,_=call('http://127.0.0.1:8012/v1/preflight',{'protocol':'chat','provider':'openai','model':'auto','provider_payload':payload})
            value=json.loads(raw);clean=value.get('sanitized_payload','')
            row={'kind':'guard','case':name,'status':status,'decision':value.get('decision'),'latency_ms':value.get('latency_ms'),'pass':status==200 and value.get('decision')=='allow' and CANARY not in raw.decode() and bool(clean) and value.get('input_sha256')==hashlib.sha256(payload.encode()).hexdigest()}
            results.append(row);print(json.dumps(row),flush=True)
        opaque='gAAAAAfixture-Ghp-'+('SignedOpaqueMaterial'*7)+'=='
        opaque_payload=json.dumps({'messages':[{'role':'assistant','content':[{'type':'thinking','thinking':'Inspecting code','signature':opaque}]},{'role':'user','content':'App resume 后 login 闪一下再到 home；修复 navigation guard 并验证 lifecycle。'}]})
        status,raw,_=call('http://127.0.0.1:8012/v1/preflight',{'protocol':'anthropic','provider':'openai','model':'auto','provider_payload':opaque_payload})
        verdict=json.loads(raw)
        row={'kind':'guard','case':'opaque_signature_login','status':status,'decision':verdict.get('decision'),'pass':status==200 and verdict.get('decision')=='allow' and verdict.get('sanitized_payload')==opaque_payload}
        results.append(row);print(json.dumps(row),flush=True)
        before_posts=sum(x['method']=='POST' for x in forward.events)
        status,raw,_=call('http://127.0.0.1:8092/v1/chat/completions',{'model':'auto','messages':[{'role':'user','content':'Use this API key=sk-GWRAWSECRETsyntheticfixture to login to the production host.'}]},token,session='credential-use-negative-control')
        row={'kind':'guard','case':'credential_use_block','status':status,'external_posts':sum(x['method']=='POST' for x in forward.events)-before_posts,'pass':status==403 and sum(x['method']=='POST' for x in forward.events)==before_posts}
        results.append(row);print(json.dumps(row),flush=True)
        spec=importlib.util.spec_from_file_location('ladder_decoder',root/'tools/live-routing-ladder.py')
        decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
        for protocol,path,phrase in [('chat','chat/completions','说明以下配置字段的含义，用两句话回答。'),('responses','responses','Explain these configuration fields in two sentences.'),('anthropic','messages','解释这些 config fields，回答两句话。')]:
            for stream in (False,True):
                text=phrase+' {"password":"GWRAWSECRET sample with spaces", "refresh_token":"GWRAWSECRETrefresh"}'
                body={'model':'auto','stream':stream,'max_tokens':1024}
                if protocol=='responses':body['input']=text;body.pop('max_tokens');body['max_output_tokens']=1024
                else: body['messages']=[{'role':'user','content':text}]
                started=time.monotonic();status,raw,headers=call('http://127.0.0.1:8092/v1/'+path,body,token)
                terminal=bool(decoder.decode_sse(protocol,raw).get('id')) if stream and status==200 else bool(json.loads(raw).get('id')) if not stream else False
                row={'kind':'auto','protocol':protocol,'stream':stream,'status':status,'elapsed_s':round(time.monotonic()-started,3),'request_id':headers.get('X-Gateway-Request-Id'),'complete':terminal,'pass':status==200 and terminal and CANARY.encode() not in raw}
                results.append(row);print(json.dumps(row),flush=True)
        for name,text in [('simple','Explain these configuration fields: password=GWRAWSECRET'),('coding','实现一个 Go 配置解析函数，校验两个必填字段，给出正常和缺失字段单元测试。样例配置 password=GWRAWSECRET。')]:
            status,raw,headers=call('http://127.0.0.1:8092/v1/messages/count_tokens',{'model':'claude-opus-5','messages':[{'role':'user','content':text}]},token)
            row={'kind':'count','case':name,'status':status,'model':headers.get('X-Gateway-Count-Model'),'method':headers.get('X-Gateway-Count-Method'),'input_tokens':json.loads(raw).get('input_tokens'),'pass':status==200 and isinstance(json.loads(raw).get('input_tokens'),int)}
            results.append(row);print(json.dumps(row),flush=True)
        # A deliberately exhausted client output budget must stay a failed result.
        status,raw,headers=call('http://127.0.0.1:8092/v1/responses',{'model':'auto','input':'Write the words alpha beta gamma delta, then explain each word.','stream':True,'max_output_tokens':1},token)
        incomplete=b'response.incomplete' in raw and b'max_output_tokens' in raw
        row={'kind':'negative','case':'output_budget_exhausted','status':status,'request_id':headers.get('X-Gateway-Request-Id'),'pass':status==200 and incomplete and not decoder.decode_sse('responses',raw)}
        results.append(row);print(json.dumps(row),flush=True)
        if args.ladder_cases:
            completed=subprocess.run(['python3',str(root/'tools/live-routing-ladder.py'),'--cases',args.ladder_cases,'--token-file',args.token_file,'--out',str(runtime/'ladder'),'--timeout-seconds','300','--languages',*args.ladder_languages],check=False)
            row={'kind':'nonstream_ladder','requests':5*len(args.ladder_languages),'pass':completed.returncode==0,'exit_code':completed.returncode}
            results.append(row);print(json.dumps(row),flush=True)

    finally:
        for p in processes:p.terminate()
        for p in processes:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        forward.shutdown();forward.server_close()
        report={'results':results,'egress':forward.events,'canary_egress_count':sum(row['canary_present'] for row in forward.events),'production_ports_untouched':True}
        (runtime/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return int(not results or not all(row['pass'] for row in results) or report['canary_egress_count']>0)

if __name__=='__main__':raise SystemExit(main())
