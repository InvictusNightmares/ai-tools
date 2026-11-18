# 顺丰 App 签到

青龙脚本：`sf_checkin.js`。

> 私有配置 `sf_app_profile.json` 部署在青龙 `data/config/`，不随仓库迁移。
> 服务器上脚本位于 `data/scripts/sf_checkin.js`，因此脚本内的 `../config/` 指向 `data/config/`。
> 仓库内只保留脚本和离线测试，不含任何真实凭据。

`sf_checkin.js` 在 App 模式下，每次运行先调用官方 `universalSign` 取新票，
再通过会员登录入口取得会话并确认登录状态，随后执行原有两项签到。
取票失败、账号不一致或登录无效时停止，不循环重试旧票。

脚本优先读取相对脚本目录的 `../config/sf_app_profile.json`，文件必须为普通文件，
仅所有者可读写（`0600`），不能是符号链接。此文件不存在时，兼容原 `sfsyUrl`
环境变量中的 Cookie、分享链接或 App JSON 配置；文件不可读或内容无效时停止，
不会悄悄退回旧 Cookie。私有文件和环境变量中的真实凭据都不能进入仓库。

App 配置包含 `type: "sf-app"`、`version: 1`、抓到的原生请求 `headers`、
原始 JSON 正文字符串 `body`，以及会员入口的 `redirect` 参数（不包含旧 `sign`）。
`loginUserAgent` 使用会员登录跳转请求的 User-Agent，原生取票请求仍保留自己的 User-Agent。
请求正文、原生签名和时间戳作为同一份抓包材料保存，不擅自改写时间戳。
当前尚未实现原生动态签名生成或 App 登录令牌刷新；服务端有效期及跨天复用需要实际验证。

```bash
# 无网络、无通知，仅验证实际配置来源和格式
node sf_checkin.js --dry-run

# 会取新票、建立会员会话，再查询登录和签到状态；不签到、不发通知
node sf_checkin.js --check-session

# 离线回归
node --test sf_checkin.test.js
```

定时任务仍使用原有 `daily_checkin_common.js` 的随机等待及通知流程。
替换前备份旧脚本，并记录私有配置文件原先是否存在；替换后用 `--check-session`
验收正式脚本，失败则恢复本次修改。使用已授权的服务器文件访问即可部署此单任务配置，
不需要读取面板登录令牌或修改其他任务。

签到成功后的飞书通知会附带 `已连续签到 N 天`（来自 `getTodaySign` 的 `dayCount`）；
查询连续天数失败不会影响签到结果。
