# 2026-09-16 历史开发任务真实回归

范围：用户已确认将固定的 48 条脱敏重建样本发送到东京测试端点，测试 Key 141。4000/4001 未改动。下面“分类结果”的三轮仅调用分类器；后续新增的真实业务与 Guard 结果分开记录，不能混算。

## 分类结果

| 方案 | 有效分类 | 三语难度与目标 effort 一致 | 中位延迟 | p95 | 最慢 |
| --- | ---: | ---: | ---: | ---: | ---: |
| [semantic-v4 Sol→Astra](sol-astra-checkpoints.jsonl) | 48/48 | 15/16（93.75%） | 3479ms | 6156ms | 8162ms |
| [semantic-v4 Astra(low)→Sol](astra-sol-checkpoints.jsonl) | 48/48 | 13/16（81.25%） | 4727.5ms | 10274ms | 14992ms |
| [semantic-v5 Sol→Astra](sol-astra-v5-checkpoints.jsonl) | 48/48 | 16/16（100%） | 3118ms | 9314ms | 56514ms |

三轮各 48 条任务边界判断均与题集一致，其中 12 条新任务切换都正确。v5 的目标 effort 为 none 12、low 12、medium 24；这些是任务分类结果，不是业务模型的实际执行强度。分类调用自身使用主模型 none、Astra 复核 low，不能与业务 effort 混看。

首轮英文提醒列表修正被判 multi_step，中文/混合为 bounded；Astra 主分类还在启动要求、工具结果上出现差异。v5 明确按未解决的推理依赖判断，不把局部修改条数、文件数和常规读改测步骤直接当复杂度。固定题集、翻译和预设标签未修改。这个题集现在已经用于修订规则，是回归集，不能继续宣称盲测；还需独立新样本与实际产物验证。

v5 有 3 条主分类传输失败后由 Astra 接替，最慢 56.514 秒，不能用总体 48/48 掩盖这一尾延迟。评估工具单次 HTTP 超时 60 秒，试运行服务为 30 秒，两者延迟边界不同。

原题集把启动流程三个检查点都预设为 complex，但初始提示只是明确的条件逻辑实现，缺少复杂度证据。保留原标签及全部差异；不为了提高准确率事后重标，也不把语义一致率当业务质量。两个方案对 coding/debugging 标签仍有差异，见 [完整统计](comparison.json)。这组任务没有 exceptional 场景，未覆盖最高档。

## 修复与验证

- 评估脚本原先漏掉 history_holdout，现按题集派生 split，检查重复、缺失、协议错配，分母包含全部预定样本，分别统计任务边界和复杂度/effort。一组样本重复三次不能冒充三语通过。5 个 Python 回归通过。
- 计数接口缺失工具绑定时原先没有异常审计；成功事件也缺少 Guard allow、分类策略、HTTP 状态和完整性。两个失败回归复现后修复，计数不推进会话状态。
- 真实分类传输失败事件的 effective_reasoning_effort 原先为空；现在在发请求前记录待发送强度，主分类失败和复核失败也能按模型/effort 对账。旧原始证据保持原样，不回填伪造历史字段。
- Auto [完整 race](local-race-final.jsonl) 262 个测试/子测试通过，vet 通过；Guard 根模块 [完整 race](guard-root-race.jsonl) 16 个通过，vet 通过。早期 `guard-race.jsonl` 仅覆盖 go-check 14 个测试，不作为整个 Guard 模块的依据。

## 网络恢复与后续服务器验收

