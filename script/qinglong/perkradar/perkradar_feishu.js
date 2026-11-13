'use strict';

// Supports a dedicated private bot without changing Qinglong's shared credentials.
const KEYS = ['QL_FEISHU_APP_ID', 'QL_FEISHU_APP_SECRET', 'QL_FEISHU_OPEN_ID'];

function failure(message, ambiguous) {
  return Object.assign(new Error(message), { ambiguous });
}

function createSender(env = process.env, fetchImpl = fetch) {
  if (!KEYS.every(key => typeof env[key] === 'string' && env[key].trim())) throw failure('飞书私聊配置不完整', false);
  if (!/^ou_[A-Za-z0-9]+$/.test(env.QL_FEISHU_OPEN_ID.trim())) throw failure('飞书接收人配置无效', false);
  let token;
  let tokenUntil = 0;
  async function post(url, body, bearer, sending = false) {
    let response;
    try {
      response = await fetchImpl(url, {
        method: 'POST', redirect: 'error', signal: AbortSignal.timeout(20000),
        headers: { 'Content-Type': 'application/json', ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}) },
        body: JSON.stringify(body),
      });
    } catch { throw failure('飞书连接失败或超时', sending); }
    if (!response.ok) throw failure(`飞书 HTTP ${response.status}`, sending && response.status >= 500);
    let result;
    try { result = await response.json(); } catch { throw failure('飞书响应无效', sending); }
    if (result.code !== 0) {
      const code = Number.isInteger(result.code) ? result.code : '未知';
      throw failure(`飞书业务错误 ${code}`, false);
    }
    return result;
  }
  return async (title, body, uuid) => {
    if (!/^[0-9a-f-]{36}$/i.test(uuid)) throw failure('消息去重标识无效', false);
    if (!token || Date.now() >= tokenUntil) {
      const auth = await post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal', {
        app_id: env.QL_FEISHU_APP_ID.trim(), app_secret: env.QL_FEISHU_APP_SECRET.trim(),
      });
      if (!auth.tenant_access_token) throw failure('飞书未返回访问凭据', false);
      token = auth.tenant_access_token;
      tokenUntil = Date.now() + Math.max(60, Number(auth.expire || 3600) - 60) * 1000;
    }
    const result = await post('https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id', {
      receive_id: env.QL_FEISHU_OPEN_ID.trim(), msg_type: 'text', uuid,
      content: JSON.stringify({ text: `${title}\n\n${body}` }),
    }, token, true);
    if (!result.data?.message_id) throw failure('飞书未确认消息 ID', true);
    return result.data.message_id;
  };
}

function createConfiguredSender(config, env = process.env, fetchImpl = fetch) {
  if (!Object.prototype.hasOwnProperty.call(config, 'feishu')) return createSender(env, fetchImpl);
  const credentials = config.feishu;
  if (!credentials || typeof credentials !== 'object' || Array.isArray(credentials)) throw failure('专用飞书机器人配置无效', false);
  // A broken dedicated configuration must fail, never silently send through the shared bot.
  return createSender({
    QL_FEISHU_APP_ID: credentials.appId,
    QL_FEISHU_APP_SECRET: credentials.appSecret,
    QL_FEISHU_OPEN_ID: credentials.openId,
  }, fetchImpl);
}

module.exports = { createSender, createConfiguredSender, KEYS };
