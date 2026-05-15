#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline/promises');
const { spawnSync } = require('node:child_process');

const DEFAULT_EXTERNAL_BASE_URL = 'http://192.168.64.16:4001/v1';
const DEFAULT_DACS_BASE_URL = 'http://47.117.95.192:4001/v1';
const DEFAULT_MODEL = 'gpt-5.5';
const DEFAULT_CODEX_MODEL = DEFAULT_MODEL;
const PROVIDER_KEY = '启源Code Model';

const AGENTS = ['claude-code', 'codex', 'opencode'];
const MODES = ['install-and-config', 'install-only', 'config-only', 'verify-only'];

const OPENCODE_MODELS = {
  'qwen3.6-plus': 'Qwen3.6 Plus',
  'MiniMax-M2.5': 'MiniMax M2.5',
  'glm-5': 'GLM-5',
  'deepseek-v3.2': 'DeepSeek V3.2',
  'deepseek-v4-pro': 'DeepSeek V4 Pro',
  'deepseek-v4-flash': 'DeepSeek V4 Flash',
  'glm-5.1': 'GLM-5.1',
  'kimi-k2.6': 'Kimi K2.6',
  'qwen3.6-flash': 'Qwen3.6 Flash',
  'gpt-5.5': 'GPT-5.5',
  'gpt-5.4': 'GPT-5.4',
  'gpt-5.4-mini': 'GPT-5.4 Mini',
  'gpt-5.3-codex': 'GPT-5.3 Codex',
  'gpt-5.2': 'GPT-5.2'
};

function supportsImageInput(modelId) {
  return /^(gpt|qwen|kimi)-/i.test(modelId);
}

function usage() {
  console.log(`Usage: node script/code-agent/install.js [options]

Options:
  --agents <list>       all or comma-separated: claude-code,codex,opencode
  --api-key <key>       API key for 启源Code Model
  --external-url <url>  DACS external API base URL
  --dacs-url <url>      DACS internal API base URL
  --mode <mode>         install-and-config, install-only, config-only, verify-only
  --yes                 Do not prompt for confirmation
  --force               Reinstall or overwrite existing files without asking
  --dry-run             Print actions without changing files
  --verbose             Print executed commands
  --help                Show this help`);
}

function parseArgs(argv) {
  const options = {
    agents: undefined,
    apiKey: '',
    externalBaseURL: '',
    dacsBaseURL: '',
    mode: undefined,
    yes: false,
    force: false,
    dryRun: false,
    verbose: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];

    if (arg === '--help' || arg === '-h') {
      usage();
      process.exit(0);
    }

    if (arg === '--yes') {
      options.yes = true;
      continue;
    }

    if (arg === '--force') {
      options.force = true;
      continue;
    }

    if (arg === '--dry-run') {
      options.dryRun = true;
      continue;
    }

    if (arg === '--verbose') {
      options.verbose = true;
      continue;
    }

    if (['--agents', '--api-key', '--external-url', '--dacs-url', '--mode'].includes(arg)) {
      const value = argv[index + 1];
      if (!value || value.startsWith('--')) {
        throw new Error(`Missing value for ${arg}`);
      }

      if (arg === '--agents') options.agents = value;
      if (arg === '--api-key') options.apiKey = value;
      if (arg === '--external-url') options.externalBaseURL = value;
      if (arg === '--dacs-url') options.dacsBaseURL = value;
      if (arg === '--mode') options.mode = value;
      index += 1;
      continue;
    }

    throw new Error(`Unknown option: ${arg}`);
  }

  if (options.mode && !MODES.includes(options.mode)) {
    throw new Error(`Invalid mode: ${options.mode}`);
  }

  return options;
}

function title(text) {
  console.log(`\n${text}`);
  console.log('='.repeat([...text].length));
}

function step(text) {
  console.log(`\n> ${text}`);
}

function success(text) {
  console.log(`OK: ${text}`);
}

function warn(text) {
  console.warn(`Warning: ${text}`);
}

function maskSecret(value) {
  if (!value) return '';
  if (value.length <= 8) return '****';
  return `${value.slice(0, 4)}...${value.slice(-4)}`;
}

function redact(value, apiKey) {
  if (!apiKey) return value;
  return String(value).split(apiKey).join('***');
}

