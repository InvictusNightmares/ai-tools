const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const scriptPath = path.resolve(__dirname, '..', 'setup-opencode-bailian.js');

const {
  PROVIDER_KEY,
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  parseArgs,
  buildProviderConfig,
  mergeProviderConfig,
  readConfigFile,
  writeBackupFile,
  getConfigPath,
  getInstallPlan,
  getOpencodeCommand,
  getOpencodeCandidates,
  buildManualInstallHint,
  validateConfig,
  resolveRuntimeOptions,
  ensureOpencodeInstalled,
  formatSuccessLines,
  run,
} = require(scriptPath);

function createExpectedProviderConfig({
  apiKey = 'token-123',
  baseURL = DEFAULT_BASE_URL,
} = {}) {
  return {
    npm: '@ai-sdk/openai-compatible',
    name: '启源阿里百炼Token Plan',
    options: {
      apiKey,
      baseURL,
    },
    models: {
      'qwen3.6-plus': {
        name: 'Qwen3.6 Plus',
        modalities: {
          input: ['text', 'image'],
          output: ['text'],
        },
        options: {
          thinking: {
            type: 'enabled',
            budgetTokens: 8192,
          },
        },
        limit: {
          context: 1000000,
          output: 65536,
        },
      },
      'MiniMax-M2.5': {
        name: 'MiniMax M2.5',
        modalities: {
          input: ['text'],
          output: ['text'],
        },
        options: {
          thinking: {
            type: 'enabled',
            budgetTokens: 8192,
          },
        },
        limit: {
          context: 196608,
          output: 24576,
        },
      },
      'glm-5': {
        name: 'GLM-5',
        modalities: {
          input: ['text'],
          output: ['text'],
        },
        options: {
          thinking: {
            type: 'enabled',
            budgetTokens: 8192,
          },
        },
        limit: {
          context: 202752,
          output: 16384,
        },
      },
      'deepseek-v3.2': {
        name: 'DeepSeek V3.2',
        modalities: {
          input: ['text'],
          output: ['text'],
        },
        limit: {
          context: 131072,
          output: 16384,
        },
      },
    },
  };
}

test('exports the Bailian setup contract', () => {
  assert.equal(PROVIDER_KEY, 'bailian-token-plan');
  assert.equal(
    DEFAULT_BASE_URL,
    'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
  );
  assert.equal(DEFAULT_MODEL, 'qwen3.6-plus');

  assert.equal(typeof parseArgs, 'function');
  assert.equal(typeof buildProviderConfig, 'function');
  assert.equal(typeof mergeProviderConfig, 'function');
});

test('parseArgs reads api key, base url, model, dry-run, and force flags', () => {
  const argv = [
    '--api-key',
    'token-123',
    '--base-url',
    'https://example.invalid/compatible-mode/v1',
    '--model',
    'qwen3.6-plus',
    '--dry-run',
    '--force',
  ];

  const parsed = parseArgs(argv);

  assert.deepEqual(parsed, {
    apiKey: 'token-123',
    baseURL: 'https://example.invalid/compatible-mode/v1',
    model: 'qwen3.6-plus',
    dryRun: true,
    force: true,
  });
});

test('parseArgs returns defaults when optional flags are absent', () => {
  const parsed = parseArgs(['--api-key', 'token-123']);

  assert.deepEqual(parsed, {
    apiKey: 'token-123',
    baseURL: undefined,
    model: undefined,
    dryRun: false,
    force: false,
  });
});

test('parseArgs rejects unknown flags', () => {
  assert.throws(() => parseArgs(['--wat']), /Unknown argument: --wat/);
});

test('parseArgs rejects missing values for value-taking flags', () => {
  assert.throws(() => parseArgs(['--api-key']), /Missing value for --api-key/);
  assert.throws(() => parseArgs(['--base-url', '--force']), /Missing value for --base-url/);
  assert.throws(() => parseArgs(['--model']), /Missing value for --model/);
});

