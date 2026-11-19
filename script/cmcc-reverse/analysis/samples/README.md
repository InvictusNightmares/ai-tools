# 脱敏抓包样本

这些文件来自 2026-11-19 中国移动 App 的一次冷启动抓包，已做脱敏，可随仓库提交。

| 文件 | 内容 |
| --- | --- |
| `autoLogin.sanitized.json` | App 冷启动 `autoLogin` 请求头、解密后的模板、响应 |
| `jtWx10086AuthLogin.sanitized.json` | 江苏 `jtWx10086AuthLogin` 请求/响应与 Set-Cookie 名称 |
| `hyl-sso.sanitized.json` | 会员 SSO `provider-user/sso/china/mobile` 响应结构 |
| `act2510-initIndexPage.sanitized.json` | 江苏活动 `initIndexPage` 响应结构 |
| `act2510-initChallengeFloor.sanitized.json` | 江苏活动 `initChallengeFloor` 响应结构 |
| `profile.example.json` | `cmcc_profile.json` 的脱敏结构示例 |

脱敏规则：

- Cookie、Set-Cookie、`x-token`、`xs`、`x-sign`、`r-token` 等值替换为 `***`；
- 手机号、`tel`、`cellNum`、`xk`、`ctid`、`ak`、`imei`、`devToken`、`caid`、
  `userId`、`userName`、`mobileDES`、`mywaytoopen` 等替换为 `***`；
- Set-Cookie 保留 Cookie 名和 `Path`/`Domain`/`HttpOnly`/`Secure` 属性；
- URL、HTTP 方法、请求头名称、参数名、状态码和字段结构保持不变。

原始抓包在 `out/captures/`，含真实 Cookie、token、手机号和设备标识，已被 `.gitignore` 排除。
需要重新生成样本时：

```bash
python3 analysis/sanitize_flows.py --input out/captures/flows/<id>.json
```

`***` 不是真实值；任何需要真实值的操作都必须使用本地或青龙 `data/config/` 中的私有 profile。
