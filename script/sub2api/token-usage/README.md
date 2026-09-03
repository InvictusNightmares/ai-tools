# Token 用量日报

本目录保留 [daily/](daily/) 日报工具，统一统计美西、东京的人员及业务组用量。

| 文件 | 用途 |
| --- | --- |
| [email_daily_report.py](daily/email_daily_report.py) | 定时任务入口，生成日报图片并发送邮件 |
| [sub2api_daily_person_token_usage.py](daily/sub2api_daily_person_token_usage.py) | 查询两端数据、汇总人员和业务组用量；独立运行时可生成 Excel 并上传腾讯文档 |
| [person_group_mapping.csv](daily/person_group_mapping.csv) | 服务器、Key ID、人员和业务组的映射 |
| [build_sub2api_daily_person_token_usage.mjs](daily/build_sub2api_daily_person_token_usage.mjs) | 手动 Excel 流程的构建器，邮件定时任务不调用 |
| [ai-gateway-token-usage.cron.example](daily/ai-gateway-token-usage.cron.example) | GPU 服务器的 cron 配置示例 |
| [.env.email.example](daily/.env.email.example) | 邮件配置模板 |

## 定时任务

定时任务部署在 GPU 服务器 `qiyuan-gpu`，每天北京时间 **09:00** 统计前一天数据。美西、东京作为数据源，通过 SSH 查询；两端没有这套日报 cron。

- cron 配置：`/etc/cron.d/ai-gateway-token-usage`
- 程序目录：`/data/ai-gateway-token-usage/`，对应本地 `daily/` 中的邮件脚本、统计脚本和人员映射。
- 入口：`/data/ai-gateway-token-usage/email_daily_report.py`
- 邮件配置：`/data/ai-gateway-token-usage/.env.email`
- 运行日志：`/data/ai-gateway-token-usage/email-daily.log`

邮件脚本调用同目录统计模块和人员映射，生成 PNG 日报后通过 SMTP 发送。该流程使用 Python、Pillow、中文字体以及两端 SSH 访问配置。

## 使用

从仓库根目录运行：

```sh
python3 script/sub2api/token-usage/daily/email_daily_report.py --help
python3 script/sub2api/token-usage/daily/sub2api_daily_person_token_usage.py --help
```

日期按默认 `Asia/Shanghai` 时区计算，起止日期均包含；可通过 `--timezone` 调整。不传日期时默认统计昨天。

独立运行统计脚本的 Excel 流程另需 Node.js 和 `@oai/artifact-tool`；可使用 `SUB2API_NODE`、`SUB2API_NODE_MODULES` 指定运行时路径。Excel 默认输出到 `daily/outputs/`，腾讯文档上传参数见脚本帮助。

私有配置 `daily/.env.tencent-docs`、`daily/.env.email` 及邮件运行目录 `daily/email-runs/` 由仓库 `.gitignore` 排除。邮件配置文件需设为仅所有者可读写（`600`）。
