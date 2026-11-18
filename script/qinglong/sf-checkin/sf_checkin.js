'use strict';
// Sign-in endpoints adapted from smallfawn/QLScriptPublic daily/sfsy.py,
// commit 640dbac72a991fbc3c8cdedb17ad204eee3c15d9. Only daily sign-ins are enabled.
const { createHash, randomBytes } = require('node:crypto');
const { constants, openSync, fstatSync, readFileSync, closeSync } = require('node:fs');
const { resolve } = require('node:path');
const postJson = (...args) => require('./daily_checkin_common').postJson(...args);
const PRIVATE_PROFILE = resolve(__dirname, '../config/sf_app_profile.json');

const ORIGIN = 'https://mcs-mimp-web.sf-express.com';
const APP_TICKET_URL = 'https://ccsp-egmas.sf-express.com/cx-app-member/member/app/user/universalSign';
const APP_LOGIN_URL = ORIGIN + '/mcs-mimp/share/app/activityRedirect';
const BASE = 'https://mcs-mimp-web.sf-express.com/mcs-mimp/commonPost/';
const SIGN_PATHS = [
  ['每日签到', '~memberNonactivity~integralSignV2Service~sign', 'SFAPP', {}],
  ['会员签到', '~memberNonactivity~integralTaskSignPlusService~automaticSignFetchPackage', 'MINI_PROGRAM', { comeFrom: 'vioin', channelFrom: 'WEIXIN' }],
];

const MINI_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36 NetType/WIFI MicroMessenger/7.0.20.1781(0x6700143B) WindowsWechat(0x63090551) XWEB/6945 Flue';
const APP_UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148';
const APP_HEADERS = new Set('clientversion cookie user-agent languagecode mediacode systemversion memberid regioncode jsbundle srcdeviceguid deviceid token syttoken carrier accept-language model requestsign accept content-type screensize timeinterval accept-encoding priority'.split(' '));

