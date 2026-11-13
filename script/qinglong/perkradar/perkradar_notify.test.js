'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { canonical, eligible, openStore, requestBoard, runOnce, RETRY_WINDOW_MS } = require('./perkradar_notify');
const { createSender, createConfiguredSender } = require('./perkradar_feishu');

const TIME = Date.UTC(2026, 10, 13, 7);
function item(id, extras = {}) {
  return { title: `优惠 ${id}`, url: `https://deals.example/item/${id}`, category: '限免', sourceId: 'test', sourceName: '测试源', publishedAt: TIME, expiresAt: null, ...extras };
}
function board(items, extra = {}) {
  return { deals: items, sources: [], sourceHealth: { ok: 7, total: 7 }, activeCount: items.length, roundStatus: 'success', failures: [], ...extra };
}
function fixture(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'perkradar-notifier-test-'));
  const filename = path.join(directory, 'state.sqlite');
  let db = openStore(filename);
  t.after(() => { db.close(); fs.rmSync(directory, { recursive: true, force: true }); });
  return { get db() { return db; }, reopen() { db.close(); db = openStore(filename); return db; } };
}

test('same original URL is deduplicated despite tracking parameters and fragment', () => {
  assert.equal(canonical('https://deals.example/x?utm_source=a&b=2&a=1#reply'), 'https://deals.example/x?a=1&b=2');
  assert.equal(canonical('https://user:secret@deals.example/x'), null);
  assert.equal(canonical('javascript:alert(1)'), null);
  const picked = eligible(board([item(1), item(1, { url: 'https://deals.example/item/1?utm_source=feed#reply' }), item(2, { expiresAt: TIME }), item(3, { category: '其他' })]), TIME);
  assert.equal(picked.length, 1);
});

test('every eligible item is queued, and restarting the process sends none twice', async t => {
  const f = fixture(t);
  const sent = [];
  const data = board(Array.from({ length: 35 }, (_, i) => item(i)));
  const send = async (title, body, id) => { sent.push({ body, id }); return 'om_' + id; };
  const first = await runOnce({ db: f.db, boardLoader: async () => data, send, now: () => TIME, maxBytes: 1000 });
  assert.equal(first.sentItems, 35);
  assert.ok(first.sentMessages > 1);
  const count = sent.length;
  const second = await runOnce({ db: f.reopen(), boardLoader: async () => data, send, now: () => TIME + 900000 });
  assert.equal(second.sentItems, 0);
  assert.equal(sent.length, count);
  const third = await runOnce({ db: f.db, boardLoader: async () => board([...data.deals, item(99)]), send, now: () => TIME + 1800000 });
  assert.equal(third.sentItems, 1);
});

test('an ambiguous send failure retries the same persisted UUID and body', async t => {
  const f = fixture(t);
  const calls = [];
  const send = async (title, body, id) => {
    calls.push({ title, body, id });
    if (calls.length === 1) throw Object.assign(new Error('connection lost'), { ambiguous: true });
    return 'om_confirmed';
  };
  const opts = { boardLoader: async () => board([item(1)]), send };
  await assert.rejects(runOnce({ db: f.db, ...opts, now: () => TIME }));
  const result = await runOnce({ db: f.reopen(), ...opts, now: () => TIME + 900000 });
  assert.equal(result.sentItems, 1);
  assert.deepEqual(calls[0], calls[1]);
});

test('messages confirmed before a later chunk fails are never resent', async t => {
  const f = fixture(t);
  const confirmed = [];
  const failed = [];
  const data = board([item(1, { title: '甲'.repeat(180) }), item(2, { title: '乙'.repeat(180) })]);
  await assert.rejects(runOnce({ db: f.db, boardLoader: async () => data, now: () => TIME, maxBytes: 800, send: async (title, body, id) => {
    if (confirmed.length) { failed.push(id); throw Object.assign(new Error('timeout'), { ambiguous: true }); }
    confirmed.push(id); return 'om_ok';
  } }));
  const retried = [];
  const result = await runOnce({ db: f.reopen(), boardLoader: async () => data, now: () => TIME + 900000, send: async (title, body, id) => { retried.push(id); return 'om_retry'; } });
  assert.deepEqual(retried, failed);
  assert.equal(result.sentItems, 1);
  assert.ok(!retried.includes(confirmed[0]));
});

test('unknown delivery beyond the provider dedup window is held, while new items proceed', async t => {
  const f = fixture(t);
  await assert.rejects(runOnce({ db: f.db, boardLoader: async () => board([item(1)]), now: () => TIME, send: async () => { throw Object.assign(new Error('timeout'), { ambiguous: true }); } }));
  const bodies = [];
  const result = await runOnce({ db: f.reopen(), boardLoader: async () => board([item(1), item(2)]), now: () => TIME + RETRY_WINDOW_MS + 1, send: async (title, body) => { bodies.push(body); return 'om_new'; } });
  assert.equal(result.uncertainTotal, 1);
  assert.equal(result.sentItems, 1);
  assert.ok(bodies.every(body => !body.includes('/item/1')));
});

test('definite rejections can retry later without being incorrectly quarantined', async t => {
  const f = fixture(t);
  await assert.rejects(runOnce({ db: f.db, boardLoader: async () => board([item(1)]), now: () => TIME, send: async () => { throw Object.assign(new Error('auth rejected'), { ambiguous: false }); } }));
  const result = await runOnce({ db: f.reopen(), boardLoader: async () => board([item(1)]), now: () => TIME + 86400000, send: async () => 'om_later' });
  assert.equal(result.sentItems, 1);
  assert.equal(result.uncertainTotal, 0);
});