test('buildProviderConfig returns the Bailian provider with the full expected shape', () => {
  const providerConfig = buildProviderConfig({
    apiKey: 'token-123',
    baseURL: DEFAULT_BASE_URL,
  });

  assert.deepEqual(providerConfig, createExpectedProviderConfig());
});

test('mergeProviderConfig preserves schema and other providers while adding Bailian', () => {
  const existingConfig = {
    $schema: 'https://opencode.ai/config.schema.json',
    provider: {
      openai: {
        npm: '@ai-sdk/openai',
        name: 'OpenAI',
        options: {
          apiKey: 'openai-key',
          baseURL: 'https://api.openai.com/v1',
        },
        models: {
          'gpt-4.1': {},
        },
      },
    },
  };

  const providerConfig = createExpectedProviderConfig();

  const merged = mergeProviderConfig(existingConfig, providerConfig);

  assert.equal(merged.$schema, 'https://opencode.ai/config.schema.json');
  assert.deepEqual(merged.provider.openai, existingConfig.provider.openai);
  assert.deepEqual(merged.provider[PROVIDER_KEY], providerConfig);
});

test('mergeProviderConfig throws when provider exists and force is false', () => {
  const existingConfig = {
    provider: {
      [PROVIDER_KEY]: {
        name: 'Old Provider',
      },
    },
  };

  const providerConfig = buildProviderConfig({
    apiKey: 'token-123',
    baseURL: DEFAULT_BASE_URL,
  });

  assert.throws(
    () => mergeProviderConfig(existingConfig, providerConfig, { force: false }),
    new RegExp(`${PROVIDER_KEY} already exists`)
  );
});

test('mergeProviderConfig treats a null existing provider entry as already present', () => {
  const existingConfig = {
    provider: {
      [PROVIDER_KEY]: null,
    },
  };

  const providerConfig = buildProviderConfig({
    apiKey: 'token-123',
    baseURL: DEFAULT_BASE_URL,
  });

  assert.throws(
    () => mergeProviderConfig(existingConfig, providerConfig),
    new RegExp(`${PROVIDER_KEY} already exists`)
  );
});

test('mergeProviderConfig defaults $schema when it is absent', () => {
  const existingConfig = {
    provider: {
      openai: {
        name: 'OpenAI',
      },
    },
  };

  const providerConfig = buildProviderConfig({
    apiKey: 'token-123',
    baseURL: DEFAULT_BASE_URL,
  });

  const merged = mergeProviderConfig(existingConfig, providerConfig);

  assert.equal(merged.$schema, 'https://opencode.ai/config.json');
  assert.deepEqual(merged.provider.openai, existingConfig.provider.openai);
  assert.deepEqual(merged.provider[PROVIDER_KEY], providerConfig);
});

test('mergeProviderConfig allows overwrite when force is truthy', () => {
  const existingConfig = {
    $schema: 'https://opencode.ai/config.schema.json',
    provider: {
      [PROVIDER_KEY]: null,
    },
  };

  const providerConfig = buildProviderConfig({
    apiKey: 'token-456',
    baseURL: DEFAULT_BASE_URL,
  });

  const merged = mergeProviderConfig(existingConfig, providerConfig, { force: true });

  assert.equal(merged.$schema, 'https://opencode.ai/config.schema.json');
  assert.deepEqual(merged.provider[PROVIDER_KEY], providerConfig);
});

test('readConfigFile returns parsed JSON for a valid file', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-config-'));
  const configPath = path.join(tempDir, 'opencode.json');
  const expected = {
    $schema: 'https://opencode.ai/config.schema.json',
    provider: {
      openai: {
        name: 'OpenAI',
      },
    },
  };
  fs.writeFileSync(configPath, JSON.stringify(expected), 'utf8');

  assert.deepEqual(readConfigFile(configPath), expected);
});