function createPrompt() {
  if (!process.stdin.isTTY && process.platform !== 'win32') {
    try {
      const fd = fs.openSync('/dev/tty', 'r');
      const input = fs.createReadStream(null, { fd, autoClose: true });
      return readline.createInterface({ input, output: process.stdout, terminal: true });
    } catch {
      // Fall back to stdin so non-interactive executions still fail with a clear error.
    }
  }

  return readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
}

async function askText(rl, prompt, defaultValue = '') {
  const suffix = defaultValue ? ` [${defaultValue}]` : '';
  const answer = await rl.question(`${prompt}${suffix}: `);
  return answer.trim() || defaultValue;
}

async function askSecret(rl, prompt) {
  if (process.platform === 'win32') {
    return askText(rl, prompt);
  }

  const stdin = process.stdin;
  const onData = (char) => {
    char = char.toString();
    if (char === '\n' || char === '\r' || char === '\u0004') {
      process.stdout.write('\n');
    } else {
      process.stdout.write('*');
    }
  };

  stdin.on('data', onData);
  const answer = await rl.question(`${prompt}: `);
  stdin.off('data', onData);
  return answer.trim();
}

async function askYesNo(rl, prompt, defaultYes = true) {
  const suffix = defaultYes ? '[Y/n]' : '[y/N]';
  const answer = (await rl.question(`${prompt} ${suffix} `)).trim().toLowerCase();
  if (!answer) return defaultYes;
  return answer === 'y' || answer === 'yes';
}

async function askChoice(rl, prompt, choices) {
  console.log(`\n${prompt}`);
  choices.forEach((choice, index) => console.log(`${index + 1}. ${choice.label}`));

  while (true) {
    const answer = await rl.question(`请选择 [1-${choices.length}]: `);
    const parsed = Number(answer.trim());
    if (Number.isInteger(parsed) && parsed >= 1 && parsed <= choices.length) {
      return choices[parsed - 1].value;
    }
    warn('无效选择，请重试。');
  }
}

function normalizeAgents(raw) {
  if (!raw || raw === 'all') return [...AGENTS];

  const selected = [];
  for (const item of raw.split(',').map((entry) => entry.trim()).filter(Boolean)) {
    const normalized = item === 'claude' ? 'claude-code' : item;
    if (!AGENTS.includes(normalized)) {
      throw new Error(`Unknown agent: ${item}`);
    }
    if (!selected.includes(normalized)) selected.push(normalized);
  }

  return selected;
}

function normalizeBaseURL(raw) {
  const baseURL = String(raw || '').trim();
  if (!baseURL) throw new Error('Base URL 不能为空。');
  try {
    return new URL(baseURL).toString().replace(/\/$/, '');
  } catch {
    throw new Error(`Invalid base URL: ${baseURL}`);
  }
}

function claudeBaseURL(baseURL) {
  return baseURL.replace(/\/v1\/?$/, '');
}

async function collectAgents(rl) {
  const choice = await askChoice(rl, '请选择要安装的Code Agent CLI', [
    { label: 'Claude Code', value: ['claude-code'] },
    { label: 'Codex', value: ['codex'] },
    { label: 'OpenCode', value: ['opencode'] },
    { label: '全部安装', value: [...AGENTS] },
    { label: '自定义选择', value: 'custom' },
  ]);

  if (choice !== 'custom') return choice;

  const selected = [];
  if (await askYesNo(rl, '是否安装 Claude Code?', true)) selected.push('claude-code');
  if (await askYesNo(rl, '是否安装 Codex?', true)) selected.push('codex');
  if (await askYesNo(rl, '是否安装 OpenCode?', true)) selected.push('opencode');

  if (selected.length === 0) throw new Error('至少选择一个平台。');
  return selected;
}

async function collectMode(rl) {
  return askChoice(rl, '请选择操作', [
    { label: '安装并配置', value: 'install-and-config' },
    { label: '仅安装 CLI', value: 'install-only' },
    { label: '仅写配置', value: 'config-only' },
    { label: '仅验证', value: 'verify-only' },
  ]);
}

function homeDir() {
  return os.homedir();
}

function configDir() {
  if (process.platform === 'win32') {
    return path.join(homeDir(), '.config');
  }
  return process.env.XDG_CONFIG_HOME || path.join(homeDir(), '.config');
}

