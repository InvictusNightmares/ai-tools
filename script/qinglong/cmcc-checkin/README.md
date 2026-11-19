# 中国移动江苏 act2510 签到

## 当前方案：`cmcc_auto.py`（会话自动续期）

`cmcc_auto.py` 不再依赖手工抓取的江苏活动 Cookie，也不再调用原生 `leadeon.getYDRZToken()`。每次运行自动重建活动会话：

```text
autoLogin（client.app.coc）       现签 App 会话
→ appTokenLogin（qwhdsso）        换 QWHD 会话
→ getYDRZToken(sourceId=039014)  换江苏 jtToken
→ jtWx10086AuthLogin             换江苏活动 Cookie
→ initIndexPage                  查登录 / 今日签到 / 本月签到
→ doSign（仅未签到时）            完成签到
```

### 私有配置

`/ql/data/config/cmcc_profile.json`，权限 `0600`，不进入仓库。字段：

| 字段 | 说明 |
| --- | --- |
| `auto_login_url` | `https://client.app.coc.10086.cn/biz-orange/LN/uamonekeylogin/autoLogin` |
| `auto_login_template` | 从 App 冷启动抓包解密得到的 autoLogin 明文模板 |
| `xk` | 模板里的 `xk`，会话签名需要 |
| `phone` | 本人手机号，用于 `userCheckId` |
| `province_code` / `city_code` | 江苏 / 苏州：`250` / `0512` |
| `carrier_operator` | `002` |
| `app_version_code` | App 版本，如 `12.5.6` |
| `source_id` | 江苏活动 `039014` |
| `mywaytoopen` | 江苏活动 H5 指纹，抓包值 |
| `auto_login_user_agent` | 可选，autoLogin 的 UA |
| `sso_user_agent` / `jsyd_user_agent` | 可选，SSO 与江苏页面 UA |

模板里的 `xk` / `cellNum` 由 App 运行时生成，不能离线伪造。首次需要从 App 冷启动抓一次 `autoLogin` 请求；之后每次运行都会重新现签，不需要反复抓包。

### 运行

```bash
# 只查登录和签到状态，不签到
python3 cmcc_auto.py --check

# 签到；成功后发飞书通知
python3 cmcc_auto.py
```

青龙任务：

```text
命令：task cmcc-checkin/cmcc_auto.py
定时：0 9 * * *
```

脚本只输出登录状态、今日是否签到、本月签到天数，不打印 Cookie、token、手机号。

### 验收

```bash
python3 cmcc_auto.py --check
# 期望：登录=成功 今日已签到=True/False 本月签到=N
```

当前已在青龙容器实测：

```text
登录=成功 今日已签到=True 本月签到=5
飞书通知已发送
```

## 旧版活动层适配器（保留）

`china_mobile_checkin.js` 与 `china_mobile_act2510.js` 是早期实现，只做活动层请求，依赖手工抓取的 `chinaMobile` Cookie。会话约一天过期，不具备自动续期能力，现已由 `cmcc_auto.py` 替代；保留用于对照和回滚。

旧版配置只放青龙环境变量，字段为 `cookie`、`fingerprint`、`userAgent`。不要将真实值写入仓库、命令行或日志。
