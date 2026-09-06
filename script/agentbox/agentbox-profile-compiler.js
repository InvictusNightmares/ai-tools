#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { isIP } = require('node:net');

const yaml = require(path.join(__dirname, 'vendor', 'js-yaml.cjs'));

const MAX_CONFIG_BYTES = 10 * 1024 * 1024;
const SCRIPT_TIMEOUT_MS = 5000;
const PROFILE_FILE_RE = /^(?:[RLmrpg][A-Za-z0-9]+\.yaml|s[A-Za-z0-9]+\.js|Merge\.yaml|Script\.js)$/;
const BUILTIN_POLICIES = new Set(['DIRECT', 'REJECT', 'REJECT-DROP', 'PASS']);
const DATA_KEYS = ['proxies', 'proxy-providers', 'proxy-groups', 'rule-providers', 'rules'];
const HANDLE_KEYS = [
  'mode', 'redir-port', 'tproxy-port', 'mixed-port', 'socks-port', 'port',
  'allow-lan', 'log-level', 'ipv6', 'external-controller', 'secret', 'unified-delay',
];
const REMOVE_FOR_HEADLESS = [
  'port', 'socks-port', 'mixed-port', 'redir-port', 'tproxy-port',
  'external-controller', 'external-controller-unix', 'external-controller-pipe',
  'external-controller-cors', 'secret', 'authentication', 'skip-auth-prefixes',
  'listeners',
];

function fail(message) {
  throw new Error(message);
}

function parseArgs(argv) {
  const result = Object.create(null);
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith('--')) fail(`Unexpected argument: ${token}`);
    const key = token.slice(2);
    if (['settings', 'self-test', 'replace-current-source'].includes(key)) {
      result[key] = true;
      continue;
    }
    if (index + 1 >= argv.length) fail(`Missing value for --${key}`);
    result[key] = argv[index + 1];
    index += 1;
  }
  return result;
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function readText(file) {
  const stat = fs.statSync(file);
  if (!stat.isFile()) fail('A required profile input is not a regular file.');
  if (stat.size > MAX_CONFIG_BYTES) fail('A profile input exceeds the 10 MiB safety limit.');
  return fs.readFileSync(file, 'utf8');
}

function readYaml(file, allowEmpty = false) {
  const text = readText(file);
  if (allowEmpty && text.split(/\r?\n/).every((line) => line.trim() === '' || line.trimStart().startsWith('#'))) {
    return {};
  }
  const value = yaml.load(text);
  if (!isObject(value)) fail('A required YAML document is not a mapping.');
  return value;
}

function writePrivate(file, content) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  const temporary = `${file}.new`;
  fs.writeFileSync(temporary, content, { encoding: 'utf8', mode: 0o600 });
  fs.chmodSync(temporary, 0o600);
  fs.renameSync(temporary, file);
}

function lowerTopLevel(config) {
  const result = {};
  for (const [key, value] of Object.entries(config)) result[key.toLowerCase()] = value;
  return result;
}

function deepMerge(target, patch) {
  if (!isObject(target) || !isObject(patch)) return structuredClone(patch);
  const result = structuredClone(target);
  for (const [key, value] of Object.entries(patch)) {
    result[key] = isObject(result[key]) && isObject(value)
      ? deepMerge(result[key], value)
      : structuredClone(value);
  }
  return result;
}

function profilePath(bundle, file) {
  if (typeof file !== 'string' || !PROFILE_FILE_RE.test(file) || path.basename(file) !== file) {
    fail('A profile item has an unsafe or unsupported file name.');
  }
  const root = path.resolve(bundle, 'profiles');
  const resolved = path.resolve(root, file);
  if (path.dirname(resolved) !== root) fail('A profile file escapes the private bundle.');
  return resolved;
}

