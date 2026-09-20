from media_fixture import image_fixture, image_payloads, verify_capture
import argparse,datetime,json,os,pathlib,queue,signal,subprocess,sys,threading,time,hashlib,http.server
ap=argparse.ArgumentParser();ap.add_argument('--base');ap.add_argument('--key-file');ap.add_argument('--region',default='fixture');ap.add_argument('--gateway-bin');args=ap.parse_args();region=args.region
os.umask(0o077);root=pathlib.Path('/private/tmp/gateway-codex-tools-'+region+'-'+datetime.datetime.now().strftime('%H%M%S'));root.mkdir(mode=0o700)
(root/'a.txt').write_text('NATIVE_ALPHA_731');(root/'b.txt').write_text('NATIVE_BETA_842')
records=[];delay_started=threading.Event();fixture_server=None;gateway=None
class Fixture(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"data":[]}')
 def do_POST(self):
  wire=self.rfile.read(int(self.headers['Content-Length']));b=json.loads(wire);records.append({'wire_sha256':hashlib.sha256(wire).hexdigest(),'body':b,'headers':{k:v for k,v in self.headers.items() if k.lower() not in ('authorization','x-api-key')},'at':time.time()});idx=len(records);items=b.get('input',[]);serialized=json.dumps(items);last=next((json.dumps(x) for x in reversed(items) if x.get('role')=='user'),'');rid='resp_native_'+str(idx)
  tool_names=[t.get('name') for t in b.get('tools',[])];outputs=[];last_user=max((i for i,x in enumerate(items) if x.get('role')=='user'),default=-1);tool_done=any(x.get('type')=='function_call_output' for x in items[last_user+1:])
  if 'NATIVE_MULTITOOL' in last and not tool_done and 'exec_command' in tool_names:
   for i,name in enumerate(['a.txt','b.txt']):outputs.append({'id':'fc_'+str(idx)+'_'+str(i),'type':'function_call','call_id':'call_'+str(idx)+'_'+str(i),'name':'exec_command','arguments':json.dumps({'cmd':'cat '+str(root/name),'max_output_tokens':1000}),'status':'completed'})
  elif 'NATIVE_SPAWN_PARENT' in last and not tool_done:
   outputs=[{'id':'fc_spawn_'+str(idx),'type':'function_call','call_id':'call_spawn_'+str(idx),'name':'spawn_agent','namespace':'multi_agent_v1','arguments':json.dumps({'message':'NATIVE_CHILD_ONLY: Reply NATIVE_ALPHA_731, without tools. This is a native subagent compatibility fixture.'}),'status':'completed'}]
  else:
   text='NATIVE_ALPHA_731 NATIVE_BETA_842 NATIVE_MARKER_COBALT_527 NATIVE_PHASE_READY'
   outputs=[{'id':'msg_'+rid,'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':text,'annotations':[],'logprobs':[]}]}]
  response={'id':rid,'object':'response','created_at':int(time.time()),'model':b.get('model','auto'),'status':'completed','output':outputs,'usage':{'input_tokens':4000,'output_tokens':15,'total_tokens':4015,'input_tokens_details':{'cached_tokens':0}}}
  stream=b.get('stream',False);self.send_response(200);self.send_header('Content-Type','text/event-stream' if stream else 'application/json');self.end_headers()
  def event(typ,data):self.wfile.write(('event: '+typ+'\ndata: '+json.dumps({'type':typ,**data})+'\n\n').encode());self.wfile.flush()
  try:
   if not stream:self.wfile.write(json.dumps(response).encode());return
   event('response.created',{'response':dict(response,status='in_progress',output=[])})
   if 'NATIVE_CANCEL_NOW' in last:
    delay_started.set()
    for _ in range(120):self.wfile.write(b': native fixture waiting\n\n');self.wfile.flush();time.sleep(.2)
   for i,item in enumerate(outputs):
    event('response.output_item.added',{'output_index':i,'item':dict(item,status='in_progress',**({'content':[]} if item['type']=='message' else {'arguments':''}))})
    if item['type']=='function_call':
     event('response.function_call_arguments.delta',{'output_index':i,'item_id':item['id'],'delta':item['arguments']});event('response.function_call_arguments.done',{'output_index':i,'item_id':item['id'],'arguments':item['arguments']})
    else:
     part=item['content'][0];event('response.content_part.added',{'output_index':i,'item_id':item['id'],'content_index':0,'part':dict(part,text='')});event('response.output_text.delta',{'output_index':i,'item_id':item['id'],'content_index':0,'delta':part['text'],'logprobs':[]});event('response.output_text.done',{'output_index':i,'item_id':item['id'],'content_index':0,'text':part['text']});event('response.content_part.done',{'output_index':i,'item_id':item['id'],'content_index':0,'part':part})
    event('response.output_item.done',{'output_index':i,'item':item})
   event('response.completed',{'response':response})
  except (BrokenPipeError,ConnectionResetError):records[-1]['client_disconnected']=True
