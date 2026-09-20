# Gateway 工具

| 目录 | 内容 |
| --- | --- |
| [ai-gateway](ai-gateway/README.md) | 智能网关完整项目：Auto、Guard、代码、部署、文档、CHANGELOG 和验收证据 |
| [token-usage](token-usage/README.md) | 美西、东京人员及业务组日报、邮件任务和人员映射 |
| [policy-log](policy-log/README.md) | Sub2API 异常记录源码、补丁及独立升级流程 |
| [work-observation](work-observation/README.md) | 正式4000/4001持续采集、受限存储和滚动分析；采集已接入，离线分析/性能验收持续进行 |
| [auto-routing-cache-experiment](auto-routing-cache-experiment/) | 早期缓存实验，保留历史数据，不作为当前网关实现 |

智能网关从 [AI Gateway 项目入口](ai-gateway/README.md) 阅读。原 `auto-gateway/`、`guard-gateway/` 和 `doc/gateway` 中的智能网关总计划、evidence 已统一迁入该项目。

Sub2API 异常记录插件的构建、升级仍见 [policy-log 技术文档](policy-log/技术文档.md)，不与 Auto/Guard 的运行服务混为一套版本。
