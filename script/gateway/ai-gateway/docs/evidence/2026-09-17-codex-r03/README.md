# R03：Codex 迁移压缩兼容与普通阶段降档

2026-09-17。4004/4005是可随时更新的多人测试入口，按用户要求快速发现、修复和迭代；部分人员试用不视为正式切流。本轮只更新Auto到v30/semantic-v10-task-routing-r3，Guard复用v29/r19。

## 真实测试发现与证据边界

按美西 `api_key_id=5` 和维护映射定位付晓镇；不使用共享 `user_id=1` 归属。Sub2API实际UA为 Codex Desktop 0.154.0-alpha.6.2 / macOS 15.8.0。通过独立账单的client request ID精确关联网关身份，再检查13:40–13:49（北京时间）的记录：

- 73条路由事件中，43条 `request_rejected / 404 model_not_found` 在Guard和分类之前发生；没有业务上游调用。17条与Nginx `/v1/responses` 404精确匹配，其余26条无逐请求Nginx关联，可能包含WebSocket内请求，但无法确认。
- 旧拒绝审计未保存模型名、会话摘要和压缩类型，因此不能把43条全部说成压缩，也不能断言用户当时提交了哪个具体模型名。用户无法提供客户端错误原文；未读取或重放其原始业务内容。
- 9次业务均为Terra medium；5次延续多步agent任务、1次多步audit，其余是summary/simple、quick_qa/simple及其工具续轮。前两次简单阶段分数5、置信度0.96/0.94，却因 `sticky_quality_floor` 保留Terra。旧日志没有完整结构化评估或原提问，不能由模型标签反推具体任务内容。
- 17/17次调用与本人Key账单精确匹配：9次业务合计 **0.2489548 USD**，4次Luna分类 **0.0202800 USD**，4次Sol复核 **0.527130 USD**。分类/复核合计约为业务的2.20倍。工具绑定期间没有逐轮重复分类；复核曾纠正难度及处理主分类无效，不能简单删除复核来节约费用。本轮保持用户选定的Luna主分类和95%门槛。13:32的Sol直连账单不属于这组4005请求。

## 根因、修复与兼容

1. `ValidatePublicModel` 原来接受auto和Claude别名，却拒绝目录内GPT/DeepSeek名称。Codex CLI 0.154.0源码 `session/turn.rs::maybe_run_previous_model_inline_compact` 表明，切换模型时可能使用上一模型发起压缩。两地合成请求带 `gpt-5.6-sol`，旧式 `/responses/compact` 与v2 `/responses` 压缩都复现相同404（4/4）。这是已证明的兼容缺陷；与用户旧记录的错误一致，但旧日志不足以逐条确定同因。
2. 现在目录内的DeepSeek Flash、Luna、Terra、Sol、Astra均可作为Auto输入别名，覆盖普通请求、压缩和子任务。实际模型继续由Auto选择；指定Sol不强制用Sol。未知名称仍404，公开列表保持auto与原生审核模型，Guard顺序不变。
3. 会话规则过去只允许新任务或TTL重置后降档，导致同任务进入简单总结阶段仍维持旧档位和effort。现在通过语义评估确认低不确定性、无失败、低推理依赖、置信度至少0.9的普通信息阶段可在用户回合边界降档。未完成工具回合、流中途、混合审计/诊断目标继续保持约束；能力和上下文筛选先执行，原生加密压缩状态不会发送给不支持它的模型。
4. 审计增加协议、`compaction/completion`、会话摘要和拒绝模型摘要，未知模型正文不入日志；成功路由记录已验证的结构化任务评估。以后可直接区分压缩拒绝与普通请求拒绝。

分类提示词、schema、主分类/复核模型未修改；路由语义变化将策略升至r3、业务缓存修订升v30，使旧分类/工具评估保守失效。会话结构没有不兼容变更，状态和用户Key保留。只有普通信息阶段主动降档，复杂任务继续按质量要求即时升级。实现文件见[改动清单](changed-files.json)。

## 验证