if args.base:
 base=args.base.rstrip('/');key=pathlib.Path(args.key_file).read_text().strip()
else:
 fixture_server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=fixture_server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(fixture_server.server_port)+'/v1';key='synthetic-native-fixture'
if args.gateway_bin:
 assert fixture_server is not None
 import importlib.util
 spec=importlib.util.spec_from_file_location('native_fixture_proxy',str(pathlib.Path(__file__).with_name('collector_adapter.py')));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);gateway=module.GatewayFixture(root,args.gateway_bin,base.removesuffix('/v1'));base=gateway.base+'/v1'
profile=root/'profile';profile.mkdir(mode=0o700)
env=dict(os.environ,AI_GATEWAY_TEST_API_KEY=key,CODEX_HOME=str(profile))
cmd=['codex']
opts={'model':'auto','model_provider':'gateway_replay','model_providers.gateway_replay.name':'Gateway native fixture','model_providers.gateway_replay.base_url':base,'model_providers.gateway_replay.env_key':'AI_GATEWAY_TEST_API_KEY','model_providers.gateway_replay.wire_api':'responses','model_providers.gateway_replay.supports_websockets':False,'model_providers.gateway_replay.request_max_retries':0,'model_providers.gateway_replay.stream_max_retries':0,'web_search':'disabled','features.multi_agent':True}
for k,v in opts.items():cmd+=['-c',k+'='+json.dumps(v)]
cmd+=['app-server','--stdio']
err=(root/'stderr.log').open('w');p=subprocess.Popen(cmd,cwd=root,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1,start_new_session=True)
messages=queue.Queue();events=[];seq=0;pending={};window=0
def reader():
 for line in p.stdout:
  try:messages.put(json.loads(line))
  except Exception:pass
threading.Thread(target=reader,daemon=True).start()
def send(method,params):
 global seq,window
 if method in ("turn/start","thread/compact/start"):window=len(events)
 seq+=1;p.stdin.write(json.dumps({'id':seq,'method':method,'params':params})+'\n');p.stdin.flush();return seq
def next_event(timeout):
 row=messages.get(timeout=timeout);events.append(row)
 if 'id' in row and ('result' in row or 'error' in row):pending[row['id']]=row
 if 'id' in row and 'method' in row:
  # This fixture never authorizes tool execution or external communication.
  p.stdin.write(json.dumps({'id':row['id'],'error':{'code':-32601,'message':'Fixture does not execute requested client tools'}})+'\n');p.stdin.flush()
 return row
def response(identifier,timeout=90):
 deadline=time.monotonic()+timeout
 while identifier not in pending:next_event(max(.1,deadline-time.monotonic()))
 row=pending.pop(identifier)
 if 'error' in row:raise RuntimeError('rpc_'+str(row['error'].get('code')))
 return row['result']
def wait_turn(thread_id,timeout=180):
 deadline=time.monotonic()+timeout;seen=list(events[window:])
 for row in seen:
  if row.get("method")=="turn/completed" and row.get("params",{}).get("threadId")==thread_id:return row["params"]["turn"],seen
 while time.monotonic()<deadline:
  row=next_event(max(.1,deadline-time.monotonic()));seen.append(row)
  if row.get('method')=='turn/completed' and row.get('params',{}).get('threadId')==thread_id:return row['params']['turn'],seen
 raise TimeoutError('turn')
def turn(thread_id,text):
 response(send('turn/start',{'threadId':thread_id,'input':[{'type':'text','text':text,'text_elements':[]}]}))
 return wait_turn(thread_id)