function timestamp() {
  const now = new Date();
  const pad = (value) => String(value).padStart(2, '0');
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;
}

function ensureDir(dir, options) {
  if (options.dryRun) {
    console.log(`[dry-run] mkdir ${dir}`);
    return;
  }
  fs.mkdirSync(dir, { recursive: true });
}

function backupFile(filePath, options) {
  if (!fs.existsSync(filePath)) return;
  const backupPath = `${filePath}.bak.${timestamp()}`;
  if (options.dryRun) {
    console.log(`[dry-run] copy ${filePath} ${backupPath}`);
    return;
  }
  fs.copyFileSync(filePath, backupPath);
  success(`已备份 ${filePath} -> ${backupPath}`);
}

async function writeFileSafely(filePath, content, options, rl) {
  ensureDir(path.dirname(filePath), options);

  if (fs.existsSync(filePath) && !options.force && !options.yes) {
    const overwrite = await askYesNo(rl, `文件已存在，是否覆盖 ${filePath}?`, false);
    if (!overwrite) {
      warn(`跳过写入 ${filePath}`);
      return;
    }
  }

  backupFile(filePath, options);

  if (options.dryRun) {
    console.log(`[dry-run] write ${filePath}`);
    return;
  }

  fs.writeFileSync(filePath, `${content}\n`, 'utf8');
}

function commandCandidates(command) {
  if (process.platform !== 'win32') return [command];

  const candidates = [`${command}.cmd`, command];
  if (process.env.APPDATA) {
    candidates.push(path.join(process.env.APPDATA, 'npm', `${command}.cmd`));
    candidates.push(path.join(process.env.APPDATA, 'npm', command));
  }
  return [...new Set(candidates)];
}

function commandExists(command) {
  if (process.platform === 'win32') {
    return commandCandidates(command).some((candidate) => {
      const result = spawnSync('where', [candidate], { stdio: 'ignore', shell: true });
      if (result.status === 0) return true;
      return fs.existsSync(candidate);
    });
  }

  const probe = process.platform === 'win32' ? 'where' : 'command';
  const args = process.platform === 'win32' ? [command] : ['-v', command];
  const result = spawnSync(probe, args, { stdio: 'ignore', shell: process.platform !== 'win32' });
  return result.status === 0;
}

function runCommandCandidate(command, args, options) {
  for (const candidate of commandCandidates(command)) {
    if (options.dryRun) {
      console.log(`[dry-run] ${candidate} ${args.join(' ')}`);
      return true;
    }

    const result = process.platform === 'win32'
      ? spawnSync('cmd.exe', ['/d', '/s', '/c', `"${candidate}" ${args.join(' ')}`], {
          stdio: 'ignore',
        })
      : spawnSync(candidate, args, { stdio: 'ignore' });
    if (result.status === 0) return true;
  }
  return false;
}

function run(command, args, options, env = process.env) {
  if (options.dryRun) {
    console.log(`[dry-run] ${command} ${args.join(' ')}`);
    return;
  }

  if (options.verbose) {
    console.log(`$ ${command} ${args.join(' ')}`);
  }

  const result = spawnSync(command, args, { stdio: 'inherit', shell: process.platform === 'win32', env });
  if (result.status !== 0) {
    throw new Error(`Command failed: ${command} ${args.join(' ')}`);
  }
}

function installNpmPackage(packageName, binaryName, options) {
  if (commandExists(binaryName) && !options.force) {
    success(`${binaryName} 已安装`);
    return;
  }

  if (!commandExists('node') || !commandExists('npm')) {
    throw new Error('需要 Node.js 和 npm。请先安装 Node.js 18+ 后重试。');
  }

  run('npm', ['install', '-g', packageName], options);

  if (!options.dryRun && !commandExists(binaryName)) {
    const hint = process.platform === 'win32' && process.env.APPDATA
      ? ` Expected candidate: ${path.join(process.env.APPDATA, 'npm', `${binaryName}.cmd`)}`
      : '';
    throw new Error(`${binaryName} was installed but is not runnable from PATH.${hint}`);
  }
}

