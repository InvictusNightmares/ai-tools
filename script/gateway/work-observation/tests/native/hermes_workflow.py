from media_fixture import image_fixture, image_payloads, verify_capture
import argparse,datetime,hashlib,http.server,json,os,pathlib,pty,signal,sqlite3,subprocess,threading,time
ap=argparse.ArgumentParser();ap.add_argument('--gateway-bin');ap.add_argument('--base');ap.add_argument('--key-file');ap.add_argument('--region',default='fixture');args=ap.parse_args();os.umask(0o077)
root=pathlib.Path('/private/tmp/gateway-hermes-advanced-'+args.region+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));root.mkdir();(root/'driver.py').write_bytes(pathlib.Path(__file__).read_bytes());work=root/'work';work.mkdir();profile=root/'profile';profile.mkdir();(work/'a.txt').write_text('NATIVE_ALPHA_731\n');(work/'b.txt').write_text('NATIVE_BETA_842\n');records=[];delay=threading.Event();fixture=None;checks=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"data":[{"id":"auto","object":"model"}]}')
 def do_POST(self):
  wire=self.rfile.read(int(self.headers['Content-Length']));b=json.loads(wire);rec={'wire_sha256':hashlib.sha256(wire).hexdigest(),'body':b,'headers':{k:v for k,v in self.headers.items() if k.lower() not in ('authorization','x-api-key')}};records.append(rec);msgs=b.get('messages',[]);last=next((json.dumps(x) for x in reversed(msgs) if x.get('role')=='user'),'');tail=msgs[-1].get('role') if msgs else '';names=[t.get('function',{}).get('name') for t in b.get('tools',[])];message={'role':'assistant','content':'NATIVE_ALPHA_731 NATIVE_BETA_842 NATIVE_MARKER_COBALT_527 NATIVE_PHASE_READY'};finish='stop'
  if 'NATIVE_MULTITOOL' in last and tail!='tool' and 'read_file' in names:
   message={'role':'assistant','content':None,'tool_calls':[{'id':'call_'+str(len(records))+'_'+str(i),'type':'function','function':{'name':'read_file','arguments':json.dumps({'path':str(work/f)})}} for i,f in enumerate(['a.txt','b.txt'])]};finish='tool_calls'
  elif 'NATIVE_DELEGATE' in last and tail!='tool' and 'delegate_task' in names:
   message={'role':'assistant','content':None,'tool_calls':[{'id':'call_'+str(len(records)),'type':'function','function':{'name':'delegate_task','arguments':json.dumps({'tasks':[{'goal':'Read '+str(work/'a.txt')+' and report its marker. Do not delegate further.'}]})}}]};finish='tool_calls'
  if 'NATIVE_CANCEL_NOW' in last:delay.set();time.sleep(20)
  r={'id':'chatcmpl_native_'+str(len(records)),'object':'chat.completion','created':int(time.time()),'model':'auto','choices':[{'index':0,'message':message,'finish_reason':finish}],'usage':{'prompt_tokens':4000,'completion_tokens':30,'total_tokens':4030}}
  try:
   self.send_response(200);self.send_header('Content-Type','text/event-stream' if b.get('stream') else 'application/json');self.end_headers()
   if not b.get('stream'):self.wfile.write(json.dumps(r).encode());return
   delta=dict(message)
   if 'tool_calls' in delta:delta['tool_calls']=[dict(t,index=i) for i,t in enumerate(delta['tool_calls'])]
   for d,f in [(delta,None),({},finish)]:self.wfile.write(('data: '+json.dumps(dict(r,object='chat.completion.chunk',choices=[{'index':0,'delta':d,'finish_reason':f}]))+'\n\n').encode());self.wfile.flush()
   self.wfile.write(b'data: [DONE]\n\n')
  except (BrokenPipeError,ConnectionResetError):rec['client_disconnected']=True
if not args.base:fixture=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=fixture.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(fixture.server_port)+'/v1';key='synthetic-fixture'
else:base=args.base.rstrip('/');key=pathlib.Path(args.key_file).read_text().strip()
gateway=None
if args.gateway_bin:
 assert fixture is not None, 'gateway fixture requires synthetic backend'
 import importlib.util
 spec=importlib.util.spec_from_file_location('native_fixture_proxy',str(pathlib.Path(__file__).with_name('collector_adapter.py')));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 gateway=module.GatewayFixture(root,args.gateway_bin,base.removesuffix('/v1'));base=gateway.base+'/v1'
config={'model':{'default':'auto','provider':'gateway-fixture','base_url':base,'context_length':1000000,'supports_vision':True},'providers':{'gateway-fixture':{'base_url':base,'key_env':'AI_GATEWAY_TEST_API_KEY','default_model':'auto','transport':'chat_completions'}},'memory':{'memory_enabled':False,'user_profile_enabled':False},'terminal':{'backend':'local','cwd':str(work)},'display':{'tool_progress':'off'},'delegation':{'max_concurrent_children':1,'max_spawn_depth':1}}
(profile/'config.yaml').write_text(json.dumps(config));env=dict(os.environ,HERMES_HOME=str(profile),AI_GATEWAY_TEST_API_KEY=key,TERM='xterm-256color',HERMES_YES='1');master,slave=pty.openpty();log=(root/'terminal.raw').open('wb');p=subprocess.Popen(['/private/tmp/gateway-hermes-20260916/.venv/bin/hermes','chat','--cli','--model','auto','--provider','gateway-fixture','--toolsets','file,delegation','--max-turns','6','--run-budget','240'],cwd=work,env=env,stdin=slave,stdout=slave,stderr=slave,start_new_session=True);os.close(slave)
def read():
 try:
  while True:
   b=os.read(master,65536)
   if not b:return
   log.write(b);log.flush()
 except OSError:pass
