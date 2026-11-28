'use strict';

const fs = require('node:fs');
const readline = require('node:readline');
const { DatabaseSync } = require('node:sqlite');

const DEFAULT_DB_PATH = '/ql/data/db/database.sqlite';
const DEFAULT_ENV_NAME = 'QL_MS_LOGIN_INPUT';
const DEFAULT_POLL_MS = 2000;

function formatSqliteTimestamp(date = new Date()) {
  return date.toISOString().replace('T', ' ').replace('Z', ' +00:00');
}

function consumeLoginInput(dbPath = process.env.QL_DB_PATH || DEFAULT_DB_PATH, envName = DEFAULT_ENV_NAME) {
  if (!dbPath || !fs.existsSync(dbPath)) return null;
  const db = new DatabaseSync(dbPath);
  try {
    db.exec('PRAGMA busy_timeout = 5000;');
    db.exec('BEGIN IMMEDIATE;');
    try {
      const row = db
        .prepare(
          "SELECT id, value FROM Envs WHERE name = ? AND TRIM(COALESCE(value, '')) != '' ORDER BY updatedAt DESC, id DESC LIMIT 1",
        )
        .get(envName);
      const value = typeof row?.value === 'string' ? row.value.trim() : '';
      if (!value) {
        db.exec('COMMIT;');
        return null;
      }
      db.prepare(
        "UPDATE Envs SET value = '', status = 1, updatedAt = ? WHERE name = ? AND (TRIM(COALESCE(value, '')) != '' OR status != 1)",
      ).run(formatSqliteTimestamp(), envName);
      db.exec('COMMIT;');
      return value;
    } catch (error) {
      try { db.exec('ROLLBACK;'); } catch { /* ignore rollback error */ }
      throw error;
    }
  } finally {
    db.close();
  }
}

function sanitizePrompt(promptText) {
  return String(promptText || '')
    .replace(/\r?\n/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 300);
}

function installLoginInputBridge(options = {}) {
  const dbPath = options.dbPath || process.env.QL_DB_PATH || DEFAULT_DB_PATH;
  const envName = options.envName || DEFAULT_ENV_NAME;
  const pollMs = Number.isFinite(options.pollMs) && options.pollMs >= 50 ? options.pollMs : DEFAULT_POLL_MS;
  const log = options.log || (msg => console.log(msg));
  const stdin = options.stdin || process.stdin;
  const rlModule = options.readlineModule || readline;

  try {
    Object.defineProperty(stdin, 'isTTY', {
      value: true,
      configurable: true,
      writable: true,
    });
  } catch {
    // Fallback if stdin.isTTY is non-configurable in a custom environment.
  }

  const originalCreateInterface = rlModule.createInterface;

  rlModule.createInterface = function patchedCreateInterface(ifaceOptions, ...rest) {
    const usesStdin = !ifaceOptions || ifaceOptions.input === stdin || ifaceOptions.input === process.stdin;
    if (!usesStdin) {
      return originalCreateInterface.call(this, ifaceOptions, ...rest);
    }

    let closed = false;
    let activeTimer = null;

    const clearPending = () => {
      if (activeTimer) {
        clearTimeout(activeTimer);
        activeTimer = null;
      }
    };

    return {
      question(query, callback) {
        if (closed) return;
        const promptSummary = sanitizePrompt(query);
        log(`[LOGIN-INPUT] 等待输入（请在青龙环境变量 ${envName} 中填入最新验证码/邮箱后保存）：${promptSummary}`);

        const poll = () => {
          if (closed) return;
          try {
            const value = consumeLoginInput(dbPath, envName);
            if (value) {
              closed = true;
              clearPending();
              log(`[LOGIN-INPUT] 已读取 ${envName} 并自动清空。`);
              if (typeof callback === 'function') callback(value);
              return;
            }
          } catch (error) {
            log(`[LOGIN-INPUT] 读取 ${envName} 失败，稍后重试：${error instanceof Error ? error.message : String(error)}`);
          }
          if (!closed) {
            activeTimer = setTimeout(poll, pollMs);
          }
        };

        poll();
      },
      close() {
        closed = true;
        clearPending();
      },
      on() {
        return this;
      },
      once() {
        return this;
      },
      removeListener() {
        return this;
      },
    };
  };

  return () => {
    rlModule.createInterface = originalCreateInterface;
  };
}

module.exports = {
  DEFAULT_DB_PATH,
  DEFAULT_ENV_NAME,
  consumeLoginInput,
  installLoginInputBridge,
};

if (require.main === module) {
  console.error('此脚本需通过 node --require bing_rewards_login_input.js 预加载，不可直接运行。');
  process.exitCode = 2;
} else if (process.env.BING_LOGIN_INPUT_ENABLE === '1' || require.main === undefined) {
  installLoginInputBridge();
}
