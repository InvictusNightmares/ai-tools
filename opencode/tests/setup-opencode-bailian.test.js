const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const scriptPath = path.resolve(__dirname, '..', 'setup-opencode-bailian.js');

const {
  BAILIAN_PROVIDER_KEY,
  CLIPROXY_PROVIDER_KEY,
  PROVIDER_KEY,
  DEFAULT_BASE_URL,
  DEFAULT_MODEL,
  CLIPROXY_DEFAULT_BASE_URL,
  CLIPROXY_DEFAULT_MODEL,
  parseArgs,
  buildProviderConfig,
  buildBailianProviderConfig,
  buildCLIProxyProviderConfig,
  mergeProviderConfig,
  readConfigFile,
  getConfigPath,
  validateConfig,
  resolveRuntimeOptions,
  ensureOpencodeInstalled,
  formatSuccessLines,
  run,
} = require(scriptPath);

function createBailianProviderConfig({
  apiKey = 'bailian-token',
  baseURL = DEFAULT_BASE_URL,
} = {}) {
  return buildBailianProviderConfig({ apiKey, baseURL });
}

function createCLIProxyProviderConfig({
  apiKey = 'cliproxy-token',
  baseURL = CLIPROXY_DEFAULT_BASE_URL,
} = {}) {
  return buildCLIProxyProviderConfig({ apiKey, baseURL });
}

test('exports keep Bailian as the legacy default and expose CLIProxy constants', () => {
  assert.equal(PROVIDER_KEY, BAILIAN_PROVIDER_KEY);
  assert.equal(BAILIAN_PROVIDER_KEY, 'bailian-token-plan');
  assert.equal(CLIPROXY_PROVIDER_KEY, 'cli-proxy-api');
  assert.equal(DEFAULT_BASE_URL, 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1');
  assert.equal(DEFAULT_MODEL, 'qwen3.6-plus');
  assert.equal(CLIPROXY_DEFAULT_BASE_URL, 'http://8.216.44.189:8317/v1');
  assert.equal(CLIPROXY_DEFAULT_MODEL, 'gpt-5.5');
});

test('parseArgs supports both Bailian and CLIProxyAPI flags', () => {
  const parsed = parseArgs([
    '--ali-api-key',
    'bailian-token',
    '--codex-api-key',
    'cliproxy-token',
    '--cliproxy-base-url',
    'https://example.invalid/v1',
    '--cliproxy-model',
    'gpt-5.2',
    '--default-provider',
    'cli-proxy-api',
    '--dry-run',
  ]);

  assert.deepEqual(parsed, {
    apiKey: 'bailian-token',
    baseURL: undefined,
    model: undefined,
    cliproxyApiKey: 'cliproxy-token',
    cliproxyBaseURL: 'https://example.invalid/v1',
    cliproxyModel: 'gpt-5.2',
    defaultProvider: 'cli-proxy-api',
    dryRun: true,
    force: false,
  });
});

test('buildProviderConfig stays backward-compatible for Bailian', () => {
  assert.deepEqual(buildProviderConfig({ apiKey: 'bailian-token' }), createBailianProviderConfig());
});

test('mergeProviderConfig writes multiple providers together', () => {
  const merged = mergeProviderConfig(
    {
      provider: {
        openai: { name: 'OpenAI' },
      },
    },
    {
      [BAILIAN_PROVIDER_KEY]: createBailianProviderConfig(),
      [CLIPROXY_PROVIDER_KEY]: createCLIProxyProviderConfig(),
    }
  );

  assert.deepEqual(merged.provider.openai, { name: 'OpenAI' });
  assert.deepEqual(merged.provider[BAILIAN_PROVIDER_KEY], createBailianProviderConfig());
  assert.deepEqual(merged.provider[CLIPROXY_PROVIDER_KEY], createCLIProxyProviderConfig());
});

test('readConfigFile returns default config when missing', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-config-'));
  const configPath = path.join(tempDir, 'missing.json');

  assert.deepEqual(readConfigFile(configPath), {
    $schema: 'https://opencode.ai/config.json',
    provider: {},
  });
});

test('getConfigPath resolves supported platform paths', () => {
  assert.equal(
    getConfigPath({ platform: 'darwin', env: { HOME: '/Users/demo' } }),
    '/Users/demo/.config/opencode/opencode.json'
  );

  assert.equal(
    getConfigPath({ platform: 'win32', env: { USERPROFILE: 'C:\\Users\\demo' } }),
    path.join('C:\\Users\\demo', '.config', 'opencode', 'opencode.json')
  );
});

test('validateConfig validates only the configured providers', () => {
  const config = {
    provider: {
      [CLIPROXY_PROVIDER_KEY]: createCLIProxyProviderConfig(),
    },
  };

  assert.deepEqual(
    validateConfig(config, [{ key: CLIPROXY_PROVIDER_KEY, defaultModel: CLIPROXY_DEFAULT_MODEL }]),
    []
  );
});

