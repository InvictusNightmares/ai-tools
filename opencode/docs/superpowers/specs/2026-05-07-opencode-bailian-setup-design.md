# OpenCode 阿里云 Token Plan 跨平台配置脚本设计

## 目标

提供一套适用于 macOS 和 Windows 的 OpenCode 配置脚本，用于接入阿里云 Model Studio Token Plan 团队版。

脚本需要完成以下工作：

1. 检测本机是否已安装 `opencode`
2. 未安装时尝试自动安装
3. 默认写入全局 `opencode.json`
4. 将阿里云 Token Plan provider 合并进现有配置，而不是覆盖其他配置
5. 完成配置后执行校验并输出清晰提示

目标是让公司成员尽量通过一次执行完成安装、配置和验证，减少手工编辑 JSON 的步骤。

## 非目标

本设计不包含以下内容：

- 不实现 Linux 支持
- 不处理公司内部私有安装源
- 不自动验证真实模型调用是否成功
- 不修改除目标 provider 以外的现有 provider 配置
- 不负责管理或轮换 API Key

## 交付物

主交付物：

- `setup-opencode-bailian.js`

辅助交付物：

- `run-setup.sh`
- `run-setup.ps1`

主脚本负责全部业务逻辑。辅助脚本只负责简化启动方式。

## 用户体验

默认使用方式：

```bash
node setup-opencode-bailian.js
```

支持的输入方式优先级如下：

1. 命令行参数
2. 环境变量
3. 交互输入

支持的关键参数：

- `--api-key`
- `--base-url`
- `--model`
- `--force`
- `--dry-run`

默认行为：

- 默认写入全局配置
- 默认 provider key 为 `bailian-token-plan`
- 默认 base URL 为 `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- 默认模型为 `qwen3.6-plus`

## 配置内容

脚本写入的 provider 结构如下：

- provider key：`bailian-token-plan`
- npm：`@ai-sdk/openai-compatible`
- name：`Model Studio Token Plan 团队版`
- options.baseURL：`https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
- options.apiKey：用户提供的 API Key

脚本默认写入以下模型定义：

- `qwen3.6-plus`
- `MiniMax-M2.5`
- `glm-5`
- `deepseek-v3.2`

默认模型选择为 `qwen3.6-plus`。脚本会将这些模型定义完整写入目标 provider，便于后续直接切换。

## 系统行为

### 1. 平台识别

脚本通过 Node.js 运行时判断当前平台是否为 macOS 或 Windows。

- macOS：继续执行
- Windows：继续执行
- 其他平台：明确提示当前版本不支持，并退出

### 2. OpenCode 检测

脚本先执行 `opencode --version`。

- 成功：视为已安装，进入配置阶段
- 失败：进入自动安装阶段

### 3. 自动安装

如果未检测到 `opencode`，脚本尝试自动安装。

安装策略采用“首选方式失败后尝试备用方式”的顺序。

设计要求：

- macOS 使用该平台主流安装方式优先尝试
- Windows 使用该平台主流安装方式优先尝试
- 自动安装全部失败时，不继续伪造成功，而是打印清晰的手动安装建议
- 手动安装建议需要包含：建议命令、重新运行脚本的方法、常见失败原因提示

具体安装命令属于实现细节，应在实现阶段依据 OpenCode 官方安装文档确定。

### 4. 全局配置路径解析

脚本默认写入全局配置文件，不要求用户手动指定路径。

路径解析按平台处理：

- macOS：使用用户级配置目录
- Windows：使用用户级配置目录

具体路径值属于实现细节，应在实现阶段依据 OpenCode 官方配置文档确定，不在设计中写死。

如果目标目录不存在，脚本应自动创建。

### 5. 读取和备份现有配置

如果配置文件存在：

- 读取当前 JSON 内容
- 解析 JSON
- 在写入前创建备份文件

如果配置文件不存在：

- 创建新的最小合法 JSON 文档

如果配置文件存在但 JSON 非法：

- 不直接覆盖原文件
- 输出错误说明
- 告知用户文件路径和修复建议
- 退出

### 6. 配置合并规则

脚本只修改目标 provider，不影响其他配置。

合并规则如下：

- 保留现有 `$schema`
- 保留现有 `provider` 下的其他项
- 若不存在 `provider` 对象，则自动创建
- 若不存在 `provider["bailian-token-plan"]`，则新增
- 若已存在 `provider["bailian-token-plan"]`：
  - 默认提示用户选择覆盖更新还是跳过
  - 若传入 `--force`，则直接覆盖更新