function opencodeConfig(apiKey, baseURL) {
  const models = Object.fromEntries(
    Object.entries(OPENCODE_MODELS).map(([id, name]) => [
      id,
      {
        name,
        modalities: {
          input: supportsImageInput(id) ? ['text', 'image'] : ['text'],
          output: ['text'],
        },
      },
    ])
  );

  return JSON.stringify(
    {
      $schema: 'https://opencode.ai/config.json',
      provider: {
        [PROVIDER_KEY]: {
          npm: '@ai-sdk/openai-compatible',
          name: PROVIDER_KEY,
          options: {
            apiKey,
            baseURL,
          },
          models,
        },
      },
      model: `${PROVIDER_KEY}/${DEFAULT_MODEL}`,
    },
    null,
    2
  );
}

async function writeOpencodeConfig(runtime, options, rl) {
  const opencodeDir = path.join(configDir(), 'opencode');
  const activeConfigPath = path.join(opencodeDir, 'opencode.json');
  const externalConfigPath = path.join(opencodeDir, 'opencode.external.json');
  const dacsConfigPath = path.join(opencodeDir, 'opencode.dacs.json');
  const externalConfig = opencodeConfig(runtime.apiKey, runtime.externalBaseURL);

  await writeFileSafely(activeConfigPath, externalConfig, options, rl);
  await writeFileSafely(externalConfigPath, externalConfig, options, rl);
  await writeFileSafely(dacsConfigPath, opencodeConfig(runtime.apiKey, runtime.dacsBaseURL), options, rl);
  success(`OpenCode DACS 外配置: ${externalConfigPath}`);
  success(`OpenCode DACS 内配置: ${dacsConfigPath}`);
}

function codexConfig(baseURL) {
  const catalogPath = path.join(homeDir(), '.codex', 'models.json');
  return `model_provider = "${PROVIDER_KEY}"
model = "${DEFAULT_CODEX_MODEL}"
model_reasoning_effort = "high"
network_access = "enabled"
disable_response_storage = true
model_catalog_json = ${JSON.stringify(catalogPath)}

[model_providers.${JSON.stringify(PROVIDER_KEY)}]
name = "OpenAI"
base_url = "${baseURL}"
wire_api = "responses"
requires_openai_auth = true`;
}

function codexModelCatalog() {
  return JSON.stringify(
    {
      models: Object.entries(OPENCODE_MODELS).map(([slug, displayName], index) => ({
        slug,
        display_name: displayName,
        description: `${displayName} via ${PROVIDER_KEY}`,
        default_reasoning_level: null,
        supported_reasoning_levels: [],
        shell_type: 'default',
        visibility: 'list',
        supported_in_api: true,
        priority: index + 1,
        additional_speed_tiers: [],
        service_tiers: [],
        availability_nux: null,
        upgrade: null,
        base_instructions: '',
        model_messages: null,
        supports_reasoning_summaries: false,
        default_reasoning_summary: 'auto',
        support_verbosity: false,
        default_verbosity: null,
        apply_patch_tool_type: null,
        web_search_tool_type: 'text',
        truncation_policy: {
          mode: 'bytes',
          limit: 10000,
        },
        supports_parallel_tool_calls: false,
        supports_image_detail_original: false,
        context_window: 272000,
        max_context_window: 272000,
        auto_compact_token_limit: null,
        effective_context_window_percent: 95,
        experimental_supported_tools: [],
        input_modalities: supportsImageInput(slug) ? ['text', 'image'] : ['text'],
        supports_search_tool: false,
      })),
    },
    null,
    2
  );
}

function codexAuth(apiKey) {
  return JSON.stringify(
    {
      OPENAI_API_KEY: apiKey,
    },
    null,
    2
  );
}

async function writeCodexConfig(runtime, options, rl) {
  const codexDir = path.join(homeDir(), '.codex');
  const activeConfigPath = path.join(codexDir, 'config.toml');
  const externalConfigPath = path.join(codexDir, 'config.external.toml');
  const dacsConfigPath = path.join(codexDir, 'config.dacs.toml');
  const externalConfig = codexConfig(runtime.externalBaseURL);

  await writeFileSafely(activeConfigPath, externalConfig, options, rl);
  await writeFileSafely(externalConfigPath, externalConfig, options, rl);
  await writeFileSafely(dacsConfigPath, codexConfig(runtime.dacsBaseURL), options, rl);
  success(`Codex DACS 外配置: ${externalConfigPath}`);
  success(`Codex DACS 内配置: ${dacsConfigPath}`);
}