test('CLIProxy provider includes gpt-image-2', () => {
  const provider = createCLIProxyProviderConfig();

  assert.deepEqual(provider.models['gpt-image-2'], {
    name: 'GPT Image 2',
    modalities: {
      input: ['text', 'image'],
      output: ['image'],
    },
    limit: {
      context: 128000,
      output: 8192,
    },
  });
});

test('Qwen, Kimi, and GPT chat models support image input', () => {
  const bailianProvider = createBailianProviderConfig();
  const cliproxyProvider = createCLIProxyProviderConfig();

  for (const model of ['qwen3.6-plus', 'qwen3.6-flash', 'kimi-k2.6']) {
    assert.deepEqual(bailianProvider.models[model].modalities.input, ['text', 'image']);
  }

  for (const model of ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.3-codex', 'gpt-5.2']) {
    assert.deepEqual(cliproxyProvider.models[model].modalities.input, ['text', 'image']);
  }
});

test('resolveRuntimeOptions supports both env groups and picks CLIProxyAPI as default when present', async () => {
  const runtime = await resolveRuntimeOptions({
    args: {
      apiKey: undefined,
      baseURL: undefined,
      model: undefined,
      cliproxyApiKey: undefined,
      cliproxyBaseURL: undefined,
      cliproxyModel: undefined,
      defaultProvider: undefined,
      dryRun: false,
      force: true,
    },
    env: {
      DASHSCOPE_API_KEY: 'bailian-token',
      CLIPROXY_API_KEY: 'cliproxy-token',
      CLIPROXY_MODEL: 'gpt-5.2',
    },
    isInteractive: false,
    prompt: async () => 'unused',
  });

  assert.equal(runtime.bailianApiKey, 'bailian-token');
  assert.equal(runtime.cliproxyApiKey, 'cliproxy-token');
  assert.equal(runtime.defaultProvider, CLIPROXY_PROVIDER_KEY);
  assert.equal(runtime.cliproxyModel, 'gpt-5.2');
});

test('resolveRuntimeOptions throws if no provider key is supplied', async () => {
  await assert.rejects(
    () =>
      resolveRuntimeOptions({
        args: {
          apiKey: undefined,
          baseURL: undefined,
          model: undefined,
          cliproxyApiKey: undefined,
          cliproxyBaseURL: undefined,
          cliproxyModel: undefined,
          defaultProvider: undefined,
          dryRun: false,
          force: false,
        },
        env: {},
        isInteractive: false,
        prompt: async () => 'unused',
      }),
    /Missing API key/
  );
});

test('ensureOpencodeInstalled returns already installed when opencode works', () => {
  const calls = [];
  const execFileSync = (command, args, options) => {
    calls.push([command, args, options]);
    return '1.2.3';
  };

  assert.deepEqual(ensureOpencodeInstalled(execFileSync, 'darwin'), {
    installed: true,
    installedNow: false,
  });
  assert.deepEqual(calls, [['opencode', ['--version'], { stdio: 'pipe', encoding: 'utf8' }]]);
});

test('run dry-run previews both providers when both keys are supplied', async () => {
  const result = await run({
    argv: [
      '--ali-api-key',
      'bailian-token',
      '--codex-api-key',
      'cliproxy-token',
      '--default-provider',
      'cli-proxy-api',
      '--dry-run',
    ],
    platform: 'darwin',
    env: { HOME: '/Users/demo' },
    isInteractive: false,
  });

  assert.deepEqual(result, {
    mode: 'dry-run',
    configPath: '/Users/demo/.config/opencode/opencode.json',
    preview: {
      [BAILIAN_PROVIDER_KEY]: createBailianProviderConfig(),
      [CLIPROXY_PROVIDER_KEY]: createCLIProxyProviderConfig(),
    },
    providerKey: CLIPROXY_PROVIDER_KEY,
    defaultModel: CLIPROXY_DEFAULT_MODEL,
  });
});

test('run write mode writes both providers and uses the selected default provider', async () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'opencode-run-write-'));
  const configPath = path.join(tempDir, '.config', 'opencode', 'opencode.json');

  const result = await run({
    argv: [
      '--ali-api-key',
      'bailian-token',
      '--codex-api-key',
      'cliproxy-token',
      '--cliproxy-model',
      'gpt-5.2',
      '--default-provider',
      'cli-proxy-api',
    ],
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
    providerKey: CLIPROXY_PROVIDER_KEY,
    defaultModel: 'gpt-5.2',
  });
  assert.equal(writtenConfig.model, `${CLIPROXY_PROVIDER_KEY}/gpt-5.2`);
  assert.ok(writtenConfig.provider[BAILIAN_PROVIDER_KEY]);
  assert.ok(writtenConfig.provider[CLIPROXY_PROVIDER_KEY]);
});

test('formatSuccessLines keeps the existing final output shape', () => {
  assert.deepEqual(formatSuccessLines({ providerKey: CLIPROXY_PROVIDER_KEY, defaultModel: 'gpt-5.2' }), [
    'Next steps:',
    '1. opencode',
    `2. Use provider ${CLIPROXY_PROVIDER_KEY}`,
    '3. Start with model gpt-5.2',
  ]);
});
