'use strict';
// All credentials in these offline regressions are synthetic.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { parseAccounts, resolveAccountCookie, checkin, inspectStatus, readPrivateProfile, main } = require('./sf_checkin');

const userId = 'a'.repeat(32);
const nativeUrl = 'https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/universalSign';
const loginUrl = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/share/app/activityRedirect';
const config = {
  type: 'sf-app', version: 1,
  loginUserAgent: 'SYNTHETIC_WEBVIEW_UA',
  headers: { token: 'SYNTHETIC_APP_TOKEN', syttoken: 'SYNTHETIC_SYT_TOKEN', requestsign: 'SYNTHETIC_NATIVE_SIGN', timeinterval: '1700000000000', deviceid: 'SYNTHETIC_DEVICE', 'user-agent': 'SYNTHETIC_APP_UA', 'content-type': 'application/json' },
  body: JSON.stringify({ needReqTime: '1', memNo: 'b'.repeat(32), mobile: '13800000000', userId, extra: '', name: 'mcs-mimp-web.sf-express.com' }, null, 2),
  redirect: { bizCode: '622', source: 'SFAPP', citycode: '', cityname: '' },
};
const account = () => parseAccounts(JSON.stringify(config))[0];
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });
function loginResponse(session = 'SYNTHETIC_SESSION', id = userId) {
  const headers = new Headers({ Location: 'https://unrelated.example/never-follow' });
  headers.append('Set-Cookie', `sessionId=${session}; Path=/; HttpOnly; Secure`);
  headers.append('Set-Cookie', `_login_user_id_=${id}; Path=/; Secure`);
  return new Response(null, { status: 302, headers });
}
function exchange() {
  const calls = [];
  let sequence = 0;
  const fetch = async (url, options) => {
    calls.push({ url, options });
    if (url === nativeUrl) return json({ success: true, obj: { userId, sign: `SYNTHETIC_TICKET_${++sequence}` } });
    assert.equal(new URL(url).origin + new URL(url).pathname, loginUrl);
    return loginResponse(`SYNTHETIC_SESSION_${sequence}`);
  };
  return { calls, fetch };
}

test('accepts App profiles and preserves legacy Cookie and URL account formats', () => {
  assert.equal(parseAccounts(JSON.stringify([config, config])).length, 2);
  const cookie = `sessionId=SYNTHETIC_OLD; _login_user_id_=${userId}`;
  assert.equal(parseAccounts(cookie)[0].cookie, cookie);
  assert.equal(parseAccounts('Cookie: ' + cookie)[0].cookie, cookie);
  const url = loginUrl + '?sign=SYNTHETIC_OLD';
  assert.equal(parseAccounts(url)[0].url, url);
});

test('configuration failures do not echo credentials and reject header or target injection', () => {
  const cases = [
    {}, [], { ...config, version: 2 },
    { ...config, headers: { ...config.headers, token: 'SYNTHETIC_SECRET\r\nHost: unrelated.example' } },
    { ...config, headers: { ...config.headers, host: 'unrelated.example' } },
    { ...config, loginUserAgent: 'SYNTHETIC_SECRET\r\nInjected: value' },
    { ...config, body: JSON.stringify({ ...JSON.parse(config.body), name: 'unrelated.example' }) },
    { ...config, redirect: { ...config.redirect, redirectUrl: 'https://unrelated.example/' } },
    { ...config, redirect: { ...config.redirect, source: 'OTHER' } },
  ];
  for (const value of cases) assert.throws(() => parseAccounts(JSON.stringify(value)), error => !error.message.includes('SYNTHETIC'));
  assert.throws(() => parseAccounts('{"SYNTHETIC_SECRET":'), error => !error.message.includes('SYNTHETIC'));
});

