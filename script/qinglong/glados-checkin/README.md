# GLaDOS 每日签到（青龙）

针对 `https://glados.cloud/console/checkin` 的 2026-11 新版签到流程。纯 API 模式可直接跑在青龙里；服务端命中 Cloudflare Turnstile 时，可在本机用真浏览器通道兜底。

## 结论

| 场景 | 可行性 | 说明 |
| --- | --- | --- |
| 青龙 + 纯 API（`GLADOS_MODE=api`） | 视账号与出口 IP | 请求流程已完全还原，Cookie 与 UA 匹配时可直接签到；机房 IP / 高风险出口大概率被 Turnstile 拒 |
| 青龙 + 远程 Browserless（`GLADOS_MODE=browser` + WS） | 已验证可用 | 由脚本自动点击 Turnstile 复选框，机房出口也能完成签到 |
| 本机 + Chrome/Edge | 可用 | 需本机有桌面；脚本同样自动点击 Turnstile 复选框 |
| 旧脚本（`koa:sess` + `token=glados.one`） | 已失效 | 新版认证改用 `gld:sess`，签到要求 nonce + proof |

签到成功与否不只看 HTTP 200，要看响应里的 `code` / `reason`：`code=0` 或 `code=1`（今日已签）都算完成；`reason=turnstile`、`device-mismatch` 是两类明确拒绝。

## 抓到的签到流程

新版控制台是 React SPA，签到逻辑在 `static/js/main~21b3c6c3.*.chunk.js`，请求走 `/api` 前缀：

```text
1. GET  /api/user/checkin/challenge
   -> {"code":0,"nonce":"...","ttl":300000,"turnstile":"<sitekey>"|null,"ip":"..."}

2. 页面等待至少 2500ms（服务端会检查 challenge 与提交的时间差）

3. proof = SHA-256(nonce + ".glados-observe-v1")，输出 64 位小写 hex

4. POST /api/user/checkin
   {
     "token": "<当前域名，如 glados.cloud>",
     "nonce": "<上一步 nonce>",
     "proof": "<上一步 proof>",
     "tsState": "off|ok|timeout|error",     // 页面附带；纯 API 可省略
     "turnstile": "<Turnstile token>"       // 仅在人机验证启用时
   }
```

返回字段：`code=0` 成功并带 `points`、`breakdown`（`base/level/streak/cable/lucky/site/exitIp`）；`code=1` 或 `message` 含 `Checkin Repeats` / `Today's observation logged` 表示今日已签；`code=5, reason=turnstile` 表示人机验证未过；`code=4, reason=device-mismatch` 表示当前 UA 与登录设备不一致；`code=-2` / HTTP 401 表示 Cookie 失效。

### 四层反自动化

1. **Challenge + nonce + ttl**：nonce 一次性、有时效，且绑定签发域名，不能跨域重放。
2. **时间下界**：提交必须晚于 challenge 约 2.5 秒，太快直接拒。
3. **proof 签名**：`SHA-256(nonce + ".glados-observe-v1")`，salt 硬编码在前端 bundle 中。
4. **Cloudflare Turnstile + 设备绑定**：challenge 可能下发 Turnstile sitekey（`action=checkin`, `cData=nonce`, `interaction-only`）；同时服务端记录登录时的设备指纹，签到要求与登录 UA 一致。

纯 API 能稳定完成 1–3；第 4 层取决于出口 IP 信誉和 UA 是否匹配。浏览器模式本质上不是“绕过”，而是让官方页面在真实浏览器里完成同一套验证。

### 原始请求示例

```sh
# 1) 取 challenge（需要登录 Cookie）
curl -s 'https://glados.cloud/api/user/checkin/challenge' \
  -H 'Cookie: gld:sess=<value>; gld:sess.sig=<value>' \
  -H 'User-Agent: <与登录浏览器一致>' \
  -H 'Referer: https://glados.cloud/console/checkin'

# 2) 用返回的 nonce 计算 proof
python3 -c 'import hashlib,sys;print(hashlib.sha256((sys.argv[1]+".glados-observe-v1").encode()).hexdigest())' '<nonce>'

# 3) 提交签到
curl -s 'https://glados.cloud/api/user/checkin' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: gld:sess=<value>; gld:sess.sig=<value>' \
  -H 'User-Agent: <与登录浏览器一致>' \
  -H 'Origin: https://glados.cloud' \
  -H 'Referer: https://glados.cloud/console/checkin' \
  --data '{"token":"glados.cloud","nonce":"<nonce>","proof":"<proof>"}'
```

## 文件

- `glados_checkin.py`：签到脚本，API / 浏览器 / 自动回退三种模式，多账号、推送、只读诊断。
- `tests/test_glados_checkin.py`：离线单测（proof 向量、响应分类、配置解析、Cookie 脱敏）。

## 青龙部署

1. 把 `glados_checkin.py` 放到青龙脚本目录（也可整目录放入）。
2. 安装依赖：

```sh
pip3 install requests
# 只有浏览器模式需要：
pip3 install playwright && playwright install chromium
```