async function codexLogin(apiKey, options) {
  if (options.dryRun) {
    console.log('[dry-run] codex login --with-api-key');
    return false;
  }

  const result = spawnSync('codex', ['login', '--with-api-key'], {
    input: `${apiKey}\n`,
    stdio: ['pipe', options.verbose ? 'inherit' : 'ignore', options.verbose ? 'inherit' : 'ignore'],
    shell: process.platform === 'win32',
  });
  return result.status === 0;
}

function claudeSettings(apiKey, baseURL) {
  return JSON.stringify(
    {
      availableModels: Object.keys(OPENCODE_MODELS),
      env: {
        ANTHROPIC_API_KEY: apiKey,
        ANTHROPIC_AUTH_TOKEN: apiKey,
        ANTHROPIC_BASE_URL: claudeBaseURL(baseURL),
        ANTHROPIC_MODEL: DEFAULT_MODEL,
      },
    },
    null,
    2
  );
}

function claudeGlobalConfig(existing = {}) {
  return JSON.stringify(
    {
      ...existing,
      hasCompletedOnboarding: true,
    },
    null,
    2
  );
}

async function writeClaudeSettings(runtime, options, rl) {
  const claudeDir = path.join(homeDir(), '.claude');
  const activeSettingsPath = path.join(claudeDir, 'settings.json');
  const externalSettingsPath = path.join(claudeDir, 'settings.external.json');
  const dacsSettingsPath = path.join(claudeDir, 'settings.dacs.json');
  const externalSettings = claudeSettings(runtime.apiKey, runtime.externalBaseURL);

  await writeFileSafely(activeSettingsPath, externalSettings, options, rl);
  await writeFileSafely(externalSettingsPath, externalSettings, options, rl);
  await writeFileSafely(dacsSettingsPath, claudeSettings(runtime.apiKey, runtime.dacsBaseURL), options, rl);
  success(`Claude Code DACS 外配置: ${externalSettingsPath}`);
  success(`Claude Code DACS 内配置: ${dacsSettingsPath}`);
}

function readJsonFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return {};
  }
}

const agentDefinitions = {
  'claude-code': {
    install: (options) => installNpmPackage('@anthropic-ai/claude-code', 'claude', options),
    configure: async (runtime, options, rl) => {
      await writeClaudeSettings(runtime, options, rl);
      const claudeJsonPath = path.join(homeDir(), '.claude.json');
      await writeFileSafely(claudeJsonPath, claudeGlobalConfig(readJsonFile(claudeJsonPath)), options, rl);
    },
    verify: (options) => verifyCommand('claude', options),
    next: () => 'Claude Code: run claude.',
  },
  codex: {
    install: (options) => installNpmPackage('@openai/codex', 'codex', options),
    configure: async (runtime, options, rl) => {
      await writeCodexConfig(runtime, options, rl);
      await writeFileSafely(path.join(homeDir(), '.codex', 'models.json'), codexModelCatalog(), options, rl);
      if (!(await codexLogin(runtime.apiKey, options))) {
        await writeFileSafely(path.join(homeDir(), '.codex', 'auth.json'), codexAuth(runtime.apiKey), options, rl);
      }
    },
    verify: (options) => verifyCommand('codex', options),
    next: () => 'Codex: run codex.',
  },
  opencode: {
    install: (options) => installNpmPackage('opencode-ai@latest', 'opencode', options),
    configure: async (runtime, options, rl) => {
      await writeOpencodeConfig(runtime, options, rl);
    },
    verify: (options) => verifyCommand('opencode', options),
    next: () => `OpenCode: run 'opencode' and use ${PROVIDER_KEY}/${DEFAULT_MODEL}.`,
  },
};

function verifyCommand(command, options) {
  if (options.dryRun) {
    console.log(`[dry-run] ${commandCandidates(command)[0]} --version`);
    return;
  }

  if (runCommandCandidate(command, ['--version'], options)) {
    success(`${command} 可用`);
  } else {
    const candidates = commandCandidates(command).join(', ');
    warn(`${command} --version 执行失败。Checked: ${candidates}`);
  }
}

