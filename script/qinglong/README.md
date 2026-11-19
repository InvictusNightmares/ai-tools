# 青龙脚本

青龙面板相关脚本按任务分目录维护：

| 目录 | 任务 | 说明 |
| --- | --- | --- |
| `glados-checkin/` | GLaDOS 每日签到 | 纯 API + 远程 Browserless，自动处理 Turnstile |
| `perkradar/` | PerkRadar 采集与飞书推送 | 常驻采集器 + 青龙定时推送 |
| `cmcc-checkin/` | 中国移动江苏 act2510 签到 | 自动续期：autoLogin → QWHD → 039014 → 江苏 Cookie |
| `sf-checkin/` | 顺丰 App 签到 | App 自动取票 + 会员签到 |

各目录的 README 说明部署、配置、运行模式和验收方式。真实 Cookie、令牌、Open ID、私有配置文件只放青龙环境变量或 `0600` 私有文件，不入库。

通用约定：

- 定时任务命令使用 `task <相对路径>`，例如 `task glados-checkin/glados_checkin.py`。
- 通知复用青龙现有飞书私聊变量 `QL_FEISHU_APP_ID`、`QL_FEISHU_APP_SECRET`、`QL_FEISHU_OPEN_ID`。
- 脚本内的相对私有配置路径以**部署后的脚本目录**为准，不以仓库目录为准。
