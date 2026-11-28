'use strict';

const { randomUUID } = require('node:crypto');
const CONFIG_KEYS = ['QL_FEISHU_APP_ID', 'QL_FEISHU_APP_SECRET', 'QL_FEISHU_OPEN_ID'];

function isEnabled(env = process.env) {
  return CONFIG_KEYS.some(key => Boolean(env[key]));
}

async function postJson(url, body, accessToken) {
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(20000),
      redirect: 'error',
    });
  } catch {
    throw new Error('飞书接口连接失败或超时');
  }
  if (!response.ok) throw new Error(`飞书接口 HTTP ${response.status}`);
  let result;
  try { result = await response.json(); }
  catch { throw new Error('飞书接口返回了无效 JSON'); }
  if (result.code !== 0) {
    // Do not log request bodies, tokens, or uncontrolled API diagnostics.
    const code = Number.isFinite(Number(result.code)) ? Number(result.code) : '未知';
    throw new Error(`飞书接口业务错误 ${code}`);
  }
  return result;
}

async function sendFeishuDirect(title, message, env = process.env) {
  if (!CONFIG_KEYS.every(key => env[key]?.trim())) {
    throw new Error('飞书私聊配置不完整，需要应用 ID、应用密钥和本人 Open ID');
  }
  if (!/^ou_[A-Za-z0-9]+$/.test(env.QL_FEISHU_OPEN_ID.trim())) {
    throw new Error('飞书接收人 Open ID 格式不正确');
  }
  const auth = await postJson(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    { app_id: env.QL_FEISHU_APP_ID.trim(), app_secret: env.QL_FEISHU_APP_SECRET.trim() },
  );
  if (!auth.tenant_access_token) throw new Error('飞书未返回应用访问凭证');
  const result = await postJson(
    'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id',
    {
      receive_id: env.QL_FEISHU_OPEN_ID.trim(),
      msg_type: 'text',
      content: JSON.stringify({ text: `${title}\n\n${message}` }),
      uuid: randomUUID(),
    },
    auth.tenant_access_token,
  );
  if (!result.data?.message_id) throw new Error('飞书未返回消息 ID，无法确认发送结果');
  return true;
}

module.exports = { sendFeishuDirect, isEnabled, CONFIG_KEYS };

if (require.main === module) {
  if (process.argv[2] !== '--test') {
    console.error('此文件由签到包装脚本调用；测试推送请使用 --test 参数。');
    process.exitCode = 2;
  } else {
    sendFeishuDirect('青龙个人助手 · 连接测试', '飞书私聊推送连接成功。签到任务执行结果将发送到此会话。')
      .then(() => console.log('飞书私聊测试消息发送成功。'))
      .catch(error => { console.error(error.message); process.exitCode = 1; });
  }
}