function loadProfiles(bundle) {
  const profiles = readYaml(path.join(bundle, 'profiles.yaml'));
  if (typeof profiles.current !== 'string' || !Array.isArray(profiles.items)) {
    fail('profiles.yaml has no current profile or item list.');
  }
  const byUid = new Map();
  for (const item of profiles.items) {
    if (isObject(item) && typeof item.uid === 'string') byUid.set(item.uid, item);
  }
  const current = byUid.get(profiles.current);
  if (!current || current.type !== 'remote' || typeof current.url !== 'string' || current.url.length === 0) {
    fail('The current Clash Verge profile is not a downloadable remote profile.');
  }
  profilePath(bundle, current.file);
  return { profiles, byUid, current };
}

function loadItem(bundle, byUid, uid, expectedType, fallback) {
  if (typeof uid !== 'string') return structuredClone(fallback);
  const item = byUid.get(uid);
  if (!item || item.type !== expectedType) return structuredClone(fallback);
  const file = profilePath(bundle, item.file);
  if (expectedType === 'script') return readText(file);
  return readYaml(file, true);
}

function sequenceMap(value) {
  if (!isObject(value)) return { prepend: [], append: [], delete: [] };
  return {
    prepend: Array.isArray(value.prepend) ? structuredClone(value.prepend) : [],
    append: Array.isArray(value.append) ? structuredClone(value.append) : [],
    delete: Array.isArray(value.delete) ? value.delete.filter((item) => typeof item === 'string') : [],
  };
}

function itemName(item) {
  if (typeof item === 'string') return item;
  return isObject(item) && typeof item.name === 'string' ? item.name : null;
}

function useSequence(config, sequence, field) {
  const seq = sequenceMap(sequence);
  const deleted = new Set(seq.delete);
  const existing = Array.isArray(config[field]) ? config[field] : [];
  config[field] = [
    ...seq.prepend,
    ...existing.filter((item) => {
      const name = itemName(item);
      return name === null || !deleted.has(name);
    }),
    ...seq.append,
  ];

  if (field !== 'proxies' || !Array.isArray(config['proxy-groups'])) return config;

  const added = [];
  const seenAdded = new Set();
  for (const item of [...seq.prepend, ...seq.append]) {
    const name = itemName(item);
    if (name !== null && !seenAdded.has(name)) {
      seenAdded.add(name);
      added.push(name);
    }
  }

  let inserted = false;
  for (const group of config['proxy-groups']) {
    if (!isObject(group)) continue;
    if (Array.isArray(group.proxies)) group.proxies = group.proxies.filter((name) => !deleted.has(name));
    const type = typeof group.type === 'string' ? group.type.toLowerCase() : '';
    if (!inserted && added.length > 0 && (type === 'select' || type === 'selector')) {
      const merged = [];
      const seen = new Set();
      for (const name of [...added, ...(Array.isArray(group.proxies) ? group.proxies : [])]) {
        if (typeof name !== 'string' || !seen.has(name)) {
          merged.push(name);
          if (typeof name === 'string') seen.add(name);
        }
      }
      group.proxies = merged;
      inserted = true;
    }
  }
  return config;
}

function runUserScript(source, config, profileName) {
  if (Buffer.byteLength(source, 'utf8') > MAX_CONFIG_BYTES) fail('A JavaScript enhancement exceeds the safety limit.');
  const sandbox = Object.create(null);
  sandbox.__config = structuredClone(lowerTopLevel(config));
  sandbox.__name = String(profileName || '').slice(0, 1024);
  sandbox.console = Object.freeze({
    log() {}, info() {}, error() {}, debug() {}, warn() {}, table() {},
  });
  const context = vm.createContext(sandbox, {
    name: 'agentbox-clash-verge-profile',
    codeGeneration: { strings: false, wasm: false },
  });
  const wrapped = `'use strict';\n${source}\n;(() => {\n` +
    `if (typeof main !== 'function') throw new Error('main function is required');\n` +
    `const value = main(__config, __name);\n` +
    `if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('main must return an object');\n` +
    `return value;\n})()`;
  const result = new vm.Script(wrapped, { filename: 'private-profile.js' })
    .runInContext(context, { timeout: SCRIPT_TIMEOUT_MS, breakOnSigint: true });
  const serialized = JSON.stringify(result);
  if (Buffer.byteLength(serialized, 'utf8') > MAX_CONFIG_BYTES) fail('A JavaScript enhancement result exceeds the safety limit.');
  return lowerTopLevel(JSON.parse(serialized));
}

