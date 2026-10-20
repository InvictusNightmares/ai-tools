# dispatch

Claude Code 总调度：Claude 拆任务、写任务卡，用 `agent-run` 派给工人 agent，验收后合并。

- `SKILL.md`：Claude Code skill（`/dispatch`），调度流程、工人分工、任务卡模板、验收规则。
- `agent-run`：把一张任务卡派给一个工人，独立 worktree + 分支，跑完自动执行验收命令，结果写入 `~/.agent-runs/<run>/meta.json`。

## 工人

| worker | harness | 模型 |
|---|---|---|
| `deepseek` | Claude Code（`claude -p`，开启沙盒） | `deepseek-flash`，经兼容 Anthropic 的网关 |
| `codex` | 官方 `codex exec`（`workspace-write` 沙盒） | codex 默认模型，ChatGPT 账号登录 |

## 安装

```bash
ln -s "$PWD/script/dispatch" ~/.claude/skills/dispatch
ln -s "$PWD/script/dispatch/agent-run" ~/.local/bin/agent-run
```

在 `~/.zshrc` 中配置网关（不要提交到仓库）：

```bash
export GATEWAY_BASE_URL='https://<your-gateway>'
export GATEWAY_API_KEY='<your-key>'
```

依赖：`claude`（Claude Code CLI）、`codex`（已登录）、`python3`、`git`。

## 用法

```bash
agent-run deepseek card.md --dir <repo> --test "python3 -m pytest -q"
agent-run codex card.md --dir <repo> --mode ro
```
