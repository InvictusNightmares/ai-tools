#!/usr/bin/env python3
"""Synthetic CLI lifecycle acceptance; loopback only, no real upstream calls."""
import argparse
import base64
from collections import Counter
import hashlib
import http.server
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request


def wait(predicate,seconds=8):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if predicate():return
        time.sleep(.03)
    raise AssertionError('bounded wait expired')


class Origin(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def do_GET(self):
        self.reply(b'{"ready":true}')
    def reply(self,body,content_type='application/json'):
        self.send_response(200);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)));self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_POST(self):
        data=self.rfile.read(int(self.headers.get('Content-Length',0)))
        if self.path=='/slow':
            time.sleep(2)
        if self.path.endswith('/stream'):
            self.reply(b'id: stream-1\nevent: response.output_text.delta\ndata: {"type":"response.output_text.delta","delta":"literal reply"}\n\ndata: {"type":"response.completed","response":{"usage":{"input_tokens":8,"output_tokens":3},"output":[{"role":"assistant","content":"literal reply"}]}}\n\ndata: [DONE]\n\n','text/event-stream')
        else:
            self.reply(json.dumps({'echo_sha256':hashlib.sha256(data).hexdigest(),'output':[{'role':'assistant','content':'literal reply'}]}).encode())


def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--work-dir',required=True);args=p.parse_args()
    binary=str(Path(args.binary).resolve());root=Path(args.work_dir).resolve();root.mkdir(mode=0o700,parents=True,exist_ok=True)
    # One unique run avoids destroying prior failure evidence or private state.
    run=Path(tempfile.mkdtemp(prefix='smoke-',dir=root));store=run/'store'
    origin=http.server.ThreadingHTTPServer(('127.0.0.1',0),Origin);origin.daemon_threads=True
    thread=threading.Thread(target=origin.serve_forever,daemon=True);thread.start()
    probe=socket.socket();probe.bind(('127.0.0.1',0));port=probe.getsockname()[1];probe.close()
    config={'listen':f'127.0.0.1:{port}','upstream':f'http://127.0.0.1:{origin.server_port}',
            'region':'synthetic','ingress':'isolated','store_dir':str(store),
            'identity_salt_file':str(store/'identity.salt'),'capture_enabled':False,
            'queue_items':64,'memory_bytes':8<<20,'body_bytes':2<<20,'storage_bytes':64<<20}
    cfg=run/'config.json';cfg.write_text(json.dumps(config));os.chmod(cfg,0o600)
    subprocess.run([binary,'init','--dir',str(store)],check=True,capture_output=True)
    log=(run/'process.log').open('ab');process=None
    def launch():return subprocess.Popen([binary,'serve','--config',str(cfg)],stdout=log,stderr=log)
    def status():
        try:return json.loads((store/'status.json').read_text())
        except (OSError,ValueError):return {}
    def ready():
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.2):return process.poll() is None
        except OSError:return False
    def request(path,body,client):
        raw=json.dumps(body).encode();r=urllib.request.Request(f'http://127.0.0.1:{port}'+path,data=raw,
            headers={'Content-Type':'application/json','User-Agent':client+'/synthetic','Authorization':'Bearer synthetic-transport-secret','X-Observation-Ingress':'spoofed'})
        with urllib.request.urlopen(r,timeout=6) as response:return response.read(),raw
    try:
        process=launch();wait(ready);assert not status().get('capture_enabled')
        request('/v1/responses',{'input':'disabled fixture'},'codex')
        assert not list((store/'events').rglob('*.json'))
        subprocess.run([binary,'enable','--dir',str(store)],check=True,capture_output=True);wait(lambda:status().get('capture_enabled') is True)
        for client,path,body in (
            ('codex','/v1/responses',{'input':'password=fixture literal user request'}),
            ('opencode','/v1/chat/completions',{'messages':[{'role':'tool','tool_call_id':'c1','content':'literal tool output'}]}),
            ('hermes','/v1/chat/completions',{'messages':[{'role':'user','content':'continue'}]}),
            ('claude','/v1/messages',{'system':'literal instructions','messages':[{'role':'user','content':[{'type':'tool_result','tool_use_id':'t1','content':'quoted document'}]}]}),
        ):
            reply,raw=request(path,body,client);assert json.loads(reply)['echo_sha256']==hashlib.sha256(raw).hexdigest()
        stream,_=request('/v1/responses/stream',{'input':'stream fixture'},'codex');assert b'literal reply' in stream
        wait(lambda:status().get('written',0)>=5)
        pending=threading.Thread(target=lambda:slow_request(request),daemon=True);pending.start()
        wait(lambda:bool(list((store/'active').glob('*.json'))));process.kill();process.wait(timeout=5)
        process=launch();wait(ready);wait(lambda:status().get('recovered_interrupted_requests')==1)
        assert status().get('capture_enabled') is True
        subprocess.run([binary,'disable','--dir',str(store)],check=True,capture_output=True);wait(lambda:status().get('capture_enabled') is False)
        process.send_signal(signal.SIGTERM);assert process.wait(timeout=8)==0;process=None
        previous_start=status()['started_at']
        process=launch();wait(ready);wait(lambda:status().get('started_at')!=previous_start)
        assert status().get('capture_enabled') is False
        request('/v1/responses',{'input':'disabled after restart fixture'},'codex')
        process.send_signal(signal.SIGTERM);assert process.wait(timeout=8)==0;process=None
        exported=subprocess.check_output([binary,'export','--dir',str(store)],timeout=10)
        events=[json.loads(line) for line in exported.splitlines()]
        assert len(events)==6, len(events)
        assert all(x['region']=='synthetic' and x['ingress']=='isolated' for x in events)
        assert all(x['content_policy']=='literal_text_attachment_metadata' for x in events)
        assert b'synthetic-transport-secret' not in exported
        assert b'password=fixture literal user request' in exported
        assert any(x['outcome']=='process_interrupted' for x in events)
        assert all((p.stat().st_mode&0o777)==0o600 for p in (store/'events').rglob('*.json'))
        tools=Path(__file__).parent
        evidence=run/'evidence.jsonl'
        subprocess.run(['python3',str(tools/'evidence.py'),'--output',str(evidence)],input=exported,check=True,capture_output=True)
        analysis=run/'analysis.sqlite'
        subprocess.run(['python3',str(tools/'analyze.py'),'--db',str(analysis),'ingest'],input=exported,check=True,capture_output=True)
        report=json.loads(subprocess.check_output(['python3',str(tools/'analyze.py'),'--db',str(analysis),'report','--hours','1']))
        assert report['events']==6 and report['cost_unknown_events']==6
        assert report['input_tokens_known']==8 and report['output_tokens_known']==3
        assert report['evidence_quality']=={'unknown':6}
        summary={'scope':'synthetic_isolated_cli_lifecycle','events':len(events),'outcomes':dict(Counter(x['outcome'] for x in events)),
                 'clients':dict(Counter(x['client'] for x in events)),'body_integrity':True,'auth_headers_excluded':True,
                 'default_disabled':True,'enable_disable':True,'restart_gap_visible':True,'plaintext_private_files':True,
                 'restart_switch_persisted_before_traffic':True,
                 'export_to_evidence_and_analysis':True,'native_clients':False,'production_changed':False}
        (run/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
    finally:
        if process is not None and process.poll() is None:process.terminate();process.wait(timeout=8)
        origin.shutdown();origin.server_close();log.close()


def slow_request(request):
    try:request('/slow',{'input':'restart fixture'},'codex')
    except Exception:pass


if __name__=='__main__':main()
