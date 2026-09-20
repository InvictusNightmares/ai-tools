from media_fixture import image_fixture, image_payloads, verify_capture
import argparse,concurrent.futures,datetime,hashlib,http.server,json,os,pathlib,signal,socket,subprocess,threading,time,urllib.request
ap=argparse.ArgumentParser();ap.add_argument('--gateway-bin');ap.add_argument('--base');ap.add_argument('--key-file');ap.add_argument('--region',default='fixture');args=ap.parse_args()
os.umask(0o077);root=pathlib.Path('/private/tmp/gateway-opencode-advanced-'+args.region+'-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));root.mkdir()
for f in ['config','data','state','cache','work']:(root/f).mkdir()
(root/'work/a.txt').write_text('NATIVE_ALPHA_731\n');(root/'work/b.txt').write_text('NATIVE_BETA_842\n')
records=[];delay_started=threading.Event();fixture_server=None
class Fixture(http.server.BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"data":[]}')
 def do_POST(self):
  wire=self.rfile.read(int(self.headers['Content-Length']));b=json.loads(wire);records.append({'wire_sha256':hashlib.sha256(wire).hexdigest(),'body':b,'headers':{k:v for k,v in self.headers.items() if k.lower() not in ('authorization','x-api-key')},'at':time.time()});idx=len(records);items=b.get('input',[]);serialized=json.dumps(items);last=next((json.dumps(x) for x in reversed(items) if x.get('role')=='user'),'');rid='resp_native_'+str(idx)
  tool_names=[t.get('name') for t in b.get('tools',[])];outputs=[];tool_done=any(x.get('type')=='function_call_output' for x in items[-8:])
  if 'NATIVE_MULTITOOL' in last and not tool_done and 'read' in tool_names:
   for i,name in enumerate(['a.txt','b.txt']):outputs.append({'id':'fc_'+str(idx)+'_'+str(i),'type':'function_call','call_id':'call_'+str(idx)+'_'+str(i),'name':'read','arguments':json.dumps({'filePath':str(root/'work'/name)}),'status':'completed'})
  else:
   text='NATIVE_ALPHA_731 NATIVE_BETA_842 NATIVE_MARKER_COBALT_527 NATIVE_PHASE_READY'
   outputs=[{'id':'msg_'+rid,'type':'message','role':'assistant','status':'completed','content':[{'type':'output_text','text':text,'annotations':[],'logprobs':[]}]}]
  response={'id':rid,'object':'response','created_at':int(time.time()),'model':'auto','status':'completed','output':outputs,'usage':{'input_tokens':4000,'output_tokens':15,'total_tokens':4015,'input_tokens_details':{'cached_tokens':0}}}
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
if not args.base:
 fixture_server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=fixture_server.serve_forever,daemon=True).start();base='http://127.0.0.1:'+str(fixture_server.server_port)+'/v1';key='synthetic-native-fixture'
else:base=args.base.rstrip('/');key=pathlib.Path(args.key_file).read_text().strip()
gateway=None
if args.gateway_bin:
 assert fixture_server is not None, 'gateway fixture requires synthetic backend'
 import importlib.util
 spec=importlib.util.spec_from_file_location('native_fixture_proxy',str(pathlib.Path(__file__).with_name('collector_adapter.py')));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 gateway=module.GatewayFixture(root,args.gateway_bin,base.removesuffix('/v1'));base=gateway.base+'/v1'
