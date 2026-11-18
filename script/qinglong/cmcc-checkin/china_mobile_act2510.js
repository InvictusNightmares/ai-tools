'use strict';

// 中国移动 act2510（江苏）签到。
// 使用从 App 抓到的 SSO Cookie（cmtokenid / cmjsSSOCookie / mywaytoopen 等）。
// Cookie 文件权限 0600，丢失/失效后重新抓取即可。

const { readFileSync } = require('node:fs');
const { runDaily } = require('./daily_checkin_common');

const COOKIE_FILE = '/ql/data/config/cm_act2510_cookie.txt';
const ACTION_URL = 'https://wap.js.10086.cn/nact/action.do';
const INDEX_URL = 'https://wap.js.10086.cn/nact/resource/2510/html/index.html';
const UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148/wkwebview leadeon/12.0.5/CMCCIT';
const REQUIRED = ['cmtokenid', 'cmjsSSOCookie', 'mywaytoopen'];

function loadCookie() {
  const raw = readFileSync(COOKIE_FILE, 'utf8').trim();
  if (!raw) throw new Error('act2510 Cookie 文件为空');
  for (const key of REQUIRED) {
    if (!new RegExp(`(?:^|;\\s*)${key}=`).test(raw)) throw new Error(`act2510 Cookie 缺少 ${key}`);
  }
  return raw;
}

function cookieValue(cookie, key) {
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${key}=([^;]+)`));
  return match ? match[1] : '';
}

async function action(cookie, body) {
  const myway = cookieValue(cookie, 'mywaytoopen');
  let response;
  try {
    response = await fetch(ACTION_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'User-Agent': UA,
        'Referer': INDEX_URL,
        'Origin': 'https://wap.js.10086.cn',
        'X-Requested-With': 'XMLHttpRequest',
        'hgvhv': myway,
        'Cookie': cookie,
      },
      body,
      signal: AbortSignal.timeout(20000),
    });
  } catch {
    throw new Error('act2510 请求超时或连接失败');
  }
  if (!response.ok) throw new Error(`act2510 HTTP ${response.status}`);
  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error('act2510 返回了无效 JSON');
  }
  if (String(result.resultCode) !== '1') {
    throw new Error(`act2510 返回 resultCode=${result.resultCode}`);
  }
  return result;
}

async function checkin() {
  const cookie = loadCookie();
  const myway = cookieValue(cookie, 'mywaytoopen');
  const init = await action(cookie, `reqUrl=act2510&method=initIndexPage&operType=1&actCode=2510&isJtAPP=true&env=jt_app&extendParams=&ywcheckcode=&mywaytoopen=${encodeURIComponent(myway)}`);
  if (init.resultObj?.isLogin !== true) throw new Error('act2510 会话未登录，SSO Cookie 可能已失效');
  const sign = await action(cookie, `reqUrl=act2510&method=doSign&operType=1&actCode=2510&isJtAPP=true&fxmobile=&env=jt_app&extendParams=&ywcheckcode=&mywaytoopen=${encodeURIComponent(myway)}`);
  if (sign.resultObj?.isLogin === false) throw new Error('act2510 签到未登录');
  return { ok: true, lines: ['SSO 会话：有效', 'act2510 签到：接口确认成功'] };
}

function parse() {
  const cookie = loadCookie();
  return [{ cookie, secrets: [cookie] }];
}

if (require.main === module) {
  runDaily({ title: '中国移动 act2510 签到', envName: 'CM_ACT2510_COOKIE', parse, checkin })
    .catch(error => { console.error('act2510 任务初始化失败。'); process.exitCode = 1; });
}

module.exports = { checkin, loadCookie, cookieValue };
