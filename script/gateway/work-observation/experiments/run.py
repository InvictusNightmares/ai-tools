#!/usr/bin/env python3
"""Run only on the isolated GPU lab directory; never target production ports."""
import argparse
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import threading
import time

ROOT = Path('/data/work-observation-lab')
PREFIX = 'work-observation-bench-'
RUST = 'rust:bookworm'
GO = 'golang:1.27.1-bookworm'
NAMES = ['origin', 'go-off', 'go-on', 'rust-off', 'rust-on', 'nginx']
PORTS = {'nginx': 18085, 'go-off': 18086, 'go-on': 18087,
         'rust-off': 18088, 'rust-on': 18089}


def command(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def docker(*args):
    return command(['docker', *args])


def start():
    for port in range(18080, 18090):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))
    for name in NAMES:
        existing = docker('ps', '-aq', '--filter', f'name=^/{PREFIX}{name}$')
        if existing:
            raise RuntimeError(f'Existing lab container {name}; inspect/stop it first')
    conf = ['worker_processes 2;', 'error_log /dev/stderr error;',
            'events { worker_connections 4096; }', 'http {', 'access_log off;',
            'map $http_upgrade $conn { default upgrade; "" ""; }']
    for i, name in enumerate(PORTS):
        upstream = 18080 if name == 'nginx' else 18081 + i - 1
        conf += [f'upstream b{i} {{ server 127.0.0.1:{upstream}; keepalive 128; }}',
                 f'server {{ listen 127.0.0.1:{PORTS[name]}; client_max_body_size 200m;',
                 f'location / {{ proxy_pass http://b{i}; proxy_http_version 1.1;',
                 'proxy_buffering off; proxy_request_buffering off; proxy_next_upstream off;',
                 'proxy_set_header Host $http_host; proxy_set_header Upgrade $http_upgrade;',
                 'proxy_set_header Connection $conn; proxy_read_timeout 60s; } }']
    conf.append('}')
    (ROOT / 'nginx.conf').write_text('\n'.join(conf))
    common = ['run', '-d', '--network=host', '--cpus=2', '--memory=2g',
              '--memory-swap=2g', '--pids-limit=96', '--ulimit', 'core=0',
              '-v', f'{ROOT}:/work:ro', '-e', 'GOMAXPROCS=2']
    docker(*common, '--name', PREFIX+'origin', GO, '/work/bench-bin', '-role', 'serve')
    for name, port in [('go-off',18081),('go-on',18082),('rust-off',18083),('rust-on',18084)]:
        is_go = name.startswith('go')
        docker(*common, '--name', PREFIX+name, '-e', f'BENCH_LISTEN=127.0.0.1:{port}',
               '-e', 'BENCH_CAPTURE='+('1' if name.endswith('on') else '0'),
               GO if is_go else RUST,
               '/work/go-proxy-bin' if is_go else '/work/pingora/target/release/observation-proxy-bench')
    docker(*common, '--name', PREFIX+'nginx', '-v', f'{ROOT}/nginx.conf:/etc/nginx/nginx.conf:ro',
           'nginx:alpine')
    time.sleep(2)
    for name in NAMES:
        if docker('inspect','--format','{{.State.Running}}',PREFIX+name) != 'true':
            raise RuntimeError(f'Lab {name} failed: '+docker('logs',PREFIX+name))
    metadata = {}
    for name in NAMES:
        metadata[name] = json.loads(docker('inspect',PREFIX+name))[0]
        # Allowlist runtime identity, not environment or generic container configuration.
        m = metadata[name]
        metadata[name] = {'image_id': m['Image'], 'pid': m['State']['Pid'],
                          'memory_limit':m['HostConfig']['Memory'], 'nano_cpus':m['HostConfig']['NanoCpus']}
    metadata['rust_version'] = docker('exec', PREFIX+'rust-off','rustc','--version')
    metadata['go_version'] = docker('exec',PREFIX+'go-off','go','version')
    (ROOT/'runtime.json').write_text(json.dumps(metadata,indent=2))


def stop():
    for name in reversed(NAMES):
        if docker('ps','-aq','--filter',f'name=^/{PREFIX}{name}$'):
            logs = subprocess.run(['docker','logs',PREFIX+name],capture_output=True,text=True)
            (ROOT/(name+'.log')).write_text(logs.stdout+logs.stderr)
            docker('stop','-t','5',PREFIX+name)
            docker('rm',PREFIX+name)


def process_sample(pids):
    ticks = rss = 0
    for pid in pids:
        try:
            fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            ticks += int(fields[11]) + int(fields[12])
            rss += int(fields[21]) * os.sysconf('SC_PAGE_SIZE')
        except FileNotFoundError:
            pass
    return ticks / os.sysconf('SC_CLK_TCK'), rss


def pids(name):
    root = int(docker('inspect','--format','{{.State.Pid}}',PREFIX+name))
    children = Path(f'/proc/{root}/task/{root}/children').read_text().split()
    return [root]+list(map(int,children))


def run(rounds):
    # 0ms exposes forwarding cost. 20ms approximates a fast remote first-byte path.
    scenarios = [('json',1024,0,1000,16,0),('json',1024,20,400,16,0),
                 ('json',1<<20,0,256,16,0),('json',8<<20,0,64,4,0),
                 ('sse',1<<20,20,128,16,0),('ws',4096,0,256,16,0),
                 ('json',1<<20,20,200,16,50),('sse',1<<20,20,200,16,50)]
    out = ROOT/'results.jsonl'
    if out.exists():
        raise RuntimeError('Preserve existing results; rename explicitly before another experiment')
    with out.open('w') as f:
        for repetition in range(rounds):
            for mode,size,delay,n,c,rate in scenarios:
                names = list(PORTS)
                random.Random(917+repetition*31+size+delay).shuffle(names)
                for name in names:
                    ids = pids('nginx')
                    if name != 'nginx': ids += pids(name)
                    before,_ = process_sample(ids)
                    done = threading.Event()
                    peak = [0]
                    def monitor():
                        while not done.wait(.025):
                            peak[0] = max(peak[0],process_sample(ids)[1])
                    thread = threading.Thread(target=monitor);thread.start()
                    try:
                        result = json.loads(command([str(ROOT/'bench-bin'),'-addr',f'127.0.0.1:{PORTS[name]}',
                            '-mode',mode,'-size',str(size),'-delay',str(delay),'-n',str(n),'-c',str(c),'-rate',str(rate)],
                            env={**os.environ,'GOMAXPROCS':'2'},timeout=120))
                    finally:
                        done.set();thread.join()
                    after,_ = process_sample(ids)
                    result.update(candidate=name,round=repetition,cpu_s_including_warmup=after-before,
                                  peak_rss_bytes=peak[0])
                    f.write(json.dumps(result)+'\n');f.flush()
                    print(json.dumps({k:v for k,v in result.items() if k not in ('first_ms','total_ms')}),flush=True)
                    if result.get('ok') != n:
                        raise RuntimeError(f'Correctness failure: {name} {mode}')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','run','stop']);parser.add_argument('--rounds',type=int,default=3)
    args=parser.parse_args()
    if not ROOT.is_dir(): raise SystemExit('Run on the GPU isolated lab only')
    {'start':start,'run':lambda:run(args.rounds),'stop':stop}[args.action]()