threading.Thread(target=read,daemon=True).start()
def sql(query):
 try:
  c=sqlite3.connect(profile/'state.db',timeout=1);rows=c.execute(query).fetchall();c.close();return rows
 except sqlite3.Error:return []
def wait(fn,timeout=180):
 end=time.time()+timeout
 while time.time()<end:
  out=fn()
  if out:return out
  if p.poll() is not None:raise RuntimeError('client_exited')
  time.sleep(.2)
 raise TimeoutError('native_wait')
def send(text):
 data=text.encode()
 if len(data)>1024:data=b'\x1b[200~'+data+b'\x1b[201~'
 data+=b'\r'
 while data:
  n=os.write(master,data);data=data[n:]
def assistants():return sql("SELECT id,content FROM messages WHERE role='assistant' AND finish_reason='stop' AND content IS NOT NULL AND content!='' AND session_id IN (SELECT id FROM sessions WHERE parent_session_id IS NULL) ORDER BY id")
def turn(text):
 old=max([x[0] for x in assistants()]+[0]);send(text);rows=wait(lambda:[x for x in assistants() if x[0]>old]);time.sleep(1);return rows[-1][1] or ''
def check(name,passed,**extra):row={'check':name,'passed':bool(passed),**extra};checks.append(row);print(json.dumps(row),flush=True)
try:
 wait(lambda:(profile/'state.db').exists(),30);time.sleep(2)
 text=turn('Remember NATIVE_MARKER_COBALT_527 and NATIVE_PHASE_READY. Reply with both; do not use tools.');check('initial_marker','NATIVE_MARKER_COBALT_527' in text)
 for i in range(7):turn('Preserve marker and phase. Archive '+str(i)+': '+('Historical logout UI notes. '*600)+' Reply with the marker and phase.')
 old=len(records);send('/compress Preserve the remembered marker and phase.');wait(lambda:sql('SELECT id FROM messages WHERE _compressed_summary=1 OR compacted=1'),90);time.sleep(1);check('native_compress',True,new_requests=len(records)-old)
 text=turn('Return the marker and phase I asked you to remember. Do not use tools.');check('recall_after_compress','NATIVE_MARKER_COBALT_527' in text)
 text=turn('NATIVE_MULTITOOL: Read a.txt and b.txt using two separate read_file tools and return both exact strings.');calls=sql("SELECT count(*) FROM messages WHERE role='tool' AND tool_name='read_file'");check('multiple_native_tools','NATIVE_ALPHA_731' in text and 'NATIVE_BETA_842' in text and calls and calls[0][0]>=2,tool_count=calls[0][0] if calls else 0)
 text=turn('NATIVE_DELEGATE: Use delegate_task to ask one child to read a.txt and return its marker. Do not read it yourself.');children=sql('SELECT count(*) FROM sessions WHERE parent_session_id IS NOT NULL');check('native_child_session',children and children[0][0]>0,child_sessions=children[0][0] if children else 0)
 wait(lambda:sql('SELECT id FROM sessions WHERE parent_session_id IS NOT NULL AND ended_at IS NOT NULL'),120)
 wait(lambda:sql("SELECT id FROM messages WHERE role='user' AND content LIKE '[ASYNC DELEGATION BATCH COMPLETE%'"),120)
 turn('Confirm that the delegated file read is finished. Reply READY only. No tools.')
 send('NATIVE_CANCEL_NOW: Write an exhaustive 10000-word explanation of generic UI event loops. Do not use tools.')
 if fixture:delay.wait(20)
 else:time.sleep(3)
 os.write(master,b'\x03');time.sleep(2);check('native_cancel_process_alive',p.poll() is None)
 text=turn('Return the original memory code beginning NATIVE_MARKER saved before compression. No tools.');check('resume_after_cancel','NATIVE_MARKER_COBALT_527' in text)
 image_path,image_b64=image_fixture(work)
 text=turn(str(image_path)+' Describe this image. Reply with NATIVE_ALPHA_731 and NATIVE_BETA_842; no tools.')
 check('native_image_forwarded',bool(text) and any(image_payloads(r['body']) for r in records))
except Exception as e:check('harness_error',False,error_type=type(e).__name__);(root/'error.txt').write_text(str(e))
finally:
 if p.poll() is None:
  send('/exit');
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10)
 os.close(master);log.close()
 if gateway:
  gateway.close();media=verify_capture(gateway,records);print('MEDIA='+json.dumps(media),flush=True)
 if fixture:fixture.shutdown();fixture.server_close()
 (root/'requests.json').write_text(json.dumps(records,indent=2));(root/'result.json').write_text(json.dumps({'scope':'native hermes through observation collector to synthetic provider' if gateway else 'native Hermes PTY to local deterministic provider fixture; no gateway or real model' if fixture else 'native Hermes PTY through gateway and real model','checks':checks,'gateway_candidate_tested':bool(gateway),'guard_and_models':'no Guard; synthetic provider' if gateway else 'provider fixture only' if fixture else 'real regional services','region':args.region,'request_count':len(records),'session_header_names':sorted({k.lower() for r in records for k in r['headers'] if 'session' in k.lower() or 'agent' in k.lower() and k.lower()!='user-agent'})},indent=2));print('RESULT_ROOT='+str(root),flush=True)

if not all(x['passed'] for x in checks) or (gateway and not media['passed']):raise SystemExit('native_workflow_acceptance_failed')