function mergeDefaultConfig(config, appConfig, verge) {
  const result = structuredClone(config);
  const socksEnabled = verge.verge_socks_enabled === true;
  const httpEnabled = verge.verge_http_enabled === true;
  const externalEnabled = verge.enable_external_controller === true;
  for (const [key, value] of Object.entries(appConfig)) {
    const lower = key.toLowerCase();
    if (lower === 'tun') {
      result.tun = { ...(isObject(result.tun) ? result.tun : {}), ...(isObject(value) ? structuredClone(value) : {}) };
    } else if (lower === 'socks-port' && !socksEnabled) {
      delete result['socks-port'];
    } else if (lower === 'port' && !httpEnabled) {
      delete result.port;
    } else if (lower === 'redir-port' || lower === 'tproxy-port') {
      delete result[lower];
    } else if (lower === 'external-controller') {
      result[lower] = externalEnabled ? structuredClone(value) : '';
    } else {
      result[lower] = structuredClone(value);
    }
  }
  return result;
}

function applyBuiltins(config) {
  if (Array.isArray(config.proxies)) {
    for (const proxy of config.proxies) {
      if (isObject(proxy) && proxy.type === 'hysteria' && typeof proxy.alpn === 'string') proxy.alpn = [proxy.alpn];
    }
  }
  if (config.mode === 'script') config.mode = 'rule';
  return config;
}

function applyTun(config, enabled) {
  const tun = isObject(config.tun) ? structuredClone(config.tun) : {};
  if (enabled) {
    const dns = isObject(config.dns) ? structuredClone(config.dns) : {};
    const mode = typeof dns['enhanced-mode'] === 'string' ? dns['enhanced-mode'] : 'fake-ip';
    if (mode === 'fake-ip' || !Object.hasOwn(dns, 'enhanced-mode')) {
      dns.enable = true;
      dns.ipv6 = config.ipv6 === true;
      if (!Object.hasOwn(dns, 'enhanced-mode')) dns['enhanced-mode'] = 'fake-ip';
      if (!Object.hasOwn(dns, 'fake-ip-range')) dns['fake-ip-range'] = '198.18.0.1/16';
      if (dns.ipv6 && !Object.hasOwn(dns, 'fake-ip-range6')) dns['fake-ip-range6'] = 'fdfe:dcba:9876::1/64';
    }
    config.dns = dns;
  }
  tun.enable = enabled;
  config.tun = tun;
  return config;
}

function applyDnsSettings(config, bundle, enabled) {
  if (!enabled) return config;
  const file = path.join(bundle, 'dns_config.yaml');
  if (!fs.existsSync(file)) return config;
  const dnsConfig = readYaml(file);
  if (isObject(dnsConfig.hosts)) config.hosts = structuredClone(dnsConfig.hosts);
  const source = Object.hasOwn(dnsConfig, 'dns') ? dnsConfig.dns : dnsConfig;
  if (isObject(source)) {
    const replacement = structuredClone(source);
    const fakeIp = !Object.hasOwn(replacement, 'enhanced-mode') || replacement['enhanced-mode'] === 'fake-ip';
    if (replacement.ipv6 === true && fakeIp && (typeof replacement['fake-ip-range6'] !== 'string' || replacement['fake-ip-range6'].trim() === '')) {
      replacement['fake-ip-range6'] = 'fdfe:dcba:9876::1/64';
    }
    config.dns = replacement;
  }
  return config;
}

