# 中国移动江苏 act2510 签到

## 当前方案：`cmcc_auto.py`（会话自动续期 + 风控硬熔断）

`cmcc_auto.py` 不再依赖手工抓取的江苏活动 Cookie，也不再调用原生 `leadeon.getYDRZToken()`。每次运行自动重建活动会话：

```text
autoLogin（client.app.coc）       冷启动现签 App 会话（不带伪造 Cookie，x-sign 第 4 段用 "null"）
→ appTokenLogin（qwhdsso）        换 QWHD 会话
→ getYDRZToken(sourceId=039014)  换江苏 jtToken
→ jtWx10086AuthLogin             换江苏活动 Cookie
→ initIndexPage                  查登录 / 今日签到 / 本月签到
→ doSign（仅未签到时）            完成签到
```

同时兼容：
- 全国版「中国移动」（`cn.10086.app`，如 v12.5.8）与「中国移动江苏」（`com.jsmcc.ZP7267A6ES`，如 v12.0.5）；
- `uamonekeylogin/autoLogin`、`uamrandcodelogin/autoLogin` 等抓包真实入口路径；
- 未显式配置 `app_version_code` / UA 时自动对齐模板 `cv` 与 `sv`，并补齐 `Accept-Language: zh-CN,zh-Hans;q=0.9`。

### 私有配置

`/ql/data/config/cmcc_profile.json`，权限 `0600`，不进入仓库。字段：

| 字段 | 说明 |
| --- | --- |
| `auto_login_url` | 抓包真实 `autoLogin` 地址（如 `.../uamonekeylogin/autoLogin` 或 `.../uamrandcodelogin/autoLogin`） |
| `auto_login_template` | 从 App 冷启动抓包解密得到的 `autoLogin` 明文模板 |
| `xk` | 模板里的 `xk`，会话签名需要（须与模板一致） |
| `phone` | 本人 11 位手机号，用于 `userCheckId` |
| `province_code` / `city_code` | 江苏 / 苏州：`250` / `0512` |
| `carrier_operator` | `002` |
| `app_version_code` | App 版本，导入时默认对齐抓包模板 `cv`（如 `12.5.8` 或 `12.0.5`） |
| `source_id` | 江苏活动 `039014` |
| `mywaytoopen` | 江苏活动 H5 指纹，抓包值 |
| `auto_login_user_agent` | 可选，`autoLogin` 的原生 UA；缺省按模板 `cv`/`sv` 推导 |
| `sso_user_agent` / `jsyd_user_agent` | 可选，SSO 与江苏页面 WebView UA；缺省按版本号对齐 `leadeon/<ver>/CMCCIT` |

模板里的 `xk` / `cellNum` 由 App 运行时生成，不能离线伪造。首次或更换设备/会话时，需从 iPhone App 冷启动抓一次 `autoLogin` 请求，用 `script/cmcc-reverse/analysis/import_auto_login.py` 导入为 `0600` 私有 profile。

### 风控硬熔断与跨进程冷却

脚本默认在与 profile 同目录下维护 `0600` 持久化状态文件（例如 `/ql/data/config/cmcc_profile.state.json`，可用 `CMCC_STATE_FILE` 或 `--state-file` 覆盖；仅保存 SHA-256 哈希、时间戳与状态码，不保存任何手机号或凭据）：

- **风控/频控硬熔断**：`autoLogin` 命中 `214100`~`214105`、`214200`、`214300`、`213245`、`420000`、`233031` 中任意错误码时，立即落盘锁定并发送飞书告警。熔断期间后续所有定时任务直接以退出码 `2` **零请求退出**（不等待延迟、不请求移动接口、不重复发飞书），避免升级为实人/人脸校验。
- **解除熔断**：
  - 更换新的 `cmcc_profile.json` 后，脚本检测到 profile SHA-256 哈希变更会自动解除历史熔断；
  - 人工确认账号恢复正常后，也可执行 `python3 cmcc_auto.py --clear-lockout` 手动解除（纯本地操作，不发任何网络请求）。
- **跨进程冷却保护**：通过文件锁在发起 `autoLogin` 前记录调用时间，默认最小间隔 `300` 秒（可通过 `CMCC_MIN_INTERVAL` 或 `--min-interval` 调整），防止定时任务与手工调试意外连发触发 `233031`。
- **非整点随机启动延迟**：常规运行默认随机等待 `30`~`900` 秒（`CMCC_DELAY_MIN` / `CMCC_DELAY_MAX`）避开整点并发；传入 `--now`、`--check` 或 `--dry-run` 时自动跳过。

### 运行

```bash
# 1. 纯离线校验配置、冷启动签名与风控状态（零网络请求、不改状态文件）
python3 cmcc_auto.py --dry-run

# 2. 只查登录和签到状态，不签到（跳过随机延迟，仍受熔断与冷却保护）
python3 cmcc_auto.py --check

# 3. 立即签到（跳过随机延迟）
python3 cmcc_auto.py --now

# 4. 常规签到（非整点随机延迟后执行，成功后发飞书通知）
python3 cmcc_auto.py

# 5. 手动解除风控熔断（纯本地操作，不发网络请求）
python3 cmcc_auto.py --clear-lockout
```

退出码：
- `0`：签到成功 / 今日已签 / `--check` 成功 / `--dry-run` 通过 / `--clear-lockout` 完成
- `1`：配置错误、状态文件损坏或运行时异常
- `2`：命中风控硬熔断或跨进程冷却保护（零网络请求退出）

青龙任务（建议使用非整点分钟，再叠加脚本内 30~900 秒随机延迟）：

```text
命令：task cmcc-checkin/cmcc_auto.py
定时：13 9 * * *
```

脚本只输出登录状态、今日是否签到、连续与本月签到天数，不打印 Cookie、token、`xk`、`cellNum` 或完整手机号。

### 离线单元测试

```bash
# 1. cmcc_auto.py 离线单测（冷启动签名对齐、双端兼容、风控硬熔断/自动解锁/冷却、随机延迟、--dry-run）
python3 -m unittest discover -s tests -p 'test_*.py' -v

# 2. import_auto_login.py 离线单测（在仓库根目录运行）
python3 -m unittest discover -s script/cmcc-reverse/analysis -p 'test_*.py' -v

# 3. 旧版 JS 适配器离线单测
node --test china_mobile_checkin.test.js
```

### 在线验证建议

抓包导入新 profile 后，先执行 `--dry-run` 确认 URL、版本号与冷启动签名均正确；随后在住宅宽带环境先执行一次 `python3 cmcc_auto.py --check`，确认返回 `登录=成功` 后再迁回青龙定时任务。不要使用旧的已触发风控的 profile 反复重试。

## 旧版活动层适配器（保留）

`china_mobile_checkin.js` 与 `china_mobile_act2510.js` 是早期实现，只做活动层请求，依赖手工抓取的 `chinaMobile` Cookie。会话约一天过期，不具备自动续期能力，现已由 `cmcc_auto.py` 替代；保留用于对照和回滚。

旧版配置只放青龙环境变量，字段为 `cookie`、`fingerprint`、`userAgent`。不要将真实值写入仓库、命令行或日志。