[网络诊断和修改范围](network-proposal.md)：Clash 的 DIRECT 规则已存在并命中，TUN 仍接管了公司内网目标。用户手动在当前订阅 Merge 合并 fake-IP 排除和两个精确 TUN 排除地址，启用公司 VPN 后，09:07 三个 SSH 别名均成功。已确认原有 8 条 DNS 排除保留、新增堡垒机域名，Guard ready。客户端 Merge 对数组整体替换，见 [2.5.2 合并实现](https://github.com/clash-verge-rev/clash-verge-rev/blob/v2.5.2/src-tauri/src/enhance/merge.rs)。本次没有修改 dmit-rules.yaml 或服务器网络配置。

源码已同步到 GPU `/tmp/gateway-v5-verify.ptCiNs`，88/88 文件 SHA 校验通过，独立 Guard8012、Auto8092 验证。生产 Guard8011 和 Nginx4000/4001 未替换。初版、Guard r2、历史适配修复的 Linux 检查分别见同目录 `gpu-*-verify.log`。

## 真实业务修改验证循环

[逐请求元数据](live-first-and-r2.json) 不包含提示词、模型正文或凭据。首轮计划 48 次，发出 41 次：36 成功、5 次 Guard 403，失败流程余下 7 步未发出，不能记为 48 次测试。被误拦的是中文/英文/混合退出清理和英文/混合发布流程。

根因：Go 将 persistence/持久化、production、代码块等弱信号组合升成 medium/high，覆盖 Qwen3Guard 的 Safe 判定。`preflight-r2` 把这些组合保留为 review 原因码，交给真实 Guard 判断语义；凭据使用硬拦截、Unsafe/Controversial 拒绝、不可用 fail-closed 保留。5 个回归先失败后通过，Guard 全量 race 21 项、vet 通过。真实本地 Guard 正反样本：正常开发/防御 4/4 allow，合成凭据使用、凭据窃取中英文、勒索、钓鱼、暴力 6/6 block；这 6 条只发送 GPU 本机 Guard，没有发送外部模型。它是针对性回归，不是全面安全效果评估。

Guard r2 后，12 个三语开发流程的 48 次真实请求全部完成：Terra/medium 18、Luna/low 15、Luna/medium 3、Deepseek/none 11、Terra/none 1。每个流程包含真实模型生成的 Read 调用 ID、固定脱敏工具结果、后续修正和新任务；没有执行生成代码或完整 Codex/Claude Code 客户端，产物质量仍需独立验收。一个简单新任务选 Terra/none 是旧上下文超过当前 8KB 保守能力门，不能误报为复杂度变高；模型上下文容量门仍需真实容量验证。

额外 15 次递增难度首轮只有 5 次完整成功：Responses 历史 reasoning_text 被分类器拒绝 4 次503；Messages 将 Deepseek 的加密思考签名送给下一模型，出现4次400；Chat复杂/极复杂请求选中Sol/high、Astra/xhigh但返回2次504。失败结果完整保留。

针对真实历史结构，本地和 GPU 增加归一化及转发修复：不把供应商 reasoning item 当用户任务；已结束回合保留可见正文、phase、工具与结果，去掉不可跨供应商复用的私有思考状态；当前未结束工具回合保持原始思考及调用 ID。参考 [OpenAI 官方 reasoning 文档](https://developers.openai.com/api/docs/guides/reasoning)：工具调用续接需保留最近用户消息后的完整回合。本 pilot 采用当前回合思考连续性，尚未实现跨回合私有状态的模型/账号来源认证；跨回合推理复用和缓存收益需要另测。修复后 Auto 全量 race 267 项、vet 和 Python 8 项通过；15 条 SSE 真实复测全部完成，三语分别使用 Chat、Responses、Messages，每条会话顺序经过 Deepseek/none → Luna/low → Terra/medium → Sol/high → Astra/xhigh。Astra Responses 明确回报 high，数据库也确认分组映射；Messages 简单任务实际被旧转换默认成 medium，已另行修正并补充实测。因此15/15仅证明完成和历史续接，不能冒充全部强度正确。耗时7.1–186.7秒，包括完整输出；非流式长任务504仍未解决。

[东京用量 effort 显示核对](tokyo-effort-report.md)：UI 横线包含 none/minimal/空值三种情况。分类请求、业务目标、发送值和 Sub2API 实际映射须分开；codex-E 的 xhigh/max→high 未改。

## Messages none 最终修复与当前验收边界

东京真实版本的转换忽略 thinking.type，缺省 effort 为 medium。Auto 现在对 Messages 桥接始终发送 output_config.effort，包括 none；Astra最低仍为low。五模型回归先复现旧实现四项失败，修复后 Auto 全量 race 273、vet、Python8项通过，GPU Linux同样通过。三条真实定义请求全部200，东京数据库三条请求/实际记录均为none，见 [参数核对](tokyo-effort-report.md)。不能把此前15条SSE的“完整成功”当作修复前Messages强度正确；最终参数修复单独记录。

生产前仍未通过：共享codex-E将xhigh/max映射high，非流式长输出504，完整Codex/Claude Code的压缩/取消/agent并发，生成产物质量，实际上下文容量与缓存收益，多人配额和持久化事务。另一个必须解决的输入边界是：Guard对疑似凭据做本机模型脱敏，但Auto仍持有原始业务payload；仅“解释凭据”且未触发使用拦截的输入还没有经过外发脱敏验收，不能据Guard的allow推断外部模型一定收不到明文。当前整体仍是隔离pilot，禁止据本轮HTTP通过切生产。

后续状态：09:57之后的外发脱敏修复和验收转记于[输入脱敏证据](../2026-09-16-input-redaction/README.md)。本文件保留本轮原始结果，不将后续修复回填成旧版本已通过。

## 源码一致性与清理

最终源码包 `gateway-history-final-20260916.tgz` SHA-256 为 `54a258d182e9609ec26db875fc356568327c63bb9462fb4b493a5198c42a99d1`，93个源文件与GPU已验证目录逐一一致，见 [最终清单](source-final-manifest.json)。早期88文件清单保留为历史快照，不代表最新版本。

本轮临时Guard8012和Auto8092已停止，远端测试Key副本已删除；生产Guard8011及vLLM8001健康200，见[清理与健康检查](isolation-close.jsonl)。本地Key私有文件保留供后续授权验收使用。服务器原始模型响应仅保留在私有临时目录，仓库证据不含这些正文。