function cleanupProxyGroups(config) {
  const proxyNames = new Set((Array.isArray(config.proxies) ? config.proxies : []).map(itemName).filter(Boolean));
  const groups = Array.isArray(config['proxy-groups']) ? config['proxy-groups'] : [];
  const groupNames = new Set(groups.map(itemName).filter(Boolean));
  const providerNames = new Set(isObject(config['proxy-providers']) ? Object.keys(config['proxy-providers']) : []);
  const allowed = new Set([...proxyNames, ...groupNames, ...providerNames, ...BUILTIN_POLICIES]);
  for (const group of groups) {
    if (!isObject(group)) continue;
    let validProvider = false;
    if (Array.isArray(group.use)) {
      group.use = group.use.filter((name) => {
        const valid = typeof name === 'string' && providerNames.has(name);
        validProvider ||= valid;
        return valid;
      });
    }
    if (Array.isArray(group.proxies)) {
      group.proxies = group.proxies.filter((name) => typeof name !== 'string' || allowed.has(name) || validProvider);
    }
  }
  return config;
}

function sortTopLevel(config) {
  const sorted = {};
  for (const key of HANDLE_KEYS) if (Object.hasOwn(config, key)) sorted[key] = config[key];
  for (const [key, value] of Object.entries(config)) {
    if (!HANDLE_KEYS.includes(key) && !DATA_KEYS.includes(key)) sorted[key] = value;
  }
  for (const key of DATA_KEYS) if (Object.hasOwn(config, key)) sorted[key] = config[key];
  return sorted;
}

function sanitizeHeadless(config, port) {
  const result = lowerTopLevel(structuredClone(config));
  for (const key of REMOVE_FOR_HEADLESS) delete result[key];
  result['mixed-port'] = port;
  result['allow-lan'] = false;
  result['bind-address'] = '127.0.0.1';
  result.mode = 'rule';
  result.tun = { ...(isObject(result.tun) ? result.tun : {}), enable: false };
  if (isObject(result.dns)) delete result.dns.listen;
  return sortTopLevel(result);
}

// Applied last and only when explicitly installed on this cloud computer.
// A subscription refresh cannot restore domestic DIRECT rules or system DNS.
function applyUsPolicy(config, policy, port) {
  if (policy.environment !== 'us' || isIP(policy['proxy-server']) !== 4 ||
      !/^[a-z0-9-]+\.ts\.net$/.test(policy['tailnet-domain'] || '')) {
    fail('Invalid Agentbox US environment policy.');
  }
  const server = policy['proxy-server'];
  const proxies = (config.proxies || []).filter(p => isObject(p) && p.server === server &&
    typeof p.name === 'string' && ['vless', 'hysteria2'].includes(p.type));
  if (!proxies.length) fail('The subscription has no eligible US proxy; refusing a direct fallback.');
  const group = 'AGENTBOX-US';
  if (config.proxies.some(p => p.name === group)) fail('Reserved US policy name is used by a proxy.');
  config['proxy-groups'] = (config['proxy-groups'] || []).filter(g => g.name !== group);
  config['proxy-groups'].push({ name: group, type: 'fallback', proxies: proxies.map(p => p.name),
    url: 'https://www.gstatic.com/generate_204', interval: 300, lazy: false });
  const excludes = ['127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
    '100.64.0.0/10', '169.254.0.0/16', `${server}/32`, '::1/128', 'fc00::/7', 'fe80::/10'];
  config.rules = [
    ...excludes.map(cidr => `${cidr.includes(':') ? 'IP-CIDR6' : 'IP-CIDR'},${cidr},DIRECT,no-resolve`),
    ...(config.rules || []).filter(r => /,REJECT(?:-DROP)?(?:,no-resolve)?$/.test(r)),
    `MATCH,${group}`,
  ];
  config.ipv6 = false;
  config.dns = {
    enable: true, listen: port === 7898 ? '0.0.0.0:53' : '127.0.0.1:1053',
    ipv6: false, 'enhanced-mode': 'redir-host', 'use-hosts': true, 'use-system-hosts': true,
    // Literal DoH IPs and literal proxy IPs require no public bootstrap lookup.
    'default-nameserver': ['1.1.1.1'],
    nameserver: [`https://1.1.1.1/dns-query#${group}`, `https://8.8.8.8/dns-query#${group}`, `tls://9.9.9.9#${group}`],
    'nameserver-policy': { [`+.${policy['tailnet-domain']}`]: '100.100.100.100#tailscale0' },
  };
  config.tun = { enable: port === 7898, device: 'ab-us', stack: 'gvisor', mtu: 1400,
    'auto-route': true, 'auto-detect-interface': true, 'strict-route': true,
    'iproute2-table-index': 2022, 'iproute2-rule-index': 9000,
    'route-exclude-address': excludes,
  };
  return config;
}

