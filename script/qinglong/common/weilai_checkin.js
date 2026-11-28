'use strict';

const { spawn } = require('node:child_process');
const path = require('node:path');
const { randomInt } = require('node:crypto');
const { setTimeout: delay } = require('node:timers/promises');
const { sendFeishuDirect, isEnabled, CONFIG_KEYS } = require('./feishu_private_notify');
const tokens = (process.env.weilai || '').split(/[&\n]/).map(x => x.split('#')[0].trim()).filter(Boolean);
const privateNotify = isEnabled();
const secrets = [...tokens, process.env.PUSH_PLUS_TOKEN, process.env.FSKEY, process.env.FSSECRET,
  ...CONFIG_KEYS.map(key => process.env[key])].filter(Boolean);

function sanitize(text) {
  for (const secret of secrets) text = text.split(secret).join('[令牌已隐藏]');
  return text.replace(/Bearer\s+[A-Za-z0-9._~+\/=\-]+/gi, 'Bearer [令牌已隐藏]');
}

async function notify(failed, details) {
  if (!privateNotify) return true;
  const time = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });
  try {
    await sendFeishuDirect(`蔚来签到 · ${failed ? '失败' : '成功'}`, `${time}（北京时间）\n${sanitize(details)}`);
    console.log('飞书私聊通知发送成功。');
    return true;
  } catch (error) {
    console.error(`飞书私聊通知失败：${sanitize(error.message)}。`);
    return false;
  }
}

async function main() {
  if (!tokens.length) {
    const message = '尚未配置 weilai 登录令牌，请在青龙环境变量中更新。';
    console.error(message);
    await notify(true, message);
    process.exitCode = 2;
    return;
  }
  if (!process.argv.includes('--now')) {
    const seconds = randomInt(0, 15 * 60 + 1);
    const startAt = new Date(Date.now() + seconds * 1000).toLocaleTimeString('zh-CN', { timeZone: 'Asia/Shanghai' });
    console.log(`随机启动：等待 ${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒，预计北京时间 ${startAt} 签到。`);
    await delay(seconds * 1000);
  }
  let output = '';
  let exceeded = false;
  let timedOut = false;
  let spawnFailed = false;
  const childEnv = { ...process.env, HITOKOTO: 'false' };
  for (const key of Object.keys(childEnv)) {
    if (/^ACCOUNT_\d+_|^QL_FEISHU_|^QL_MS_LOGIN_INPUT$/.test(key)) delete childEnv[key];
  }
  if (privateNotify) {
    childEnv.SKIP_PUSH_TITLE = [...new Set([...(childEnv.SKIP_PUSH_TITLE || '').split('\n'), '蔚来签到'])].filter(Boolean).join('\n');
  }
  const child = spawn(process.execPath, [path.join(__dirname, 'smallfawn_QLScriptPublic_main/daily/weilai.js')], {
    env: childEnv, stdio: ['ignore', 'pipe', 'pipe'],
  });
  const append = chunk => {
    if (exceeded) return;
    output += chunk.toString();
    if (output.length > 1024 * 1024) {
      output = output.slice(0, 1024 * 1024);
      exceeded = true;
      child.kill('SIGTERM');
    }
  };
  child.stdout.on('data', append);
  child.stderr.on('data', append);
  const timer = setTimeout(() => { timedOut = true; child.kill('SIGTERM'); }, 90000);
  child.on('error', () => { spawnFailed = true; });
  child.on('close', async code => {
    clearTimeout(timer);
    output = sanitize(output);
    process.stdout.write(output);
    const accountLines = output.split('\n').filter(line => /账号\[\d+\]/.test(line));
    const failed = timedOut || exceeded || spawnFailed || code !== 0 ||
      /签到-失败|AxiosError|Error:|共找到0个账号/.test(output) || accountLines.length < tokens.length;
    let details = accountLines.map(line => line.trim().slice(0, 500)).slice(0, 10).join('\n');
    if (timedOut) details = '签到请求超时（90 秒），请检查网络或登录状态。';
    else if (exceeded) details = '日志输出异常，任务已停止。';
    else if (spawnFailed) details = '无法启动蔚来签到脚本。';
    else if (failed && !details) details = '签到执行失败，请查看青龙任务日志。';
    if (failed) console.error('蔚来签到未确认成功，请查看以上日志。');
    const notified = await notify(failed, details);
    process.exitCode = failed || !notified ? 1 : 0;
  });
}

main().catch(() => { console.error('蔚来任务初始化失败。'); process.exitCode = 1; });
