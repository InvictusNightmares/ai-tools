# 中国移动江苏 act2510 签到

青龙脚本：`china_mobile_checkin.js`（活动层适配器）与 `china_mobile_act2510.js`。

> 私有配置只放青龙环境变量 `chinaMobile`，不入库。部署路径为青龙 `data/scripts/`。

`china_mobile_checkin.js` 对应官方 App 中江苏 `act2510` 活动，替换旧 `qwhdhub` 接口实现。
它先调用 `initIndexPage`；只有明确已登录、今日未签到时才调用一次 `doSign`。
HTTP 200、`success:true` 或普通提示文字都不能单独视为签到成功。

这是活动层适配器，尚未实现 `getYDRZToken` 的原生自动取票。活动 Cookie 过期时会明确失败，
需要本人 App 更新会话。当前会话测试通过后可以按计划运行，但不代表可长期无人值守；
必须另行验证正式取票和自然失效后的恢复，才能确认长期续期能力。

配置沿用 `chinaMobile` 环境变量，值为 JSON 对象或对象数组。字段为：

| 字段 | 来源 |
| --- | --- |
| `cookie` | 本人成功登录江苏活动后，活动请求的完整 Cookie |
| `fingerprint` | 同一活动请求的 `mywaytoopen`，与 `hgvhv` 请求头一致 |
| `userAgent` | 同一活动请求的 User-Agent |

不要将真实值放进仓库、命令行参数或日志。旧 `QWHD_SESSION_TOKEN` 不兼容此活动。
配置只应存储在面板受控环境变量中，人工导入时避免复制其他应用的凭据。

运行模式：

```bash
# 无网络、无通知，仅检查配置结构
node china_mobile_checkin.js --dry-run

# 只查询登录及签到状态，不签到、不发通知；仍会向官方接口发送所配置的会话
node china_mobile_checkin.js --status

# 执行签到但不发通知，仅用于已获授权的验收
node china_mobile_checkin.js --now --no-notify
```

普通定时运行依赖面板已有的同目录 `daily_checkin_common.js`，保留它的随机等待与通知行为。
源码测试和 `--dry-run` 不会加载该通知模块。

```bash
node --test china_mobile_checkin.test.js
```

替换时先保留旧脚本和任务元数据的受控备份，使用面板 API 更新原任务，不创建重复定时任务。
在服务器上完成只查状态的真实验证，并核对面板生成的环境变量与正式脚本一致后，再启用
当前会话的定时任务。验证失败时保留候选文件，原任务维持停用；不要用已失效的旧 Cookie
反复尝试登录，也不要据离线测试宣称部署验收完成。

已验证当前本人会话可以从本机和部署容器查询到已登录、今日已签到。正式入口的配置检查、
状态查询和生成环境一致性检查均已通过；这些结果不包含自然过期后的原生取票验证。
