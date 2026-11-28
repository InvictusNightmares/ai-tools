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
    put('agentbox-policy.yaml', {
      environment: 'us',
      'proxy-server': '203.0.113.7',
      'proxy-server-hostname': 'us.example.test',
      'tailnet-domain': 'tail123.ts.net',
      'fallback-servers': [{ server: '198.51.100.9', hostname: 'sg.example.test' }],
    });
    for (const generation of [1, 2]) {
      const source = {
        proxies: [
          { name: 'US-Hysteria2', type: 'hysteria2', server: 'us.example.test', port: 443 },
          { name: 'US-Vless-SG-Hysteria2', type: 'vless', server: 'us.example.test', port: 443, tls: true, servername: 'relay.example.test' },
          { name: 'US-Vless', type: 'vless', server: 'us.example.test', port: 443, tls: true, servername: 'us-tls.example.test' },
          { name: 'SG-Vless', type: 'vless', server: 'sg.example.test', port: 443, tls: true, servername: 'sg-tls.example.test' },
          { name: 'SG-Hysteria2', type: 'hysteria2', server: 'sg.example.test', port: 443 },
          { name: 'SG-Vless-US-Hysteria2', type: 'vless', server: 'sg.example.test', port: 443, tls: true, 'dialer-proxy': 'US-Hysteria2' },
        ],
        'proxy-groups': [
          { name: 'Auto', type: 'fallback', proxies: ['US-Vless', 'US-Hysteria2'] },
          { name: 'PROXY', type: 'select', proxies: ['Auto', 'US-Vless', 'US-Hysteria2'] },
        ],
        'rule-providers': { ads: { type: 'inline', behavior: 'domain', payload: ['ads.example'] } },
        rules: [
          `DOMAIN,direct-${generation}.example,DIRECT`,
          'RULE-SET,ads,REJECT',
          'AND,((NETWORK,UDP),(DST-PORT,443),(GEOSITE,geolocation-!cn)),REJECT',
          'GEOSITE,geolocation-!cn,PROXY',
          'GEOIP,CN,DIRECT',
          'AND,((NETWORK,UDP),(DST-PORT,443)),REJECT',
          'MATCH,PROXY',
        ],
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
        assert.equal(actual.ipv6, false);
        assert.equal(actual['log-level'], 'warning');
        assert.equal(actual['tcp-concurrent'], true);
        assert.equal(actual['keep-alive-idle'], 15);
        assert.equal(actual['keep-alive-interval'], 15);
        assert.equal(actual['geo-auto-update'], true);
        assert.deepEqual(actual.profile, { 'store-selected': false, 'store-fake-ip': false });
        assert.deepEqual(actual.dns['nameserver-policy']['geosite:cn,private'], [
          'https://223.5.5.5/dns-query#DIRECT',
          'https://1.12.12.12/dns-query#DIRECT',
        ]);
        assert.equal(actual.dns['nameserver-policy']['+.stun.*.*'], undefined, 'STUN must not leak to domestic DNS');
        assert.deepEqual(actual.dns['nameserver-policy']['+.tail123.ts.net'], '100.100.100.100#tailscale0');
        assert.equal(actual.tun.enable, port === 7898);
        assert.ok(actual.tun['route-exclude-address'].includes('203.0.113.7/32'));
        assert.ok(actual.tun['route-exclude-address'].includes('198.51.100.9/32'));
        assert.equal(actual.dns.listen, port === 7898 ? '0.0.0.0:53' :
          port === 7897 ? '127.0.0.1:1054' : '127.0.0.1:1053');
        const usGroup = actual['proxy-groups'].find((g) => g.name === 'AGENTBOX-US');
        assert.deepEqual(usGroup.proxies, ['US-Vless', 'US-Hysteria2']);
        if (port === 7897) {
          const bsGroup = actual['proxy-groups'].find((g) => g.name === 'AGENTBOX-BOOTSTRAP');
          assert.deepEqual(bsGroup.proxies, ['US-Vless', 'US-Hysteria2', 'SG-Vless', 'SG-Hysteria2']);
          assert.deepEqual(actual['proxy-groups'].find((g) => g.name === 'PROXY'), {
            name: 'PROXY', type: 'select', proxies: ['AGENTBOX-BOOTSTRAP'],
          });
          assert.deepEqual(actual.dns.nameserver, [
            'https://1.1.1.1/dns-query#AGENTBOX-BOOTSTRAP',
            'https://8.8.8.8/dns-query#AGENTBOX-BOOTSTRAP',
          ]);
        } else {
          assert.deepEqual(actual['proxy-groups'].filter((g) => g.name !== 'AGENTBOX-US'), source['proxy-groups']);
          assert.deepEqual(actual.dns.nameserver, [
            'https://1.1.1.1/dns-query#AGENTBOX-US',
            'https://8.8.8.8/dns-query#AGENTBOX-US',
          ]);
        }
      }
    }
  } finally {
    rmSync(bundle, { recursive: true, force: true });
  }
});
