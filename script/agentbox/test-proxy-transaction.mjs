import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

// Execute the real activation/EXIT rollback code against temporary files and
// stub service/network commands. Never touch local services or /etc configs.
const updater = readFileSync(new URL('./update-agentbox-proxy.sh', import.meta.url), 'utf8');
const cleanup = updater.slice(updater.indexOf('cleanup() {'), updater.indexOf('chmod 0700 "$work"'));
const activation = updater.slice(updater.indexOf('check_proxy() {'));

for (const failure of ['none', 'production-restart', 'bootstrap-restart', 'bootstrap-dns', 'source-cache']) {
  test(`dual proxy transaction: ${failure}`, () => {
    const fixture = mkdtempSync(path.join(tmpdir(), 'agentbox-transaction-'));
    try {
      mkdirSync(path.join(fixture, 'work'));
      for (const [name, value] of Object.entries({
        production: 'old-production', bootstrap: 'old-bootstrap',
        'work/candidate.yaml': 'new-production', 'work/bootstrap.yaml': 'new-bootstrap',
      })) writeFileSync(path.join(fixture, name), value);
      const shell = `set -Eeuo pipefail
work="$FIXTURE/work"
production_config="$FIXTURE/production"
bootstrap_config="$FIXTURE/bootstrap"
previous_config="$FIXTURE/previous"
state_dir="$FIXTURE/state"
last_success="$state_dir/last-success"
compiler=stub; bundle=stub; candidate_pid=''
production_changed=0; bootstrap_changed=0; committed=0; sync_bootstrap=1
install() {
  while [[ $1 == -* ]]; do
    if [[ $1 == -d ]]; then shift; continue; fi
    shift 2
  done
  if [[ $# == 1 ]]; then mkdir -p "$1"; else cp "$1" "$2"; fi
}
systemctl() {
  [[ $1 != restart ]] && return 0
  printf '%s\\n' "$2" >>"$FIXTURE/restarts"
  if [[ ! -e $FIXTURE/failed ]] && {
    [[ $FAILURE == production-restart && $2 == mihomo.service ]] ||
    [[ $FAILURE == bootstrap-restart && $2 == mihomo-bootstrap.service ]];
  }; then touch "$FIXTURE/failed"; return 1; fi
}
curl() { return 0; }
python3() { [[ $FAILURE != bootstrap-dns || $3 != 1054 ]]; }
node() { [[ $FAILURE != source-cache ]]; }
${cleanup}
${activation}`;
      const result = spawnSync('bash', ['-c', shell], {
        env: { ...process.env, FIXTURE: fixture, FAILURE: failure }, encoding: 'utf8',
      });
      assert.equal(result.status, failure === 'none' ? 0 : 1, result.stderr);
      assert.equal(readFileSync(path.join(fixture, 'production'), 'utf8'),
        failure === 'none' ? 'new-production' : 'old-production');
      assert.equal(readFileSync(path.join(fixture, 'bootstrap'), 'utf8'),
        failure === 'none' ? 'new-bootstrap' : 'old-bootstrap');
      const restarts = readFileSync(path.join(fixture, 'restarts'), 'utf8').trim().split('\n');
      assert.deepEqual(restarts, failure === 'none' ? ['mihomo.service', 'mihomo-bootstrap.service'] :
        failure === 'production-restart' ? ['mihomo.service', 'mihomo.service'] :
          ['mihomo.service', 'mihomo-bootstrap.service', 'mihomo.service', 'mihomo-bootstrap.service']);
    } finally {
      rmSync(fixture, { recursive: true, force: true });
    }
  });
}