test('failed source round never presents cached data as a successful new fetch', async t => {
  const f = fixture(t);
  await assert.rejects(runOnce({ db: f.db, boardLoader: async () => board([item(1)], { roundStatus: 'failed', sourceHealth: { ok: 0, total: 7 } }), now: () => TIME, send: async () => assert.fail('must not send') }), /所有来源失败/);
  assert.equal(f.db.prepare('SELECT count(*) AS n FROM items').get().n, 0);
});

test('partial source success is disclosed; dry run does not reserve or send anything', async t => {
  const f = fixture(t);
  const data = board([item(1)], { roundStatus: 'partial', sourceHealth: { ok: 6, total: 7 }, failures: [{ sourceName: '暂缺源' }] });
  const preview = await runOnce({ db: f.db, boardLoader: async () => data, now: () => TIME, dryRun: true, send: async () => assert.fail('preview') });
  assert.equal(preview.unsentCount, 1);
  assert.equal(f.db.prepare('SELECT count(*) AS n FROM items').get().n, 0);
  await runOnce({ db: f.db, boardLoader: async () => data, now: () => TIME, send: async (title, body) => { assert.match(body, /6\/7/); assert.match(body, /暂缺源/); return 'om_partial'; } });
});

test('overlapping invocation does not launch another collection or delivery', async t => {
  const f = fixture(t);
  let release;
  const blocked = new Promise(resolve => { release = resolve; });
  const running = runOnce({ db: f.db, boardLoader: async () => { await blocked; return board([]); }, send: async () => assert.fail('empty'), now: () => TIME });
  const result = await runOnce({ db: f.db, boardLoader: async () => assert.fail('overlap'), send: async () => assert.fail('overlap'), now: () => TIME });
  assert.equal(result.skipped, 'already_running');
  release();
  await running;
});

test('refresh is awaited and authentication is only in its header', async () => {
  const config = { baseUrl: 'http://perkradar:38471', accessToken: 'x'.repeat(48) };
  const result = await requestBoard(config, true, async (url, init) => {
    assert.equal(url.pathname, '/api/refresh'); assert.equal(url.search, '');
    assert.equal(init.method, 'POST'); assert.equal(init.redirect, 'error');
    assert.equal(init.headers.Authorization, 'Bearer ' + config.accessToken);
    return { ok: true, json: async () => board([item(1)]) };
  });
  assert.equal(result.deals.length, 1);
  await assert.rejects(requestBoard(config, true, async () => ({ ok: false, status: 429 })), /HTTP 429/);
});

test('existing Feishu account uses the durable UUID and caches auth only in memory', async () => {
  const env = { QL_FEISHU_APP_ID: 'test-app', QL_FEISHU_APP_SECRET: 'test-secret', QL_FEISHU_OPEN_ID: 'ou_test' };
  let auths = 0;
  const messages = [];
  const sender = createSender(env, async (url, init) => {
    const body = JSON.parse(init.body);
    if (url.includes('/auth/')) { auths++; return { ok: true, json: async () => ({ code: 0, tenant_access_token: 'test-token', expire: 7200 }) }; }
    messages.push(body);
    assert.equal(body.receive_id, 'ou_test');
    return { ok: true, json: async () => ({ code: 0, data: { message_id: 'om_' + messages.length } }) };
  });
  const id = '12345678-1234-1234-1234-123456789012';
  await sender('title', 'body', id); await sender('title', 'body', id);
  assert.equal(auths, 1); assert.equal(messages[0].uuid, id); assert.equal(messages[1].uuid, id);
});

test('dedicated bot uses its own app and app-scoped recipient without mutating shared credentials', async () => {
  const shared = { QL_FEISHU_APP_ID: 'shared-app', QL_FEISHU_APP_SECRET: 'shared-secret', QL_FEISHU_OPEN_ID: 'ou_shared' };
  const original = { ...shared };
  const config = { feishu: { appId: 'dedicated-app', appSecret: 'dedicated-secret', openId: 'ou_dedicated' } };
  const sender = createConfiguredSender(config, shared, async (url, init) => {
    const body = JSON.parse(init.body);
    if (url.includes('/auth/')) {
      assert.equal(body.app_id, 'dedicated-app'); assert.equal(body.app_secret, 'dedicated-secret');
      return { ok: true, json: async () => ({ code: 0, tenant_access_token: 'dedicated-token', expire: 7200 }) };
    }
    assert.equal(body.receive_id, 'ou_dedicated');
    assert.equal(init.headers.Authorization, 'Bearer dedicated-token');
    return { ok: true, json: async () => ({ code: 0, data: { message_id: 'om_dedicated' } }) };
  });
  assert.equal(await sender('test', 'test', '12345678-1234-1234-1234-123456789012'), 'om_dedicated');
  assert.deepEqual(shared, original);
});

test('incomplete dedicated bot configuration never falls back to the shared bot', () => {
  const shared = { QL_FEISHU_APP_ID: 'shared-app', QL_FEISHU_APP_SECRET: 'shared-secret', QL_FEISHU_OPEN_ID: 'ou_shared' };
  for (const feishu of [null, [], {}, { appId: 'partial' }, { appId: 123, appSecret: 'secret', openId: 'ou_new' }]) {
    assert.throws(() => createConfiguredSender({ feishu }, shared, () => assert.fail('must not call network')), /配置/);
  }
});
