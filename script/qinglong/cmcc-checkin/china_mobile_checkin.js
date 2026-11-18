'use strict';

// Jiangsu act2510 adapter. Authentication must come from the owner's App.
// This module does not obtain getYDRZToken tickets or renew native sessions.
const ENDPOINT = 'https://wap.js.10086.cn/nact/action.do';
const REFERER = 'https://wap.js.10086.cn/nact/resource/2510/html/index.html';
const TITLE = '中国移动江苏签到';
const ENV_NAME = 'chinaMobile';
const CONTROL = /[\x00-\x1f\x7f]/;

function requiredText(value, name, limit) {
  if (typeof value !== 'string' || !value.trim() || value.length > limit || CONTROL.test(value)) {
    throw new Error(`江苏签到配置 ${name} 缺失或格式错误。`);
  }
  return value.trim();
}

function parseAccounts(raw) {
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch { throw new Error('chinaMobile 需要江苏活动会话 JSON；旧 QWHD_SESSION_TOKEN 不能用于此活动。'); }
  const accounts = Array.isArray(parsed) ? parsed : [parsed];
  if (!accounts.length || accounts.length > 20) throw new Error('江苏签到需配置 1–20 个本人账号。');
  return accounts.map(input => {
    if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('江苏账号配置必须是对象。');
    const cookie = requiredText(input.cookie, 'cookie', 16384);
    const fingerprint = requiredText(input.fingerprint, 'fingerprint', 256);
    const userAgent = requiredText(input.userAgent, 'userAgent', 1024);
    const parts = cookie.split(';').map(value => value.trim()).filter(Boolean);
    if (parts.some(part => !/^[!#$%&'*+.^_`|~0-9A-Za-z-]+=[\x21-\x3a\x3c-\x7e]*$/.test(part))) {
      throw new Error('江苏活动 Cookie 格式错误。');
    }
    if (!parts.some(part => /^(JSESSIONID|cmjsSSOCookie|CM_ORG_LOG)=/.test(part))) {
      throw new Error('配置未包含江苏活动会话；不能使用旧 QWHD_SESSION_TOKEN。');
    }
    return { cookie, fingerprint, userAgent, secrets: [cookie, fingerprint, ...parts.map(part => part.slice(part.indexOf('=') + 1))] };
  });
}

function updateCookies(cookie, setCookies) {
  let parts = cookie.split(';').map(value => value.trim()).filter(Boolean);
  for (const header of setCookies) {
    if (CONTROL.test(header)) continue;
    const [pair, ...attributes] = header.split(';').map(value => value.trim());
    const index = pair.indexOf('=');
    if (index <= 0) continue;
    const name = pair.slice(0, index);
    const value = pair.slice(index + 1);
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(name) || !/^[\x21-\x3a\x3c-\x7e]*$/.test(value)) continue;
    const attrs = new Map(attributes.map(attr => {
      const split = attr.indexOf('=');
      return split < 0 ? [attr.toLowerCase(), ''] : [attr.slice(0, split).toLowerCase(), attr.slice(split + 1)];
    }));
    const domain = (attrs.get('domain') || 'wap.js.10086.cn').replace(/^\./, '').toLowerCase();
    if (!['wap.js.10086.cn', 'js.10086.cn', '10086.cn'].includes(domain)) continue;
    const path = attrs.get('path') || '/nact';
    const targetPath = '/nact/action.do';
    if (!(targetPath === path || targetPath.startsWith(path.endsWith('/') ? path : `${path}/`))) continue;
    parts = parts.filter(part => part.slice(0, part.indexOf('=')) !== name);
    const maxAge = attrs.get('max-age');
    const expires = attrs.get('expires');
    const expired = maxAge !== undefined && /^-?\d+$/.test(maxAge)
      ? Number(maxAge) <= 0
      : expires !== undefined && Number.isFinite(Date.parse(expires)) && Date.parse(expires) <= Date.now();
    if (!expired && value) parts.push(pair);
  }
  return parts.join('; ');
}

function createRequester(account, fetchImpl = fetch) {
  let cookie = account.cookie;
  return async method => {
    if (!['initIndexPage', 'doSign'].includes(method)) throw new Error('不支持的江苏活动操作。');
    const form = new URLSearchParams({
      reqUrl: 'act2510', method, operType: '1', actCode: '2510', isJtAPP: 'true',
      env: 'jt_app', extendParams: '', ywcheckcode: '', mywaytoopen: account.fingerprint,
    });
    if (method === 'doSign') form.set('fxmobile', '');
    let response;
    try {
      response = await fetchImpl(ENDPOINT, {
        method: 'POST', redirect: 'error', signal: AbortSignal.timeout(20000),
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          Accept: 'application/json, text/javascript, */*; q=0.01',
          Origin: 'https://wap.js.10086.cn', Referer: REFERER,
          'User-Agent': account.userAgent, 'X-Requested-With': 'XMLHttpRequest',
          Cookie: cookie, hgvhv: account.fingerprint,
        },
        body: form.toString(),
      });
    } catch { throw new Error('江苏活动请求超时、连接失败或发生重定向；本次未自动重试。'); }
    if (!response.ok) throw new Error(`江苏活动返回 HTTP ${response.status}。`);
    let result;
    try { result = await response.json(); }
    catch { throw new Error('江苏活动未返回有效 JSON；请在 App 内检查活动状态。'); }
    if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('江苏活动返回格式异常。');
    cookie = updateCookies(cookie, response.headers.getSetCookie());
    return result;
  };
}