function compile(bundle, sourceFile, port) {
  const { byUid, current } = loadProfiles(bundle);
  const option = isObject(current.option) ? current.option : {};
  let config = readYaml(sourceFile || profilePath(bundle, current.file));
  config = useSequence(config, loadItem(bundle, byUid, option.rules || 'Rules', 'rules', {}), 'rules');
  config = useSequence(config, loadItem(bundle, byUid, option.proxies || 'Proxies', 'proxies', {}), 'proxies');
  config = useSequence(config, loadItem(bundle, byUid, option.groups || 'Groups', 'groups', {}), 'proxy-groups');

  const appConfig = readYaml(path.join(bundle, 'config.yaml'));
  const verge = readYaml(path.join(bundle, 'verge.yaml'));
  config = mergeDefaultConfig(config, appConfig, verge);
  if (verge.enable_builtin_enhanced !== false) config = applyBuiltins(config);
  config = applyTun(config, verge.enable_tun_mode === true);
  config = applyDnsSettings(config, bundle, verge.enable_dns_settings === true);

  config = deepMerge(config, loadItem(bundle, byUid, 'Merge', 'merge', {}));
  config = runUserScript(loadItem(bundle, byUid, 'Script', 'script', 'function main(config){return config}'), config, current.name || '');
  config = deepMerge(config, loadItem(bundle, byUid, option.merge || 'Merge', 'merge', {}));
  config = runUserScript(loadItem(bundle, byUid, option.script || 'Script', 'script', 'function main(config){return config}'), config, current.name || '');

  config = cleanupProxyGroups(config);
  const sanitized = sanitizeHeadless(config, port);
  const policyFile = path.join(bundle, 'agentbox-policy.yaml');
  return fs.existsSync(policyFile) ? applyUsPolicy(sanitized, readYaml(policyFile), port) : sanitized;
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (!isObject(value)) return value;
  const result = {};
  for (const key of Object.keys(value).sort()) result[key] = stable(value[key]);
  return result;
}

function compareCritical(compiled, currentFile, port) {
  const current = sanitizeHeadless(readYaml(currentFile), port);
  for (const key of DATA_KEYS) {
    if (JSON.stringify(stable(compiled[key])) !== JSON.stringify(stable(current[key]))) {
      fail(`The reproduced configuration differs from Clash Verge in critical section: ${key}`);
    }
  }
}

