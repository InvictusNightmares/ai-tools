'use strict';
// All accounts, secrets, and OTP codes in these offline tests are synthetic.

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { DatabaseSync } = require('node:sqlite');

const {
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
} = require('./bing_rewards_notify');
const {
  consumeLoginInput,
  installLoginInputBridge,
} = require('./bing_rewards_login_input');

test('redact removes ANSI sequences, real emails, env secrets, bearer tokens, and URL queries while preserving masked hints', () => {
  const env = {
    ACCOUNT_1_PASSWORD: 'SYNTHETIC_PASSWORD_123',
    QL_FEISHU_APP_SECRET: 'SYNTHETIC_FEISHU_SECRET',
    weilai: 'SYNTHETIC_WEILAI_TOKEN',
  };
  const input =
    '\u001b[32muser@example.com\u001b[0m pass=SYNTHETIC_PASSWORD_123 secret=SYNTHETIC_FEISHU_SECRET ' +
    'Authorization: Bearer SYNTHETIC_BEARER_XYZ https://login.live.com/oauth?code=12345&state=abc ' +
    'hint="ab*****9@example.com"';
  const out = redact(input, env);
  assert.doesNotMatch(out, /user@example\.com|SYNTHETIC_PASSWORD_123|SYNTHETIC_FEISHU_SECRET|SYNTHETIC_BEARER_XYZ|code=12345|\u001b/);
  assert.match(out, /\[微软账号\]/);
  assert.match(out, /Bearer \[已隐藏\]/);
  assert.match(out, /https:\/\/login\.live\.com\/oauth\?\[参数已隐藏\]/);
  assert.match(out, /hint="ab\*\*\*\*\*9@example\.com"/);
});

test('extractStreak reads v5 streakCounter and legacy Chinese streaks while ignoring weekly streak=N/M puzzle counts', () => {
  const v5Output = [
    '[REACT-PARSE] Snapshot complete | offers=48 | reportable=32 | streaks=3 | streakProtectionEnabled=true | streakCounter=2 | level=2',
    '[STREAKS] Bing Search Streak completed today | streak=5/7',
    '[STREAKS] Daily Set Streak completed today | streak=3/3',
  ].join('\n');
  assert.equal(extractStreak(v5Output), 2);

  const updatedV5Output = [
    '[REACT-PARSE] Snapshot complete | offers=48 | reportable=32 | streaks=3 | streakProtectionEnabled=true | streakCounter=9 | level=2',
    '[REACT-PARSE] Snapshot complete | offers=48 | reportable=32 | streaks=3 | streakProtectionEnabled=true | streakCounter=10 | level=2',
  ].join('\n');
  assert.equal(extractStreak(updatedV5Output), 10);

  const zhOutput =
    '[REACT-PARSE] 快照完成 | offers=52 | 可上报=34 | streaks=3 | 连续保护已启用=false | 连续计数=7 | 等级=2';
  assert.equal(extractStreak(zhOutput), 7);

  assert.equal(
    extractStreak('[REACT-PARSE] Snapshot complete | offers=40 | streaks=3 | streakCounter=null\n[STREAKS] Bing App Streak completed today | streak=4/7'),
    0,
  );
});

