# 青龙共用辅助脚本

本目录保存青龙面板根目录（`/ql/data/scripts/`）使用的共用脚本与蔚来签到包装器，供 `sf_checkin.js`、`bing_rewards_notify.js` 等任务直接通过相对路径 `require('./feishu_private_notify')` / `require('./daily_checkin_common')` 引用：

| 文件 | 作用 | 部署路径 |
| --- | --- | --- |
| `feishu_private_notify.js` | 飞书应用私聊推送（基于 `QL_FEISHU_APP_ID` / `QL_FEISHU_APP_SECRET` / `QL_FEISHU_OPEN_ID`） | `/ql/data/scripts/feishu_private_notify.js` |
| `daily_checkin_common.js` | 每日签到通用随机等待、脱敏与飞书结果推送封装 | `/ql/data/scripts/daily_checkin_common.js` |
| `weilai_checkin.js` | 蔚来签到包装器（08:30–08:45 随机启动、凭据隔离与飞书通知，调用订阅仓库 `smallfawn_QLScriptPublic_main/daily/weilai.js`） | `/ql/data/scripts/weilai_checkin.js` |

测试飞书私聊连通性：

```bash
node /ql/data/scripts/feishu_private_notify.js --test
```