3. 在青龙「环境变量」添加：

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `GLADOS_COOKIE` | 单账号必填 | 浏览器 F12 / Cookie-Editor 复制的完整 Cookie，须含 `gld:sess` 与 `gld:sess.sig` |
| `GLADOS_COOKIES` | 多账号必填 | 每行一个 Cookie，`#` 开头为注释 |
| `GLADOS_USER_AGENT` | 强烈建议 | 登录该账号时浏览器的完整单行 UA；设备校验依赖它 |
| `GLADOS_USER_AGENTS` | 多账号可选 | 每行一个 UA，按行与 `GLADOS_COOKIES` 对应 |
| `GLADOS_MODE` | 否 | `auto`（默认，先 API 后浏览器）/ `api` / `browser` |
| `GLADOS_BROWSER_HEADLESS` | 否 | 默认 `1`；本机有桌面时设 `0` 通过率更高 |
| `GLADOS_BROWSER_TIMEOUT` | 否 | 点签到后的等待秒数，默认 `150` |
| `GLADOS_BROWSER_WS` | 远程浏览器必填 | Browserless 的 Playwright 入口，如 `ws://<browserless-host>:3000/chrome/playwright` |
| `GLADOS_BROWSER_TOKEN` | 远程浏览器必填 | Browserless 的 `TOKEN`；容器重建后需同步更新 |
| `GLADOS_DOMAINS` | 否 | 默认 `https://glados.cloud,https://glados.rocks` |
| `GLADOS_DELAY` | 否 | 多账号间隔，默认 `3` 秒 |
| `QL_FEISHU_APP_ID` / `QL_FEISHU_APP_SECRET` / `QL_FEISHU_OPEN_ID` | 否 | 复用青龙现有飞书私聊机器人，与其他签到任务一致 |
| `PUSHPLUS_TOKEN` / `SERVERCHAN_SENDKEY` / `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | 否 | 其他推送渠道，配置任一即可 |

4. 新建定时任务：

```text
任务名称：GLaDOS 签到
命令：task glados_checkin.py
定时：30 9 * * *
```

先手动运行一次 `task glados_checkin.py --check` 做只读诊断；确认能读到邮箱/积分后，再跑正式签到。

### 已验证的青龙运行环境

已在现有青龙（Debian 镜像，Python 3.11 + requests + Playwright）中验证：脚本放在 `data/scripts/glados-checkin/`，环境变量写入青龙面板，任务命令 `task glados-checkin/glados_checkin.py`，定时 `30 9 * * *`，并配置 12:30 / 20:30 两个补签时段。远程 Browserless 通道（headed）可自动点击 Turnstile 复选框并完成签到；日志位于 `data/log/glados_checkin/`。

### 从本机 Chrome 导入 Cookie（macOS）

不想手动复制请求头时：

```sh
python3 import_chrome.py
```

脚本从 Chrome 的 `Cookies` 数据库解密 `gld:sess` / `gld:sess.sig`（钥匙串可能弹窗授权），并读取真实 Chrome UA，生成权限 `0600` 的 `.env.local`。之后：

```sh
set -a; source .env.local; set +a
python3 glados_checkin.py --check
```

或先从浏览器复制请求为 cURL，再用 `import_curl.py .curl.txt` 解析。`.env.local`、`.curl.txt`、`cookie*.txt` 均已被本目录 `.gitignore` 排除。

## 本机浏览器模式

青龙宿主没有桌面、或机房 IP 被 Turnstile 拦时，在家宽机器上运行：

```sh
pip3 install requests playwright
playwright install chromium
export GLADOS_COOKIE='gld:sess=...; gld:sess.sig=...'
export GLADOS_USER_AGENT='Mozilla/5.0 (...) Chrome/131.0.0.0 Safari/537.36'
export GLADOS_MODE=browser
export GLADOS_BROWSER_HEADLESS=0
python3 glados_checkin.py
```

脚本会优先用系统 Chrome，其次 Edge，最后 Playwright Chromium。首次运行会弹出浏览器窗口，属正常现象。浏览器 profile 按账号隔离在 `~/.cache/glados-checkin/`。

### Turnstile 处理

页面把人机验证组件渲染在跨域 iframe 里，内部 DOM 不可读。脚本在点击签到后轮询 iframe 尺寸，找到可见的 300×65 组件后，按坐标点击左侧复选框；隐藏的 1×1 挑战帧会被跳过。点击通过后页面自己计算 proof 并提交签到。

如果 Cloudflare 升级为图片选择题，脚本无法自动完成，本次会返回 `reason=turnstile`，等下一个补签时段重试即可。

## 验证

```sh
cd script/qinglong/glados-checkin
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 glados_checkin.py --self-test
GLADOS_COOKIE='<cookie>' python3 glados_checkin.py --check   # 只读
GLADOS_COOKIE='<cookie>' python3 glados_checkin.py           # 正式签到
```

预期：正式签到输出 `签到成功（success）` 或 `签到成功（repeat）`，并刷新出最新积分/剩余天数；重复运行只返回 `repeat`，不会重复加分。

## 排障

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `code=-2` / `没有权限` | Cookie 缺失、过期或域名不匹配 | 重新登录 `glados.cloud` 复制 `gld:sess` + `gld:sess.sig` |
| `reason=device-mismatch` | UA 与登录设备不一致 | 把 `GLADOS_USER_AGENT` 设成登录时的完整 UA；必要时重新登录 |
| `reason=turnstile` | 人机验证未过或升级为图片题 | 等 12:30 / 20:30 补签；检查 `GLADOS_BROWSER_WS` / Token；远程浏览器需 `headless=false` |
| `challenge-unavailable` / `challenge-expired` | challenge 获取失败或等待超时 | 稍后重试；避免并发运行 |
| 浏览器找不到签到按钮 | 页面未登录 / 加载失败 | 检查 Cookie 是否注入成功；截图与页面日志需自行排查 |

签到接口按“天”去重，重复提交只会返回今日已签；但网络超时属于结果未知，不要为了确认而并发或反复补签，先看官网积分流水。

成功、今日已签、失败都会发送通知；成功时会带上当前积分、今日加分和“已连续签到 N 天”。

## 隐私

Cookie 等同于账号登录态，不要写进脚本、日志、Issue 或截图。脚本只打印 Cookie 名并隐去值；浏览器 profile、`.env` 和任何含凭据的文件都不要提交到版本库。
