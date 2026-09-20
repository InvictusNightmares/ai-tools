# 三语分类、全模型 effort 与 Claude Code 验证记录

日期：2026-09-15。测试使用已授权的东京 test Key（ID 141）；此目录不保存 Key、用户提示词或响应正文。题集中的开发任务为脱敏重建或合成样本。

## 结论与范围

本地语义分类器已覆盖中文、英文、混合表达，独立复核、工具续接和分类缓存；全模型 effort 适配与 Claude Code 入口已补充。当前测试分别是本地回归、真实区域分类调用和真实供应商参数探测，尚不能合并称为新版 Guard→Auto→业务模型全链路通过。

GPU SSH、堡垒机及 VPN Guard API 当前不可达；新版代码未上传 GPU，4000/4001 生产入口未切换。原 stage12 的 GPU 验证只适用于原归档。

## 三种语言的分类对比

[冻结题集](cases-60.json)包含 60 个任务，每个任务各有中文、英文和混合表达；12 个开发任务、48 个保留任务，按任务分组划分。同一任务的译文不会跨集合。标签由实现者在测试前给定，尚未独立人工复核。

| 主分类模型 → 复核模型 | 保留集合法结果 | 三语难度一致组 | 一致率 |
| --- | ---: | ---: | ---: |
| DeepSeek Flash → Sol | 142/144 | 44/48 | 91.67% |
| Luna → Sol | 144/144 | 46/48 | 95.83% |
| Sol → Astra | 144/144 | 47/48 | 97.92% |
| Astra（low）→ Sol | 144/144 | 47/48 | 97.92% |

详细分语言延迟、任务标签、失败与不一致样本见 [comparison.json](comparison.json)。上述“一致率”仅表示三种表达获得相同难度，不是选型正确率。后三种组合达到本项 95% 门槛；仍需业务产物构建/测试、多轮切换、缓存及日志对账才能决定生产方案。

Sol→Astra、Astra→Sol 各完成 180 条开发加保留集评估，均得到 180 条合法最终结果。曾误发 Astra/none 的批次已停止，其 164 条最终结果全部依赖 Sol 复核，不能作为 Astra 成功证据，也未纳入比较；见 [错误批次说明](astra-none-incident.json)。

## 五个文本模型的参数探测

[汇总](effort-probe-summary.json)覆盖 DeepSeek Flash、Luna、Terra、Sol、Astra，各自全部原生 effort，三种语言以及 Chat、Responses、Messages 三种协议，共 243 次。243 次均 HTTP 200，且具备测试程序要求的响应完整性字段。

- [Chat/Responses 162 次记录](all-model-effort-probe.jsonl)。
- [Messages 81 次记录](all-model-anthropic-effort-probe.jsonl)。
- [东京分组规则只读证据](tokyo-test-effort-policy.json)：test 当前所属 codex-E 的全模型规则将 xhigh 和 max 改写为 high，最大 effort 字段本身为“不限制”。

Responses 中 27 次明确报告的 effort 与请求不一致，全部回报 high，与上述配置一致。HTTP 200 不能证明 xhigh/max 已执行；Chat/Messages 未提供对应回报时只能确认参数和传输。共享分组未被修改，专用测试分组的临时验证方案待用户明确批准。

这套探测只检查参数兼容和返回完整性，提示词很短，不能代替复杂开发任务或模型能力比较。当前语义策略产生 none/low/medium/high/xhigh；max 仅完成参数探测，尚不自动产生。

## Claude Code

东京管理员近 7 天视图中已有 Opus→Sol 3,480 次、Sonnet→Terra 1,523 次、Haiku 4.5→Luna 110 次，入口为 `/v1/messages`；见 [脱敏观察记录](claude-code-observed-mappings.json)。这是当前 Sub2API 的静态映射，不能当作 Claude 原生模型调用。

四个兼容名称分别直连东京 Messages 与 count_tokens，共 [8 次 HTTP 200](claude-alias-count-probe.json)。本地新增别名、system 数组、工具结果续接、Messages effort 与格式合并、计数接口和认证传递测试。完整客户端的流式工具循环、取消、压缩及主/子 agent 独立会话仍待验收；美西也尚未完成同范围验证。

## 源码与本地验证

[源码变更清单](changed-files.md)按文件比较当前源码与 stage12 归档，不依赖 Git 是否已跟踪；[清单及哈希](source-manifest.json)同时记录源码包、Linux 程序和冻结题集的 SHA-256。

本地使用 Go 1.27.1 执行格式检查、全量测试、vet、race，并交叉构建 Linux amd64 静态程序。[最新 race 记录](local-race-v3.jsonl)含 194 个通过的测试/子测试，0 失败。它与较早的 `local-race.jsonl` 属于不同源码时点，旧记录保留作为历史，不替换其内容。

源码包不含 Key、状态、日志或编译产物；实际上传和 GPU 构建后还须逐文件对照哈希，不能仅凭本地构建成功声称服务器已更新。