test('summarize distinguishes real completed, partial, and 100%-failed single-account v5 runs (where RUN-END logs status=partial and exit code is 0)', () => {
  const completed = summarize(
    [
      '[REACT-PARSE] Snapshot complete | offers=50 | streaks=3 | streakCounter=12 | level=2',
      '[ACCOUNT-END] Finished account: [微软账号] | pointsGained=315 | previousBalance=1155 | currentBalance=1470 | durationSeconds=11070.0 | status=completed | activities: 6 completed, 0 incomplete, 0 unavailable, 0 not applicable',
      '[RUN-END] Completed all accounts | accountsProcessed=1 | pointsGained=315 | previousBalance=1155 | currentBalance=1470 | runtimeMinutes=184.5 | status=completed',
    ],
    0,
    null,
  );
  assert.equal(completed.title, '微软 Rewards · 完成');
  assert.match(completed.message, /本次积分：315/);
  assert.match(completed.message, /积分余额：1155 → 1470/);
  assert.match(completed.message, /用时：184\.5 分钟/);
  assert.match(completed.message, /已连续 12 天/);

  const partialApp = summarize(
    [
      '[LOGIN-APP] Failed to get app access token: oauth redirect failed',
      '[POINTS] App points unavailable',
      '[ACCOUNT-END] Finished account: [微软账号] | pointsGained=150 | previousBalance=1000 | currentBalance=1150 | durationSeconds=5412.0 | status=partial | activities: 4 completed, 0 incomplete, 1 unavailable, 0 not applicable',
      '[RUN-END] Completed all accounts | accountsProcessed=1 | pointsGained=150 | previousBalance=1000 | currentBalance=1150 | runtimeMinutes=90.2 | status=partial',
    ],
    0,
    null,
  );
  assert.equal(partialApp.title, '微软 Rewards · 部分完成');
  assert.match(partialApp.message, /App 签到未执行/);

  // Real v5 behavior on single-account login failure: process exits 0 and RUN-END logs status=partial,
  // while ACCOUNT-END logs status=failed with 0 completed activities. Must be classified as 未完成 with reason!
  const loginFailedV5 = summarize(
    [
      '[FLOW] Account flow failed for [微软账号]: Email-code authentication requires interactive stdin; unavailable in background mode',
      '[ACCOUNT-END] Finished account: [微软账号] | pointsGained=unknown | previousBalance=0 | currentBalance=0 | durationSeconds=12.4 | status=failed | reason="Email-code authentication requires interactive stdin; unavailable in background mode" | activities: 0 completed, 0 incomplete, 0 unavailable, 0 not applicable',
      '[RUN-END] Completed all accounts | accountsProcessed=1 | pointsGained=unknown | previousBalance=0 | currentBalance=0 | runtimeMinutes=0.2 | status=partial',
    ],
    0,
    null,
  );
  assert.equal(loginFailedV5.title, '微软 Rewards · 未完成');
  assert.match(loginFailedV5.message, /--login-setup/);
  assert.doesNotMatch(loginFailedV5.message, /积分余额：0 → 0/);

  const rateLimitedV5 = summarize(
    [
      '[ACCOUNT-SKIP] Finished account: [微软账号] | pointsGained=unknown | previousBalance=0 | currentBalance=0 | durationSeconds=5.0 | status=skipped | reason="Service rate limit; retry after 2026-11-28T12:00:00.000Z" | activities: 0 completed, 0 incomplete, 0 unavailable, 0 not applicable',
      '[RUN-END] Completed all accounts | accountsProcessed=1 | pointsGained=unknown | previousBalance=0 | currentBalance=0 | runtimeMinutes=0.1 | status=partial',
    ],
    0,
    null,
  );
  assert.equal(rateLimitedV5.title, '微软 Rewards · 未完成');
  assert.match(rateLimitedV5.message, /HTTP 429/);

  const unknownPointsCompleted = summarize(
    [
      '[ACCOUNT-END] Finished account: [微软账号] | pointsGained=unknown | previousBalance=1000 | currentBalance=1000 | durationSeconds=300.0 | status=completed | activities: 2 completed, 0 incomplete, 0 unavailable, 0 not applicable',
      '[RUN-END] Completed all accounts | accountsProcessed=1 | pointsGained=unknown | previousBalance=1000 | currentBalance=1000 | runtimeMinutes=5.0 | status=completed',
    ],
    0,
    null,
  );
  assert.equal(unknownPointsCompleted.title, '微软 Rewards · 完成');
  assert.match(unknownPointsCompleted.message, /本次积分：未知/);

  const botWarning = summarize(['[WARN] Fraud_UserWarning_BotScore_UX detected'], 1, null);
  assert.equal(botWarning.title, '微软 Rewards · 未完成');
  assert.match(botWarning.message, /自动化风险/);

  const parsedAccount = parseAccountResult(
    '[ACCOUNT-END] Finished account: [微软账号] | pointsGained=unknown | previousBalance=0 | currentBalance=0 | durationSeconds=8.1 | status=failed | reason="Email-code authentication requires interactive stdin" | activities: 0 completed, 0 incomplete, 0 unavailable, 0 not applicable',
  );
  assert.deepEqual(parsedAccount, {
    status: 'failed',
    completed: 0,
    incomplete: 0,
    unavailable: 0,
    reason: 'Email-code authentication requires interactive stdin',
  });
});