test('readConfigFile throws helpful invalid JSON error', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-config-'));
  const configPath = path.join(tempDir, 'opencode.json');
  fs.writeFileSync(configPath, '{ nope', 'utf8');

  assert.throws(
    () => readConfigFile(configPath),
    new RegExp(`Invalid JSON in config file: ${configPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`)
  );
});

test('writeBackupFile creates sibling backup file', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-config-'));
  const configPath = path.join(tempDir, 'opencode.json');
  fs.writeFileSync(configPath, '{"ok":true}', 'utf8');

  const backupPath = writeBackupFile(configPath);

  assert.match(backupPath, /opencode\.json\.bak\./);
  assert.equal(path.dirname(backupPath), tempDir);
  assert.equal(fs.existsSync(backupPath), true);
  assert.equal(fs.readFileSync(backupPath, 'utf8'), '{"ok":true}');
});

test('readConfigFile missing file returns minimal default config', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-config-'));
  const configPath = path.join(tempDir, 'missing-opencode.json');

  assert.deepEqual(readConfigFile(configPath), {
    $schema: 'https://opencode.ai/config.json',
    provider: {},
  });
});

test('getConfigPath resolves macOS config path', () => {
  const configPath = getConfigPath({
    platform: 'darwin',
    env: { HOME: '/Users/demo' },
  });

  assert.equal(configPath, '/Users/demo/.config/opencode/opencode.json');
});

test('getConfigPath resolves Windows config path', () => {
  const configPath = getConfigPath({
    platform: 'win32',
    env: { APPDATA: 'C:\\Users\\demo\\AppData\\Roaming' },
  });

  assert.equal(configPath, path.join('C:\\Users\\demo\\AppData\\Roaming', 'opencode', 'opencode.json'));
});

test('getConfigPath throws when APPDATA is missing on Windows', () => {
  assert.throws(() => getConfigPath({ platform: 'win32', env: {} }), /APPDATA/);
});

test('getConfigPath throws for unsupported platforms', () => {
  assert.throws(() => getConfigPath({ platform: 'linux', env: {} }), /Unsupported platform: linux/);
});

test('getInstallPlan returns npm-only macOS command', () => {
  assert.deepEqual(getInstallPlan('darwin'), [
    ['npm', ['i', '-g', 'opencode-ai@latest']],
  ]);
});

test('getInstallPlan returns npm-only Windows command', () => {
  assert.deepEqual(getInstallPlan('win32'), [
    ['cmd.exe', ['/d', '/s', '/c', 'npm i -g opencode-ai@latest']],
  ]);
});

test('getOpencodeCommand returns platform-specific command name', () => {
  assert.equal(getOpencodeCommand('darwin'), 'opencode');
  assert.equal(getOpencodeCommand('win32'), 'opencode.cmd');
});

test('getOpencodeCandidates includes APPDATA shim on Windows', () => {
  assert.deepEqual(getOpencodeCandidates('darwin', {}), ['opencode']);
  assert.deepEqual(getOpencodeCandidates('win32', { APPDATA: 'C:\\Users\\demo\\AppData\\Roaming' }), [
    'opencode.cmd',
    path.join('C:\\Users\\demo\\AppData\\Roaming', 'npm', 'opencode.cmd'),
  ]);
});

test('buildManualInstallHint joins npm-only commands with newlines', () => {
  assert.equal(
    buildManualInstallHint('win32'),
    'npm i -g opencode-ai@latest'
  );
});

test('validateConfig returns [] for a valid expected config', () => {
  const issues = validateConfig({
    provider: {
      [PROVIDER_KEY]: createExpectedProviderConfig(),
    },
  });

  assert.deepEqual(issues, []);
});

