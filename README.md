# ai-tools

个人工具、服务部署脚本与操作文档。

| 入口 | 内容 |
| --- | --- |
| [服务域名网关](script/domain-gateway/README.md) | 公网 SNI 分流、私网 HTTPS、证书维护与验收工具 |
| [域名配置实施记录](doc/domain-gateway/implementation.md) | 本次操作、访问边界、验证结果与遗留问题 |
| [域名迁移遗漏复查](doc/domain-gateway/audit-followup.md) | 订阅来源链、登录后的页面、跨服务地址与后续修复 |
| [三台主机清理记录](doc/domain-gateway/cleanup.md) | 历史备份与临时文件清理、验证及当前备份状态 |
| [浏览器登录入口迁移](doc/domain-gateway/browser-logins.md) | 本机保存的登录条目修改步骤与私有地址清单说明 |
| [静态订阅生成器](script/clash/static-subscription/README.md) | 订阅合并、发布及故障回退 |
| [Hermes](script/agentbox/hermes/README.md) | 私网助手与网页后台 |
| [PerkRadar](script/qinglong/perkradar/README.md) | 采集任务与通知流程 |
| [API 网关文档](doc/gateway/README.md) | 网关运维文档索引 |

真实部署参数、账号、密钥与订阅入口只保存在受控私有配置中。公开文档使用角色和占位符；修改前阅读 [AGENTS.md](AGENTS.md)。
