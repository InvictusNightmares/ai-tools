#!/usr/bin/env bash
# First installation only. Existing deployments are updated through the runbook.
set -euo pipefail
umask 077
[[ ${EUID} -eq 0 ]] || { echo 'Run as root on CTYun.' >&2; exit 1; }
src=$(cd -- "$(dirname -- "$0")" && pwd -P)
dest=/srv/agentbox/hermes
[[ "$src" != "$dest" ]] || { echo 'Run from the reviewed source directory.' >&2; exit 1; }
[[ ! -e "$dest/compose.yaml" ]] || { echo 'Hermes is already installed; follow the upgrade runbook.' >&2; exit 1; }
for path in /srv/agentbox "$dest" "$dest/data" "$dest/workspace"; do
  [[ ! -L "$path" ]] || { echo "Refusing symlink: $path" >&2; exit 1; }
done
for network in agentbox-egress agentbox-browser; do
  docker network inspect "$network" >/dev/null
done
image=$(sed -n 's/^    image: //p' "$src/compose.yaml")
docker image inspect "$image" >/dev/null
[[ -s "$dest/data/.env" ]] || { echo 'Place the dedicated CPA_API_KEY in data/.env first (0600).' >&2; exit 1; }
install -d -m 0700 "$dest" "$dest/backups" "$dest/verification"
install -d -m 0700 -o 10000 -g 10000 "$dest/data" "$dest/workspace"
install -m 0600 "$src/compose.yaml" "$dest/compose.yaml"
install -m 0600 -o 10000 -g 10000 "$src/config.yaml" "$dest/data/config.yaml"
install -m 0644 -o 10000 -g 10000 "$src/workspace-instructions.md" "$dest/workspace/AGENTS.md"
install -m 0755 "$src/backup.sh" "$dest/backup.sh"
python3 - <<'PY'
import os, re
from pathlib import Path
from urllib.parse import urlencode
base=Path('/srv/agentbox/hermes')
env=base/'data/.env'
assert not env.is_symlink(), 'Refusing credential symlink'
def read_env(path):
    values={}
    for line in path.read_text().splitlines():
        line=line.strip()
        if line and not line.startswith('#') and '=' in line:
            k,v=line.split('=',1)
            values[k]=v.strip().strip('\"').strip("'")
    return values
values=read_env(env)
assert values.get('CPA_API_KEY'), 'Dedicated CPA key is missing'
assert values.get('HERMES_DASHBOARD_BASIC_AUTH_USERNAME'), 'Dashboard username is missing'
assert values.get('HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH') or values.get('HERMES_DASHBOARD_BASIC_AUTH_PASSWORD'), 'Dashboard password or password hash is missing'
assert len(values.get('HERMES_DASHBOARD_BASIC_AUTH_SECRET', '')) >= 32, 'Dashboard session signing secret is missing or too short'
browser=read_env(Path('/srv/agentbox/headless-chrome/client.env'))
assert browser.get('BROWSERLESS_BASE_URL')=='ws://headless-chrome:3000/chrome'
assert browser.get('BROWSERLESS_PROXY_SERVER')=='http://172.18.0.1:7898'
assert re.fullmatch('[a-f0-9]{64}',browser.get('BROWSERLESS_TOKEN',''))
values.update({
    'FEISHU_DOMAIN':'feishu', 'FEISHU_CONNECTION_MODE':'websocket',
    'FEISHU_GROUP_POLICY':'disabled', 'FEISHU_ALLOW_BOTS':'none',
    'FEISHU_ALLOW_ALL_USERS':'false', 'GATEWAY_ALLOW_ALL_USERS':'false',
    'HERMES_YOLO_MODE':'0',
    'BROWSER_CDP_URL':browser['BROWSERLESS_BASE_URL']+'?'+urlencode({
        'token':browser['BROWSERLESS_TOKEN'],
        '--proxy-server':browser['BROWSERLESS_PROXY_SERVER'],
        '--lang':browser.get('BROWSERLESS_LANGUAGE','en-US'),
    }),
})
if values.get('FEISHU_APP_ID') or values.get('FEISHU_APP_SECRET'):
    assert all(values.get(k) for k in ('FEISHU_APP_ID','FEISHU_APP_SECRET','FEISHU_ALLOWED_USERS')), 'Complete Feishu credentials AND owner allowlist before enabling Feishu'
for key,value in values.items():
    assert re.fullmatch('[A-Z][A-Z0-9_]*',key) and '\n' not in value and '\r' not in value
with env.open('w') as f:
    for key,value in values.items():
        # All provisioned secrets and URLs are single-line, without quotes.
        assert "'" not in value
        f.write(key+"='"+value+"'\n")
os.chmod(env,0o600)
os.chown(env,10000,10000)
print('Private environment configured; secret values suppressed.')
PY
docker compose -f "$dest/compose.yaml" config --quiet
docker compose -f "$dest/compose.yaml" up -d
install -m 0644 "$src/agentbox-hermes-backup.service" /etc/systemd/system/agentbox-hermes-backup.service
install -m 0644 "$src/agentbox-hermes-backup.timer" /etc/systemd/system/agentbox-hermes-backup.timer
systemctl daemon-reload
systemctl enable --now agentbox-hermes-backup.timer
echo 'Hermes installed. Run acceptance checks before declaring the Feishu assistant ready.'
