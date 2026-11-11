# DACS 双向通讯桥

让 DACS 安全空间（域 104）和个人域（域 6）互相访问对方的本地服务。
一条命令可以同时拉起两边服务、双向桥和域 104 子进程。

## 架构

```text
外部客户端 --TCP(域6)--> outside 监听(域6) --匿名管道--> inside 子进程(域104) --TCP(域104)--> 内部服务
DACS 浏览器 --TCP(域104)--> inside 监听(域104) --匿名管道--> outside 角色(域6) --TCP(域6)--> 外部服务
```

DACS 的 NELO 对跨域 TCP 环回双向 `DENY`，同域 TCP `PASS`。
因此桥的两端各自完成同域 TCP，跨域部分只走宿主到子进程的匿名管道。
详细封禁机制见 [DACS-reverse-blocking-analysis.md](../DACS-reverse-blocking-analysis.md)。

## 文件

| 文件 | 说明 |
|---|---|
| `dacs_bidir_bridge.py` | 桥主程序；已内嵌压缩的 `python-real` |
| `README.md` | 本文 |

## 前置条件

- DACS 已登录，安全空间浏览器可用。
- **只在外面（宿主）终端启动一次**；里面不要单独启动桥。
- 默认域 104 暂存目录：`~/meili/zhangcheng/Applications/104`。
  如果 DACS 用户名不是 `zhangcheng`，用 `--inside-python` 指向实际的
  `.../Applications/104/python-real`。
- 脚本会自动准备 `python-real`：优先探测宿主真实 Python（`proc_pidpath`），
  找不到时解压脚本内嵌副本；无需手工拷贝。

## 快速开始

### 1. 两个 Downloads 目录互访

```bash
cd ~/code/ai-tools
python3 script/dacs/bridge/dacs_bidir_bridge.py \
  --inside-serve "$HOME/meili/zhangcheng/104/Downloads:18090" \
  --outside-serve "$HOME/Downloads:18091" \
  --inside-listen 18101 --outside-listen 18102
```

| 访问地址 | 到达 |
|---|---|
| 外面浏览器/curl `http://127.0.0.1:18102` | 里面的 Downloads |
| DACS 浏览器 `http://127.0.0.1:18101` | 外面的 Downloads |

### 2. 服务已经手动启动

里面用域 104 的可执行文件启动（例如 `$DACS_STAGING/python-real` 或
`$DACS_STAGING/node`），外面正常启动，然后只起桥：

```bash
cd ~/code/ai-tools
python3 script/dacs/bridge/dacs_bidir_bridge.py \
  --inside-target 127.0.0.1:8000 \
  --outside-target 127.0.0.1:3000
```

- 外面 → 里面：`http://127.0.0.1:18102` → 域 104 的 `8000`
- 里面 → 外面：DACS 浏览器 `http://127.0.0.1:18101` → 域 6 的 `3000`

### 3. 自动拉起自定义服务

```bash
cd ~/code/ai-tools
python3 script/dacs/bridge/dacs_bidir_bridge.py \
  --inside-cmd 'cd /path/to/project && "$DACS_STAGING/python-real" app.py' --inside-port 8000 \
  --outside-cmd 'cd /path/to/project && npm run dev' --outside-port 3000
```

`--inside-cmd` 里的监听进程必须使用域 104 暂存目录下的可执行文件，
否则它会被判为域 6，inside 子进程访问它时会被 `DENY`。

## 参数

| 参数 | 作用 |
|---|---|
| `--inside-listen` | 域104 监听端口，DACS 浏览器访问它，默认 `18101` |
| `--outside-listen` | 域6 监听端口，外面客户端访问它，默认 `18102` |
| `--inside-target` | 域104 目标服务，外面客户端经 `18102` 到达它 |
| `--outside-target` | 域6 目标服务，DACS 浏览器经 `18101` 到达它 |
| `--inside-serve DIR[:PORT]` | 自动用域104 Python 起静态服务，默认端口 `8000` |
| `--outside-serve DIR[:PORT]` | 自动用宿主 Python 起静态服务，默认端口 `3000` |
| `--inside-cmd` / `--outside-cmd` | 自动拉起自定义服务 |
| `--inside-port` / `--outside-port` | 配合 `--inside-cmd` / `--outside-cmd` 使用 |
| `--inside-python` | 域104 Python 真实二进制路径 |
| `--bind` | 监听地址，默认 `127.0.0.1` |

## 停止与清理

- 在启动桥的终端按 `Ctrl+C`，脚本会停掉它拉起的 inside/outside 服务和桥子进程。
- 暂存目录里的 `dacs_bidir_bridge_inside.py` 是运行时自动复制的，可以随时删除，
  下次运行会重建。
- 日志：`/tmp/dacs_bridge_inside-serve.log`、`/tmp/dacs_bridge_outside-serve.log`、
  `/tmp/dacs_bridge_inside-cmd.log`、`/tmp/dacs_bridge_outside-cmd.log`。

## 原理与验证

NELO 日志应出现同域 `PASS`：

```text
domain(104) to 127 domain(104), dstPath:.../Applications/104/python-real, 127 PASS
pri 127 to domain(6), dstPath:/opt/homebrew/.../Python, 127 PASS
```

跨域 TCP 不会出现在 NELO 日志里，因为跨域只走匿名管道。

## 排障

| 现象 | 处理 |
|---|---|
| `Address already in use` | 改 `--inside-listen` / `--outside-listen` 或对应服务端口 |
| `inside python` 准备失败 | 用 `--inside-python` 指定真实 framework Python；`DACS_BRIDGE_PREFER_EMBEDDED=1` 强制用内嵌副本 |
| `connect ... failed` | 目标服务未启动或不在正确域；检查端口和启动方式 |
| 里面服务被 DENY | 服务的实际监听进程不在域104路径；用 `$DACS_STAGING/python-real` / `node` 启动 |
| 桥启动后无流量 | 检查 `lsof -nP -iTCP:18101 -iTCP:18102 -sTCP:LISTEN` 和桥日志 |

## 注意

- 只在外面启动；里面手动启动 `--role inside` 没有和外面的匿名管道，无法通讯。
- 桥是原始 TCP 转发，支持 HTTP / WebSocket / SSE。
  `--inside-serve` / `--outside-serve` 是只读 HTTP 下载；需要上传时换成支持 PUT 的
  文件服务，并用 `--inside-cmd` / `--outside-cmd` 启动。
- `--bind 0.0.0.0` 会把入口暴露到局域网，按需使用。
- 该工具绕过 DACS 的跨域网络隔离，仅在授权的设备/环境中使用。
