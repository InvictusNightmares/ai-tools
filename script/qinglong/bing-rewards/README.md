# 微软 Rewards（青龙面板集成）

基于上游 [`wangixangya/Microsoft-Rewards-Script`](https://github.com/wangixangya/Microsoft-Rewards-Script)（`v5` 分支，Node.js 24 + Patchright）封装的青龙定时任务，保持在青龙面板中统一调度、展示日志并复用现有飞书私聊通知。

> **隐私边界**：真实微软账号（`ACCOUNT_1_EMAIL`）、密码（`ACCOUNT_1_PASSWORD`）、临时验证码（`QL_MS_LOGIN_INPUT`）、飞书应用凭据、登录态数据库（`sessions/sessions.db`）和运行日志均只存于宿主机私有卷或青龙环境变量中，不进入仓库。

## 为什么不复用 `agentbox-headless-chrome`（Browserless）

在恢复本任务时已对照源码与容器配置评估过复用宿主机已有 `agentbox-headless-chrome` 的可行性，结论为**不可取**：

1. **上游仅支持本地 `patchright` 启动且依赖反检测通道**：`src/browser/BrowserManager.ts` 固定调用 `rebrowser.chromium.launch(...)`（Patchright），没有远程 `connectOverCDP` 支持；强行改造为远程 CDP 会破坏 Patchright 的反自动化补丁，并引入维护脆弱的上游分叉。
2. **版本兼容性问题**：`agentbox-headless-chrome` 当前内置 Google Chrome 152，而 Chromium/Edge 152 搭配 Playwright 1.6x 访问 `rewards.bing.com` 存在已知崩溃问题（`microsoft/playwright#41438`）；Patchright 需配合其锁定的内置 Chromium 版本。
3. **长时慢速执行与 Browserless 超时冲突**：为避免微软风控限制，本任务必须维持 `searchDelay 6–12min`、`readDelay 6–11min`、`searchResultVisitTime 20sec` 等慢速节奏，单次运行常持续 2–4.5 小时；而 `agentbox-headless-chrome` 为保护共享池配置了 `TIMEOUT=300000`（5 分钟），会在执行中途强行断开会话，若全局放宽至数小时则会使异常任务长期占死共享池。
4. **共享资源与定时窗口冲突**：`agentbox-headless-chrome` 限额 `CONCURRENT=2`、`mem_limit: 4g`、`pids_limit: 512`，同时服务 Hermes 与 GLaDOS 持久 Chrome 窗口（`09:28–09:48` / `12:28–12:48`），与微软 Rewards 的 `09:15–16:30` 运行窗口高度重叠。

因此采用最干净的隔离方案：**基于 `whyour/qinglong:2.24.0-debian` 构建极薄自定义镜像 `agentbox-qinglong:2.24.0-playwright`**，仅在镜像层固化 Chromium 所需的 Debian 12 运行时共享库与中文字体并清理 `apt` 缓存；Chromium 浏览器二进制持久化在宿主机挂载卷 `/ql/data/browsers`（`PLAYWRIGHT_BROWSERS_PATH=/ql/data/browsers`），登录会话持久化在 `/ql/data/scripts/bing_rewards/sessions`。容器可写层保持极小，重建容器不丢依赖、不丢登录态，且与 `agentbox-headless-chrome` 零干扰。

## 目录与部署映射

| 仓库文件 | 青龙宿主机部署位置 | 作用 |
| --- | --- | --- |
| `Dockerfile` | `/srv/agentbox/qinglong/Dockerfile` | 在 `whyour/qinglong:2.24.0-debian` 上固化 Chromium 共享库与字体 |
| `.dockerignore` | `/srv/agentbox/qinglong/.dockerignore` | 构建时忽略 `./data` 与私密文件，避免传入构建上下文 |
| `compose.yaml` | `/srv/agentbox/qinglong/compose.yaml` | 青龙编排模板（`agentbox-qinglong:2.24.0-playwright`、`shm_size: 1gb`、`PLAYWRIGHT_BROWSERS_PATH`） |
| `patches/0001-use-global-bing-origin.patch` | 应用于 `bing_rewards/src/constants/urls.ts` | 将 `BING` 由 `https://cn.bing.com` 改回 `https://www.bing.com`，防止代理环境下出现中美 IP 分裂 |
| `patches/0002-preserve-cookies-on-locale-refresh.patch` | 应用于 `bing_rewards/src/browser/BrowserManager.ts` | 首次 `geoLocale=auto` 自动解析账户区域（如 `zh-CN` → `zh-US`）刷新指纹时保留有效登录 Cookie，避免 `--login-setup` 会话在首日/次日被误丢弃 |
| `patches/0003-handle-account-interrupt.patch` | 应用于 `bing_rewards/src/browser/auth/Login*.ts` | 识别并自动跳过 `account.live.com/interrupt/*`（如 `credentialaction`）可选提示插页，若遇不可跳过提示则记录脱敏标题与按钮并快速退出 |
| `ql_run.sh` | `/srv/agentbox/qinglong/data/scripts/bing_rewards/ql_run.sh` | 青龙定时任务入口（`task bing_rewards/ql_run.sh`） |
| `config.example.json` | `/srv/agentbox/qinglong/data/scripts/bing_rewards/config.json`（`0600`） | 全开 worker + 慢速防风控参数配置 |
| `bing_rewards_notify.js` | `/srv/agentbox/qinglong/data/scripts/bing_rewards_notify.js` | 随机启动延迟、代理/凭据隔离、中英文日志汇总、连续天数统计、非致命飞书推送、`--dry-run` / `--login-setup` |
| `bing_rewards_login_input.js` | `/srv/agentbox/qinglong/data/scripts/bing_rewards_login_input.js` | `--login-setup` 预加载桥接，轮询青龙 SQLite 中 `QL_MS_LOGIN_INPUT` 并原子清空 |
| `bing_rewards_notify.test.js` | 仅仓库离线回归 | 覆盖脱敏、中英文日志汇总、连续天数、环境隔离、代理派生与 SQLite 验证码原子消费 |

## 防风控与关键配置说明

- **随机启动窗口**：青龙定时为 `15 9 * * *`（北京时间 09:15 触发），`bing_rewards_notify.js` 默认随机等待 `0–180` 分钟（覆盖 `09:15–12:15`），仅在显式传入 `--now`、`--login-setup` 或 `--dry-run` 时跳过随机等待。
- **慢速节奏（严禁为图快缩短）**：`config.example.json` 保持 `rewardsMode: "browser"`、`clusters: 1`、`parallelSearching: false`、`clusterSearch: false`、`searchDelay: 6min–12min`、`readDelay: 6min–11min`、`searchResultVisitTime: 20sec`、`globalTimeout: "50sec"`、`maxBonusSearches: 10`、`continueOnBotWarning: false`，同时开启全部 13 个 worker、`ensureStreakProtection: true`、`autoClaimPunchcardRewards: true`、`experimental.edgeBrowsing: true`。
- **同区域一致代理**：
  - `bing_rewards_notify.js` 会把容器的 `HTTP_PROXY` / `HTTPS_PROXY` 自动映射为 `ACCOUNT_N_PROXY_URL` / `ACCOUNT_N_PROXY_PORT` / `ACCOUNT_N_PROXY_HTTP=true`（若用户未单独配置账号代理），保证 Patchright Chromium 与 `impit` HTTP 客户端均显式走主代理。
  - `patches/0001-use-global-bing-origin.patch` 把上游分叉中面向国内直连的 `https://cn.bing.com` 还原为 `https://www.bing.com`，避免主代理的分流规则把 `cn.bing.com` 放行直连而把 `rewards.bing.com` 走海外代理，造成跨区 IP 触发微软限制。

## 部署与复现步骤

### 1. 构建自定义青龙镜像并拉起容器

```bash
cd /srv/agentbox/qinglong
docker build --network=host -t agentbox-qinglong:2.24.0-playwright .
docker compose up -d
```

### 2. 部署上游 `v5`、打补丁并安装持久化 Chromium

```bash
TARGET=/srv/agentbox/qinglong/data/scripts/bing_rewards
git clone --depth 1 -b v5 https://github.com/wangixangya/Microsoft-Rewards-Script.git "$TARGET"
git -C "$TARGET" apply /path/to/patches/0001-use-global-bing-origin.patch
git -C "$TARGET" apply /path/to/patches/0002-preserve-cookies-on-locale-refresh.patch
git -C "$TARGET" apply /path/to/patches/0003-handle-account-interrupt.patch
mkdir -p "$TARGET/sessions" && chmod 700 "$TARGET/sessions"

docker exec -w /ql/data/scripts/bing_rewards qinglong bash -lc '
  set -euo pipefail
  export PLAYWRIGHT_BROWSERS_PATH=/ql/data/browsers
  npm ci --include=dev --ignore-scripts
  npm run build
  ./node_modules/.bin/patchright install chromium
  npm prune --omit=dev
'
```

将 `ql_run.sh`（`0700`）、`config.example.json`（复制为 `config.json`，`0600`）放入 `data/scripts/bing_rewards/`，将 `bing_rewards_notify.js`、`bing_rewards_login_input.js` 及 `../common/feishu_private_notify.js` 放入 `data/scripts/`。

### 3. 青龙环境变量与定时任务

在青龙面板「环境变量」中配置（均为私密变量，不入库）：

- `ACCOUNT_1_EMAIL`：微软 Rewards 登录邮箱
- `ACCOUNT_1_PASSWORD`：微软 Rewards 登录密码（若为无密码验证器账号可留空）
- `QL_MS_LOGIN_INPUT`：首次或失效重登时使用的临时验证码变量（默认留空并禁用，脚本读取后自动清空并禁用）

定时任务配置：

- 名称：`微软 Rewards（09:15–12:15 随机启动）`
- 命令：`task bing_rewards/ql_run.sh`
- 定时：`15 9 * * *`

### 4. 首次交互登录与日常验证

```bash
# 1) 离线回归测试（仓库目录）
node --test script/qinglong/bing-rewards/bing_rewards_notify.test.js

# 2) 容器内配置与浏览器校验（通过青龙 task 加载环境变量；无网络、不发通知）
docker exec qinglong task bing_rewards/ql_run.sh --dry-run

# 3) 首次登录并持久化桌面+移动会话（若触发邮箱验证码或验证器数字确认，会自动飞书私聊提醒；
#    收到验证码后在青龙环境变量 QL_MS_LOGIN_INPUT 填入并保存即可，脚本读取后自动清空）
docker exec qinglong task bing_rewards/ql_run.sh --login-setup

# 4) 仅在需要跳过随机启动延迟立即手动测试时使用（日常定时严禁加 --now）
docker exec qinglong task bing_rewards/ql_run.sh --now
```
