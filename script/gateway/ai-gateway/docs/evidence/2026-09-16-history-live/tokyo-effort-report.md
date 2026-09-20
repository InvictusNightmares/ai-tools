# 东京测试 Key 推理强度核对

对象：东京 Sub2API，API Key ID 141。时间均为 Asia/Shanghai；只读查询，不改 Key、共享 codex-E 分组或账号配置。

## 为什么页面经常显示横线

东京镜像版本 0.1.161，源码 revision `19149ca196eeae4a4482e5299dc6fa4ba0b06c8c`。该版本的 [formatReasoningEffort](https://github.com/Wei-Shaw/sub2api/blob/19149ca196eeae4a4482e5299dc6fa4ba0b06c8c/frontend/src/utils/format.ts#L193) 把 `none`、`minimal` 和空值都显示成 `-`；[管理用量表](https://github.com/Wei-Shaw/sub2api/blob/19149ca196eeae4a4482e5299dc6fa4ba0b06c8c/frontend/src/components/admin/usage/UsageTable.vue#L75) 调用这个函数。页面横线不能证明没有发送参数。

09:22:49 的 [数据库快照](tokyo-effort-check.jsonl) 中，今天 Sol 有 105 次 none、1 次 low，Astra 53 次 low，Luna 2 次 low，Terra 5 次 medium；这一快照没有空 effort。它不是全天统计，也不包含之后持续进行的业务测试。SQL 在 [tokyo-effort-check.sql](tokyo-effort-check.sql)。

今天早期主要是语义分类器评估：Sol 主分类用 none，Astra 复核用 low。这是分类调用自身的参数，不是它判定业务任务应该使用的强度。业务请求单独记录 `purpose=business`，路由审计记录目标与发送参数。

昨天执行过五模型、三协议的 243 次逐档参数探测，因此出现大量 high/xhigh/max 的请求记录；这些是测试主动指定的参数，不能据此判断昨天 Auto 比今天更会选高档。昨天也存在 NULL effort。数据库记录参数不能证明模型内部实际使用的推理计算量。

## 最高档的边界

只读核对的 codex-E 现有策略把 xhigh/max 映射为 high。Auto 生成 xhigh、请求发送 xhigh、Sub2API 最终记录 high 是三件事。共享分组未改，不能把前两项写成“供应商最高档已验收”。这一限制也适用于今天新增的真实复杂业务测试。

业务和分类的逐请求证据见 [本轮回归说明](README.md)。失败或未完成的请求保留，不能只统计 HTTP 200 或只看模型名称。

## 后续核对：数据库空值和实际适配问题

[09:48:40 快照](tokyo-effort-after-live.jsonl) 随业务测试增加，已出现 Deepseek 5 条、Terra 3 条空 effort；不能把早期快照“没有空值”推及全天。当前版本 [normalizeOpenAIReasoningEffort](https://github.com/Wei-Shaw/sub2api/blob/19149ca196eeae4a4482e5299dc6fa4ba0b06c8c/backend/internal/service/openai_gateway_request_body.go#L1278) 在部分路径将 none/minimal 归一化为空。这解释了 Auto 明确发送 none，数据库仍可能记 NULL 的情况；它本身不证明供应商没有接收到参数。

另外发现并修正 Auto 的 Messages 适配错误：原来目标 none 只发送 thinking.type=disabled，但该版本 [Anthropic→Responses 转换](https://github.com/Wei-Shaw/sub2api/blob/19149ca196eeae4a4482e5299dc6fa4ba0b06c8c/backend/internal/pkg/apicompat/anthropic_to_responses.go#L58) 忽略 thinking.type，仅读取 output_config.effort，缺省为 medium。09:48 快照的 Deepseek 有12条 medium，不能当作 Auto 按任务选择的 medium。

修复后对该 Sub2API 桥接始终显式发送 output_config.effort；none 发送 none，Astra 不支持 none 时仍映射 low。该合同已在五模型回归中复现旧实现4个失败并修复，不是对原生 Claude API 参数的声明。修复后 GPU 三条中文/英文/混合 Messages 请求全部200，返回仅含text；[09:56数据库核对](tokyo-messages-none-fixed.jsonl) 的 requested_reasoning_effort 和 reasoning_effort 全部为 none，输入/输出token与[客户端元数据](messages-none-fixed.json)一致。共享分组未改。

当天实际高档业务记录已有：09:44:14 Sol high（Responses）、09:45:51 Sol high（Chat）、09:48:02 Sol high（Messages）；09:46:59 Astra 请求 xhigh、记录 high（Responses）。这不是仅调用分类器或只在路由日志打印模型。部分非流式请求在客户端返回504后上游仍完成计费，必须同时保留客户端失败和Sub2API用量，不能把其中一侧当成整链路成功。