脚本只更新目标 provider 的内容，不对其他 provider 做格式化以外的逻辑改动。

### 7. 凭证获取

凭证读取优先级如下：

1. `--api-key` 参数
2. 环境变量
3. 交互输入

`baseURL` 和默认模型也遵循同样的覆盖规则：

1. 参数值优先
2. 环境变量次之
3. 使用默认值

如果缺少 API Key 且没有交互输入能力，脚本应明确提示如何通过参数或环境变量传入。

### 8. 成功校验

脚本写入后执行以下检查：

1. `opencode` 命令可执行
2. 配置文件存在
3. 配置文件 JSON 可解析
4. `provider.bailian-token-plan` 存在
5. `provider.bailian-token-plan.options.baseURL` 存在
6. `provider.bailian-token-plan.options.apiKey` 存在
7. `provider.bailian-token-plan.models.qwen3.6-plus` 存在

如果以上检查通过，则输出成功结果。

### 9. 输出信息

成功时输出：

- OpenCode 是否已安装
- 配置文件路径
- 已写入的 provider 名称
- 默认模型名称
- 建议的下一步命令

失败时输出：

- 失败步骤
- 失败原因
- 修复建议
- 是否生成了备份文件

## 默认写入配置示意

脚本最终应写入与下述结构等价的 provider：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "bailian-token-plan": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Model Studio Token Plan 团队版",
      "options": {
        "baseURL": "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "apiKey": "YOUR_API_KEY"
      },
      "models": {
        "qwen3.6-plus": {
          "name": "Qwen3.6 Plus",
          "modalities": {
            "input": ["text", "image"],
            "output": ["text"]
          },
          "options": {
            "thinking": {
              "type": "enabled",
              "budgetTokens": 8192
            }
          },
          "limit": {
            "context": 1000000,
            "output": 65536
          }
        },
        "MiniMax-M2.5": {
          "name": "MiniMax M2.5",
          "modalities": {
            "input": ["text"],
            "output": ["text"]
          },
          "options": {
            "thinking": {
              "type": "enabled",
              "budgetTokens": 8192
            }
          },
          "limit": {
            "context": 196608,
            "output": 24576
          }
        },
        "glm-5": {
          "name": "GLM-5",
          "modalities": {
            "input": ["text"],
            "output": ["text"]
          },
          "options": {
            "thinking": {
              "type": "enabled",
              "budgetTokens": 8192
            }
          },
          "limit": {
            "context": 202752,
            "output": 16384
          }
        },
        "deepseek-v3.2": {
          "name": "DeepSeek V3.2",
          "modalities": {
            "input": ["text"],
            "output": ["text"]
          },
          "limit": {
            "context": 131072,
            "output": 16384
          }
        }
      }
    }
  }
}
```

## 错误处理

脚本需要覆盖以下错误场景：

- 当前平台不是 Windows 或 macOS
- `opencode` 未安装且自动安装失败
- 配置目录创建失败
- 配置文件存在但 JSON 非法
- 配置文件无写权限
- 缺少 API Key
- provider 已存在且用户拒绝覆盖

这些错误都需要返回非零退出码，并输出可执行的后续建议。

## 测试策略

至少覆盖以下验证场景：

1. 本机已安装 `opencode`，且全局配置文件不存在
2. 本机已安装 `opencode`，且全局配置文件存在并包含其他 provider
3. 本机已安装 `opencode`，且目标 provider 已存在
4. 本机未安装 `opencode`，自动安装成功
5. 本机未安装 `opencode`，自动安装失败
6. 全局配置文件内容损坏
7. 使用 `--dry-run`
8. 使用 `--force`

## 实现边界

为了保证脚本简单稳定，本次实现不增加以下能力：

- 不支持 Linux
- 不增加图形界面
- 不接入公司内部密钥托管系统
- 不做网络层健康探测或真实 API 调用验收
- 不处理多个 provider key 的批量创建

## 推荐的下一步

下一步进入实现计划阶段时，应明确：

1. OpenCode 官方推荐安装命令
2. OpenCode 全局配置文件在 macOS 和 Windows 上的准确路径
3. 参数解析方案
4. 备份文件命名规则
5. 校验输出文案
