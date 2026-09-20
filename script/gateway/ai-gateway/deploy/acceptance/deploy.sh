#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root/deployment"
compose() { docker compose --env-file runtime.env -f compose.yaml "$@"; }
# Syntax only: never print a rendered configuration containing private values.
compose config --quiet
python3 - <<'PY'
import json, socket
from pathlib import Path
endpoint=json.loads(Path('endpoint.json').read_text())
for host,port in [(endpoint['bind_address'],endpoint['port']),('127.0.0.1',endpoint.get('guard_port',8013)),('127.0.0.1',endpoint.get('auto_port',8093))]:
    with socket.socket() as probe: probe.bind((host,port))
PY
docker run --rm --pull never \
  -v "$root/source:/src:ro" -v "$root/bin:/out" \
  golang:1.27.1-bookworm sh -ec '
    cd /src
    CGO_ENABLED=0 go build -o /out/preflight-api ./cmd/preflight-api
    CGO_ENABLED=0 go build -o /out/auto-server ./cmd/auto-server
    chmod 555 /out/preflight-api /out/auto-server
  '
compose run --rm --no-deps ingress -t -c /etc/nginx/nginx.conf
# Roll back only this new stack if any activation or readiness check fails.
rollback_on_failure() {
  code=$?
  trap - EXIT
  if [ "$code" -ne 0 ]; then compose stop ingress auto guard || true; fi
  exit "$code"
}
trap rollback_on_failure EXIT
compose up -d guard auto
if ! python3 - <<'PY'
import json, time, urllib.request
from pathlib import Path
endpoint=json.loads(Path('endpoint.json').read_text())
for port,path in [(endpoint.get('guard_port',8013),'readyz'),(endpoint.get('auto_port',8093),'healthz')]:
    for attempt in range(30):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/{path}',timeout=2) as response:
                if response.status == 200: break
        except OSError: pass
        time.sleep(.5)
    else: raise SystemExit('acceptance backend not ready')
print('acceptance_backends_ready')
PY
then
  compose stop auto guard
  exit 1
fi
compose up -d ingress
python3 - <<'PYREADY'
import json, time, urllib.request
from pathlib import Path
endpoint=json.loads(Path('endpoint.json').read_text())
url=f"http://{endpoint['bind_address']}:{endpoint['port']}/healthz"
client=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(30):
    try:
        with client.open(url,timeout=2) as response:
            if response.status == 200: break
    except OSError: pass
    time.sleep(.5)
else: raise SystemExit('acceptance ingress not ready')
print('acceptance_ingress_ready')
PYREADY
compose ps
trap - EXIT