test('validateConfig reports each missing piece when config is incomplete', () => {
  assert.deepEqual(validateConfig({}), [
    `Missing provider.${PROVIDER_KEY}`,
    'Missing provider options.baseURL',
    'Missing provider options.apiKey',
    `Missing default model ${DEFAULT_MODEL}`,
  ]);

  assert.deepEqual(
    validateConfig({
      provider: {
        [PROVIDER_KEY]: {
          options: {},
          models: {},
        },
      },
    }),
    [
      'Missing provider options.baseURL',
      'Missing provider options.apiKey',
      `Missing default model ${DEFAULT_MODEL}`,
    ]
  );
});

test('resolveRuntimeOptions prefers argv over env', async () => {
  const runtime = await resolveRuntimeOptions({
    args: {
      apiKey: 'arg-token',
      baseURL: 'https://arg.invalid/v1',
      model: 'glm-5',
      dryRun: true,
      force: true,
    },
    env: {
      DASHSCOPE_API_KEY: 'env-token',
      BAILIAN_API_KEY: 'legacy-env-token',
      BAILIAN_BASE_URL: 'https://env.invalid/v1',
      BAILIAN_MODEL: 'deepseek-v3.2',
    },
    isInteractive: false,
    prompt: async () => {
      throw new Error('prompt should not run');
    },
  });

  assert.deepEqual(runtime, {
    apiKey: 'arg-token',
    baseURL: 'https://arg.invalid/v1',
    model: 'glm-5',
    dryRun: true,
    force: true,
  });
});

test('resolveRuntimeOptions falls back to env', async () => {
  const runtime = await resolveRuntimeOptions({
    args: {
      apiKey: undefined,
      baseURL: undefined,
      model: undefined,
      dryRun: false,
      force: false,
    },
    env: {
      DASHSCOPE_API_KEY: 'env-token',
      BAILIAN_API_KEY: 'legacy-env-token',
      BAILIAN_BASE_URL: 'https://env.invalid/v1',
      BAILIAN_MODEL: 'deepseek-v3.2',
    },
    isInteractive: false,
    prompt: async () => {
      throw new Error('prompt should not run');
    },
  });

  assert.deepEqual(runtime, {
    apiKey: 'env-token',
    baseURL: 'https://env.invalid/v1',
    model: 'deepseek-v3.2',
    dryRun: false,
    force: false,
  });
});

test('resolveRuntimeOptions prompts in interactive mode when api key is missing', async () => {
  let promptCount = 0;

  const runtime = await resolveRuntimeOptions({
    args: {
      apiKey: undefined,
      baseURL: undefined,
      model: undefined,
      dryRun: false,
      force: true,
    },
    env: {},
    isInteractive: true,
    prompt: async (message) => {
      promptCount += 1;
      assert.equal(message, 'Enter Bailian API key: ');
      return '  prompted-token  ';
    },
  });

  assert.equal(promptCount, 1);
  assert.deepEqual(runtime, {
    apiKey: 'prompted-token',
    baseURL: DEFAULT_BASE_URL,
    model: DEFAULT_MODEL,
    dryRun: false,
    force: true,
  });
});

