# OpenCode Bailian Setup

给 OpenCode 配置阿里云 Bailian Token Plan 的跨平台安装脚本。

支持：
- macOS
- Windows

脚本会做这些事：
- 检测是否已安装 `opencode`
- 未安装时尝试自动安装
- 写入全局 `opencode.json`
- 将 `bailian-token-plan` provider 合并进现有配置
- 备份旧配置
- 校验写入结果

## 文件

- `setup-opencode-bailian.js`：主脚本
- `run-setup.sh`：macOS/Linux shell 包装脚本
- `run-setup.ps1`：Windows PowerShell 包装脚本

## 前提

- 机器上已安装 Node.js
- 你有阿里云 Bailian Token Plan 的 API Key

## 默认配置

脚本默认写入以下 provider：

- provider key：`bailian-token-plan`
- base URL：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- 默认模型：`qwen3.6-plus`

内置模型：
- `qwen3.6-plus`
- `MiniMax-M2.5`
- `glm-5`
- `deepseek-v3.2`

写入成功后，顶层 `model` 会被设置为：
- `bailian-token-plan/qwen3.6-plus`
- 或你通过 `--model` 指定的已支持模型

## 配置文件位置

脚本默认修改全局配置：

- macOS：`~/.config/opencode/opencode.json`
- Windows：`%APPDATA%\opencode\opencode.json`

## 快速开始

### macOS

```bash
./run-setup.sh --api-key YOUR_API_KEY
```

### Windows PowerShell

```powershell
.\run-setup.ps1 --api-key YOUR_API_KEY
```

### 直接运行 Node 脚本

```bash
node setup-opencode-bailian.js --api-key YOUR_API_KEY
```

## Dry Run

只预览将要写入的 provider，不安装、不写文件：

```bash
./run-setup.sh --api-key YOUR_API_KEY --dry-run
```

## 参数

### `--api-key`
Bailian API Key。

```bash
./run-setup.sh --api-key YOUR_API_KEY
```

### `--base-url`
覆盖默认 base URL。

```bash
./run-setup.sh --api-key YOUR_API_KEY --base-url https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
```

### `--model`
指定要选中的模型。只允许以下值：
- `qwen3.6-plus`
- `MiniMax-M2.5`
- `glm-5`
- `deepseek-v3.2`

```bash
./run-setup.sh --api-key YOUR_API_KEY --model glm-5
```

### `--force`
如果配置里已经存在 `bailian-token-plan`，强制覆盖。

```bash
./run-setup.sh --api-key YOUR_API_KEY --force
```

### `--dry-run`
预览模式，不安装、不写文件。

```bash
./run-setup.sh --api-key YOUR_API_KEY --dry-run
```

## 环境变量

如果不传 `--api-key`，脚本会按下面的优先级读取：

1. `DASHSCOPE_API_KEY`
2. `BAILIAN_API_KEY`

可选环境变量：
- `BAILIAN_BASE_URL`
- `BAILIAN_MODEL`

示例：

```bash
export DASHSCOPE_API_KEY=YOUR_API_KEY
./run-setup.sh
```

PowerShell：

```powershell
$env:DASHSCOPE_API_KEY = "YOUR_API_KEY"
.\run-setup.ps1
```

## 安装策略

如果机器上没有 `opencode`，脚本会尝试自动安装。

### macOS
按顺序尝试：

```bash
brew install anomalyco/tap/opencode
npm i -g opencode-ai@latest
```

### Windows
按顺序尝试：

```powershell
scoop install opencode
choco install opencode
npm i -g opencode-ai@latest
```

如果自动安装失败，脚本会打印手动安装建议。

## 成功后会发生什么

成功写入后，脚本会：
- 保留你已有的其他 provider
- 备份旧的 `opencode.json`
- 写入 `bailian-token-plan`
- 设置顶层 `model`
- 输出下一步提示

成功输出示例：

```text
OpenCode ready. Config written to /path/to/opencode.json
Next steps:
1. opencode
2. Use provider bailian-token-plan
3. Start with model qwen3.6-plus
```

## 常见场景

### 1. 已有别的 provider，不想丢失
脚本会合并，不会覆盖其他 provider。

### 2. 已经有 `bailian-token-plan`
默认会报错：

```text
bailian-token-plan already exists
```

如果你要覆盖，带上：

```bash
./run-setup.sh --api-key YOUR_API_KEY --force
```

### 3. 配置文件坏了
如果现有 `opencode.json` 不是合法 JSON，脚本会停止，并保留原文件。

### 4. 指定了不支持的模型
脚本会直接报错，例如：

```text
Unsupported model: xxx. Choose one of: qwen3.6-plus, MiniMax-M2.5, glm-5, deepseek-v3.2
```

## 验证

运行测试：

```bash
node --test tests/setup-opencode-bailian.test.js
```

## 备注

当前脚本默认操作的是 `opencode.json`，不是项目级配置。
如果后面要扩展成支持项目级配置、`--config-path` 或 GUI 安装器，可以在这个版本上继续加。