test('native request keeps exact signed bytes, exchanges once and never follows Location', async () => {
  const mock = exchange();
  const cookie = await resolveAccountCookie(account(), mock.fetch);
  assert.match(cookie, /sessionId=SYNTHETIC_SESSION_1/);
  assert.equal(mock.calls.length, 2);
  assert.equal(mock.calls[0].url, nativeUrl);
  assert.equal(mock.calls[0].options.body, config.body);
  assert.deepEqual(mock.calls[0].options.headers, config.headers);
  assert.equal(mock.calls[0].options.redirect, 'error');
  assert.equal(mock.calls[1].options.redirect, 'manual');
  assert.equal(mock.calls[1].options.headers['User-Agent'], config.loginUserAgent);
  assert.equal(new URL(mock.calls[1].url).searchParams.get('sign'), 'SYNTHETIC_TICKET_1');
  for (const key of ['token', 'syttoken', 'requestsign', 'cookie']) assert.equal(mock.calls[1].options.headers[key], undefined);
});

test('each run obtains a new ticket and session instead of caching the first one', async () => {
  const mock = exchange(); const current = account();
  const first = await resolveAccountCookie(current, mock.fetch);
  const second = await resolveAccountCookie(current, mock.fetch);
  assert.notEqual(first, second);
  assert.equal(mock.calls.filter(c => c.url === nativeUrl).length, 2);
  assert.ok(current.secrets.includes('SYNTHETIC_TICKET_1'));
  assert.ok(current.secrets.includes('SYNTHETIC_SESSION_2'));
});

test('native errors stop without replay, session exchange, sign-in or secret exposure', async () => {
  const failures = [
    () => json({ success: false, errorMessage: 'SYNTHETIC_APP_TOKEN' }),
    () => json({ success: 'true', obj: { userId, sign: 'SYNTHETIC_TICKET' } }),
    () => json({ success: true, obj: { userId: 'OTHER_ACCOUNT', sign: 'SYNTHETIC_TICKET' } }),
    () => json({}, 503),
    () => new Response('SYNTHETIC_INVALID_JSON'),
    () => new Response(null, { status: 302, headers: { Location: 'https://unrelated.example/' } }),
    () => { throw new Error('SYNTHETIC_APP_TOKEN'); },
  ];
  for (const failure of failures) {
    let fetches = 0; let requests = 0;
    await assert.rejects(checkin(account(), async () => { requests++; }, async () => { fetches++; return failure(); }), error => !error.message.includes('SYNTHETIC'));
    assert.equal(fetches, 1); assert.equal(requests, 0);
  }
});

test('missing or wrong-account session Cookies stop before any sign-in', async () => {
  for (const response of [new Response('{}'), loginResponse('SYNTHETIC_SESSION', 'OTHER_ACCOUNT')]) {
    let count = 0; let mutations = 0;
    const fetch = async () => ++count === 1 ? json({ success: true, obj: { userId, sign: 'SYNTHETIC_TICKET' } }) : response;
    await assert.rejects(checkin(account(), async () => { mutations++; }, fetch));
    assert.equal(count, 2); assert.equal(mutations, 0);
  }
});

test('anonymous membership state stops sign-in after the ticket exchange', async () => {
  const paths = []; const mock = exchange();
  await assert.rejects(checkin(account(), async url => {
    paths.push(new URL(url).pathname); return { success: true, obj: { loginStatus: -1 } };
  }, mock.fetch), /登录验证失败/);
  assert.deepEqual(paths, ['/mcs-mimp/ifLogin']);
});

test('daily App mode checks login then uses the existing two sign-in endpoints', async () => {
  const urls = []; const mock = exchange();
  const result = await checkin(account(), async (url, headers) => {
    urls.push(url); assert.match(headers.Cookie, /SYNTHETIC_SESSION_1/);
    if (url.endsWith('/ifLogin')) return { success: true, obj: { loginStatus: 1 } };
    if (url.endsWith('~getTodaySign')) return { success: true, obj: { signed: true, dayCount: 3 } };
    return { success: true, obj: {} };
  }, mock.fetch);
  assert.equal(result.ok, true);
  assert.match(result.lines[0], /App 自动取票并登录：成功/);
  assert.equal(urls.filter(url => url.endsWith('~sign')).length, 1);
  assert.equal(urls.filter(url => url.endsWith('~automaticSignFetchPackage')).length, 1);
  assert.equal(urls.filter(url => url.endsWith('~getTodaySign')).length, 1);
  assert.ok(result.lines.includes('已连续签到 3 天'));
  assert.equal(urls.length, 5);
});

