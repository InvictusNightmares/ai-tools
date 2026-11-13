'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { createHash, randomUUID } = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');
const { createConfiguredSender } = require('./perkradar_feishu');

const LEASE_MS = 10 * 60 * 1000;
const RETRY_WINDOW_MS = 55 * 60 * 1000;
const CATEGORIES = new Set(['免费白嫖', '限免', '低价优惠', '会员订阅', '游戏', '其他']);
const clean = (value, max = 300) => String(value ?? '').replace(/[\u0000-\u001f\u007f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max);

function canonical(value) {
  try {
    if (typeof value !== 'string' || value.length > 2048) return null;
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
    url.hash = '';
    for (const key of [...url.searchParams.keys()]) {
      if (/^utm_/i.test(key) || /^(fbclid|gclid|msclkid)$/i.test(key)) url.searchParams.delete(key);
    }
    url.searchParams.sort();
    return url.href;
  } catch { return null; }
}

function eligible(board, now, includeOther = false) {
  if (!board || !Array.isArray(board.deals) || !board.sourceHealth || !Array.isArray(board.sources)) throw new Error('PerkRadar 看板响应结构无效');
  const result = new Map();
  for (const deal of board.deals) {
    if (!deal || !CATEGORIES.has(deal.category) || (!includeOther && deal.category === '其他')) continue;
    if (deal.expiresAt != null && (!Number.isFinite(deal.expiresAt) || deal.expiresAt <= now)) continue;
    const url = canonical(deal.canonicalUrl || deal.url);
    const title = clean(deal.title, 200);
    if (!url || !title) continue;
    const key = createHash('sha256').update(url).digest('hex');
    if (!result.has(key)) result.set(key, {
      key, url, title, source: clean(deal.sourceName || deal.sourceId, 60), category: deal.category,
      expiresAt: deal.expiresAt ?? null, expiresLabel: clean(deal.expiresLabel, 40),
      publishedAt: Number.isFinite(deal.publishedAt) ? deal.publishedAt : 0,
    });
  }
  return [...result.values()].sort((a, b) => b.publishedAt - a.publishedAt || a.key.localeCompare(b.key));
}

function openStore(filename) {
  fs.mkdirSync(path.dirname(filename), { recursive: true, mode: 0o700 });
  const db = new DatabaseSync(filename);
  fs.chmodSync(filename, 0o600);
  db.exec(`PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS lease (name TEXT PRIMARY KEY, owner TEXT NOT NULL, expires_at INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS outbox (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, payload TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending', created_at INTEGER NOT NULL,
      first_attempt INTEGER, sent_at INTEGER, message_id TEXT);
    CREATE TABLE IF NOT EXISTS items (key TEXT PRIMARY KEY, url TEXT NOT NULL, batch_id TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS outbox_status ON outbox(status, created_at);`);
  return db;
}

function acquire(db, owner, now) {
  return db.prepare(`INSERT INTO lease VALUES ('run',?,?) ON CONFLICT(name) DO UPDATE
    SET owner=excluded.owner,expires_at=excluded.expires_at WHERE lease.expires_at<=?`).run(owner, now + LEASE_MS, now).changes === 1;
}

function renew(db, owner, now) {
  if (db.prepare("UPDATE lease SET expires_at=? WHERE name='run' AND owner=? AND expires_at>?").run(now + LEASE_MS, owner, now).changes !== 1) throw new Error('运行租约已失效');
}

function transaction(db, action) {
  db.exec('BEGIN IMMEDIATE');
  try { const value = action(); db.exec('COMMIT'); return value; }
  catch (error) { db.exec('ROLLBACK'); throw error; }
}

function message(items, board, time) {
  const lines = [time + '（北京时间）', `本条新增 ${items.length} 条｜来源 ${board.sourceHealth.ok}/${board.sourceHealth.total}`];
  if (board.failures?.length) lines.push('暂不可用：' + board.failures.map(x => clean(x.sourceName || x.sourceId, 40)).join('、'));
  lines.push('优惠线索，领取条件与有效性以原文为准。');
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    lines.push('', `${i + 1}. ${item.title}`, `${item.source} · ${item.category}${item.expiresLabel ? ` · 截止 ${item.expiresLabel}` : ''}`, item.url);
  }
  return lines.join('\n');
}

function queue(db, candidates, board, now, maxBytes = 7000) {
  const exists = db.prepare('SELECT 1 FROM items WHERE key=?');
  const fresh = candidates.filter(item => !exists.get(item.key));
  const time = new Date(now).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  const chunks = [];
  let chunk = [];
  for (const item of fresh) {
    if (chunk.length && Buffer.byteLength(message([...chunk, item], board, time), 'utf8') > maxBytes) { chunks.push(chunk); chunk = []; }
    chunk.push(item);
  }
  if (chunk.length) chunks.push(chunk);
  transaction(db, () => {
    for (const items of chunks) {
      const id = randomUUID();
      db.prepare('INSERT INTO outbox(id,title,body,payload,created_at) VALUES(?,?,?,?,?)')
        .run(id, '优惠雷达 · 新增优惠', message(items, board, time), JSON.stringify(items), now);
      for (const item of items) db.prepare('INSERT INTO items VALUES(?,?,?)').run(item.key, item.url, id);
    }
  });
  return fresh.length;
}

function expireUnattempted(db, now) {
  for (const row of db.prepare("SELECT id,payload FROM outbox WHERE status='pending' AND first_attempt IS NULL").all()) {
    if (JSON.parse(row.payload).some(x => x.expiresAt != null && x.expiresAt <= now)) transaction(db, () => {
      db.prepare("UPDATE outbox SET status='expired' WHERE id=?").run(row.id);
      db.prepare('DELETE FROM items WHERE batch_id=?').run(row.id);
    });
  }
}