test('resolveRuntimeOptions throws missing API key error when non-interactive or prompt empty', async () => {
  const expectedMessage = 'Missing API key. Pass --api-key or set DASHSCOPE_API_KEY.';

  await assert.rejects(
    () =>
      resolveRuntimeOptions({
        args: {
          apiKey: undefined,
          baseURL: undefined,
          model: undefined,
          dryRun: false,
          force: false,
        },
        env: {},
        isInteractive: false,
        prompt: async () => 'unused',
      }),
    new RegExp(expectedMessage.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  );

  await assert.rejects(
    () =>
      resolveRuntimeOptions({
        args: {
          apiKey: undefined,
          baseURL: undefined,
          model: undefined,
          dryRun: false,
          force: false,
        },
        env: {},
        isInteractive: true,
        prompt: async () => '   ',
      }),
    new RegExp(expectedMessage.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  );
});

test('ensureOpencodeInstalled returns installed false/now false when opencode --version works', () => {
  const calls = [];
  const execFileSync = (command, args, options) => {
    calls.push([command, args, options]);
    return '1.2.3';
  };

  assert.deepEqual(ensureOpencodeInstalled(execFileSync, 'darwin'), {
    installed: true,
    installedNow: false,
  });
  assert.deepEqual(calls, [
    ['opencode', ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
  ]);
});

test('ensureOpencodeInstalled tries npm install plan and returns installedNow true after success', () => {
  const calls = [];
  let versionChecks = 0;
  const execFileSync = (command, args, options) => {
    calls.push([command, args, options]);

    if (command === 'opencode') {
      versionChecks += 1;
      if (versionChecks === 1) {
        throw Object.assign(new Error('missing'), { code: 'ENOENT' });
      }
      return '1.2.3';
    }

    if (command === 'npm') {
      return undefined;
    }

    throw new Error(`unexpected command: ${command}`);
  };

  assert.deepEqual(ensureOpencodeInstalled(execFileSync, 'darwin'), {
    installed: true,
    installedNow: true,
  });
  assert.deepEqual(calls, [
    ['opencode', ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
    ['npm', ['i', '-g', 'opencode-ai@latest'], { stdio: 'inherit' }],
    ['opencode', ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
  ]);
});

test('ensureOpencodeInstalled uses cmd.exe wrapper for npm on Windows', () => {
  const calls = [];
  let versionChecks = 0;
  const execFileSync = (command, args, options) => {
    calls.push([command, args, options]);

    if (command === 'opencode.cmd') {
      versionChecks += 1;
      if (versionChecks === 1) {
        throw Object.assign(new Error('missing'), { code: 'ENOENT' });
      }
      return '1.2.3';
    }

    if (command === 'cmd.exe') {
      return undefined;
    }

    throw new Error(`unexpected command: ${command}`);
  };

  assert.deepEqual(ensureOpencodeInstalled(execFileSync, 'win32'), {
    installed: true,
    installedNow: true,
  });
  assert.deepEqual(calls, [
    ['opencode.cmd', ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
    ['cmd.exe', ['/d', '/s', '/c', 'npm i -g opencode-ai@latest'], { stdio: 'inherit' }],
    ['opencode.cmd', ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
  ]);
});

test('ensureOpencodeInstalled falls back to APPDATA npm shim on Windows', () => {
  const calls = [];
  const appDataShim = path.join('C:\\Users\\demo\\AppData\\Roaming', 'npm', 'opencode.cmd');
  let pathVersionChecks = 0;
  const execFileSync = (command, args, options) => {
    calls.push([command, args, options]);

    if (command === 'opencode.cmd') {
      pathVersionChecks += 1;
      throw Object.assign(new Error('missing'), { code: 'ENOENT' });
    }

    if (command === 'cmd.exe') {
      return undefined;
    }

    if (command === appDataShim) {
      return '1.2.3';
    }

    throw new Error(`unexpected command: ${command}`);
  };

  assert.deepEqual(
    ensureOpencodeInstalled(execFileSync, 'win32', { APPDATA: 'C:\\Users\\demo\\AppData\\Roaming' }),
    {
      installed: true,
      installedNow: false,
    }
  );
  assert.deepEqual(calls, [
    ['opencode.cmd', ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
    [appDataShim, ['--version'], { stdio: 'pipe', encoding: 'utf8' }],
  ]);
});

test('ensureOpencodeInstalled throws npm-only manual hint after install attempt fails', () => {
  const execFileSync = (command) => {
    if (command === 'opencode.cmd') {
      throw Object.assign(new Error('missing'), { code: 'ENOENT' });
    }

    throw new Error('install failed');
  };

  assert.throws(
    () => ensureOpencodeInstalled(execFileSync, 'win32'),
    /Unable to install opencode automatically\. Try one of:\nnpm i -g opencode-ai@latest/
  );
});

test('ensureOpencodeInstalled shows Windows post-install hint when npm succeeds but binary is still not runnable', () => {
  const execFileSync = (command) => {
    if (command === 'opencode.cmd') {
      throw Object.assign(new Error('missing'), { code: 'ENOENT' });
    }

    if (command === 'cmd.exe') {
      return undefined;
    }

    throw new Error(`unexpected command: ${command}`);
  };

  assert.throws(
    () => ensureOpencodeInstalled(execFileSync, 'win32'),
    /OpenCode install command completed, but the Windows binary is still not runnable\.[\s\S]*taskkill \/F \/IM opencode\.exe[\s\S]*npm i -g opencode-ai@latest[\s\S]*%APPDATA%\\npm\\opencode\.cmd/
  );
});


test('ensureOpencodeInstalled shows Windows EPERM hint when opencode.exe is locked during install cleanup', () => {
  const execFileSync = (command) => {
    if (command === 'opencode.cmd') {
      throw Object.assign(new Error('missing'), { code: 'ENOENT' });
    }

    throw Object.assign(new Error('locked'), {
      code: 'EPERM',
      syscall: 'unlink',
      path: 'C:\\Users\\demo\\AppData\\Roaming\\npm\\node_modules\\opencode-windows-x64\\bin\\opencode.exe',
    });
  };

  assert.throws(
    () => ensureOpencodeInstalled(execFileSync, 'win32'),
    /OpenCode may already be running and blocking the Windows install cleanup\.[\s\S]*taskkill \/F \/IM opencode\.exe[\s\S]*npm i -g opencode-ai@latest/
  );
});

test('run returns dry-run result without writing files', async () => {
  let mkdirCount = 0;
  let writeCount = 0;
  let existsCount = 0;

  const result = await run({
    argv: ['--api-key', 'token-123', '--dry-run'],
    platform: 'darwin',
    env: { HOME: '/Users/demo' },
    isInteractive: false,
    execFileSync() {
      return '1.2.3';
    },
    fs: {
      existsSync() {
        existsCount += 1;
        return false;
      },
      mkdirSync() {
        mkdirCount += 1;
      },
      writeFileSync() {
        writeCount += 1;
      },
    },
  });

  assert.deepEqual(result, {
    mode: 'dry-run',
    configPath: '/Users/demo/.config/opencode/opencode.json',
    preview: createExpectedProviderConfig(),
  });
  assert.equal(mkdirCount, 0);
  assert.equal(writeCount, 0);
  assert.equal(existsCount, 0);
});

test('run dry-run does not check installation when opencode is absent', async () => {
  let execCount = 0;

  const result = await run({
    argv: ['--api-key', 'token-123', '--dry-run'],
    platform: 'darwin',
    env: { HOME: '/Users/demo' },
    isInteractive: false,
    execFileSync() {
      execCount += 1;
      throw Object.assign(new Error('missing'), { code: 'ENOENT' });
    },
    fs: {
      existsSync() {
        throw new Error('existsSync should not run during dry-run');
      },
      mkdirSync() {
        throw new Error('mkdirSync should not run during dry-run');
      },
      writeFileSync() {
        throw new Error('writeFileSync should not run during dry-run');
      },
    },
  });

  assert.deepEqual(result, {
    mode: 'dry-run',
    configPath: '/Users/demo/.config/opencode/opencode.json',
    preview: createExpectedProviderConfig(),
  });
  assert.equal(execCount, 0);
});

test('run throws helpful error when API key is missing in non-interactive mode', async () => {
  await assert.rejects(
    () =>
      run({
        argv: [],
        platform: 'darwin',
        env: { HOME: '/Users/demo' },
        isInteractive: false,
        execFileSync() {
          return '1.2.3';
        },
      }),
    /Missing API key/
  );
});

test('run write mode writes config file contents and returns write summary', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-run-write-'));
  const configPath = path.join(tempDir, '.config', 'opencode', 'opencode.json');
  const configDir = path.dirname(configPath);
  fs.mkdirSync(configDir, { recursive: true });
  fs.writeFileSync(
    configPath,
    JSON.stringify({
      $schema: 'https://opencode.ai/config.json',
      provider: {
        openai: {
          name: 'OpenAI',
        },
      },
    }),
    'utf8'
  );

  const result = await run({
    argv: ['--api-key', 'token-123', '--force'],
    platform: 'darwin',
    env: { HOME: tempDir },
    isInteractive: false,
    execFileSync() {
      return '1.2.3';
    },
    fs,
  });

  const writtenConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));

  assert.deepEqual(result, {
    mode: 'write',
    installed: true,
    installedNow: false,
    configPath,
    providerKey: PROVIDER_KEY,
    defaultModel: DEFAULT_MODEL,
  });
  assert.equal(writtenConfig.model, `${PROVIDER_KEY}/${DEFAULT_MODEL}`);
  assert.deepEqual(writtenConfig.provider.openai, { name: 'OpenAI' });
  assert.deepEqual(writtenConfig.provider[PROVIDER_KEY], createExpectedProviderConfig());
  assert.ok(fs.readdirSync(configDir).some((name) => name.startsWith('opencode.json.bak.')));
});

test('run write mode supports configured non-default models', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-run-glm-'));
  const configPath = path.join(tempDir, '.config', 'opencode', 'opencode.json');

  const result = await run({
    argv: ['--api-key', 'token-123', '--model', 'glm-5'],
    platform: 'darwin',
    env: { HOME: tempDir },
    isInteractive: false,
    execFileSync() {
      return '1.2.3';
    },
    fs,
  });

  const writtenConfig = JSON.parse(fs.readFileSync(configPath, 'utf8'));

  assert.deepEqual(result, {
    mode: 'write',
    installed: true,
    installedNow: false,
    configPath,
    providerKey: PROVIDER_KEY,
    defaultModel: 'glm-5',
  });
  assert.equal(writtenConfig.model, `${PROVIDER_KEY}/glm-5`);
  assert.ok(writtenConfig.provider[PROVIDER_KEY].models['glm-5']);
});

test('run rejects unsupported model values before writing config', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-run-invalid-model-'));
  const configPath = path.join(tempDir, '.config', 'opencode', 'opencode.json');

  await assert.rejects(
    () =>
      run({
        argv: ['--api-key', 'token-123', '--model', 'not-a-real-model'],
        platform: 'darwin',
        env: { HOME: tempDir },
        isInteractive: false,
        execFileSync() {
          throw new Error('execFileSync should not run for invalid model');
        },
        fs: {
          ...fs,
          writeFileSync() {
            throw new Error('writeFileSync should not run for invalid model');
          },
        },
      }),
    /Unsupported model: not-a-real-model\. Choose one of: qwen3\.6-plus, MiniMax-M2\.5, glm-5, deepseek-v3\.2/
  );

  assert.equal(fs.existsSync(configPath), false);
});

test('run write mode validates resulting config and throws if validation fails', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-run-invalid-'));
  const configPath = path.join(tempDir, '.config', 'opencode', 'opencode.json');

  await assert.rejects(
    () =>
      run({
        argv: ['--api-key', 'token-123'],
        platform: 'darwin',
        env: { HOME: tempDir },
        isInteractive: false,
        execFileSync() {
          return '1.2.3';
        },
        fs,
        validateConfig() {
          return ['Missing provider options.apiKey'];
        },
      }),
    /Config validation failed:\nMissing provider options\.apiKey/
  );

  assert.equal(fs.existsSync(configPath), true);
});

test('formatSuccessLines returns the exact final next steps output', () => {
  assert.deepEqual(
    formatSuccessLines({
      providerKey: PROVIDER_KEY,
      defaultModel: DEFAULT_MODEL,
    }),
    ['Next steps:', '1. opencode', `2. Use provider ${PROVIDER_KEY}`, `3. Start with model ${DEFAULT_MODEL}`]
  );
});