test('status verification queries login and signed state without signing even if unsigned', async () => {
  for (const signed of [true, false]) {
    const urls = []; const mock = exchange();
    const result = await inspectStatus(account(), async url => {
      urls.push(url);
      return url.endsWith('/ifLogin') ? { success: true, obj: { loginStatus: 1 } } : { success: true, obj: { signed, dayCount: 1 } };
    }, mock.fetch);
    assert.deepEqual(result, { ok: true, authMode: 'sf-app', loginStatus: 1, signed, dayCount: 1 });
    assert.equal(urls.length, 2);
    assert.ok(urls[0].endsWith('/ifLogin'));
    assert.ok(urls[1].endsWith('~getTodaySign'));
  }
});

test('Cookie mode keeps working without a native authentication request', async () => {
  const legacy = parseAccounts(`sessionId=SYNTHETIC_OLD; _login_user_id_=${userId}`)[0];
  const urls = [];
  const result = await checkin(legacy, async url => {
    urls.push(url);
    if (url.endsWith('~getTodaySign')) return { success: true, obj: { signed: true, dayCount: 2 } };
    return { success: true, obj: {} };
  }, async () => { assert.fail('unexpected native request'); });
  assert.equal(result.ok, true);
  assert.equal(urls.filter(url => url.endsWith('~getTodaySign')).length, 1);
  assert.ok(result.lines.includes('已连续签到 2 天'));
  assert.equal(urls.length, 4);
});

test('transient busy responses are retried before reporting failure', async () => {
  const legacy = parseAccounts(`sessionId=SYNTHETIC_OLD; _login_user_id_=${userId}`)[0];
  let membershipCalls = 0;
  process.env.SF_BUSY_RETRY_MS = '0';
  try {
    const result = await checkin(legacy, async url => {
      if (url.endsWith('~automaticSignFetchPackage')) {
        membershipCalls++;
        if (membershipCalls === 1) return { success: false, errorMessage: '活动太火爆了，请稍后再试试~' };
        return { success: true, obj: { award: { giftBagName: 'SYNTHETIC_REWARD' } } };
      }
      if (url.endsWith('~getTodaySign')) return { success: true, obj: { signed: true, dayCount: 3 } };
      return { success: true, obj: {} };
    }, async () => { assert.fail('unexpected native request'); });
    assert.equal(result.ok, true);
    assert.equal(membershipCalls, 2);
    assert.ok(result.lines.some(line => /获得 SYNTHETIC_REWARD/.test(line)));
    assert.ok(!result.lines.some(line => /失败/.test(line)));
  } finally {
    delete process.env.SF_BUSY_RETRY_MS;
  }
});

test('dry-run takes priority over session verification and does not load the notification runner', async () => {
  const prior = { env: process.env.sfsyUrl, log: console.log, fetch: global.fetch }; const lines = [];
  try {
    process.env.sfsyUrl = JSON.stringify(config);
    console.log = line => lines.push(line);
    global.fetch = async () => assert.fail('dry-run made a network request');
    await main(['--dry-run', '--check-session']);
    assert.equal(lines.length, 1);
    assert.match(lines[0], /配置检查通过/);
    assert.doesNotMatch(lines[0], /SYNTHETIC/);
  } finally {
    if (prior.env === undefined) delete process.env.sfsyUrl; else process.env.sfsyUrl = prior.env;
    console.log = prior.log; global.fetch = prior.fetch;
  }
});

test('private profile requires a regular private file and rejects symlinks without exposing its contents', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'sf-profile-test-'));
  const file = path.join(dir, 'profile.json'); const link = path.join(dir, 'link.json');
  try {
    assert.equal(readPrivateProfile(file), null);
    fs.writeFileSync(file, JSON.stringify(config), { mode: 0o600 });
    assert.deepEqual(JSON.parse(readPrivateProfile(file)), config);
    fs.chmodSync(file, 0o644);
    assert.throws(() => readPrivateProfile(file), error => !error.message.includes('SYNTHETIC'));
    fs.chmodSync(file, 0o600); fs.symlinkSync(file, link);
    assert.throws(() => readPrivateProfile(link), /私有配置无法读取/);
    fs.writeFileSync(file, 'x'.repeat(131073));
    assert.throws(() => readPrivateProfile(file), /私有配置无法读取/);
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