test('createLogCollector preserves early streakCounter and app-failure lines across >1500 log lines', () => {
  const collector = createLogCollector({ tailLimit: 50, highlightLimit: 100 });
  collector.push('[REACT-PARSE] Snapshot complete | offers=48 | streaks=3 | streakCounter=14 | level=2');
  collector.push('[LOGIN-APP] Failed to get app access token: invalid_grant');
  for (let i = 0; i < 1500; i++) {
    collector.push(`[SEARCH] regular log line #${i}`);
  }
  collector.push(
    '[ACCOUNT-END] Finished account: [微软账号] | pointsGained=180 | previousBalance=1000 | currentBalance=1180 | durationSeconds=14400.0 | status=partial | activities: 5 completed, 0 incomplete, 1 unavailable, 0 not applicable',
  );
  collector.push(
    '[RUN-END] Completed all accounts | accountsProcessed=1 | pointsGained=180 | previousBalance=1000 | currentBalance=1180 | runtimeMinutes=240.0 | status=partial',
  );

  const summary = summarize(collector.getLines(), 0, null);
  assert.equal(summary.title, '微软 Rewards · 部分完成');
  assert.match(summary.message, /已连续 14 天/);
  assert.match(summary.message, /App 签到未执行/);
});

test('summarize preserves backward compatibility with legacy Chinese RUN-END and RUN-SKIP logs', () => {
  const legacyOk = summarize(
    [
      '[REACT-PARSE] 快照完成 | offers=52 | 可上报=34 | streaks=3 | 连续计数=7 | 等级=2',
      '[RUN-END] 全部账户完成 | 处理账户数=1 | 获得积分=720 | 原余额=435 | 现余额=1155 | 运行分钟数=266.2',
    ],
    0,
    null,
  );
  assert.equal(legacyOk.title, '微软 Rewards · 完成');
  assert.match(legacyOk.message, /本次积分：720/);
  assert.match(legacyOk.message, /已连续 7 天/);

  const skip = summarize(['[REACT-PARSE] 连续计数=8', '[RUN-SKIP] skipped today'], 0, null);
  assert.equal(skip.title, '微软 Rewards · 今日已运行');
  assert.match(skip.message, /已连续 8 天/);
});

test('summarize handles loginSetup success and timeout outcomes', () => {
  const ok = summarize(['[SESSION] Saved session'], 0, null, { loginSetup: true });
  assert.equal(ok.title, '微软 Rewards · 登录会话已保存');

  const timeout = summarize(['[LOGIN-CODE] Manual code input failed or timed out'], 1, null, { loginSetup: true });
  assert.equal(timeout.title, '微软 Rewards · 登录未完成');
  assert.match(timeout.message, /QL_MS_LOGIN_INPUT/);
});

