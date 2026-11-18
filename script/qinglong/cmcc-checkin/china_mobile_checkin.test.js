'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { ENDPOINT, parseAccounts, updateCookies, createRequester, checkin, inspectStatus, main } = require('./china_mobile_checkin');

const config = {
  cookie: 'JSESSIONID=SYNTHETIC_SESSION; CM_ORG_LOG=SYNTHETIC_LOGIN',
  fingerprint: 'SYNTHETIC_FINGERPRINT',
  userAgent: 'SYNTHETIC_APP_USER_AGENT',
};
const account = parseAccounts(JSON.stringify(config))[0];
const state = signed => ({ success: true, resultCode: '1', resultObj: { isLogin: true, isSignToday: signed, monthSignCnt: 4, flowPendingMb: 1079 } });
const response = result => new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } });

test('accepts single or multiple Jiangsu accounts and rejects old QWHD variables', () => {
  assert.equal(parseAccounts(JSON.stringify(config)).length, 1);
  assert.equal(parseAccounts(JSON.stringify([config, config])).length, 2);
  for (const raw of ['', 'QWHD_SESSION_TOKEN=SYNTHETIC_OLD', 'null', '[]', '{}', JSON.stringify({ ...config, cookie: 'QWHD_SESSION_TOKEN=SYNTHETIC_OLD' })]) {
    assert.throws(() => parseAccounts(raw));
  }
});

test('configuration errors do not echo credentials and reject header injection', () => {
  for (const key of ['cookie', 'fingerprint', 'userAgent']) {
    const input = { ...config, [key]: 'SYNTHETIC_SECRET\r\nInjected: 1' };
    assert.throws(() => parseAccounts(JSON.stringify(input)), error => !error.message.includes('SYNTHETIC_SECRET'));
  }
});

test('anonymous HTTP 200 success response is a login failure and never signs', async () => {
  const calls = [];
  await assert.rejects(checkin(account, async method => {
    calls.push(method);
    return { success: true, resultCode: '1', resultObj: { isLogin: false, isApp: true } };
  }), /登录已失效/);
  assert.deepEqual(calls, ['initIndexPage']);
});

test('already signed state skips the mutation', async () => {
  const calls = [];
  const result = await checkin(account, async method => { calls.push(method); return state(true); });
  assert.equal(result.ok, true);
  assert.equal(result.lines[0], '今日已签到');
  assert.deepEqual(calls, ['initIndexPage']);
});

test('unsigned account signs once and requires explicit signed state', async () => {
  const calls = [];
  const result = await checkin(account, async method => { calls.push(method); return state(method === 'doSign'); });
  assert.equal(result.ok, true);
  assert.deepEqual(calls, ['initIndexPage', 'doSign']);
  await assert.rejects(checkin(account, async () => state(false)), /未确认今日已签到/);
});

test('missing fields, string booleans and service failure cannot report success', async () => {
  for (const result of [
    {}, { ...state(true), success: false }, { ...state(true), resultCode: '2' },
    { ...state(true), resultObj: {} },
    { ...state(true), resultObj: { isLogin: true, isSignToday: 'true' } },
  ]) await assert.rejects(checkin(account, async () => result));
});

test('status query never performs doSign even when unsigned', async () => {
  const calls = [];
  const result = await inspectStatus(account, async method => { calls.push(method); return state(false); });
  assert.equal(result.ok, true);
  assert.deepEqual(calls, ['initIndexPage']);
});

test('form encoding uses only the fixed activity origin and captures cookie rotation', async () => {
  const calls = [];
  const request = createRequester(account, async (url, options) => {
    calls.push({ url, options });
    const result = response(state(calls.length > 1));
    result.headers.append('Set-Cookie', 'JSESSIONID=SYNTHETIC_ROTATED; Path=/; HttpOnly');
    return result;
  });
  await checkin(account, request);
  assert.equal(calls.length, 2);
  for (const call of calls) {
    assert.equal(call.url, ENDPOINT);
    assert.equal(call.options.redirect, 'error');
    assert.equal(call.options.headers.hgvhv, config.fingerprint);
    const form = new URLSearchParams(call.options.body);
    assert.equal(form.get('reqUrl'), 'act2510');
    assert.equal(form.get('mywaytoopen'), config.fingerprint);
    assert.equal(form.get('actCode'), '2510');
  }
  assert.match(calls[1].options.headers.Cookie, /JSESSIONID=SYNTHETIC_ROTATED/);
  assert.doesNotMatch(calls[1].options.headers.Cookie, /SYNTHETIC_SESSION/);
});

test('cookies from other domains and paths are ignored; expired cookies are removed', () => {
  const updated = updateCookies(config.cookie, [
    'JSESSIONID=ATTACKER; Domain=10086.cn.attacker.example; Path=/',
    'JSESSIONID=WRONG_PATH; Path=/nact-other',
    'CM_ORG_LOG=expired; Domain=.js.10086.cn; Path=/; Max-Age=0',
  ]);
  assert.equal(updated, 'JSESSIONID=SYNTHETIC_SESSION');
});

test('network failure is not retried and does not echo upstream secret values', async () => {
  let calls = 0;
  const request = createRequester(account, async () => { calls++; throw new Error('SYNTHETIC_SECRET'); });
  await assert.rejects(checkin(account, request), error => !error.message.includes('SYNTHETIC_SECRET'));
  assert.equal(calls, 1);
});

test('HTTP and invalid JSON failures cannot be interpreted as success', async () => {
  for (const result of [new Response('SYNTHETIC_SECRET', { status: 403 }), new Response('<html>login</html>')]) {
    await assert.rejects(checkin(account, createRequester(account, async () => result)), error => !error.message.includes('SYNTHETIC_SECRET'));
  }
});

test('failed sign operation is never retried automatically', async () => {
  const calls = [];
  await assert.rejects(checkin(account, async method => {
    calls.push(method);
    if (method === 'doSign') throw new Error('network failure');
    return state(false);
  }));
  assert.deepEqual(calls, ['initIndexPage', 'doSign']);
});

test('dry run does not load the notifier or issue requests', async () => {
  let invoked = 0;
  const code = await main(['--dry-run'], { chinaMobile: JSON.stringify(config) }, {
    fetchImpl: () => { invoked++; throw new Error('unexpected network'); },
    runDaily: () => { invoked++; throw new Error('unexpected notifier'); },
  });
  assert.equal(code, 0);
  assert.equal(invoked, 0);
});

test('status CLI makes only the read operation and never invokes notifier', async () => {
  const calls = [];
  const code = await main(['--status'], { chinaMobile: JSON.stringify(config) }, {
    fetchImpl: async (url, options) => { calls.push(new URLSearchParams(options.body).get('method')); return response(state(true)); },
    runDaily: () => { throw new Error('unexpected notifier'); },
  });
  assert.equal(code, 0);
  assert.deepEqual(calls, ['initIndexPage']);
});