function curlQuote(value) {
  if (/[\r\n\0]/.test(value)) fail('A download setting contains forbidden control characters.');
  return `"${value.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

function writeFetchConfig(bundle, configFile, outputFile) {
  const { current } = loadProfiles(bundle);
  const option = isObject(current.option) ? current.option : {};
  const timeout = Number.isInteger(option.timeout_seconds) && option.timeout_seconds > 0
    ? Math.min(option.timeout_seconds, 300)
    : 60;
  const userAgent = typeof option.user_agent === 'string' && option.user_agent.length > 0
    ? option.user_agent
    : 'clash-verge/v2.5.2';
  const lines = [
    `url = ${curlQuote(current.url)}`,
    `output = ${curlQuote(path.resolve(outputFile))}`,
    'proxy = "http://127.0.0.1:7897"',
    `user-agent = ${curlQuote(userAgent)}`,
    `connect-timeout = ${timeout}`,
    `max-time = ${Math.min(timeout * 3, 600)}`,
    'fail', 'location', 'compressed', 'silent', 'show-error',
  ];
  if (option.danger_accept_invalid_certs === true) fail('Unsafe certificate bypass is not supported on agentbox.');
  writePrivate(configFile, `${lines.join('\n')}\n`);
}

function printSettings(bundle) {
  const { current } = loadProfiles(bundle);
  const option = isObject(current.option) ? current.option : {};
  const enabled = option.allow_auto_update !== false;
  const interval = Number.isInteger(option.update_interval) && option.update_interval > 0
    ? option.update_interval
    : 720;
  process.stdout.write(`${enabled ? '1' : '0'} ${interval}\n`);
}

function replaceCurrentSource(bundle, downloadedFile) {
  const { current } = loadProfiles(bundle);
  const target = profilePath(bundle, current.file);
  const text = readText(downloadedFile);
  readYaml(downloadedFile);
  writePrivate(target, text);
}

function selfTest() {
  const merged = deepMerge({ a: { b: 1 }, x: [1] }, { a: { c: 2 }, x: [2] });
  if (merged.a.b !== 1 || merged.a.c !== 2 || merged.x[0] !== 2) fail('deep merge self-test failed');
  const scripted = runUserScript('function main(c){c.ok=true;return c}', { A: 1 }, 'test');
  if (scripted.a !== 1 || scripted.ok !== true) fail('script sandbox self-test failed');
  const fixture = { proxies: [{name: 'US', type: 'vless', server: '203.0.113.7'}],
    'proxy-groups': [], rules: ['GEOIP,CN,DIRECT', 'DOMAIN,ads.example,REJECT', 'MATCH,DIRECT', 'RULE-SET,REJECT,DIRECT'] };
  const policy = {environment: 'us', 'proxy-server': '203.0.113.7', 'tailnet-domain': 'tail123.ts.net'};
  const prod = applyUsPolicy(structuredClone(fixture), policy, 7898);
  const candidate = applyUsPolicy(structuredClone(fixture), policy, 17898);
  if (!prod.tun.enable || candidate.tun.enable || prod.dns.listen === candidate.dns.listen ||
      prod.rules.includes('GEOIP,CN,DIRECT') || prod.rules.includes('RULE-SET,REJECT,DIRECT') || prod.rules.at(-1) !== 'MATCH,AGENTBOX-US' ||
      !prod.rules.includes('DOMAIN,ads.example,REJECT') ||
      prod.dns.nameserver.some(s => !s.endsWith('#AGENTBOX-US'))) fail('US policy isolation self-test failed');
  let refused = false;
  try { applyUsPolicy({...fixture, proxies: []}, policy, 7898); } catch { refused = true; }
  if (!refused) fail('Missing US node must fail closed');
  process.stdout.write('agentbox profile compiler self-test passed\n');
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args['self-test']) return selfTest();
  const bundle = args.bundle ? path.resolve(args.bundle) : fail('--bundle is required');
  if (args.settings) return printSettings(bundle);
  if (args['write-fetch-config']) {
    if (!args['fetch-output']) fail('--fetch-output is required');
    return writeFetchConfig(bundle, path.resolve(args['write-fetch-config']), path.resolve(args['fetch-output']));
  }
  if (args['replace-current-source']) {
    if (!args.source) fail('--source is required');
    return replaceCurrentSource(bundle, path.resolve(args.source));
  }
  if (!args.output) fail('--output is required');
  const port = Number(args.port || 7898);
  if (!Number.isInteger(port) || port < 1024 || port > 65535) fail('Invalid mixed-port.');
  const compiled = compile(bundle, args.source ? path.resolve(args.source) : null, port);
  if (args['compare-current']) compareCritical(compiled, path.resolve(args['compare-current']), port);
  const output = yaml.dump(compiled, { noRefs: true, lineWidth: 120, sortKeys: false });
  if (Buffer.byteLength(output, 'utf8') > MAX_CONFIG_BYTES) fail('Compiled configuration exceeds the 10 MiB safety limit.');
  writePrivate(path.resolve(args.output), output);
}

try {
  main();
} catch (error) {
  process.stderr.write(`agentbox profile compiler failed: ${error.message}\n`);
  process.exitCode = 1;
}
