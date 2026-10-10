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

## 当前统计口径

- 美西查询 `sub2api-next-postgres` 容器中的 `sub2api_next` 数据库；东京仍查询 `sub2api-postgres` 中的 `sub2api`。数据库角色均为 `sub2api`。
- 美西根据 `usage_logs.user_id` 关联个人账号，以账号姓名识别人，同一账号的多个 Key 合并统计。业务组统一叫 **研发**，不使用 ecube／dpad／wcan 或资源子组名。用户新建、删除或改名 Key 不需要补 CSV；历史用量继续按账本中的用户归属计算。
- 东京及历史管理员名下的 Key 沿用 `person_group_mapping.csv`。原 `研发Codex` 仍显示为“研发”。同业务组、同名的跨节点人员继续合并；美西同名但不同账号分别统计，存在歧义时不将东京记录强行并入某个账号。
- **张成继续不纳入统计**：美西按账号姓名排除其全部 Key，东京沿用 Key 姓名排除。`研发Claude` 业务组继续排除。查询和内部汇总保留 Key／日期明细，三张邮件图片按节点、业务组和人员汇总。
- 查询必须返回完整 CSV 表头与完整数据行。即使 SSH 返回退出码 0，空输出、Docker 报错或截断数据也视为失败；任一节点失败时，邮件任务不生成或发送日报。合法的零用量日期仍须有完整表头。

修改统计代码时需同时同步 GPU 上的两个 Python 脚本，并在 cron 使用的同一把锁下替换，保留原文件以便恢复。部署前后对固定历史日期只读对账；使用 `--dry-run` 生成三张图片并检查姓名、分组、排除项和合计，不连接 SMTP。定时任务、邮件凭据和人员 CSV 无须随本次美西迁移调整；东京新增人员仍需补齐本地与 GPU 的人员 CSV 映射。

2026-10-10 09:36 已完成这次适配并从正式入口通过 dry-run：10 月 9 日美西为 67 条 Key／日期汇总、21,709 次请求、3,757,534,048 Token，东京为 55 条汇总且与旧脚本结果一致；张成已排除，未映射与姓名差异均为 0。17 项回归检查及 PostgreSQL 只读归属测试通过。当天 09:00 旧版邮件误报美西为零，本次未补发邮件。部署证据在 GPU `/data/ai-gateway-token-usage/personal-account-migration-20261010.json`，正式任务仍为每天北京时间 09:00。

本次暂存目录和临时脚本回退副本已在验收后清理。三张正式入口验证图片保留在 GPU `/data/ai-gateway-token-usage/email-runs/validation-personal-20261010/`，与已验收暂存版的图片摘要逐一一致；验证材料不包含 API Key 或 SMTP 密码。

2026-10-10 09:46 已补齐东京 4000 的任宇帆（Key 148）、王晨（Key 149），日报业务组均为 **测试**。本地与 GPU 映射一致，共 218 条；正式邮件入口 dry-run 通过，未映射与姓名差异均为 0，三张图片校验通过，未发送验证邮件。核对时两人当天尚无用量，产生调用后纳入对应日期的日报。

回归检查（运行环境需安装 Pillow）：

```sh
python3 -B -m unittest discover -s script/gateway/token-usage/daily -p 'test_*.py' -v
```

## 使用

从仓库根目录运行：

```sh
python3 script/gateway/token-usage/daily/email_daily_report.py --help
python3 script/gateway/token-usage/daily/sub2api_daily_person_token_usage.py --help
```

日期按默认 `Asia/Shanghai` 时区计算，起止日期均包含；可通过 `--timezone` 调整。不传日期时默认统计昨天。

独立运行统计脚本的 Excel 流程另需 Node.js 和 `@oai/artifact-tool`；可使用 `SUB2API_NODE`、`SUB2API_NODE_MODULES` 指定运行时路径。Excel 默认输出到 `daily/outputs/`，腾讯文档上传参数见脚本帮助。

私有配置 `daily/.env.tencent-docs`、`daily/.env.email` 及邮件运行目录 `daily/email-runs/` 由仓库 `.gitignore` 排除。邮件配置文件需设为仅所有者可读写（`600`）。