test('childEnvironment isolates unrelated secrets and derives account proxy from container proxy', () => {
  const env = {
    PATH: '/usr/bin',
    PLAYWRIGHT_BROWSERS_PATH: '/ql/data/browsers',
    HTTP_PROXY: 'http://172.18.0.1:7898',
    HTTPS_PROXY: 'http://172.18.0.1:7898',
    NO_PROXY: 'localhost,127.0.0.1',
    ACCOUNT_1_EMAIL: 'synthetic1@example.com',
    ACCOUNT_1_PASSWORD: 'SYNTHETIC_PASSWORD',
    ACCOUNT_2_EMAIL: 'synthetic2@example.com',
    ACCOUNT_2_PROXY_URL: 'http://127.0.0.1',
    ACCOUNT_2_PROXY_PORT: '1080',
    QL_FEISHU_APP_ID: 'cli_synthetic',
    QL_FEISHU_APP_SECRET: 'secret_synthetic',
    QL_FEISHU_OPEN_ID: 'ou_synthetic',
    QL_MS_LOGIN_INPUT: '123456',
    weilai: 'synthetic_nio',
    GLADOS_COOKIE: 'synthetic_glados',
  };

  const child = childEnvironment(env);
  assert.equal(child.QL_FEISHU_APP_ID, undefined);
  assert.equal(child.QL_FEISHU_APP_SECRET, undefined);
  assert.equal(child.QL_FEISHU_OPEN_ID, undefined);
  assert.equal(child.QL_MS_LOGIN_INPUT, undefined);
  assert.equal(child.weilai, undefined);
  assert.equal(child.GLADOS_COOKIE, undefined);

  assert.equal(child.ACCOUNT_1_LANG_CODE, 'zh-CN');
  assert.equal(child.ACCOUNT_1_GEO_LOCALE, 'auto');
  assert.equal(child.ACCOUNT_1_SAVE_FINGERPRINT_MOBILE, 'true');
  assert.equal(child.ACCOUNT_1_SAVE_FINGERPRINT_DESKTOP, 'true');
  assert.equal(child.ACCOUNT_1_PROXY_URL, 'http://172.18.0.1');
  assert.equal(child.ACCOUNT_1_PROXY_PORT, '7898');
  assert.equal(child.ACCOUNT_1_PROXY_HTTP, 'true');

  // Explicit per-account proxy must not be overwritten.
  assert.equal(child.ACCOUNT_2_PROXY_URL, 'http://127.0.0.1');
  assert.equal(child.ACCOUNT_2_PROXY_PORT, '1080');
  assert.equal(child.FORCE_HEADLESS, '1');
  assert.equal(child.NODE_USE_ENV_PROXY, '1');
  assert.equal(child.TZ, 'Asia/Shanghai');

  assert.equal(parseProxyUrl('not a url'), null);
  assert.equal(parseProxyUrl('ftp://127.0.0.1:21'), null);
  assert.deepEqual(parseProxyUrl('http://172.18.0.1:7898'), { url: 'http://172.18.0.1', port: '7898' });
});

test('detectLoginPromptAlert recognizes authenticator number and LOGIN-INPUT prompts', () => {
  const num = detectLoginPromptAlert('[LOGIN-PASSWORDLESS] Please approve login and select number: 42');
  assert.equal(num.title, '微软 Rewards · 需要验证器确认');
  assert.match(num.message, /42/);

  const otp = detectLoginPromptAlert('[LOGIN-INPUT] 等待输入（请在青龙环境变量 QL_MS_LOGIN_INPUT 中填入）：Enter the 6-digit code');
  assert.equal(otp.title, '微软 Rewards · 需要输入验证码');
  assert.match(otp.message, /QL_MS_LOGIN_INPUT/);

  assert.equal(detectLoginPromptAlert('[INFO] normal line'), null);
});

