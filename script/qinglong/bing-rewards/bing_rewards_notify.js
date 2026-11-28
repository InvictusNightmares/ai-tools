'use strict';

const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const { randomInt } = require('node:crypto');
const { setTimeout: delay } = require('node:timers/promises');

function loadFeishuNotifier() {
  for (const candidate of ['./feishu_private_notify', '../common/feishu_private_notify']) {
    try {
      return require(candidate);
    } catch (error) {
      if (error?.code !== 'MODULE_NOT_FOUND') throw error;
    }
  }
  return {
    isEnabled: () => false,
    sendFeishuDirect: async () => {
      throw new Error('未找到 feishu_private_notify.js');
    },
  };
}

const { sendFeishuDirect, isEnabled } = loadFeishuNotifier();

const RANDOM_START_MAX_SECONDS = 3 * 60 * 60;
const LOGIN_ALERT_COOLDOWN_MS = 150 * 1000;
const TAIL_LINE_LIMIT = 1000;
const HIGHLIGHT_LINE_LIMIT = 500;

const HIGHLIGHT_PATTERN =
  /\[(REACT-PARSE|RUN-END|RUN-SKIP|ACCOUNT-END|ACCOUNT-SKIP|POINTS|LOGIN[^\]]*|FLOW|ACCOUNT-ERROR|MAIN-ERROR|SESSIONS-END|SESSION-GENERATION)\]|连续计数=|streakCounter=|Fraud_UserWarning|bot-score warning|BotScore|本轮跳过桌面阶段|获取移动端访问令牌失败|App 仪表板不可用|App 可赚积分查询失败|App points unavailable|App data unavailable|Failed to (?:obtain|get) (?:mobile|app) access token/i;

function redact(text, env = process.env) {
  let result = String(text).replace(/\u001b\[[0-9;]*m/g, '');
  const values = Object.entries(env)
    .filter(([key, value]) => value && /(?:PASSWORD|SECRET|TOKEN|OPEN_ID|^weilai$|COOKIE)/i.test(key))
    .map(([, value]) => String(value))
    .sort((a, b) => b.length - a.length);
  for (const value of values) result = result.split(value).join('[已隐藏]');
  return result
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, (match, offset, full) => {
      const before = full.slice(Math.max(0, offset - 3), offset);
      return /\*\*$/.test(before) ? match : '[微软账号]';
    })
    .replace(/Bearer\s+\S+/gi, 'Bearer [已隐藏]')
    .replace(/(https?:\/\/[^\s?]+)\?[^\s]+/g, '$1?[参数已隐藏]');
}

