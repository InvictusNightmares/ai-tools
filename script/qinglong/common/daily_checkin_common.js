'use strict';
const { randomInt } = require('node:crypto');
const { setTimeout: sleep } = require('node:timers/promises');
const { sendFeishuDirect, CONFIG_KEYS } = require('./feishu_private_notify');

function sanitize(text, credentials = []) {
  const privateValues = [...credentials, ...CONFIG_KEYS.map(key => process.env[key])].filter(Boolean);
  for (const value of privateValues) text = String(text).split(value).join('[已隐藏]');
  return String(text).replace(/\b(1\d{2})\d{4}(\d{4})\b/g, '$1****$2');
}

async function postJson(url, headers, data, fetchImpl = fetch) {
  let response;
  try {
    response = await fetchImpl(url, { method: 'POST', headers: { 'Content-Type': 'application/json;charset=UTF-8', ...headers }, body: JSON.stringify(data), redirect: 'error', signal: AbortSignal.timeout(20000) });
  } catch { throw new Error('请求超时或连接失败'); }
  if (!response.ok) throw new Error(`接口返回 HTTP ${response.status}`);
  try { return await response.json(); }
  catch { throw new Error('接口未返回有效 JSON，可能需要重新登录'); }
}

async function runDaily({ title, envName, parse, checkin }, argv = process.argv.slice(2)) {
  const raw = process.env[envName] || '';
  let accounts;
  try { accounts = parse(raw); }
  catch (error) { console.error(`${title}：${error.message}`); process.exitCode = 2; return; }
  if (argv.includes('--dry-run')) {
    console.log(`${title}：配置检查通过，共 ${accounts.length} 个账号；未发送签到或通知请求。`);
    return;
  }
  if (!argv.includes('--now')) {
    const seconds = randomInt(0, 901);
    const start = new Date(Date.now() + seconds * 1000).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
    console.log(`随机等待 ${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒，预计北京时间 ${start} 开始。`);
    await sleep(seconds * 1000);
  }
  const lines = [];
  let failed = 0;
  for (let i = 0; i < accounts.length; i++) {
    try {
      const result = await checkin(accounts[i]);
      lines.push(`账号 ${i + 1}：${result.lines.join('\n')}`);
      if (!result.ok) failed++;
    } catch (error) {
      failed++;
      lines.push(`账号 ${i + 1}：${error.message}`);
    }
  }
  const secrets = [raw, ...accounts.flatMap(x => x.secrets || [])];
  const details = sanitize(lines.join('\n\n'), secrets);
  console.log(details);
  const resultName = failed ? (failed === accounts.length ? '失败' : '部分失败') : '成功';
  const time = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  try {
    await sendFeishuDirect(`${title} · ${resultName}`, `${time}（北京时间）\n${details}`);
    console.log('飞书私聊通知发送成功。');
  } catch (error) {
    console.error(`飞书通知失败：${sanitize(error.message, secrets)}`);
    failed++;
  }
  process.exitCode = failed ? 1 : 0;
}

module.exports = { sanitize, postJson, runDaily };