test('bing_rewards_login_input consumes QL_MS_LOGIN_INPUT even with duplicate empty rows, clears all atomically, and cleans up on close', async () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'bing-login-input-'));
  const dbPath = path.join(tmpDir, 'database.sqlite');
  try {
    const db = new DatabaseSync(dbPath);
    db.exec(`
      CREATE TABLE Envs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        value VARCHAR(255),
        timestamp VARCHAR(255),
        status NUMBER,
        position NUMBER,
        name VARCHAR(255),
        remarks VARCHAR(255),
        createdAt DATETIME,
        updatedAt DATETIME
      );
      INSERT INTO Envs (value, status, name, remarks, createdAt, updatedAt)
      VALUES ('', 1, 'QL_MS_LOGIN_INPUT', 'primary', '2026-11-28 00:00:00 +00:00', '2026-11-28 00:00:00 +00:00');
      INSERT INTO Envs (value, status, name, remarks, createdAt, updatedAt)
      VALUES ('', 1, 'QL_MS_LOGIN_INPUT', 'duplicate-empty', '2026-11-28 00:01:00 +00:00', '2026-11-28 00:01:00 +00:00');
    `);
    db.close();

    assert.equal(consumeLoginInput(dbPath), null);

    const fakeStdin = { isTTY: false };
    const fakeReadline = { createInterface: () => { throw new Error('should be patched'); } };
    const logs = [];
    const restore = installLoginInputBridge({
      dbPath,
      pollMs: 50,
      stdin: fakeStdin,
      readlineModule: fakeReadline,
      log: msg => logs.push(msg),
    });

    try {
      assert.equal(fakeStdin.isTTY, true);
      const rl = fakeReadline.createInterface({ input: fakeStdin, output: process.stdout });

      const answerPromise = new Promise(resolve => {
        rl.question('Enter the 6-digit code (waiting 60s): ', resolve);
      });

      // Populate the OLDER row (id=1) while newer row (id=2) stays empty.
      setTimeout(() => {
        const writer = new DatabaseSync(dbPath);
        writer
          .prepare('UPDATE Envs SET value = ?, status = 0, updatedAt = ? WHERE id = 1')
          .run('  654321  ', '2026-11-28 00:02:00 +00:00');
        writer.close();
      }, 120);

      const answer = await answerPromise;
      assert.equal(answer, '654321');
      assert.ok(logs.some(line => line.includes('[LOGIN-INPUT] 等待输入')));
      assert.ok(logs.every(line => !line.includes('654321')));

      const verifier = new DatabaseSync(dbPath);
      const rows = verifier.prepare('SELECT id, value, status FROM Envs WHERE name = ? ORDER BY id').all('QL_MS_LOGIN_INPUT');
      verifier.close();
      assert.equal(rows.length, 2);
      for (const row of rows) {
        assert.equal(row.value, '');
        assert.equal(row.status, 1);
      }

      // Closing before input arrives must stop polling cleanly.
      const rl2 = fakeReadline.createInterface({ input: fakeStdin, output: process.stdout });
      let lateCalled = false;
      rl2.question('Enter code again: ', () => {
        lateCalled = true;
      });
      rl2.close();
      const writer2 = new DatabaseSync(dbPath);
      writer2.prepare('UPDATE Envs SET value = ?, status = 0 WHERE id = 1').run('999888');
      writer2.close();
      await new Promise(resolve => setTimeout(resolve, 150));
      assert.equal(lateCalled, false);
    } finally {
      restore();
    }

    // Also verify real `node --require` preload marks process.stdin.isTTY === true.
    const preloadCheck = spawnSync(
      process.execPath,
      [
        '--require',
        path.join(__dirname, 'bing_rewards_login_input.js'),
        '-e',
        'process.stdout.write(String(process.stdin.isTTY))',
      ],
      { env: { ...process.env, QL_DB_PATH: dbPath }, stdio: ['ignore', 'pipe', 'pipe'] },
    );
    assert.equal(preloadCheck.status, 0);
    assert.equal(preloadCheck.stdout.toString().trim(), 'true');
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('config.example.json preserves anti-restriction pacing and all enabled workers', () => {
  const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.example.json'), 'utf8'));
  assert.equal(RANDOM_START_MAX_SECONDS, 3 * 60 * 60);
  assert.equal(cfg.headless, true);
  assert.equal(cfg.clusters, 1);
  assert.equal(cfg.rewardsMode, 'browser');
  assert.equal(cfg.ensureStreakProtection, true);
  assert.equal(cfg.autoClaimPunchcardRewards, true);
  assert.equal(cfg.continueOnBotWarning, false);
  assert.equal(cfg.globalTimeout, '50sec');
  assert.equal(cfg.searchSettings.parallelSearching, false);
  assert.equal(cfg.searchSettings.clusterSearch, false);
  assert.equal(cfg.searchSettings.maxBonusSearches, 10);
  assert.equal(cfg.searchSettings.searchResultVisitTime, '20sec');
  assert.deepEqual(cfg.searchSettings.searchDelay, { min: '6min', max: '12min' });
  assert.deepEqual(cfg.searchSettings.readDelay, { min: '6min', max: '11min' });
  assert.equal(cfg.experimental.edgeBrowsing, true);
  for (const [worker, enabled] of Object.entries(cfg.workers)) {
    assert.equal(enabled, true, `expected worker ${worker} to be enabled`);
  }
  assert.equal(parseRunEnd('[RUN-END] invalid line'), null);
});