provider='gateway-acceptance';model={'providerID':provider,'modelID':'auto'}
config={'model':provider+'/auto','provider':{provider:{'npm':'@ai-sdk/openai','options':{'baseURL':base,'apiKey':key},'models':{'auto':{'name':'Auto','modalities':{'input':['text','image'],'output':['text']},'limit':{'context':1000000,'output':32000}}}}},'share':'disabled','permission':{'*':'deny','read':'allow','task':'allow'}}
env=dict(os.environ,OPENCODE_DISABLE_MODELS_FETCH='true',OPENCODE_CONFIG_CONTENT=json.dumps(config),XDG_CONFIG_HOME=str(root/'config'),XDG_DATA_HOME=str(root/'data'),XDG_STATE_HOME=str(root/'state'),XDG_CACHE_HOME=str(root/'cache'))
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
log=(root/'server.log').open('w');p=subprocess.Popen(['opencode','serve','--pure','--hostname','127.0.0.1','--port',str(port)],cwd=root/'work',env=env,stdout=log,stderr=log,start_new_session=True)
http=urllib.request.build_opener(urllib.request.ProxyHandler({}));api='http://127.0.0.1:'+str(port);results=[];details={}
def call(path,body=None,timeout=180):
 req=urllib.request.Request(api+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
 with http.open(req,timeout=timeout) as r:raw=r.read();return json.loads(raw) if raw else None
def check(name,passed,**extra):row={'check':name,'passed':bool(passed),**extra};results.append(row);print(json.dumps(row),flush=True)
def message(sid,text):return call('/session/'+sid+'/message',{'model':model,'parts':[{'type':'text','text':text}]})
def answer(result):return ' '.join(part.get('text','') for part in (result or {}).get('parts',[]) if part.get('type')=='text')
try:
 for _ in range(80):
  try:call('/global/health',timeout=2);break
  except Exception:
   if p.poll() is not None:raise RuntimeError('server_exited')
   time.sleep(.2)
 sid=call('/session',{'title':'Native advanced isolated acceptance'})['id'];details['session']=sid
 first=message(sid,'Remember the exact marker NATIVE_MARKER_COBALT_527. The current phase is NATIVE_PHASE_READY. Reply with both strings; do not use tools.');check('initial_marker','NATIVE_MARKER_COBALT_527' in answer(first))
 for n in range(2):message(sid,'Preserve the marker and phase. Context archive '+str(n)+': '+('Historical UI refactor notes; keep logout behavior stable. '*120)+' Reply with the marker and phase only.')
 before=call('/session/'+sid+'/message');compact=call('/session/'+sid+'/summarize',model);after=call('/session/'+sid+'/message');details['compact_result']=compact;details['before_count']=len(before);details['after_count']=len(after)
 has_compaction=any(part.get('type')=='compaction' for row in after for part in row.get('parts',[]));follow=message(sid,'Return the marker and phase that I asked you to remember. Do not use tools.');check('native_compaction_and_recall',has_compaction and 'NATIVE_MARKER_COBALT_527' in answer(follow),compaction_part=has_compaction)
 multi=message(sid,'NATIVE_MULTITOOL: Read a.txt and b.txt using two separate read tool calls, preferably concurrently. Report the exact two strings from the files. Do not run a shell.');history=call('/session/'+sid+'/message');toolparts=[x for row in history for x in row.get('parts',[]) if x.get('type')=='tool' and x.get('tool')=='read' and x.get('state',{}).get('status')=='completed'];check('multiple_native_tools',len(toolparts)>=2 and 'NATIVE_ALPHA_731' in answer(multi) and 'NATIVE_BETA_842' in answer(multi),completed_reads=len(toolparts));details['multi']=multi
 child=call('/session/'+sid+'/message',{'model':model,'parts':[{'type':'subtask','prompt':'Read a.txt and return the exact marker. Do not edit files or run shell commands.','description':'Native child agent isolated file read','agent':'general','model':model}]});children=call('/session/'+sid+'/children');check('native_child_session',len(children)>0);details['children']=children;details['child_result']=child
 fork=call('/session/'+sid+'/fork',{});forkid=fork['id'];fork_result=message(forkid,'Return the original remembered marker and phase. Do not use tools.');check('native_fork_continuity',forkid!=sid and 'NATIVE_MARKER_COBALT_527' in answer(fork_result));details['fork']=fork
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
  future=pool.submit(message,sid,'NATIVE_CANCEL_NOW: Write a detailed, exhaustive 10000-word explanation of a generic UI event loop. Continue until complete; do not use tools.')
  if fixture_server:delay_started.wait(20)
  else:time.sleep(3)
  aborted=call('/session/'+sid+'/abort',{});cancel_answer=future.result(timeout=30);check('native_cancel',aborted is True);details['cancel']=cancel_answer
 resumed=message(sid,'Return the original remembered marker only. Do not use tools.');check('resume_after_cancel','NATIVE_MARKER_COBALT_527' in answer(resumed))
 image_path,image_b64=image_fixture(root/'work')
 media_result=call('/session/'+sid+'/message',{'model':model,'parts':[{'type':'text','text':'Describe the fixture image. Reply with NATIVE_ALPHA_731 and NATIVE_BETA_842; no tools.'},{'type':'file','mime':'image/png','filename':image_path.name,'url':'data:image/png;base64,'+image_b64}]})
 check('native_image_forwarded',bool(answer(media_result)) and any(image_payloads(r['body']) for r in records))
except Exception as e:check('harness_error',False,error_type=type(e).__name__);(root/'error.txt').write_text(str(e))
finally:
 os.killpg(p.pid,signal.SIGTERM)
 try:p.wait(timeout=15)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
 log.close()
 if gateway:
  gateway.close();media=verify_capture(gateway,records);print('MEDIA='+json.dumps(media),flush=True)
 if fixture_server:fixture_server.shutdown();fixture_server.server_close()
 (root/'requests.json').write_text(json.dumps(records,indent=2));(root/'details.json').write_text(json.dumps(details,indent=2));safe={'scope':'native opencode through observation collector to synthetic provider' if gateway else 'native OpenCode to local deterministic provider fixture; no gateway or real model' if fixture_server else 'native OpenCode through regional gateway and real model','gateway_candidate_tested':bool(gateway),'guard_and_models':'no Guard; synthetic provider' if gateway else 'provider fixture only' if fixture_server else 'real regional services','region':args.region,'checks':results,'native_session_sha256':sorted({hashlib.sha256(next((v for k,v in r['headers'].items() if k.lower()=='x-session-id'),'').encode()).hexdigest() for r in records}),'request_count':len(records)};(root/'result.json').write_text(json.dumps(safe,indent=2));print('RESULT_ROOT='+str(root),flush=True)

if not all(x['passed'] for x in results) or (gateway and not media['passed']):raise SystemExit('native_workflow_acceptance_failed')
