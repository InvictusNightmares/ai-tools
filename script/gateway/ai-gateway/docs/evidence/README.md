# 验收证据索引

- [2026-09-17 R06 安装包分析误判与会话隔离](2026-09-17-guard-r06/README.md)：首次语义拒绝与23次状态拒绝分开，完整原请求复现，尚未修复或部署。
- [2026-09-17 R05 Codex CLI超时](2026-09-17-codex-r05/README.md)：同版macOS两种传输成功，Windows本人超时未闭环，保留环境与日志边界。
- [2026-09-17 R04 多人选型与输出格式](2026-09-17-routing-r04/README.md)：v31，47次真实用户业务分账、普通文本能力误判修复、两地入口及46/46验收账单，保留脚本初验失败。
- [2026-09-17 R03 Codex压缩兼容与普通阶段降档](2026-09-17-codex-r03/README.md)：v30，两地原生20/20、旧模型名压缩4/4、三语路由及按Key对账，保留旧日志归因边界。

这里保存按日期冻结的结果，不参与服务运行或 Go 构建。当前状态看[实施总计划](../智能网关与Guard分阶段实施总计划.md)，版本变化看[CHANGELOG](../CHANGELOG.md)。旧报告中的“当前”“待完成”和旧目录/服务器路径只对其记录时刻成立，不能直接当作现在的状态。

2026-09-16整理前共115个文件、5,537,607字节（约5.28 MiB），另有1个空目录。检查到的内容完全相同文件仅有3个零字节 `race-vet.log`，已删除并处理引用；其余112个非空文件保留，新一轮维护验证另行增加。没有以“新版本通过”为由删除此前失败结果。

## 阅读入口

| 目录 | 保存原因与范围 |
| --- | --- |
| [2026-09-17-guard-r02](2026-09-17-guard-r02/README.md) | Markdown空值比较误拦截、旧版失败、r18真实原请求/正反例/故障、两地采用与原生续问 |
| [2026-09-17-routing-r01](2026-09-17-routing-r01/README.md) | summary/extraction选型、工具分类复用、三语失败与修复、v27两地采用及原生质量边界 |
| [2026-09-16-native-media](2026-09-16-native-media/README.md) | 图片/文件原生输入、两种GPT Image、Messages内容丢失修复、音频明确不支持、两区域及四客户端 |
| [2026-09-16-context-ua-regions](2026-09-16-context-ua-regions/README.md) | 上下文容量修正、Luna分类与DeepSeek评估、真实UA、美西4005 |
| [2026-09-16-maintenance](2026-09-16-maintenance/README.md) | 本次项目合并、路径/声明一致性、本地回归；未部署 |
| [2026-09-16-input-redaction](2026-09-16-input-redaction/README.md) | Guard r4脱敏契约、同步聚合、签名误拦、真实17项检查和源码哈希 |
| [2026-09-16-history-live](2026-09-16-history-live/README.md) | semantic-v5、历史工具流程、三语SSE递增与东京effort核对；部分缺口后来修复 |
| [2026-09-15-auto-semantic](2026-09-15-auto-semantic/README.md) | 分类候选对比、三协议参数探测、Claude映射及Astra none失败样本 |
| [2026-09-15-history-replay](2026-09-15-history-replay/README.md) | 历史题集来源、工具/会话/安全边界修复；重建样本不冒充原始抓包 |
| [2026-09-15-multilingual-classifier](2026-09-15-multilingual-classifier/README.md) | 词表分类不可靠的基线，以及旧最高档成功结论的纠正 |
| [2026-09-15-auto-xiaoyuan-replay](2026-09-15-auto-xiaoyuan-replay/runtime.md) | 保留被撤回的验收结论和真实失败，避免重复误报 |
| [2026-09-15-auto-stage3](2026-09-15-auto-stage3/README.md) | 早期测试Key、真实切换、响应缓存与异常日志 |
| [2026-09-15-auto-stage2](2026-09-15-auto-stage2/README.md) | 当时版本的上游传输和持久化基础回归 |
| [2026-09-15-phase-d-integration](2026-09-15-phase-d-integration/README.md) | mock验证Guard先于Auto/上游，不代表生产接入 |
| [2026-09-15-auto-cache](2026-09-15-auto-cache/README.md) | 缓存资格、失败不写入、命中记账；非真实Prompt Cache收益 |
| [2026-09-15-auto-payload](2026-09-15-auto-payload/README.md) | 早期协议和请求字段回归 |
| [2026-09-15-auto-session](2026-09-15-auto-session/README.md) | 区域/Key/会话状态隔离回归 |
| [2026-09-14-7d](2026-09-14-7d/observed-summary.json) | 两地七天负载基线与查询口径 |

最新：[2026-09-16客户端兼容](2026-09-16-client-compatibility/README.md)：r5/r6/r7凭据误报、未知模型404、SSE工具绑定、长输入预算和小源真实历史开发。OpenCode、Hermes、Claude Code、Codex CLI四端已完成；四份HAP及行为检查通过，保留首轮失败、评审修正、流式审计限制和真机UI未验证范围。

首次部署：[2026-09-16东京4004部署](2026-09-16-4004/README.md)：当时117文件制品、357项Go/8项Python、真实17/17、Guard503与恢复、原服务保护对照。

## 保留规则

- 保留：真实上游结果、失败→修复对照、冻结题集、源码/制品SHA、关键故障与切换验收。原始JSON/JSONL的内容和哈希不因改目录而重写。
- 日常开发：常规重复成功试跑留在临时目录；每次验收保留最终摘要、源码清单和一份必要的完整结果。不同代码版本或不同失败原因不算重复数据。
- 可清理：无内容文件、空目录、生成缓存，以及确认完全重复且引用已更新的副本。非空历史证据归档/删除先确认它支撑的结论和引用，不能只按日期判断过期。
- 不保存：真实Key/密码、认证头、原始业务输入/输出、工具正文、思考签名。只存脱敏元数据；生产受限审计留在服务器，不复制进仓库。
- CHANGELOG引用证据，evidence说明测试口径；它们不重复承担当前实施计划的职责。

合并为一个Go module后，历史 `probe_test.go` 改为 `probe_test.go.txt`，内容未变，避免旧阶段诊断片段被 `go test ./...` 误当成当前测试包。