| 范围 | 结果 |
| --- | --- |
| 旧源码定向回归 | 10个已知模型名/压缩组合全部404；5类普通阶段无法降档；原生能力边界及拒绝诊断回归失败，保存[原始失败输出](gateway-v30-red-tests.log) |
| 首轮完整验证 | 原有“拒绝Astra”的旧契约测试失败；将其改成“拒绝未知模型”后重验，不把首轮算通过 |
| 最终完整源码 | 719 Go（含子用例）、42 Python、race/vet及六构建通过；[验证摘要](verification.json) |
| 修复前后真实压缩 | 两地各旧式/v2合成压缩，404 4/4 → 200 4/4，均有非空原生encrypted compaction；[修复前](alias-before.json)、[修复后](alias-after.json) |
| 原生Codex | 本机实际CLI0.154.0 app-server，隔离配置和合成内容，东京/美西×旧式/v2共4组；初次对话、压缩、记忆续接、取消、恢复全部20/20；[结果](native-codex.json) |
| 三语路由 | 两地中/英/混合各一组“复杂诊断→只整理已有结果”，12/12成功，复杂阶段Sol，六次后续总结均DeepSeek，均为continuation=true/new_task=false及routine_phase_downshift；另见路由审计，不以HTTP成功代替任务内容质量 |
| 入口回归 | 东京17/17，美西17/17；含鉴权、网页/用量、模型列表、Chat/Responses/Messages、计数、Guard凭据阻断 |

[官方压缩契约](https://developers.openai.com/api/docs/guides/compaction)要求客户端继续使用返回的压缩窗口。此次原生验收实际检查标记与三阶段信息仍可回忆，没有用普通文本摘要冒充加密状态。所测客户端是CLI0.154.0，不冒充付晓镇Desktop alpha的原会话复测。

## 部署和回退

- release：`candidate-20260917-r19-native-v30`；源码SHA：`013b8d821aba7b0aa9904a88f64b85ee79eb06c8a85750f332418b961811aafd`，本地与远端冻结清单一致。
- Auto二进制SHA：`d9723d997e1addc7700570a0b068cf504de1a3b2142861f0f11d9c92e02fb03e`；Guard沿用v29/r19的二进制，未重建。
- 美西备份：`release-20260917-142643-754268`；东京备份：`release-20260917-142702-251698`。部署工具确认只改Auto、Key/状态保留、受保护容器未改。
- 回退使用前一v29制品与其配套状态约定；会恢复模型名拒绝和同任务粘滞缺陷。正式4000/4001/4003未切流。

尚未证明：用户旧43次错误的逐条模型名/请求类型、其原Desktop会话修复后结果；长上下文分类成本的进一步优化。此次未改分类器选型，未重跑Guard30分钟负载，历史能力画像和r19范围保留。

## 独立账单与UA核对

[对账摘要](accounting-summary.json)：东京40次attempt匹配39条账单，美西39/39，总计78/79；已知成功漏账0、Token差异0。东京唯一未匹配为Luna主分类HTTP502、success=false/usage_reported=false，随后Sol复核及业务成功；不能据此断言取消、未计费或零Token，保留未知。返回账单中的Codex原生UA、合成压缩UA、三语路由UA均正确，入口脚本本身使用Python-urllib。摘要中的空UA来自未匹配账单，不是证实UA丢失。

[部署记录](deployments.json)、[入口检查](entrypoints.json)、[原生调用与Guard匹配](native.json)、[东京路由](tokyo-extra-routes.json)、[美西路由](us-extra-routes.json)分别保留验证范围。两地原生各8次进入业务路由，Guard决策各8/8匹配；取消可能发生在业务调用前，不把客户端检查项数量当成业务请求数。

## 真实上游旧压缩状态补验

主验收后增加跨入口状态试验，账单统计范围仍是前述79次attempt，以下附加直连/网关探针不混入该数字。

- 首次[普通回复样本](signed-migration.json)没有产生encrypted reasoning，不满足“加密历史”试验前提；东京召回另未满足字符串断言，未保留当次回答正文，原因不能补猜。美西返回模型标识为gpt-6-sol，与请求gpt-5.6-sol分列，不据返回名称改业务目录。
- 改用原生compaction_trigger获得真实加密状态时，[直接上游非流式请求](opaque-migration.json)两地502，尚未进入网关；这不计为网关迁移失败或成功。
- 按已核验的上游SSE原生协议取得Sol加密compaction后，向网关只传该加密历史和不含原标记的新指令，再压缩并恢复auto，两地均200且精确回忆 `PAPAYA-8156 upload verify publish`。此时恢复上下文确实来自旧加密状态，而非在请求中重新提供标记；[最终补验](opaque-migration-sse.json)两地均通过。新旧压缩状态由真实上游产生，网关没有伪造或改写密文。
