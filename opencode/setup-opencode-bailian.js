#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline/promises');

const BAILIAN_PROVIDER_KEY = 'bailian-token-plan';
const CLIPROXY_PROVIDER_KEY = 'cli-proxy-api';

const PROVIDER_KEY = BAILIAN_PROVIDER_KEY;
const DEFAULT_BASE_URL = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1';
const DEFAULT_MODEL = 'qwen3.6-plus';

const CLIPROXY_DEFAULT_BASE_URL = 'http://8.216.44.189:8317/v1';
const CLIPROXY_DEFAULT_MODEL = 'gpt-5.5';

function parseArgs(argv) {
  const options = {
    apiKey: undefined,
    baseURL: undefined,
    model: undefined,
    cliproxyApiKey: undefined,
    cliproxyBaseURL: undefined,
    cliproxyModel: undefined,
    defaultProvider: undefined,
    dryRun: false,
    force: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === '--dry-run') {
      options.dryRun = true;
      continue;
    }

    if (arg === '--force') {
      options.force = true;
      continue;
    }

    if (
      arg === '--ali-api-key' ||
      arg === '--base-url' ||
      arg === '--model' ||
      arg === '--codex-api-key' ||
      arg === '--cliproxy-base-url' ||
      arg === '--cliproxy-model' ||
      arg === '--default-provider'
    ) {
      const value = argv[index + 1];

      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for ${arg}`);
      }

      if (arg === '--ali-api-key') {
        options.apiKey = value;
      }

      if (arg === '--base-url') {
        options.baseURL = value;
      }

      if (arg === '--model') {
        options.model = value;
      }

      if (arg === '--codex-api-key') {
        options.cliproxyApiKey = value;
      }

      if (arg === '--cliproxy-base-url') {
        options.cliproxyBaseURL = value;
      }

      if (arg === '--cliproxy-model') {
        options.cliproxyModel = value;
      }

      if (arg === '--default-provider') {
        options.defaultProvider = value;
      }

      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function buildBailianProviderConfig({ apiKey, baseURL = DEFAULT_BASE_URL }) {
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
      'deepseek-v4-pro': {
        name: 'DeepSeek V4 Pro',
        modalities: {
          input: ['text'],
          output: ['text'],
        },
        limit: {
          context: 131072,
          output: 16384,
        },
      },
      'deepseek-v4-flash': {
        name: 'DeepSeek V4 Flash',
        modalities: {
          input: ['text'],
          output: ['text'],
        },
        limit: {
          context: 131072,
          output: 16384,
        },
      },
      'glm-5.1': {
        name: 'GLM-5.1',
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
      'kimi-k2.6': {
        name: 'Kimi K2.6',
        modalities: {
          input: ['text', 'image'],
          output: ['text'],
        },
        limit: {
          context: 131072,
          output: 16384,
        },
      },
      'qwen3.6-flash': {
        name: 'Qwen3.6 Flash',
        modalities: {
          input: ['text', 'image'],
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

function buildCLIProxyProviderConfig({ apiKey, baseURL = CLIPROXY_DEFAULT_BASE_URL }) {
  return {
    npm: '@ai-sdk/openai-compatible',
    name: '启源Codex',
    options: {
      apiKey,
      baseURL,
    },
    models: {
      'gpt-5.5': {
        name: 'GPT-5.5',
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
          context: 400000,
          output: 65536,
        },
      },
      'gpt-5.4': {
        name: 'GPT-5.4',
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
          context: 400000,
          output: 65536,
        },
      },
      'gpt-5.4-mini': {
        name: 'GPT-5.4 Mini',
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
          context: 200000,
          output: 16384,
        },
      },
      'gpt-5.3-codex': {
        name: 'GPT-5.3 Codex',
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
          context: 400000,
          output: 32768,
        },
      },
      'gpt-5.3-codex-spark': {
        name: 'GPT-5.3 Codex Spark',
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
          context: 400000,
          output: 32768,
        },
      },
      'gpt-5.2': {
        name: 'GPT-5.2',
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
          context: 300000,
          output: 16384,
        },
      },
      'codex-auto-review': {
        name: 'Codex Auto Review',
        modalities: {
          input: ['text'],
          output: ['text'],
        },
        limit: {
          context: 200000,
          output: 16384,
        },
      },
    },
  };
}

function buildProviderConfig({ apiKey, baseURL = DEFAULT_BASE_URL }) {
  return buildBailianProviderConfig({ apiKey, baseURL });
}

function readConfigFile(configPath) {
  let rawConfig;

  try {
    rawConfig = fs.readFileSync(configPath, 'utf8');
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return {
        $schema: 'https://opencode.ai/config.json',
        provider: {},
      };
    }

    throw error;
  }

  try {
    return JSON.parse(rawConfig);
  } catch {
    throw new Error(`Invalid JSON in config file: ${configPath}`);
  }
}

function writeBackupFile(configPath) {
  const backupPath = `${configPath}.bak.${Date.now()}`;
  fs.copyFileSync(configPath, backupPath);
  return backupPath;
}

function getUserHomeDir(env = process.env) {
  if (env.HOME) {
    return env.HOME;
  }

  if (env.USERPROFILE) {
    return env.USERPROFILE;
  }

  if (env.HOMEDRIVE && env.HOMEPATH) {
    return `${env.HOMEDRIVE}${env.HOMEPATH}`;
  }

  return os.homedir();
}

function getConfigPath({ platform = process.platform, env = process.env } = {}) {
  if (platform === 'darwin') {
    return path.join(getUserHomeDir(env), '.config', 'opencode', 'opencode.json');
  }

  if (platform === 'win32') {
    return path.join(getUserHomeDir(env), '.config', 'opencode', 'opencode.json');
  }

  throw new Error(`Unsupported platform: ${platform}`);
}

function getInstallPlan(platform) {
  if (platform === 'darwin') {
    return [['npm', ['i', '-g', 'opencode-ai@latest']]];
  }

  if (platform === 'win32') {
    return [['cmd.exe', ['/d', '/s', '/c', 'npm i -g opencode-ai@latest']]];
  }

  throw new Error(`Unsupported platform: ${platform}`);
}

function getOpencodeCommand(platform) {
  return platform === 'win32' ? 'opencode.cmd' : 'opencode';
}

function getOpencodeCandidates(platform, env = process.env) {
  if (platform !== 'win32') {
    return ['opencode'];
  }

  const candidates = ['opencode.cmd'];

  if (env.APPDATA) {
    candidates.push(path.join(env.APPDATA, 'npm', 'opencode.cmd'));
  }

  return candidates;
}

function buildManualInstallHint(platform) {
  return getInstallPlan(platform)
    .map(([command, args]) => {
      if (command === 'cmd.exe' && args[3]) {
        return args[3];
      }

      return `${command} ${args.join(' ')}`;
    })
    .join('\n');
}

function validateProviderBlock(providerKey, provider, defaultModel) {
  const issues = [];

  if (!provider) {
    issues.push(`Missing provider.${providerKey}`);
    return issues;
  }

  if (!provider?.options?.baseURL) {
    issues.push(`Missing ${providerKey} options.baseURL`);
  }

  if (!provider?.options?.apiKey) {
    issues.push(`Missing ${providerKey} options.apiKey`);
  }

  if (!provider?.models?.[defaultModel]) {
    issues.push(`Missing default model ${defaultModel} for ${providerKey}`);
  }

  return issues;
}

function validateConfig(config, configuredProviders) {
  const providerMap = config.provider || {};
  const providers =
    configuredProviders && configuredProviders.length > 0
      ? configuredProviders
      : [
          { key: BAILIAN_PROVIDER_KEY, defaultModel: DEFAULT_MODEL },
          { key: CLIPROXY_PROVIDER_KEY, defaultModel: CLIPROXY_DEFAULT_MODEL },
        ];

  const issues = [];

  for (const providerInfo of providers) {
    issues.push(
      ...validateProviderBlock(
        providerInfo.key,
        providerMap[providerInfo.key],
        providerInfo.defaultModel
      )
    );
  }

  return issues;
}

function validateSelectedModel(providerConfig, model) {
  if (providerConfig.models?.[model]) {
    return;
  }

  throw new Error(
    `Unsupported model: ${model}. Choose one of: ${Object.keys(providerConfig.models || {}).join(', ')}`
  );
}

function ensureOpencodeInstalled(execFileSync, platform, env = process.env) {
  const opencodeCandidates = getOpencodeCandidates(platform, env);
  const runOpencodeVersion = (candidate) => {
    if (platform === 'win32') {
      return execFileSync(candidate, ['--version'], {
        stdio: 'pipe',
        encoding: 'utf8',
        shell: true,
      });
    }

    return execFileSync(candidate, ['--version'], { stdio: 'pipe', encoding: 'utf8' });
  };
  const probeOpencode = () => {
    const results = [];

    for (const candidate of opencodeCandidates) {
      try {
        runOpencodeVersion(candidate);
        results.push({ candidate, ok: true });
      } catch (error) {
        results.push({ candidate, ok: false, error });
      }
    }

    return results;
  };
  const canRunOpencode = () => probeOpencode().some((result) => result.ok);
  const formatProbeError = (error) => {
    if (!error) {
      return 'unknown error';
    }

    if (error.code && error.code !== 'UNKNOWN') {
      return error.code;
    }

    return error.message || 'unknown error';
  };
  const getWindowsWhereOpencode = () => {
    try {
      const output = execFileSync('cmd.exe', ['/d', '/s', '/c', 'where opencode'], {
        stdio: 'pipe',
        encoding: 'utf8',
      });

      return output.trim() || 'resolved with empty output';
    } catch {
      return 'not found';
    }
  };

  if (canRunOpencode()) {
    return { installed: true, installedNow: false };
  }

  let lastInstallError;
  let installCommandSucceeded = false;

  for (const [command, args] of getInstallPlan(platform)) {
    try {
      execFileSync(command, args, { stdio: 'inherit' });
      installCommandSucceeded = true;

      if (canRunOpencode()) {
        return { installed: true, installedNow: true };
      }
    } catch (error) {
      lastInstallError = error;
    }
  }

  if (platform === 'win32' && installCommandSucceeded) {
    const diagnostics = [
      `where opencode: ${getWindowsWhereOpencode()}`,
      ...probeOpencode().map((result) =>
        `${result.candidate}: ${result.ok ? 'ok' : formatProbeError(result.error)}`
      ),
    ];

    throw new Error(
      'OpenCode install command completed, but the Windows binary is still not runnable.\n' +
        'This usually means opencode.exe is locked by a running process or security software.\n' +
        'You may also see npm warn cleanup / EPERM unlink messages for opencode.exe in this case.\n' +
        'Try: taskkill /F /IM opencode.exe\n' +
        'Then run: npm i -g opencode-ai@latest\n' +
        'Finally check: "%APPDATA%\\npm\\opencode.cmd" --version\n' +
        'Diagnostics:\n' +
        diagnostics.map((line) => `- ${line}`).join('\n')
    );
  }

  if (
    platform === 'win32' &&
    lastInstallError &&
    lastInstallError.code === 'EPERM' &&
    lastInstallError.syscall === 'unlink' &&
    /opencode\.exe/i.test(lastInstallError.path || '')
  ) {
    throw new Error(
      'OpenCode may already be running and blocking the Windows install cleanup. Close OpenCode and try again.\n' +
        'You can run: taskkill /F /IM opencode.exe\n' +
        'Then retry: npm i -g opencode-ai@latest'
    );
  }

  throw new Error(
    'Unable to install opencode automatically. Try one of:\n' + buildManualInstallHint(platform)
  );
}

function normalizeDefaultProvider(defaultProvider) {
  if (
    defaultProvider === undefined ||
    defaultProvider === BAILIAN_PROVIDER_KEY ||
    defaultProvider === CLIPROXY_PROVIDER_KEY
  ) {
    return defaultProvider;
  }

  throw new Error(
    `Unsupported default provider: ${defaultProvider}. Choose one of: ${BAILIAN_PROVIDER_KEY}, ${CLIPROXY_PROVIDER_KEY}`
  );
}

async function resolveRuntimeOptions({
  args,
  env = process.env,
  isInteractive,
  prompt,
}) {
  const missingApiKeyMessage =
    'Missing API key. Pass --ali-api-key for Bailian and/or --codex-api-key for CLIProxyAPI.';

  let bailianApiKey = args.apiKey || env.DASHSCOPE_API_KEY || env.BAILIAN_API_KEY;
  let cliproxyApiKey = args.cliproxyApiKey || env.CLIPROXY_API_KEY || env.OPENAI_API_KEY;

  const bailianBaseURL = args.baseURL || env.BAILIAN_BASE_URL || DEFAULT_BASE_URL;
  const bailianModel = args.model || env.BAILIAN_MODEL || DEFAULT_MODEL;
  const cliproxyBaseURL =
    args.cliproxyBaseURL || env.CLIPROXY_BASE_URL || CLIPROXY_DEFAULT_BASE_URL;
  const cliproxyModel = args.cliproxyModel || env.CLIPROXY_MODEL || CLIPROXY_DEFAULT_MODEL;

  if (!bailianApiKey && !cliproxyApiKey && isInteractive) {
    bailianApiKey = (await prompt('Enter Bailian API key (leave empty to skip): ')).trim();
    cliproxyApiKey = (
      await prompt('Enter CLIProxyAPI API key (leave empty to skip): ')
    ).trim();
  }

  if (!bailianApiKey && !cliproxyApiKey) {
    throw new Error(missingApiKeyMessage);
  }

  const requestedDefaultProvider = normalizeDefaultProvider(
    args.defaultProvider || env.OPENCODE_DEFAULT_PROVIDER
  );
  const defaultProvider =
    requestedDefaultProvider ||
    (cliproxyApiKey ? CLIPROXY_PROVIDER_KEY : BAILIAN_PROVIDER_KEY);

  if (defaultProvider === BAILIAN_PROVIDER_KEY && !bailianApiKey) {
    throw new Error(
      `Default provider ${BAILIAN_PROVIDER_KEY} requires --ali-api-key or DASHSCOPE_API_KEY.`
    );
  }

  if (defaultProvider === CLIPROXY_PROVIDER_KEY && !cliproxyApiKey) {
    throw new Error(
      `Default provider ${CLIPROXY_PROVIDER_KEY} requires --codex-api-key or CLIPROXY_API_KEY.`
    );
  }

  return {
    bailianApiKey,
    bailianBaseURL,
    bailianModel,
    cliproxyApiKey,
    cliproxyBaseURL,
    cliproxyModel,
    defaultProvider,
    dryRun: args.dryRun,
    force: args.force,
  };
}

function mergeProviderConfig(existingConfig, providerConfigs, options = {}) {
  const existingProvider = existingConfig.provider || {};
  const mergedConfig = {
    ...existingConfig,
    $schema: existingConfig.$schema || 'https://opencode.ai/config.json',
    provider: {
      ...existingProvider,
    },
  };

  for (const [providerKey, providerConfig] of Object.entries(providerConfigs)) {
    if (Object.hasOwn(existingProvider, providerKey) && !options.force) {
      throw new Error(`${providerKey} already exists`);
    }

    mergedConfig.provider[providerKey] = providerConfig;
  }

  return mergedConfig;
}

function formatSuccessLines(result) {
  return [
    'Next steps:',
    '1. opencode',
    `2. Use provider ${result.providerKey}`,
    `3. Start with model ${result.defaultModel}`,
  ];
}

async function run({
  argv = process.argv.slice(2),
  platform = process.platform,
  env = process.env,
  isInteractive = Boolean(process.stdin.isTTY && process.stdout.isTTY),
  execFileSync = require('node:child_process').execFileSync,
  fs: fsImpl = fs,
  validateConfig: validateConfigImpl = validateConfig,
  prompt = async (question) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    try {
      return (await rl.question(question)).trim();
    } finally {
      rl.close();
    }
  },
} = {}) {
  const args = parseArgs(argv);
  const runtime = await resolveRuntimeOptions({ args, env, isInteractive, prompt });
  const configPath = getConfigPath({ platform, env });
  const configDir = path.dirname(configPath);

  const providerConfigs = {};
  const configuredProviders = [];

  if (runtime.bailianApiKey) {
    const bailianProvider = buildBailianProviderConfig({
      apiKey: runtime.bailianApiKey,
      baseURL: runtime.bailianBaseURL,
    });
    validateSelectedModel(bailianProvider, runtime.bailianModel);
    providerConfigs[BAILIAN_PROVIDER_KEY] = bailianProvider;
    configuredProviders.push({
      key: BAILIAN_PROVIDER_KEY,
      defaultModel: DEFAULT_MODEL,
    });
  }

  if (runtime.cliproxyApiKey) {
    const cliproxyProvider = buildCLIProxyProviderConfig({
      apiKey: runtime.cliproxyApiKey,
      baseURL: runtime.cliproxyBaseURL,
    });
    validateSelectedModel(cliproxyProvider, runtime.cliproxyModel);
    providerConfigs[CLIPROXY_PROVIDER_KEY] = cliproxyProvider;
    configuredProviders.push({
      key: CLIPROXY_PROVIDER_KEY,
      defaultModel: CLIPROXY_DEFAULT_MODEL,
    });
  }

  const defaultModel =
    runtime.defaultProvider === CLIPROXY_PROVIDER_KEY
      ? runtime.cliproxyModel
      : runtime.bailianModel;

  if (args.dryRun) {
    return {
      mode: 'dry-run',
      configPath,
      preview: providerConfigs,
      providerKey: runtime.defaultProvider,
      defaultModel,
    };
  }

  const install = ensureOpencodeInstalled(execFileSync, platform, env);

  fsImpl.mkdirSync(configDir, { recursive: true });
  const existingConfig = readConfigFile(configPath);

  if (fsImpl.existsSync(configPath)) {
    writeBackupFile(configPath);
  }

  const nextConfig = mergeProviderConfig(existingConfig, providerConfigs, {
    force: runtime.force,
  });
  nextConfig.model = `${runtime.defaultProvider}/${defaultModel}`;

  fsImpl.writeFileSync(configPath, JSON.stringify(nextConfig, null, 2) + '\n', 'utf8');

  const issues = validateConfigImpl(nextConfig, configuredProviders);

  if (issues.length > 0) {
    throw new Error('Config validation failed:\n' + issues.join('\n'));
  }

  return {
    mode: 'write',
    installed: install.installed,
    installedNow: install.installedNow,
    configPath,
    providerKey: runtime.defaultProvider,
    defaultModel,
  };
}

module.exports = {
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
  writeBackupFile,
  getUserHomeDir,
  getConfigPath,
  getInstallPlan,
  getOpencodeCommand,
  getOpencodeCandidates,
  buildManualInstallHint,
  validateConfig,
  ensureOpencodeInstalled,
  resolveRuntimeOptions,
  formatSuccessLines,
  run,
};

if (require.main === module) {
  run()
    .then((result) => {
      if (result.mode === 'dry-run') {
        console.log(`Dry run OK. Config path: ${result.configPath}`);
        console.log(result.preview);
        return;
      }

      console.log(`OpenCode ready. Config written to ${result.configPath}`);
      for (const line of formatSuccessLines(result)) {
        console.log(line);
      }
    })
    .catch((error) => {
      console.error(error.message);
      process.exit(1);
    });
}