function readState(result) {
  const state = result?.resultObj;
  // HTTP 200 and success:true also occur for an anonymous initIndexPage.
  if (state?.isLogin === false) {
    throw new Error('江苏活动登录已失效，需要本人 App 重新登录活动并更新会话；当前脚本尚未实现 getYDRZToken 自动取票。');
  }
  if (result?.success !== true || String(result?.resultCode) !== '1') throw new Error('江苏活动未确认操作成功。');
  if (state?.isLogin !== true || typeof state?.isSignToday !== 'boolean') throw new Error('江苏活动未返回可验证的登录及签到状态。');
  return state;
}

function summary(state, text) {
  const lines = [text];
  if (Number.isSafeInteger(state.monthSignCnt) && state.monthSignCnt >= 0) lines.push(`本月已签到 ${state.monthSignCnt} 天`);
  if (Number.isSafeInteger(state.flowPendingMb) && state.flowPendingMb >= 0) lines.push(`待提取流量 ${state.flowPendingMb} MB`);
  return lines;
}

async function checkin(account, request = createRequester(account)) {
  const before = readState(await request('initIndexPage'));
  if (before.isSignToday) return { ok: true, lines: summary(before, '今日已签到') };
  const signed = readState(await request('doSign'));
  if (!signed.isSignToday) throw new Error('签到响应未确认今日已签到；本次未自动重试。');
  return { ok: true, lines: summary(signed, '签到成功') };
}

async function inspectStatus(account, request = createRequester(account)) {
  const state = readState(await request('initIndexPage'));
  return { ok: true, lines: summary(state, state.isSignToday ? '已登录，今日已签到' : '已登录，今日未签到；本次只查状态') };
}

async function main(argv = process.argv.slice(2), env = process.env, deps = {}) {
  const args = new Set(argv);
  if (argv.some(arg => !['--dry-run', '--status', '--now', '--no-notify'].includes(arg))) throw new Error('存在不支持的启动参数。');
  const accounts = parseAccounts(env[ENV_NAME] || '');
  if (args.has('--dry-run')) {
    console.log(`${TITLE}：配置检查通过，共 ${accounts.length} 个账号；未发送签到、状态查询或通知请求。`);
    return 0;
  }
  if (args.has('--status') || args.has('--no-notify')) {
    let failures = 0;
    for (let i = 0; i < accounts.length; i++) {
      try {
        const request = createRequester(accounts[i], deps.fetchImpl || fetch);
        const result = await (args.has('--status') ? inspectStatus : checkin)(accounts[i], request);
        console.log(`账号 ${i + 1}：${result.lines.join('；')}`);
      } catch (error) { failures++; console.error(`账号 ${i + 1}：${error.message}`); }
    }
    return failures ? 1 : 0;
  }
  // Keep the panel's existing random delay and notification behavior. The
  // helper is deliberately loaded only for an actual scheduled invocation.
  const runDaily = deps.runDaily || require('./daily_checkin_common').runDaily;
  await runDaily({ title: TITLE, envName: ENV_NAME, parse: parseAccounts, checkin }, argv);
  return process.exitCode || 0;
}

module.exports = { ENDPOINT, parseAccounts, updateCookies, createRequester, readState, checkin, inspectStatus, main };
if (require.main === module) main().then(code => { process.exitCode = code; }).catch(error => { console.error(error.message); process.exitCode = 2; });