function parseProxyUrl(raw) {
  const value = String(raw || '').trim();
  if (!value) return null;
  let parsed;
  try {
    parsed = new URL(/^[a-z][a-z\d+.-]*:\/\//i.test(value) ? value : `http://${value}`);
  } catch {
    return null;
  }
  if (!['http:', 'https:', 'socks4:', 'socks5:'].includes(parsed.protocol)) return null;
  if (!parsed.hostname) return null;
  const defaultPort = parsed.protocol === 'https:' ? '443' : parsed.protocol === 'http:' ? '80' : '';
  const port = parsed.port || defaultPort;
  const portNum = Number(port);
  if (!Number.isInteger(portNum) || portNum < 1 || portNum > 65535) return null;
  return {
    url: `${parsed.protocol}//${parsed.hostname}`,
    port: String(portNum),
  };
}

function extractStreak(output) {
  let maxStreak = 0;
  for (const match of String(output).matchAll(/(?:连续计数|\bstreakCounter)=(\d+)/g)) {
    const value = Number(match[1]);
    if (Number.isFinite(value) && value > maxStreak) maxStreak = value;
  }
  return maxStreak;
}

function parseAccountResult(line) {
  if (!line || (!line.includes('[ACCOUNT-END]') && !line.includes('[ACCOUNT-SKIP]'))) return null;
  const statusMatch = line.match(/\bstatus=([a-z-]+)\b/i);
  if (!statusMatch) return null;
  const activitiesMatch = line.match(
    /\bactivities:\s*(\d+)\s+completed,\s*(\d+)\s+incomplete,\s*(\d+)\s+unavailable,\s*(\d+)\s+not applicable\b/i,
  );
  const reasonMatch = line.match(/\breason=("(?:\\.|[^"])*"|[^|]+)/);
  let reason = '';
  if (reasonMatch) {
    const rawReason = reasonMatch[1].trim();
    if (rawReason.startsWith('"') && rawReason.endsWith('"')) {
      try {
        reason = JSON.parse(rawReason);
      } catch {
        reason = rawReason.slice(1, -1);
      }
    } else {
      reason = rawReason;
    }
  }
  return {
    status: statusMatch[1].toLowerCase(),
    completed: activitiesMatch ? Number(activitiesMatch[1]) : null,
    incomplete: activitiesMatch ? Number(activitiesMatch[2]) : null,
    unavailable: activitiesMatch ? Number(activitiesMatch[3]) : null,
    reason,
  };
}

function parseRunEnd(line) {
  if (!line || !line.includes('[RUN-END]')) return null;

  const enMatch = line.match(
    /accountsProcessed=(\d+)\s*\|\s*pointsGained=(-?\d+|unknown)\s*\|\s*previousBalance=(\d+)\s*\|\s*currentBalance=(\d+)\s*\|\s*runtimeMinutes=([\d.]+)(?:\s*\|\s*status=([a-z-]+))?/i,
  );
  if (enMatch) {
    const status = (enMatch[6] || (line.includes('Completed all accounts') ? 'completed' : 'interrupted')).toLowerCase();
    return {
      accountsProcessed: enMatch[1],
      pointsGained: enMatch[2],
      previousBalance: enMatch[3],
      currentBalance: enMatch[4],
      runtimeMinutes: enMatch[5],
      status,
      completedAll: status === 'completed',
    };
  }

  const zhMatch = line.match(
    /处理账户数=(\d+)\s*\|\s*获得积分=(-?\d+)\s*\|\s*原余额=(\d+)\s*\|\s*现余额=(\d+)\s*\|\s*运行分钟数=([\d.]+)/,
  );
  if (zhMatch) {
    const completedAll = line.includes('全部账户完成');
    return {
      accountsProcessed: zhMatch[1],
      pointsGained: zhMatch[2],
      previousBalance: zhMatch[3],
      currentBalance: zhMatch[4],
      runtimeMinutes: zhMatch[5],
      status: completedAll ? 'completed' : 'interrupted',
      completedAll,
    };
  }

  return null;
}

function createLogCollector(options = {}) {
  const tailLimit = Number.isInteger(options.tailLimit) && options.tailLimit > 0 ? options.tailLimit : TAIL_LINE_LIMIT;
  const highlightLimit =
    Number.isInteger(options.highlightLimit) && options.highlightLimit > 0
      ? options.highlightLimit
      : HIGHLIGHT_LINE_LIMIT;
  const tail = [];
  const highlights = [];
  let seq = 0;

  return {
    push(line) {
      const entry = { seq: seq++, line };
      tail.push(entry);
      if (tail.length > tailLimit) tail.shift();
      if (HIGHLIGHT_PATTERN.test(line)) {
        highlights.push(entry);
        if (highlights.length > highlightLimit) highlights.shift();
      }
    },
    getLines() {
      const merged = new Map();
      for (const entry of highlights) merged.set(entry.seq, entry.line);
      for (const entry of tail) merged.set(entry.seq, entry.line);
      return [...merged.entries()].sort((a, b) => a[0] - b[0]).map(([, line]) => line);
    },
  };
}

function detectLoginPromptAlert(line) {
  const text = String(line || '');
  const numberMatch = text.match(/Please approve login and select number:\s*(\d+)/i);
  if (numberMatch) {
    return {
      key: `auth-number:${numberMatch[1]}`,
      title: '微软 Rewards · 需要验证器确认',
      message: `请在 Microsoft Authenticator 中确认登录并选择数字：${numberMatch[1]}`,
    };
  }
  if (/Please approve login on your authenticator app/i.test(text)) {
    return {
      key: 'auth-approve',
      title: '微软 Rewards · 需要验证器确认',
      message: '请在 Microsoft Authenticator 中确认本次微软账号登录请求。',
    };
  }
  const inputMatch = text.match(/\[LOGIN-INPUT\]\s*等待输入[^：]*：(.+)/);
  if (inputMatch) {
    return {
      key: `login-input:${inputMatch[1].slice(0, 60)}`,
      title: '微软 Rewards · 需要输入验证码',
      message: `微软登录正在等待输入：${inputMatch[1].trim()}\n\n请在青龙面板「环境变量」中编辑 QL_MS_LOGIN_INPUT 填入内容并保存，脚本读取后会自动清空。`,
    };
  }
  return null;
}

function diagnoseFailure(output, signal, accountResults = []) {
  const reasonsText = [output, ...accountResults.map(item => item.reason).filter(Boolean)].join('\n');
  if (signal) return '任务已被停止，尚未完成。';
  if (/Fraud_UserWarning|bot-score warning|BotScore/i.test(reasonsText)) {
    return '微软提示自动化风险，任务已停止。';
  }
  if (/密码不是.*正确密码|password.*incorrect|incorrect.*password/i.test(reasonsText)) {
    return '微软提示密码不正确，请修改青龙中的微软密码变量。';
  }
  if (/Service rate limit|HTTP 429/i.test(reasonsText)) {
    return '微软接口触发限流（HTTP 429），请等待冷却后再试。';
  }
  if (/Service rejected account access \(HTTP (?:401|403)\)/i.test(reasonsText)) {
    return '微软接口拒绝访问（HTTP 401/403），登录态可能失效或受限，请查看青龙任务日志。';
  }
  if (
    /LOGIN.*(?:错误|失败|未完成|timeout|failed|aborted)|Email-code authentication requires|TOTP secret is required|Recovery email is required|Passwordless authentication timeout|authenticat.*(?:failed|timeout)|No accounts/i.test(
      reasonsText,
    )
  ) {
    return '登录或账号验证未完成，请查看青龙任务日志（如需首次交互登录，请运行 --login-setup 并填入 QL_MS_LOGIN_INPUT）。';
  }
  if (/timeout|net::|ECONN|HTTP|Request deadline exceeded/i.test(reasonsText)) {
    return '网页或网络访问失败，请查看青龙任务日志。';
  }
  return '请查看青龙任务日志。';
}

function summarize(lines, code, signal, options = {}) {
  const output = lines.join('\n');
  const streak = extractStreak(output);

  if (options.loginSetup) {
    if (code === 0 && !signal) {
      return {
        title: '微软 Rewards · 登录会话已保存',
        message: '已完成微软账号登录并持久化桌面与移动端会话，后续定时任务将直接复用。',
      };
    }
    let reason = '登录未完成，请查看青龙任务日志。';
    if (signal) reason = '登录流程已被停止，尚未完成。';
    else if (/密码不是.*正确密码|password.*incorrect|incorrect.*password/i.test(output)) {
      reason = '微软提示密码不正确，请检查青龙中的 ACCOUNT_1_PASSWORD 变量。';
    } else if (/Manual (?:code|email|TOTP) input failed|timed out|Passwordless authentication timeout/i.test(output)) {
      reason = '等待验证码或验证器确认超时，请重新触发 --login-setup 并在提示后及时填入 QL_MS_LOGIN_INPUT。';
    }
    return { title: '微软 Rewards · 登录未完成', message: reason };
  }

  if (code === 0 && lines.some(line => line.includes('[RUN-SKIP]'))) {
    return {
      title: '微软 Rewards · 今日已运行',
      message: '今天已成功执行过，按设置跳过重复运行。' + (streak > 0 ? `\n\n已连续 ${streak} 天` : ''),
    };
  }

  const final = [...lines].reverse().find(line => line.includes('[RUN-END]'));
  const summary = parseRunEnd(final);
  const accountResults = lines.map(parseAccountResult).filter(Boolean);
  const allAccountsFailed =
    accountResults.length > 0 &&
    accountResults.every(
      item =>
        ['failed', 'cancelled', 'skipped'].includes(item.status) &&
        (item.completed === null || item.completed === 0),
    );
  const hasFailedAccount = accountResults.some(item => ['failed', 'cancelled', 'skipped'].includes(item.status));

  const skipped = [];
  if (
    /获取移动端访问令牌失败|App 仪表板不可用|App 可赚积分查询失败|App points unavailable|App data unavailable; skipping app activities|Failed to (?:obtain|get) (?:mobile|app) access token/i.test(
      output,
    )
  ) {
    skipped.push('App 签到未执行，移动端登录或接口暂不可用。');
  }
  if (/本轮跳过桌面阶段/.test(output)) {
    skipped.push('桌面搜索未执行，桌面端登录未完成。');
  }

  const ok = code === 0 && Boolean(summary) && summary.completedAll && !skipped.length && !hasFailedAccount;
  const partial =
    code === 0 &&
    Boolean(summary) &&
    !allAccountsFailed &&
    (summary.status === 'partial' || (summary.completedAll && (skipped.length > 0 || hasFailedAccount)));

  const parts = [];
  const hasMeaningfulPoints =
    Boolean(summary) &&
    !(summary.pointsGained === 'unknown' && summary.previousBalance === '0' && summary.currentBalance === '0');
  if (summary && hasMeaningfulPoints && (code === 0 || lines.some(line => line.includes('[POINTS]')))) {
    const gainedText = summary.pointsGained === 'unknown' ? '未知' : summary.pointsGained;
    parts.push(
      `账号数：${summary.accountsProcessed}\n本次积分：${gainedText}\n积分余额：${summary.previousBalance} → ${summary.currentBalance}\n用时：${summary.runtimeMinutes} 分钟`,
    );
  }
  if (streak > 0) parts.push(`已连续 ${streak} 天`);
  parts.push(...skipped);

  if (!ok && !partial) {
    parts.push(diagnoseFailure(output, signal, accountResults));
  } else if (partial && !skipped.length) {
    const reason = diagnoseFailure(output, signal, accountResults);
    if (reason !== '请查看青龙任务日志。') parts.push(reason);
    else parts.push('部分活动未能完成，请查看青龙任务日志。');
  }

  return {
    title: `微软 Rewards · ${ok ? '完成' : partial ? '部分完成' : '未完成'}`,
    message: parts.join('\n\n'),
  };
}

function childEnvironment(env = process.env, options = {}) {
  const result = {};
  const allowed =
    /^(PATH|HOME|NODE_PATH|LANG|LC_ALL|TMPDIR|SSL_CERT_FILE|SSL_CERT_DIR|NODE_EXTRA_CA_CERTS|PLAYWRIGHT_BROWSERS_PATH|NODE_USE_ENV_PROXY|HTTP_PROXY|HTTPS_PROXY|NO_PROXY|http_proxy|https_proxy|no_proxy|FORCE_HEADLESS)$/;
  for (const [key, value] of Object.entries(env)) {
    if (value === undefined) continue;
    if (allowed.test(key) || /^ACCOUNT_[1-9]\d*_/.test(key) || /^CONFIG_/.test(key)) {
      result[key] = value;
    }
  }

  const containerProxy = parseProxyUrl(env.HTTPS_PROXY || env.HTTP_PROXY || env.https_proxy || env.http_proxy);
  for (const key of Object.keys(result).filter(item => /^ACCOUNT_[1-9]\d*_EMAIL$/.test(item))) {
    const prefix = key.slice(0, -5);
    result[`${prefix}LANG_CODE`] ??= 'zh-CN';
    result[`${prefix}GEO_LOCALE`] ??= 'auto';
    result[`${prefix}SAVE_FINGERPRINT_MOBILE`] ??= 'true';
    result[`${prefix}SAVE_FINGERPRINT_DESKTOP`] ??= 'true';
    if (!result[`${prefix}PROXY_URL`] && containerProxy) {
      result[`${prefix}PROXY_URL`] = containerProxy.url;
      result[`${prefix}PROXY_PORT`] = containerProxy.port;
      result[`${prefix}PROXY_HTTP`] ??= 'true';
    }
  }

  result.TZ = 'Asia/Shanghai';
  result.NO_COLOR = '1';
  result.FORCE_HEADLESS = '1';
  result.NODE_USE_ENV_PROXY = '1';

  if (options.loginSetup) {
    result.BING_LOGIN_INPUT_ENABLE = '1';
    if (env.QL_DB_PATH) result.QL_DB_PATH = env.QL_DB_PATH;
  }

  return result;
}

function runDryCheck(appDir, env = process.env) {
  if (!env.ACCOUNT_1_EMAIL?.trim()) {
    throw new Error('尚未配置 ACCOUNT_1_EMAIL。');
  }
  const configPath = path.join(appDir, 'config.json');
  if (!fs.existsSync(configPath)) {
    throw new Error(`未找到配置文件：${configPath}`);
  }
  const rawConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  const validatorPath = path.join(appDir, 'dist/config/Validator.js');
  if (!fs.existsSync(validatorPath)) {
    throw new Error(`尚未构建 dist 产物：${validatorPath}`);
  }
  const { validateConfig } = require(validatorPath);
  const warnings = [];
  const validated = validateConfig(rawConfig, { onWarning: message => warnings.push(message) });
  if (warnings.length) {
    throw new Error(`config.json 存在校验告警：${warnings.join('; ')}`);
  }

  const patchrightPath = require.resolve('patchright', { paths: [appDir] });
  const patchright = require(patchrightPath);
  const executablePath = patchright.chromium.executablePath();
  if (!executablePath || !fs.existsSync(executablePath)) {
    throw new Error(`未找到 Patchright Chromium 可执行文件：${executablePath || '(empty)'}`);
  }

  const enabledWorkers = Object.entries(validated.workers)
    .filter(([, enabled]) => enabled)
    .map(([name]) => name);
  const childEnv = childEnvironment(env);
  const proxyActive = Boolean(childEnv.ACCOUNT_1_PROXY_URL && childEnv.ACCOUNT_1_PROXY_PORT);

  console.log(
    `微软 Rewards 配置检查通过：rewardsMode=${validated.rewardsMode}，已启用 ${enabledWorkers.length} 个 worker，searchDelay=${validated.searchSettings.searchDelay.min}-${validated.searchSettings.searchDelay.max}，readDelay=${validated.searchSettings.readDelay.min}-${validated.searchSettings.readDelay.max}，visitTime=${validated.searchSettings.searchResultVisitTime}，proxy=${proxyActive ? 'yes' : 'no'}，chromium=ok（未发送网络请求或通知）。`,
  );
  return { validated, executablePath, enabledWorkers, proxyActive };
}

async function main(argv = process.argv.slice(2)) {
  const appDir = path.join(__dirname, 'bing_rewards');
  const dryRun = argv.includes('--dry-run');
  const loginSetup = argv.includes('--login-setup');
  const now = argv.includes('--now');
  const reuse = argv.includes('--reuse');

  if (dryRun) {
    try {
      runDryCheck(appDir);
    } catch (error) {
      console.error(redact(error instanceof Error ? error.message : String(error)));
      process.exitCode = 2;
    }
    return;
  }

  const collector = createLogCollector();
  let result;
  if (!process.env.ACCOUNT_1_EMAIL?.trim()) {
    console.error('尚未配置 ACCOUNT_1_EMAIL。');
    result = { title: '微软 Rewards · 未完成', message: '青龙中尚未配置微软登录邮箱。' };
    process.exitCode = 2;
  } else {
    if (!loginSetup && !now) {
      const seconds = randomInt(0, RANDOM_START_MAX_SECONDS + 1);
      const startAt = new Date(Date.now() + seconds * 1000).toLocaleTimeString('zh-CN', {
        timeZone: 'Asia/Shanghai',
      });
      console.log(`随机启动：等待 ${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒，预计北京时间 ${startAt} 开始。`);
      await delay(seconds * 1000);
    }

    const setupArgs = loginSetup
      ? [
          '--require',
          path.join(__dirname, 'bing_rewards_login_input.js'),
          'dist/session/RegenerateSessions.js',
          '--platform',
          'both',
          ...(reuse ? ['--reuse'] : []),
        ]
      : ['dist/index.js'];

    const child = spawn(process.execPath, setupArgs, {
      cwd: appDir,
      env: childEnvironment(process.env, { loginSetup }),
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    const recentAlerts = new Map();
    const pendingAlerts = new Set();
    const maybeNotifyLoginPrompt = cleanLine => {
      if (!loginSetup || !isEnabled()) return;
      const alert = detectLoginPromptAlert(cleanLine);
      if (!alert) return;
      const lastSent = recentAlerts.get(alert.key) || 0;
      if (Date.now() - lastSent < LOGIN_ALERT_COOLDOWN_MS) return;
      recentAlerts.set(alert.key, Date.now());
      const timestamp = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
      const task = sendFeishuDirect(alert.title, `${timestamp}（北京时间）\n\n${alert.message}`).catch(error => {
        console.error(`登录验证飞书提醒发送失败：${redact(error.message)}`);
      });
      pendingAlerts.add(task);
      task.finally(() => pendingAlerts.delete(task));
    };

    const record = line => {
      const clean = redact(line).slice(0, 16384);
      console.log(clean);
      collector.push(clean);
      maybeNotifyLoginPrompt(clean);
    };

    const readers = [child.stdout, child.stderr].map(input => readline.createInterface({ input }));
    readers.forEach(reader => reader.on('line', record));

    const stopTerm = () => child.kill('SIGTERM');
    const stopInt = () => child.kill('SIGINT');
    process.on('SIGTERM', stopTerm);
    process.on('SIGINT', stopInt);

    const outcome = await new Promise(resolve => {
      child.once('error', () => {
        record('任务进程无法启动。');
        resolve({ code: 1, signal: null });
      });
      child.once('close', (code, signal) => resolve({ code, signal }));
    });

    process.removeListener('SIGTERM', stopTerm);
    process.removeListener('SIGINT', stopInt);
    if (pendingAlerts.size) await Promise.allSettled([...pendingAlerts]);

    result = summarize(collector.getLines(), outcome.code, outcome.signal, { loginSetup });
    process.exitCode = outcome.code === 0 && !/(未完成|部分完成)$/.test(result.title) ? 0 : 1;
  }

  if (isEnabled()) {
    try {
      const timestamp = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
      await sendFeishuDirect(result.title, `${timestamp}（北京时间）\n\n${result.message}`);
      console.log('飞书私聊通知发送成功。');
    } catch (error) {
      // 通知失败不应把已完成的签到/积分任务标记为失败。
      console.error(`飞书通知失败（不影响任务结果）：${redact(error.message)}`);
    }
  }
}

module.exports = {
  RANDOM_START_MAX_SECONDS,
  redact,
  parseProxyUrl,
  extractStreak,
  parseAccountResult,
  parseRunEnd,
  createLogCollector,
  detectLoginPromptAlert,
  summarize,
  childEnvironment,
  runDryCheck,
  main,
};

if (require.main === module) {
  main().catch(() => {
    console.error('微软任务包装器异常，请检查脚本。');
    process.exitCode = 1;
  });
}
