from media_fixture import image_fixture, image_payloads, verify_capture
import argparse,datetime,hashlib,http.server,json,os,pathlib,queue,signal,subprocess,threading,time,uuid
ap=argparse.ArgumentParser();ap.add_argument('--gateway-bin');ap.add_argument('--base');ap.add_argument('--key-file');ap.add_argument('--region',default='fixture');args=ap.parse_args()
os.umask(0o077);root=pathlib.Path('/private/tmp/gateway-claude-advanced-'+args.region+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));root.mkdir();(root/'driver.py').write_bytes(pathlib.Path(__file__).read_bytes());work=root/'work';work.mkdir();profile=root/'profile';profile.mkdir();(work/'a.txt').write_text('NATIVE_ALPHA_731\n');(work/'b.txt').write_text('NATIVE_BETA_842\n');records=[];delay_started=threading.Event();fixture=None
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_POST(self):
  wire=self.rfile.read(int(self.headers.get('Content-Length','0')));b=json.loads(wire);record={'wire_sha256':hashlib.sha256(wire).hexdigest(),'path':self.path,'headers':{k:v for k,v in self.headers.items() if k.lower() not in ('authorization','x-api-key')},'body':b};records.append(record)
  if 'count_tokens' in self.path:self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"input_tokens":1000}');return
  msgs=b.get('messages',[]);last=next((json.dumps(x) for x in reversed(msgs) if x.get('role')=='user'),'');names=[t['name'] for t in b.get('tools',[])];content=[];stop='end_turn'
  if 'NATIVE_MULTITOOL' in last and 'tool_result' not in last and 'Read' in names:
   content=[{'type':'tool_use','id':'tool_'+str(len(records))+'_'+str(i),'name':'Read','input':{'file_path':str(work/f)}} for i,f in enumerate(['a.txt','b.txt'])];stop='tool_use'
  elif 'NATIVE_DELEGATE' in last and 'tool_result' not in last and 'Agent' in names:
   content=[{'type':'tool_use','id':'tool_'+str(len(records)),'name':'Agent','input':{'description':'Read isolated fixture file','prompt':'Read a.txt and report its marker. Do not delegate further or edit any file.','subagent_type':'fixture'}}];stop='tool_use'
  else:content=[{'type':'text','text':'NATIVE_ALPHA_731 NATIVE_BETA_842 NATIVE_MARKER_COBALT_527 NATIVE_PHASE_READY'}]
  message={'id':'msg_fixture_'+str(len(records)),'type':'message','role':'assistant','model':b.get('model','auto'),'content':content,'stop_reason':stop,'stop_sequence':None,'usage':{'input_tokens':4000,'output_tokens':30}}
  stream=b.get('stream',False);self.send_response(200);self.send_header('Content-Type','text/event-stream' if stream else 'application/json');self.end_headers()
  def event(typ,value):self.wfile.write(('event: '+typ+'\ndata: '+json.dumps({'type':typ,**value})+'\n\n').encode());self.wfile.flush()
  try:
   if not stream:self.wfile.write(json.dumps(message).encode());return
   event('message_start',{'message':dict(message,content=[],stop_reason=None)})
   if 'NATIVE_CANCEL_NOW' in last:
    delay_started.set()
    for _ in range(150):event('ping',{});time.sleep(.2)
   for i,block in enumerate(content):
    if block['type']=='text':event('content_block_start',{'index':i,'content_block':{'type':'text','text':''}});event('content_block_delta',{'index':i,'delta':{'type':'text_delta','text':block['text']}})
    else:event('content_block_start',{'index':i,'content_block':dict(block,input={})});event('content_block_delta',{'index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(block['input'])}})
    event('content_block_stop',{'index':i})
   event('message_delta',{'delta':{'stop_reason':stop,'stop_sequence':None},'usage':{'output_tokens':30}});event('message_stop',{})
  except (BrokenPipeError,ConnectionResetError):record['client_disconnected']=True
if not args.base:fixture=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=fixture.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(fixture.server_port);key='synthetic-fixture'
else:base=args.base.rstrip('/');key=pathlib.Path(args.key_file).read_text().strip()
gateway=None
if args.gateway_bin:
 assert fixture is not None, 'gateway fixture requires synthetic backend'
 import importlib.util
 spec=importlib.util.spec_from_file_location('native_fixture_proxy',str(pathlib.Path(__file__).with_name('collector_adapter.py')));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 gateway=module.GatewayFixture(root,args.gateway_bin,base.removesuffix('/v1'));base=gateway.base
env=dict(os.environ,ANTHROPIC_API_KEY=key,ANTHROPIC_BASE_URL=base,CLAUDE_CONFIG_DIR=str(profile),CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC='1');env.pop('ANTHROPIC_AUTH_TOKEN',None);env.pop('ANTHROPIC_CUSTOM_HEADERS',None);env.pop('CLAUDE_CODE_SIMPLE',None)
cmd=['claude','-p','--model','auto','--setting-sources','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--tools','Read,Agent','--allowedTools','Read,Agent','--agents',json.dumps({'fixture':{'description':'Isolated fixture reader','prompt':'Read only requested fixture files. Do not edit files or delegate.','tools':['Read'],'model':'inherit'}}),'--input-format','stream-json','--output-format','stream-json','--verbose','--include-partial-messages']
err=(root/'stderr.log').open('w');p=subprocess.Popen(cmd,cwd=work,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1,start_new_session=True);events=[];q=queue.Queue();checks=[]
def reader():
 for line in p.stdout:
  try:row=json.loads(line)
  except ValueError:row={'unparsed':line}
  events.append(row);q.put(row)
threading.Thread(target=reader,daemon=True).start()
def send(text):p.stdin.write(json.dumps({'type':'user','message':{'role':'user','content':text}})+'\n');p.stdin.flush()
def wait_result(timeout=180):
 end=time.time()+timeout;rows=[]
 while time.time()<end:
  try:r=q.get(timeout=min(1,max(.01,end-time.time())))
  except queue.Empty:
   if p.poll() is not None:raise RuntimeError('client_exited')
   continue
  rows.append(r)
  if r.get('type')=='result' and not r.get('origin'):return r,rows
 raise TimeoutError('result_wait')
def check(name,passed,**extra):row={'check':name,'passed':bool(passed),**extra};checks.append(row);print(json.dumps(row),flush=True)
try:
 send('Remember NATIVE_MARKER_COBALT_527 and NATIVE_PHASE_READY. Reply with both. Do not use tools.');r,_=wait_result();check('initial_marker','NATIVE_MARKER_COBALT_527' in r.get('result',''))
 for i in range(2):send('Preserve marker and phase. Archive '+str(i)+': '+('Historical UI flow notes; preserve logout behavior. '*120)+' Reply with marker and phase only.');wait_result()
 before=len(records);send('/compact Preserve the remembered marker and phase.');r,rows=wait_result();compacted=any(x.get('type')=='system' and x.get('subtype')=='compact_boundary' for x in rows);check('native_compact_event',compacted,new_requests=len(records)-before)
 send('Return the marker and phase I asked you to remember. Do not use tools.');r,_=wait_result();check('recall_after_compact','NATIVE_MARKER_COBALT_527' in r.get('result','') and 'NATIVE_PHASE_READY' in r.get('result',''))
 send('NATIVE_MULTITOOL: Read a.txt and b.txt using two separate Read calls, preferably concurrently. Report their exact strings.');r,rows=wait_result();tools=[b for x in rows if x.get('type')=='assistant' for b in x.get('message',{}).get('content',[]) if b.get('type')=='tool_use'];check('multiple_native_tools',len(tools)>=2 and 'NATIVE_ALPHA_731' in r.get('result','') and 'NATIVE_BETA_842' in r.get('result',''),tool_count=len(tools))
 send('NATIVE_DELEGATE: Use the fixture agent to read a.txt and report its marker. Do not read the file yourself.');r,rows=wait_result();tools=[b for x in rows if x.get('type')=='assistant' for b in x.get('message',{}).get('content',[]) if b.get('type')=='tool_use'];check('native_subagent',any(b.get('name')=='Agent' for b in tools))
 send('NATIVE_CANCEL_NOW: Write a detailed exhaustive 10000-word generic explanation of UI event loops. Do not use tools.')
 if fixture:delay_started.wait(20)
 else:time.sleep(3)
 p.stdin.write(json.dumps({'type':'control_request','request_id':str(uuid.uuid4()),'request':{'subtype':'interrupt'}})+'\n');p.stdin.flush();r,rows=wait_result(timeout=30);check('native_interrupt',any(x.get('type')=='control_response' for x in rows))
 send('Return the remembered marker only. Do not use tools.');r,_=wait_result();check('resume_after_cancel','NATIVE_MARKER_COBALT_527' in r.get('result',''))
 image_path,image_b64=image_fixture(work)
 send([{'type':'text','text':'Describe the fixture image. Reply with NATIVE_ALPHA_731 and NATIVE_BETA_842; no tools.'},{'type':'image','source':{'type':'base64','media_type':'image/png','data':image_b64}}]);r,_=wait_result()
 check('native_image_forwarded',bool(r.get('result')) and any(image_payloads(r['body']) for r in records))
except Exception as e:check('harness_error',False,error_type=type(e).__name__);(root/'error.txt').write_text(str(e))
finally:
 p.stdin.close()
 try:p.wait(timeout=10)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGTERM);p.wait(timeout=10)
 err.close()
 if gateway:
  gateway.close();media=verify_capture(gateway,records);print('MEDIA='+json.dumps(media),flush=True)
 if fixture:fixture.shutdown();fixture.server_close()
 (root/'requests.json').write_text(json.dumps(records,indent=2));(root/'events.json').write_text(json.dumps(events,indent=2));safe={'scope':'native claude through observation collector to synthetic provider' if gateway else 'native Claude to local deterministic provider fixture; no gateway or real model' if fixture else 'native Claude through gateway and real model','gateway_candidate_tested':bool(gateway),'guard_and_models':'no Guard; synthetic provider' if gateway else 'provider fixture only' if fixture else 'real regional services','region':args.region,'checks':checks,'request_count':len(records),'session_header_sha256':sorted({hashlib.sha256(v.encode()).hexdigest() for r in records for k,v in r['headers'].items() if 'session' in k.lower()})};(root/'result.json').write_text(json.dumps(safe,indent=2));print('RESULT_ROOT='+str(root),flush=True)

if not all(x['passed'] for x in checks) or (gateway and not media['passed']):raise SystemExit('native_workflow_acceptance_failed')