async function collectRuntime(options) {
  const rl = createPrompt();
  try {
    if (!process.stdin.isTTY && process.platform !== 'win32' && !options.agents && !options.yes) {
      throw new Error(
        'Interactive input is unavailable because stdin is not a TTY. ' +
          'Run from a terminal or use: bash -s -- --agents all --api-key <key> --yes'
      );
    }

    const agents = options.agents ? normalizeAgents(options.agents) : await collectAgents(rl);
    const mode = options.mode || (options.yes ? 'install-and-config' : await collectMode(rl));

    const envExternalBaseURL = process.env.AI_TOOLS_EXTERNAL_BASE_URL || process.env.AI_TOOLS_BASE_URL || process.env.OPENAI_BASE_URL || DEFAULT_EXTERNAL_BASE_URL;
    const envDacsBaseURL = process.env.AI_TOOLS_DACS_BASE_URL || process.env.DACS_BASE_URL || DEFAULT_DACS_BASE_URL;
    const externalBaseURL = normalizeBaseURL(
      options.externalBaseURL || (options.yes ? envExternalBaseURL : await askText(rl, '请输入 DACS 外 Base URL', envExternalBaseURL))
    );
    const dacsBaseURL = normalizeBaseURL(
      options.dacsBaseURL || (options.yes ? envDacsBaseURL : await askText(rl, '请输入 DACS 内 Base URL', envDacsBaseURL))
    );

    let apiKey = options.apiKey || (options.yes ? process.env.AI_TOOLS_API_KEY || process.env.OPENAI_API_KEY || '' : '');
    if (mode !== 'install-only' && !apiKey) {
      if (options.yes) throw new Error('Missing --api-key or AI_TOOLS_API_KEY/OPENAI_API_KEY for non-interactive configuration.');
      apiKey = await askSecret(rl, '请输入 API Key');
    }

    if (mode !== 'install-only' && !apiKey) {
      throw new Error('API Key 不能为空。');
    }

    return { rl, runtime: { agents, mode, apiKey, externalBaseURL, dacsBaseURL } };
  } catch (error) {
    rl.close();
    throw error;
  }
}

function printPlan(runtime, options) {
  title('安装计划');
  console.log(`DACS 外 Base URL: ${runtime.externalBaseURL}`);
  console.log(`DACS 内 Base URL: ${runtime.dacsBaseURL}`);
  console.log(`Default model: ${DEFAULT_MODEL}`);
  console.log(`Agents: ${runtime.agents.join(', ')}`);
  console.log(`Mode: ${runtime.mode}`);
  console.log(`API Key: ${runtime.apiKey ? maskSecret(runtime.apiKey) : 'not required for this mode'}`);
  console.log(`Dry run: ${options.dryRun ? 'yes' : 'no'}`);
  console.log(`Force: ${options.force ? 'yes' : 'no'}`);
}

async function executePlan(runtime, options, rl) {
  for (const agent of runtime.agents) {
    const definition = agentDefinitions[agent];
    if (runtime.mode === 'install-and-config' || runtime.mode === 'install-only') {
      step(`安装 ${agent}`);
      definition.install(options);
    }

    if (runtime.mode === 'install-and-config' || runtime.mode === 'config-only') {
      step(`配置 ${agent}`);
      await definition.configure(runtime, options, rl);
    }
  }

  step('验证 CLI');
  for (const agent of runtime.agents) {
    agentDefinitions[agent].verify(options);
  }

}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  title('AI Agent Installer');
  const { rl, runtime } = await collectRuntime(options);

  try {
    printPlan(runtime, options);

    if (!options.yes) {
      const confirmed = await askYesNo(rl, '继续执行?', true);
      if (!confirmed) {
        warn('已取消。');
        return;
      }
    }

    await executePlan(runtime, options, rl);

    title('下一步');
    for (const agent of runtime.agents) {
      console.log(agentDefinitions[agent].next());
    }
  } finally {
    rl.close();
  }
}

main().catch((error) => {
  console.error(`Error: ${redact(error.message, process.env.AI_TOOLS_API_KEY || process.env.OPENAI_API_KEY || '')}`);
  process.exit(1);
});
