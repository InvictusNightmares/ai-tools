#!/usr/bin/env python3
"""Real ENOSPC and forwarding acceptance on a NEW 256 MiB lab-only volume."""
import errno
import atexit
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time
import urllib.request
import uuid

import volume

LAB=Path('/data/work-observation-lab')


def wait_status(runtime,predicate):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        try:
            value=json.loads((runtime/'status.json').read_text())
            if predicate(value):return value
        except (OSError,ValueError):pass
        time.sleep(.1)
    raise RuntimeError('status_condition_timeout')


def main():
    os.umask(0o077)
    root=LAB/('volume-smoke-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    root.mkdir(mode=0o700)
    mount=root/'data'
    manifest=volume.create(root/'image',mount,lab=True)
    mounted=volume.attach(manifest)
    def release_owned_mount():
        if volume.inspect(manifest)['mounted']:volume.run('umount',str(mount))
    atexit.register(release_owned_mount)
    binary=LAB/'collector-r1/observe'
    store=mount/'tokyo'
    runtime=root/'runtime';runtime.mkdir(mode=0o700)
    subprocess.run([str(binary),'init','--dir',str(store)],check=True,capture_output=True)
    body=b'{"object":"response","model":"synthetic","output":[]}'
    class Origin(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            self.rfile.read(int(self.headers['Content-Length']))
            self.send_response(200);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    origin=http.server.ThreadingHTTPServer(('127.0.0.1',0),Origin)
    threading.Thread(target=origin.serve_forever,daemon=True).start()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    config={'listen':f'127.0.0.1:{port}','upstream':f'http://127.0.0.1:{origin.server_port}',
        'region':'synthetic','ingress':'volume-fault-fixture','store_dir':str(store),'runtime_dir':str(runtime),
        'identity_salt_file':str(store/'identity.salt'),'capture_enabled':True,'storage_bytes':volume.LAB_CAPACITY}
    (root/'config.json').write_text(json.dumps(config))
    log=(root/'service.log').open('w')
    process=subprocess.Popen([str(binary),'serve','--config',str(root/'config.json')],stdout=log,stderr=log)
    result={'scope':'isolated synthetic real filesystem ENOSPC','capacity_bytes':volume.LAB_CAPACITY,'production_changed':False}
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def request():
        req=urllib.request.Request(f'http://127.0.0.1:{port}/v1/responses',data=b'{"model":"synthetic","input":"volume fixture"}',headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=5) as response:
            assert response.status==200 and response.read()==body
    try:
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.1):break
            except OSError:time.sleep(.05)
        request();before=wait_status(runtime,lambda s:s['written']==1 and s['active_requests']==0)
        filler=mount/'owned-enospc-fixture'
        full=False;written=0
        with filler.open('xb',buffering=0) as stream:
            while written<=volume.LAB_CAPACITY:
                try:written+=stream.write(b'x'*(1<<20))
                except OSError as error:
                    if error.errno!=errno.ENOSPC:raise
                    full=True;break
        assert full,'volume not bounded by its configured size'
        request();failed=wait_status(runtime,lambda s:s['captured']==2 and s['write_errors']>0 and s['active_requests']==0)
        # This is exclusively the filler created above, not user capture data.
        filler.unlink()
        request();recovered=wait_status(runtime,lambda s:s['captured']==3 and s['written']==2 and s['active_requests']==0)
        result.update(real_enospc=True,all_three_business_responses_unchanged=True,
            capture_loss_visible=failed['dropped']>0 and bool(failed['recent_losses']),
            capture_resumed_without_restart=True,filesystem_within_cap=mounted['filesystem_bytes']<=volume.LAB_CAPACITY,
            recorded_requests=recovered['written'],capture_faults=failed['write_errors'])
        result['passed']=all(result[k] for k in ('real_enospc','all_three_business_responses_unchanged','capture_loss_visible','capture_resumed_without_restart','filesystem_within_cap'))
    finally:
        process.terminate()
        try:process.wait(timeout=40)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close();origin.shutdown();origin.server_close()
        if volume.inspect(manifest)['mounted']:volume.run('umount',str(mount))
        result['unmounted_after_test']=not volume.inspect(manifest)['mounted']
        (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result));print('RESULT_ROOT='+str(root),flush=True)


if __name__=='__main__':main()