async function requestBoard(config, refresh = true, fetchImpl = fetch) {
  const root = new URL(config.baseUrl);
  if (!['http:', 'https:'].includes(root.protocol) || root.username || root.password || root.search || root.hash) throw new Error('PerkRadar 地址配置无效');
  if (typeof config.accessToken !== 'string' || config.accessToken.length < 32) throw new Error('PerkRadar 访问凭据配置无效');
  async function request(endpoint, method = 'GET') {
    let response;
    try {
      response = await fetchImpl(new URL(endpoint, root), {
        method, headers: { Authorization: `Bearer ${config.accessToken}` },
        redirect: 'error', signal: AbortSignal.timeout(90000),
      });
    } catch { throw new Error('PerkRadar 请求超时或连接失败'); }
    if (!response.ok) throw new Error(`PerkRadar HTTP ${response.status}`);
    try { return await response.json(); } catch { throw new Error('PerkRadar 返回无效 JSON'); }
  }
  if (refresh) return request('/api/refresh', 'POST');
  const board = await request('/api/deals?limit=2000');
  const all = [...(board.deals || [])];
  let page = board;
  while (page.pagination?.hasMore) {
    if (!page.deals?.length || all.length >= 100000) throw new Error('PerkRadar 分页结果异常');
    page = await request(`/api/deals?limit=2000&offset=${all.length}`);
    all.push(...page.deals);
  }
  return { ...board, deals: all };
}

async function runOnce({ db, boardLoader, send, now = Date.now, includeOther = false, dryRun = false, maxBytes = 7000 }) {
  const owner = randomUUID();
  if (!acquire(db, owner, now())) return { skipped: 'already_running', sentItems: 0, sentMessages: 0 };
  try {
    const board = await boardLoader();
    renew(db, owner, now());
    const candidates = eligible(board, now(), includeOther);
    if (board.roundStatus === 'failed' || board.sourceHealth.ok === 0) throw new Error('本轮所有来源失败，未把旧数据当作新增推送');
    if (dryRun) return { dryRun: true, sourceHealth: board.sourceHealth, activeCount: board.activeCount, eligibleCount: candidates.length, unsentCount: candidates.filter(x => !db.prepare('SELECT 1 FROM items WHERE key=?').get(x.key)).length };
    expireUnattempted(db, now());
    const queued = queue(db, candidates, board, now(), maxBytes);
    let sentItems = 0;
    let sentMessages = 0;
    let uncertain = 0;
    for (const row of db.prepare("SELECT * FROM outbox WHERE status='pending' ORDER BY created_at,id").all()) {
      renew(db, owner, now());
      if (row.first_attempt != null && now() - row.first_attempt >= RETRY_WINDOW_MS) {
        db.prepare("UPDATE outbox SET status='uncertain' WHERE id=?").run(row.id);
        uncertain++;
        continue;
      }
      db.prepare('UPDATE outbox SET first_attempt=COALESCE(first_attempt,?) WHERE id=?').run(now(), row.id);
      let messageId;
      try { messageId = await send(row.title, row.body, row.id); }
      catch (error) {
        // A definite rejection cannot have delivered this first attempt.
        if (error.ambiguous === false && row.first_attempt == null) db.prepare('UPDATE outbox SET first_attempt=NULL WHERE id=?').run(row.id);
        throw error;
      }
      renew(db, owner, now());
      if (typeof messageId !== 'string' || !messageId) throw new Error('通知未确认发送，保留原去重标识等待重试');
      db.prepare("UPDATE outbox SET status='sent',sent_at=?,message_id=? WHERE id=?").run(now(), messageId, row.id);
      sentItems += JSON.parse(row.payload).length;
      sentMessages++;
    }
    const uncertainTotal = Number(db.prepare("SELECT count(*) AS n FROM outbox WHERE status='uncertain'").get().n);
    return { sourceHealth: board.sourceHealth, activeCount: board.activeCount, eligibleCount: candidates.length, queued, sentItems, sentMessages, uncertain, uncertainTotal };
  } finally { db.prepare("DELETE FROM lease WHERE name='run' AND owner=?").run(owner); }
}

async function main() {
  const args = process.argv.slice(2);
  if (args.some(arg => !['--dry-run', '--no-refresh'].includes(arg))) throw new Error('支持参数：--dry-run、--no-refresh');
  let config;
  try { config = JSON.parse(fs.readFileSync(process.env.PERKRADAR_NOTIFY_CONFIG || '/ql/data/config/perkradar-notify.json', 'utf8')); }
  catch { throw new Error('无法读取 PerkRadar 私密配置'); }
  const db = openStore(config.stateFile);
  try {
    const dryRun = args.includes('--dry-run');
    const result = await runOnce({
      db, dryRun, includeOther: config.includeOther === true,
      maxBytes: Math.min(20000, Math.max(4000, Number(config.messageBytes) || 7000)),
      boardLoader: () => requestBoard(config, !dryRun && !args.includes('--no-refresh')),
      send: dryRun ? null : createConfiguredSender(config),
    });
    console.log(JSON.stringify(result));
    if (result.uncertainTotal) { console.error('存在超过去重重试窗口、发送结果未确认的消息，需要人工核对；没有自动重发这些消息。'); process.exitCode = 1; }
    else if (!dryRun && !result.sentMessages) console.log('没有未推送的新增优惠，本轮不发送消息。');
  } finally { db.close(); }
}

module.exports = { canonical, eligible, openStore, acquire, requestBoard, runOnce, RETRY_WINDOW_MS };
if (require.main === module) main().catch(error => { console.error(`优惠雷达：${error.message}`); process.exitCode = 1; });