result={'region':region,'client':'Codex 0.154.0 app-server','scope':'native Codex through observation collector to synthetic provider' if gateway else 'native Codex direct provider fixture' if fixture_server else 'native Codex real regional gateway','checks':{}}
def answer(rows):return '\n'.join(r.get('params',{}).get('item',{}).get('text','') for r in rows if r.get('method')=='item/completed')
try:
 response(send('initialize',{'clientInfo':{'name':'gateway_native_acceptance','version':'1.0'},'capabilities':{'experimentalApi':True,'requestAttestation':False}}));p.stdin.write(json.dumps({'method':'initialized','params':{}})+'\n');p.stdin.flush()
 thread=response(send('thread/start',{'model':'auto','modelProvider':'gateway_replay','cwd':str(root),'ephemeral':False,'sandbox':'read-only','approvalPolicy':'never'}))['thread']['id']
 t,rows=turn(thread,'Remember NATIVE_MARKER_COBALT_527. Reply with it and do not use tools.');result['checks']['initial_marker']=t['status']=='completed' and 'NATIVE_MARKER_COBALT_527' in answer(rows);print('initial',result['checks']['initial_marker'],flush=True)
 response(send('thread/compact/start',{'threadId':thread}));compacted,rows=wait_turn(thread)
 result['checks']['native_compaction']=compacted['status']=='completed'
 t,rows=turn(thread,'Return the originally remembered marker after compaction. No tools.')
 result['checks']['recall_after_compaction']=t['status']=='completed' and 'NATIVE_MARKER_COBALT_527' in answer(rows)
 print('compact',result['checks']['native_compaction'],result['checks']['recall_after_compaction'],flush=True)
 t,rows=turn(thread,'NATIVE_MULTITOOL: Read a.txt and b.txt using two distinct read-only exec_command calls, preferably concurrently. Reply with their exact contents. Do not edit anything or use network.')
 count=sum(r.get('method')=='item/completed' and r.get('params',{}).get('item',{}).get('type')=='commandExecution' for r in rows);result['checks']['multiple_native_tools']=t['status']=='completed' and count>=2 and all(x in answer(rows) for x in ['NATIVE_ALPHA_731','NATIVE_BETA_842']);print('tools',result['checks']['multiple_native_tools'],count,flush=True)
 t,rows=turn(thread,'NATIVE_SPAWN_PARENT: Explicitly spawn one native child agent to report NATIVE_ALPHA_731. While it runs, read b.txt yourself, then report the result. Do not edit files, start other agents, or use network.')
 collab=[r.get('params',{}).get('item',{}) for r in rows if r.get('method')=='item/completed' and 'collab' in r.get('params',{}).get('item',{}).get('type','').lower()];result['checks']['native_subagent']=t['status']=='completed' and bool(collab);result['collaboration_item_types']=[x.get('type') for x in collab];print('subagent',result['checks']['native_subagent'],flush=True)
 fork=response(send('thread/fork',{'threadId':thread,'cwd':str(root),'ephemeral':False}))['thread']['id'];t,rows=turn(fork,'Return the originally remembered marker. No tools.');result['checks']['native_fork']=fork!=thread and t['status']=='completed' and 'NATIVE_MARKER_COBALT_527' in answer(rows);print('fork',result['checks']['native_fork'],flush=True)
 started=response(send('turn/start',{'threadId':thread,'input':[{'type':'text','text':'NATIVE_CANCEL_NOW: Write a detailed 10000-word explanation of event loops. No tools.','text_elements':[]}]}))
 if fixture_server:delay_started.wait(20)
 else:time.sleep(2)
 response(send('turn/interrupt',{'threadId':thread,'turnId':started['turn']['id']}));canceled,rows=wait_turn(thread,90);result['checks']['native_cancel']=canceled['status']=='interrupted'
 t,rows=turn(thread,'Return the remembered marker, no tools.');result['checks']['resume_after_cancel']=t['status']=='completed' and 'NATIVE_MARKER_COBALT_527' in answer(rows)
 image_path,image_b64=image_fixture(root)
 response(send('turn/start',{'threadId':thread,'input':[{'type':'text','text':'Describe the attached fixture image. Reply with NATIVE_ALPHA_731 and NATIVE_BETA_842; no tools.','text_elements':[]},{'type':'localImage','path':str(image_path)}]}))
 t,rows=wait_turn(thread);result['checks']['native_image_forwarded']=t['status']=='completed' and any(image_payloads(r['body']) for r in records)
 result['passed']=all(result['checks'].values())
except Exception as error:result.update(passed=False,error_type=type(error).__name__);(root/'error.txt').write_text(str(error))
finally:
 if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
 try:p.wait(timeout=15)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 err.close()
 if gateway:
  gateway.close();media=verify_capture(gateway,records);print('MEDIA='+json.dumps(media),flush=True)
 if fixture_server:fixture_server.shutdown();fixture_server.server_close()
 (root/'events.json').write_text(json.dumps(events).replace(key,'<REDACTED>'));(root/'requests.json').write_text(json.dumps(records));(root/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True);print('RESULT_ROOT='+str(root),flush=True)

if not result.get('passed') or (gateway and not media['passed']):raise SystemExit('native_workflow_acceptance_failed')
