# dispatch

Claude Code 总调度：Claude 拆任务、写任务卡，用 `agent-run` 派给工人 agent，验收后合并。

- `SKILL.md`：Claude Code skill（`/dispatch`），调度流程、工人分工、任务卡模板、验收规则。
- `agent-run`：把一张任务卡派给一个工人，独立 worktree + 分支，跑完自动执行验收命令，结果写入 `~/.agent-runs/<run>/meta.json`。

## 工人

| worker | harness | 模型 |
|---|---|---|
| `deepseek` | Claude Code（`claude -p`，开启沙盒） | `deepseek-flash`，经兼容 Anthropic 的网关 |
| `codex` | 官方 `codex exec`（`workspace-write` 沙盒） | codex 默认模型，ChatGPT 账号登录 |

涉及 computer use（操作桌面 App、浏览器、GUI）的任务一律交给 codex：`--mode cu`，依赖 codex 的 computer-use 插件；`agent-run` 拒绝把 `cu` 任务派给 deepseek。

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
agent-run codex card.md --dir <repo> --net
agent-run codex card.md --mode cu --apps Calculator --test "test -s result.txt"
```

## 实时查看

`agent-run` 边跑边把工人的事件翻译成可读进度写进运行目录的 `live.log`（命令与退出码、工具调用/computer use 每一步、文件改动、工人的消息）；直接在终端里跑时也会实时打印。另开终端跟踪：

```bash
agent-run watch <name>      # 跟踪指定任务，结束后打印结果摘要并退出
agent-run watch             # 跟踪最新的任务
```

## 权限在派活时决定

codex 在 `exec` 模式下遇到授权不会弹窗，只会失败，所以权限要在派活时就给好：

- `--net`：允许工人的命令联网（默认沙盒不能联网）。
- `--add-dir DIR`：额外的可写目录。
- `--apps A,B`：computer use 要操作的 App。必须已经授权过（记录在本机 `~/.agent-runs/approved-apps.json`），否则 `agent-run` 不启动并以退出码 3 结束，打印 `approve_cmd`。在终端里运行一次这条命令（交互式 codex），选择始终允许即可。跑完后能打开的 App 会自动记入已授权列表。
- `--auto-approve`：codex 的 `--approve-for-me`，由 codex 的审核模型代批越权请求。默认不用：它不覆盖 computer use 的 App 授权。