function readPrivateProfile(path = PRIVATE_PROFILE) {
  let fd;
  try {
    fd = openSync(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    const stat = fstatSync(fd);
    if (!stat.isFile() || (stat.mode & 0o077) || stat.size > 131072) throw new Error('invalid private file');
    return readFileSync(fd, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw new Error('顺丰 App 私有配置无法读取，请检查文件类型、大小及 0600 权限。');
  } finally {
    if (fd !== undefined) closeSync(fd);
  }
}

function parseAppProfile(profile) {
  const invalid = () => { throw new Error('顺丰 App 配置不完整或格式不正确，请重新导入抓包配置。'); };
  if (!profile || profile.type !== 'sf-app' || profile.version !== 1 ||
      typeof profile.body !== 'string' || profile.body.length > 65536 ||
      typeof profile.loginUserAgent !== 'string' || !profile.loginUserAgent || /[\r\n\0]/.test(profile.loginUserAgent) ||
      !profile.headers || typeof profile.headers !== 'object' || Array.isArray(profile.headers)) invalid();
  const headers = {};
  for (const [key, value] of Object.entries(profile.headers)) {
    if (!APP_HEADERS.has(key) || typeof value !== 'string' || /[\r\n\0]/.test(value)) invalid();
    headers[key] = value;
  }
  for (const key of ['token', 'syttoken', 'requestsign', 'timeinterval', 'deviceid', 'user-agent', 'content-type']) {
    if (!headers[key]) invalid();
  }
  let body;
  try { body = JSON.parse(profile.body); } catch { invalid(); }
  if (!body || typeof body !== 'object' || Array.isArray(body) ||
      body.name !== 'mcs-mimp-web.sf-express.com' || body.needReqTime !== '1' ||
      !['mobile', 'memNo', 'userId'].every(k => typeof body[k] === 'string' && body[k].length > 0) ||
      Object.keys(body).some(k => !['mobile', 'memNo', 'userId', 'name', 'needReqTime', 'extra'].includes(k))) invalid();
  const redirect = profile.redirect;
  if (!redirect || typeof redirect !== 'object' || Array.isArray(redirect) ||
      redirect.source !== 'SFAPP' || typeof redirect.bizCode !== 'string' || !redirect.bizCode ||
      Object.entries(redirect).some(([k, v]) => !['bizCode', 'source', 'citycode', 'cityname'].includes(k) || typeof v !== 'string' || /[\r\n\0]/.test(v))) invalid();
  return {
    app: { headers, body: profile.body, userId: body.userId, userAgent: profile.loginUserAgent, redirect: { ...redirect } },
    secrets: [profile.body, body.mobile, body.memNo, body.userId,
      ...['token', 'syttoken', 'requestsign', 'cookie', 'deviceid', 'srcdeviceguid'].map(k => headers[k]).filter(Boolean)],
  };
}

async function resolveAppCookie(account, fetchImpl = fetch) {
  const app = account.app;
  let response;
  try {
    // Preserve the captured body bytes and all signed header values together.
    // Native signature generation and App-token renewal are not implemented.
    response = await fetchImpl(APP_TICKET_URL, {
      method: 'POST', headers: { ...app.headers }, body: app.body,
      redirect: 'error', signal: AbortSignal.timeout(20000),
    });
  } catch { throw new Error('顺丰 App 取票连接失败；本次未重试。'); }
  if (!response.ok) throw new Error(`顺丰 App 取票返回 HTTP ${response.status}。`);
  let result;
  try { result = await response.json(); } catch { throw new Error('顺丰 App 取票响应不是有效 JSON。'); }
  if (result?.success !== true || typeof result.obj?.sign !== 'string' || !result.obj.sign) {
    throw new Error('顺丰 App 取票未成功，请检查或重新抓取 App 登录凭据。');
  }
  if (result.obj.userId !== app.userId) throw new Error('顺丰取票返回的账号与配置不一致，已停止。');
  const url = new URL(APP_LOGIN_URL);
  for (const [key, value] of Object.entries(app.redirect)) url.searchParams.set(key, value);
  url.searchParams.set('sign', result.obj.sign);
  account.secrets.push(result.obj.sign, url.toString());
  try {
    response = await fetchImpl(url.toString(), {
      method: 'GET', redirect: 'manual',
      headers: { 'User-Agent': app.userAgent, Accept: 'text/html,application/xhtml+xml,*/*', Referer: ORIGIN + '/' },
      signal: AbortSignal.timeout(20000),
    });
  } catch { throw new Error('顺丰票据换取会话连接失败；本次未重试。'); }
  const jar = new Map();
  if (response.status >= 200 && response.status < 400) {
    for (const raw of response.headers.getSetCookie()) {
      const pair = raw.split(';')[0];
      const at = pair.indexOf('=');
      if (at > 0) jar.set(pair.slice(0, at).trim(), pair.slice(at + 1).trim());
    }
  }
  if (!jar.get('sessionId') || !jar.get('_login_user_id_')) {
    throw new Error('顺丰新票据未换到有效登录 Cookie，已停止。');
  }
  if (jar.get('_login_user_id_') !== app.userId) throw new Error('顺丰登录会话账号与配置不一致，已停止。');
  // The first App redirect already supplies the login cookies. Do not follow
  // its Location or forward the native credentials to the activity host.
  return [...jar].map(([key, value]) => `${key}=${value}`).join('; ');
}

async function resolveAccountCookie(account, fetchImpl = fetch) {
  let cookie = account.cookie;
  if (account.app) cookie = await resolveAppCookie(account, fetchImpl);
  else if (account.url) cookie = await resolveCookieFromUrl(account.url, fetchImpl);
  const parsed = parseCookie(cookie);
  account.secrets = [...(account.secrets || []), cookie, ...Object.values(parsed.values)];
  return cookie;
}

function parseCookie(cookie) {
  const values = Object.fromEntries(cookie.split(';').map(x => x.trim()).filter(x => x.includes('=')).map(x => [x.slice(0, x.indexOf('=')), x.slice(x.indexOf('=') + 1)]));
  if (!values.sessionId || !values._login_user_id_) throw new Error('顺丰 Cookie 缺少 sessionId 或 _login_user_id_，请重新登录获取。');
  return { cookie, values };
}

async function resolveCookieFromUrl(url, fetchImpl = fetch) {
  let current = url;
  const jar = new Map();
  const userAgent = /\/share\/app\//i.test(url) ? APP_UA : MINI_UA;
  for (let i = 0; i < 8; i++) {
    let response;
    try {
      response = await fetchImpl(current, {
        method: 'GET',
        redirect: 'manual',
        headers: {
          'User-Agent': userAgent,
          'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
          'Accept-Language': 'zh-CN,zh',
          'Referer': 'https://mcs-mimp-web.sf-express.com/',
        },
        signal: AbortSignal.timeout(20000),
      });
    } catch {
      throw new Error('顺丰分享链接请求失败，请检查网络或链接是否有效');
    }
    const setCookies = typeof response.headers.getSetCookie === 'function' ? response.headers.getSetCookie() : [];
    for (const raw of setCookies) {
      const pair = raw.split(';')[0];
      const index = pair.indexOf('=');
      if (index > 0) jar.set(pair.slice(0, index).trim(), pair.slice(index + 1).trim());
    }
    if (response.status >= 300 && response.status < 400) {
      const location = response.headers.get('location');
      if (!location) break;
      current = new URL(location, current).toString();
      continue;
    }
    break;
  }
  const cookie = [...jar].map(([key, value]) => `${key}=${value}`).join('; ');
  if (!cookie) throw new Error('分享链接没有返回登录 Cookie，可能已失效，请重新复制');
  return parseCookie(cookie).cookie;
}

function parseAccounts(raw) {
  const text = raw.trim();
  if (!text || text === '待填写') throw new Error('请先在 sfsyUrl 环境变量中填写顺丰 App 配置、登录 Cookie 或分享链接。');
  if (text.startsWith('{') || text.startsWith('[')) {
    let parsed;
    try { parsed = JSON.parse(text); } catch { throw new Error('顺丰 App 配置不是有效 JSON，请重新导入。'); }
    const profiles = Array.isArray(parsed) ? parsed : [parsed];
    if (!profiles.length) throw new Error('顺丰 App 配置中没有账号。');
    return profiles.map(parseAppProfile);
  }
  return text.split(/\r?\n/).map(x => x.trim()).filter(Boolean).map(line => {
    const value = line.replace(/^Cookie:\s*/i, '');
    if (/^https?:\/\//i.test(value)) {
      if (!/^https:\/\/mcs-mimp-web\.sf-express\.com\//i.test(value)) throw new Error('顺丰分享链接域名不正确，需要 mcs-mimp-web.sf-express.com 的 share 链接。');
      return { url: value, secrets: [value] };
    }
    return { cookie: parseCookie(value).cookie, secrets: [value] };
  });
}

function signedHeaders(cookie, platform, now = Date.now()) {
  const timestamp = String(now);
  const sysCode = 'MCS-MIMP-CORE';
  const signature = createHash('md5').update(`token=wwesldfs29aniversaryvdld29&timestamp=${timestamp}&sysCode=${sysCode}`).digest('hex');
  return { Cookie: cookie, platform, sysCode, timestamp, signature, Origin: 'https://mcs-mimp-web.sf-express.com', Referer: 'https://mcs-mimp-web.sf-express.com/superWelfare', 'User-Agent': MINI_UA };
}

async function requireLogin(cookie, request = postJson) {
  const login = await request(ORIGIN + '/mcs-mimp/ifLogin', signedHeaders(cookie, 'SFAPP'), {});
  if (login?.success !== true || login.obj?.loginStatus !== 1) throw new Error('顺丰会话登录验证失败，已停止。');
}

async function inspectStatus(account, request = postJson, fetchImpl = fetch) {
  const cookie = await resolveAccountCookie(account, fetchImpl);
  await requireLogin(cookie, request);
  const status = await request(BASE + '~memberNonactivity~integralSignV2Service~getTodaySign', signedHeaders(cookie, 'SFAPP'), {});
  if (status?.success !== true || typeof status.obj?.signed !== 'boolean') throw new Error('顺丰签到状态查询未返回有效结果。');
  return { ok: true, authMode: account.app ? 'sf-app' : 'legacy', loginStatus: 1, signed: status.obj.signed, dayCount: status.obj.dayCount };
}

async function checkin(account, request = postJson, fetchImpl = fetch) {
  const cookie = await resolveAccountCookie(account, fetchImpl);
  if (account.app) await requireLogin(cookie, request);
  const lines = account.app ? ['App 自动取票并登录：成功'] : [];
  let failures = 0;
  for (const [name, path, platform, body] of SIGN_PATHS) {
    try {
      const response = await request(BASE + path, signedHeaders(cookie, platform), body);
      if (response?.success !== true) {
        const message = String(response?.errorMessage || response?.errorCode || '接口未确认成功').slice(0, 180);
        if (/今日已签到|今天已签到|您已签到/.test(message)) {
          lines.push(`${name}：今日已签到`);
          continue;
        }
        failures++; lines.push(`${name}：失败，${message}`);
        continue;
      }
      const obj = response.obj;
      if (Array.isArray(obj)) {
        const names = obj.map(x => x.packetName).filter(Boolean);
        lines.push(`${name}：${names.length ? names.join('、') : '已完成或无待领取奖励'}`);
      } else {
        const rewards = obj?.integralTaskSignPackageVOList?.map(x => x.packetName).filter(Boolean) || [];
        const reward = obj?.award?.giftBagName || rewards.join('、');
        lines.push(`${name}：${reward ? '获得 ' + reward : '接口确认成功（含已签到）'}`);
      }
    } catch (error) { failures++; lines.push(`${name}：${error.message}`); }
  }
  if (failures === 0) {
    try {
      const status = await request(BASE + '~memberNonactivity~integralSignV2Service~getTodaySign', signedHeaders(cookie, 'SFAPP'), {});
      const days = Number(status?.obj?.dayCount);
      if (status?.success === true && Number.isFinite(days)) lines.push(`已连续签到 ${days} 天`);
    } catch { /* 连续天数查询失败不影响签到结果 */ }
  }
  try {
    const points = await request(BASE + '~memberNonactivity~integralTaskStrategyService~queryPointTaskAndSignFromES', signedHeaders(cookie, 'MINI_PROGRAM'), { channelType: '1', deviceId: randomBytes(12).toString('hex') });
    if (points?.success === true && points.obj?.totalPoint !== undefined) lines.push(`当前积分：${points.obj.totalPoint}`);
  } catch { lines.push('积分余额查询失败，请以顺丰 App 为准。'); }
  return { ok: failures === 0, lines };
}

async function main(argv = process.argv.slice(2)) {
  const privateProfile = readPrivateProfile();
  const parse = raw => parseAccounts(privateProfile ?? raw);
  if (argv.includes('--dry-run') || argv.includes('--check-session')) {
    const accounts = parse(process.env.sfsyUrl || '');
    if (argv.includes('--dry-run')) {
      console.log(`顺丰签到：配置检查通过，共 ${accounts.length} 个账号；未发送签到或通知请求。`);
      return;
    }
    for (let i = 0; i < accounts.length; i++) console.log(JSON.stringify({ account: i + 1, ...await inspectStatus(accounts[i]) }));
    return;
  }
  return require('./daily_checkin_common').runDaily({ title: '顺丰签到', envName: 'sfsyUrl', parse, checkin }, argv);
}

module.exports = { parseAccounts, signedHeaders, checkin, SIGN_PATHS, resolveCookieFromUrl, resolveAppCookie, resolveAccountCookie, inspectStatus, readPrivateProfile, main };
if (require.main === module) main().catch(error => { console.error(`顺丰任务失败：${error.message}`); process.exitCode = 1; });
