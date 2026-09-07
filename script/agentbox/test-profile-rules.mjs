import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const here = path.dirname(fileURLToPath(import.meta.url));
const yaml = createRequire(import.meta.url)('./vendor/js-yaml.cjs');

test('online subscription routing survives local enhancements and future refreshes', () => {
  const bundle = mkdtempSync(path.join(tmpdir(), 'agentbox-rules-'));
  const put = (name, value) => writeFileSync(path.join(bundle, name), yaml.dump(value));
  try {
    mkdirSync(path.join(bundle, 'profiles'));
    put('profiles.yaml', { current: 'remote', items: [
      { uid: 'remote', type: 'remote', file: 'Rtest.yaml', url: 'https://example.test/profile' },
      { uid: 'Merge', type: 'merge', file: 'Merge.yaml' },
      { uid: 'Script', type: 'script', file: 'Script.js' },
    ] });
    put('config.yaml', {});
    put('verge.yaml', { enable_builtin_enhanced: false });
    put('profiles/Merge.yaml', { rules: ['MATCH,REJECT'] });
    writeFileSync(path.join(bundle, 'profiles/Script.js'), 'function main(c){c.rules=["MATCH,DIRECT"];return c}');
    put('agentbox-policy.yaml', { environment: 'us', 'proxy-server': '203.0.113.7', 'tailnet-domain': 'tail123.ts.net' });
    for (const generation of [1, 2]) {
      const source = {
        proxies: [{ name: 'US', type: 'vless', server: '203.0.113.7', port: 443 }],
        'proxy-groups': [{ name: 'PROXY', type: 'select', proxies: ['US'] }],
        'rule-providers': { ads: { type: 'inline', behavior: 'domain', payload: ['ads.example'] } },
        rules: [`DOMAIN,direct-${generation}.example,DIRECT`, 'RULE-SET,ads,REJECT', 'GEOIP,CN,DIRECT', 'MATCH,PROXY'],
      };
      put('profiles/Rtest.yaml', source);
      put('download.yaml', source);
      for (const port of [17898, 7897, 7898]) {
        const output = path.join(bundle, `compiled-${port}.yaml`);
        execFileSync(process.execPath, [path.join(here, 'agentbox-profile-compiler.js'), '--bundle', bundle,
          '--source', path.join(bundle, 'download.yaml'), '--port', String(port), '--output', output]);
        const actual = yaml.load(readFileSync(output, 'utf8'));
        assert.deepEqual(actual.rules, source.rules, 'subscription rule order and targets must remain exact');
        assert.deepEqual(actual['rule-providers'], source['rule-providers']);
        assert.deepEqual(actual['proxy-groups'].filter(g => g.name !== 'AGENTBOX-US'), source['proxy-groups']);
        assert.deepEqual(actual.dns.nameserver, ['https://1.1.1.1/dns-query#AGENTBOX-US',
          'https://8.8.8.8/dns-query#AGENTBOX-US', 'tls://9.9.9.9#AGENTBOX-US']);
        assert.equal(actual.tun.enable, port === 7898);
        assert.equal(actual.dns.listen, port === 7898 ? '0.0.0.0:53' :
          port === 7897 ? '127.0.0.1:1054' : '127.0.0.1:1053');
      }
    }
  } finally {
    rmSync(bundle, { recursive: true, force: true });
  }
});
