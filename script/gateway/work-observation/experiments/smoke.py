#!/usr/bin/env python3
"""Loopback protocol smoke test for one built comparison proxy."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import time

ROOT=Path('/data/work-observation-lab')


def docker(*args):
    return subprocess.check_output(['docker',*args],text=True).strip()


def smoke(candidate):
    names=[]
    for port in (18180,18181):
        with socket.socket() as s:s.bind(('127.0.0.1',port))
    for name in ('origin',candidate):
        if docker('ps','-aq','--filter',f'name=^/work-observation-smoke-{name}$'):
            raise RuntimeError('Inspect existing smoke container before starting another')
    try:
        common=['run','-d','--network=host','--cpus=1','--memory=1g','--memory-swap=1g',
                '--pids-limit=96','-e','GOMAXPROCS=2','-v',f'{ROOT}:/work:ro']
        name='work-observation-smoke-origin'
        docker(*common,'--name',name,'golang:1.27.1-bookworm','/work/bench-bin','-role','serve','-addr','127.0.0.1:18180')
        names.append(name)
        name='work-observation-smoke-'+candidate
        docker(*common,'--name',name,'-e','BENCH_LISTEN=127.0.0.1:18181',
               '-e','BENCH_UPSTREAM=127.0.0.1:18180','-e','BENCH_CAPTURE=1',
               'golang:1.27.1-bookworm' if candidate=='go' else 'rust:bookworm',
               '/work/go-proxy-bin' if candidate=='go' else '/work/pingora/target/release/observation-proxy-bench')
        names.append(name);time.sleep(1)
        results=[]
        for mode in ('json','sse','ws'):
            r=json.loads(subprocess.check_output([str(ROOT/'bench-bin'),'-addr','127.0.0.1:18181',
                '-mode',mode,'-n','16','-c','2','-size','4096'],text=True,env={**os.environ,'GOMAXPROCS':'2'},timeout=60))
            r={k:v for k,v in r.items() if k not in ('first_ms','total_ms')}
            r['candidate']=candidate;results.append(r)
            print(json.dumps(r),flush=True)
            if r.get('ok')!=16:raise RuntimeError('protocol validation failed')
        (ROOT/f'smoke-{candidate}.json').write_text(json.dumps(results,indent=2))
    finally:
        for name in reversed(names):
            logs=subprocess.run(['docker','logs',name],capture_output=True,text=True)
            (ROOT/(name+'.log')).write_text(logs.stdout+logs.stderr)
            docker('stop','-t','3',name);docker('rm',name)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('candidate',choices=['go','rust']);args=p.parse_args()
    smoke(args.candidate)
