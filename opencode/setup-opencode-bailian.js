#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline/promises');

const PROVIDER_KEY = 'bailian-token-plan';
const DEFAULT_BASE_URL = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1';
const DEFAULT_MODEL = 'qwen3.6-plus';

function parseArgs(argv) {
  const options = {
    apiKey: undefined,
    baseURL: undefined,
    model: undefined,
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

    if (arg === '--api-key' || arg === '--base-url' || arg === '--model') {
      const value = argv[index + 1];

      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for ${arg}`);
      }

      if (arg === '--api-key') {
        options.apiKey = value;
      }

      if (arg === '--base-url') {
        options.baseURL = value;
      }

      if (arg === '--model') {
        options.model = value;
      }

      index += 1;
      continue;
    }

    throw new Error(`Unknown argument: ${arg}`);
  }

  return options;
}

function buildProviderConfig({ apiKey, baseURL = DEFAULT_BASE_URL }) {
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

function getConfigPath({ platform = process.platform, env = process.env } = {}) {
  if (platform === 'darwin') {
    return path.join(env.HOME || os.homedir(), '.config', 'opencode', 'opencode.json');
  }

  if (platform === 'win32') {
    if (!env.APPDATA) {
      throw new Error('APPDATA is required to resolve the OpenCode config path on Windows');
    }

    return path.join(env.APPDATA, 'opencode', 'opencode.json');
  }

  throw new Error(`Unsupported platform: ${platform}`);
}

function getInstallPlan(platform) {
  if (platform === 'darwin') {
    return [
      ['npm', ['i', '-g', 'opencode-ai@latest']],
    ];
  }

  if (platform === 'win32') {
    return [
      ['cmd.exe', ['/d', '/s', '/c', 'npm i -g opencode-ai@latest']],
    ];
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

function validateConfig(config) {
  const issues = [];
  const provider = config.provider && config.provider[PROVIDER_KEY];

  if (!provider) {
    issues.push(`Missing provider.${PROVIDER_KEY}`);
  }

  if (!provider?.options?.baseURL) {
    issues.push('Missing provider options.baseURL');
  }

  if (!provider?.options?.apiKey) {
    issues.push('Missing provider options.apiKey');
  }

  if (!provider?.models?.[DEFAULT_MODEL]) {
    issues.push(`Missing default model ${DEFAULT_MODEL}`);
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
      return execFileSync('cmd.exe', ['/d', '/s', '/c', `"${candidate}" --version`], {
        stdio: 'pipe',
        encoding: 'utf8',
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

async function resolveRuntimeOptions({
  args,
  env = process.env,
  isInteractive,
  prompt,
}) {
  const missingApiKeyMessage = 'Missing API key. Pass --api-key or set DASHSCOPE_API_KEY.';

  let apiKey = args.apiKey || env.DASHSCOPE_API_KEY || env.BAILIAN_API_KEY;
  const baseURL = args.baseURL || env.BAILIAN_BASE_URL || DEFAULT_BASE_URL;
  const model = args.model || env.BAILIAN_MODEL || DEFAULT_MODEL;

  if (!apiKey) {
    if (!isInteractive) {
      throw new Error(missingApiKeyMessage);
    }

    apiKey = (await prompt('Enter Bailian API key: ')).trim();

    if (!apiKey) {
      throw new Error(missingApiKeyMessage);
    }
  }

  return {
    apiKey,
    baseURL,
    model,
    dryRun: args.dryRun,
    force: args.force,
  };
}

function mergeProviderConfig(existingConfig, providerConfig, options = {}) {
  const existingProvider = existingConfig.provider || {};
  const mergedConfig = {
    ...existingConfig,
    $schema: existingConfig.$schema || 'https://opencode.ai/config.json',
    provider: {
      ...existingProvider,
    },
  };

  if (Object.hasOwn(existingProvider, PROVIDER_KEY) && !options.force) {
    throw new Error(`${PROVIDER_KEY} already exists`);
  }

  mergedConfig.provider[PROVIDER_KEY] = providerConfig;
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
  const providerConfig = buildProviderConfig(runtime);

  validateSelectedModel(providerConfig, runtime.model);

  if (args.dryRun) {
    return {
      mode: 'dry-run',
      configPath,
      preview: providerConfig,
    };
  }

  const install = ensureOpencodeInstalled(execFileSync, platform, env);

  fsImpl.mkdirSync(configDir, { recursive: true });
  const existingConfig = readConfigFile(configPath);

  if (fsImpl.existsSync(configPath)) {
    writeBackupFile(configPath);
  }

  const nextConfig = mergeProviderConfig(existingConfig, providerConfig, {
    force: runtime.force,
  });
  nextConfig.model = `${PROVIDER_KEY}/${runtime.model}`;

  fsImpl.writeFileSync(configPath, JSON.stringify(nextConfig, null, 2) + '\n', 'utf8');

  const issues = validateConfigImpl(nextConfig);

  if (issues.length > 0) {
    throw new Error('Config validation failed:\n' + issues.join('\n'));
  }

  return {
    mode: 'write',
    installed: install.installed,
    installedNow: install.installedNow,
    configPath,
    providerKey: PROVIDER_KEY,
    defaultModel: runtime.model,
  };
}

module.exports = {
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
