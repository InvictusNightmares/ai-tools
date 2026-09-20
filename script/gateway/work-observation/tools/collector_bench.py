#!/usr/bin/env python3
"""Full collector benchmark on synthetic loopback traffic. No production routes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import threading
import time

LAB=Path('/data/work-observation-lab')
ROOT=LAB/'collector-r1'
PREFIX='work-observation-full-'
NAMES=('origin','off','on','nginx')
PORTS={'nginx':18485,'off':18486,'on':18487}

def cmd(args,**kwargs):return subprocess.check_output(args,text=True,**kwargs).strip()
def docker(*args):return cmd(['docker',*args])
def pids(name):
    root=int(docker('inspect','--format','{{.State.Pid}}',PREFIX+name))
    return [root]+[int(x) for x in Path(f'/proc/{root}/task/{root}/children').read_text().split()]
def sample(ids):
    ticks=rss=0
    for pid in ids:
        try:
            f=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            ticks+=int(f[11])+int(f[12]);rss+=int(f[21])*os.sysconf('SC_PAGE_SIZE')
        except FileNotFoundError:pass
    return ticks/os.sysconf('SC_CLK_TCK'),rss

def main():
    p=argparse.ArgumentParser();p.add_argument('--rounds',type=int,default=3)
    p.add_argument('--extended',action='store_true',help='include 8 MiB HTTP/SSE and 64 KiB WebSocket payloads')
    p.add_argument('--capture-memory-mib',type=int,default=512)
    p.add_argument('--only',choices=('all','ws'),default='all',help='targeted WebSocket regression; not a full acceptance run')
    args=p.parse_args()
    if not 1<=args.rounds<=3:raise SystemExit('bounded rounds 1..3')
    if args.capture_memory_mib not in (128,256,512):raise SystemExit('bounded capture memory: 128, 256 or 512 MiB')
    out=LAB/('full-capture-'+time.strftime('%Y%m%d-%H%M%S'));out.mkdir(mode=0o700)
    for port in (18080,18481,18482,*PORTS.values()):
        with socket.socket() as sock:sock.bind(('127.0.0.1',port))
    for name in NAMES:
        if docker('ps','-aq','--filter','name=^/'+PREFIX+name+'$'):raise RuntimeError('existing isolated container; inspect first')
    mount='/capture-run'
    for name,port in (('off',18481),('on',18482)):
        private=out/name
        subprocess.run([str(ROOT/'observe'),'init','--dir',str(private)],check=True,capture_output=True)
        config={'listen':f'127.0.0.1:{port}','upstream':'http://127.0.0.1:18080','region':'synthetic',
                'ingress':'full-benchmark-'+name,'store_dir':mount+'/'+name,
                'identity_salt_file':mount+'/'+name+'/identity.salt','capture_enabled':name=='on',
                'queue_items':4096,'memory_bytes':args.capture_memory_mib<<20,'body_bytes':32<<20,'storage_bytes':8<<30}
        (out/(name+'.json')).write_text(json.dumps(config))
    conf=['worker_processes 2;','error_log /dev/stderr error;','events { worker_connections 4096; }','http { access_log off;','map $http_upgrade $conn { default upgrade; "" ""; }']
    for i,(name,port) in enumerate(PORTS.items()):
        upstream={'nginx':18080,'off':18481,'on':18482}[name]
        conf += [f'upstream b{i} {{ server 127.0.0.1:{upstream}; keepalive 128; }}',
                 f'server {{ listen 127.0.0.1:{port}; client_max_body_size 200m; location / {{',
                 f'proxy_pass http://b{i}; proxy_http_version 1.1; proxy_request_buffering off; proxy_buffering off;',
                 'proxy_next_upstream off; proxy_set_header Host $http_host;',
                 'proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection $conn; proxy_read_timeout 60s; } }']
    conf.append('}');(out/'nginx.conf').write_text('\n'.join(conf))
    common=['run','-d','--network=host','--cpus=2','--memory=2g','--memory-swap=2g','--pids-limit=96','--ulimit','core=0','-e','GOMAXPROCS=2','-v',str(LAB)+':/lab:ro','-v',str(out)+':'+mount]
    started=[]
    try:
        docker(*common,'--name',PREFIX+'origin','golang:1.27.1-bookworm','/lab/bench-bin','-role','serve');started.append('origin')
        for name in ('off','on'):
            docker(*common,'--name',PREFIX+name,'golang:1.27.1-bookworm','/lab/collector-r1/observe','serve','--config',mount+'/'+name+'.json');started.append(name)
        docker(*common,'--name',PREFIX+'nginx','-v',str(out/'nginx.conf')+':/etc/nginx/nginx.conf:ro','nginx:alpine');started.append('nginx')
        time.sleep(2)
        for name in NAMES:
            if docker('inspect','--format','{{.State.Running}}',PREFIX+name)!='true':raise RuntimeError('isolated process not running')
        runtime={}
        for name in NAMES:
            value=json.loads(docker('inspect',PREFIX+name))[0]
            runtime[name]={'image':value['Image'],'cpu_limit':value['HostConfig']['NanoCpus'],'memory_limit':value['HostConfig']['Memory']}
        (out/'runtime.json').write_text(json.dumps(runtime,indent=2))
        scenarios=[('json',1024,0,300,8,200),('json',1<<20,20,200,16,50),('sse',1<<20,20,200,16,50),('ws',4096,0,80,4,10)]
        if args.extended:
            scenarios += [('json',8<<20,20,60,8,10),('sse',8<<20,20,60,8,10),('ws',64<<10,0,80,4,10)]
        if args.only=='ws':scenarios=[s for s in scenarios if s[0]=='ws']
        (out/'scope.json').write_text(json.dumps({'version':cmd([str(ROOT/'observe'),'version']),
            'only':args.only,'extended':args.extended,'rounds':args.rounds,
            'capture_memory_mib':args.capture_memory_mib,'scenarios':scenarios},indent=2))
        expected_captured=0
        with (out/'results.jsonl').open('x') as f:
            for rep in range(args.rounds):
                for mode,size,delay,n,concurrency,rate in scenarios:
                    names=list(PORTS);random.Random(20260917+rep*31+size).shuffle(names)
                    for name in names:
                        ids=pids('nginx')+(pids(name) if name!='nginx' else [])
                        before,_=sample(ids);stop=threading.Event();peak=[0]
                        def monitor():
                            while not stop.wait(.025):peak[0]=max(peak[0],sample(ids)[1])
                        monitor_thread=threading.Thread(target=monitor);monitor_thread.start()
                        try:
                            row=json.loads(cmd([str(LAB/'bench-bin'),'-addr',f'127.0.0.1:{PORTS[name]}','-mode',mode,'-size',str(size),'-delay',str(delay),'-n',str(n),'-c',str(concurrency),'-rate',str(rate)],env={**os.environ,'GOMAXPROCS':'2'},timeout=60))
                        finally:stop.set();monitor_thread.join()
                        after,_=sample(ids)
                        row.update(round=rep,candidate=name,cpu_s_including_warmup=after-before,peak_rss_bytes=peak[0])
                        if name=='on':
                            expected_captured+=n+32
                            until=time.monotonic()+30
                            while time.monotonic()<until:
                                status=json.loads((out/'on/status.json').read_text())
                                if status['captured']>=expected_captured and status['queued_bytes']==0 and status['queue_items']==0 and status['active_requests']==0:break
                                time.sleep(.1)
                            else:raise RuntimeError('collector backlog failed to drain')
                            row['expected_captured']=expected_captured
                            row['capture_status']={k:status.get(k) for k in ('captured','written','dropped','truncated','write_errors','projection_errors','queued_bytes','stored_bytes')}
                        f.write(json.dumps(row)+'\n');f.flush()
                        print(json.dumps({k:row.get(k) for k in ('candidate','round','mode','ok','count','first_p95_ms','total_p95_ms','capture_status')}),flush=True)
                        if row['ok']!=n:raise RuntimeError('forwarding correctness failure')
        print(json.dumps({'completed':True,'output':str(out)}),flush=True)
    finally:
        for name in reversed(started):
            result=subprocess.run(['docker','logs',PREFIX+name],capture_output=True,text=True)
            (out/(name+'.log')).write_text(result.stdout+result.stderr)
            docker('stop','-t','5',PREFIX+name);docker('rm',PREFIX+name)

if __name__=='__main__':main()
