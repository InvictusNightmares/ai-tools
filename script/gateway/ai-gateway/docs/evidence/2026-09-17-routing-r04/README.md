# R04：4005多人选型核对与输出格式修复

2026-09-17。统计只包括经4005精确关联网关request ID的流量，按API Key归属。4004/4005仍是可随时迭代的测试入口；本轮两地Auto更新v31/semantic-v10-task-routing-r4，Guard复用v29/r19。

## 真实使用情况

最终只读快照14:58（北京时间），窗口13:00起。实际业务用户2个Key：付晓镇Key5、产爱军Key60。Key4在此窗口为内部验收，已排除；Sub2API其他入口的账单也未计入。人数是此网关/窗口内的观测，不代表公司总使用人数。

| 用户 | 业务次数 | DeepSeek | Luna | Terra | 分类/复核次数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 付晓镇 | 19 | 4 | 2 | 13 | 13 |
| 产爱军 | 28 | 0 | 0 | 28 | 9 |
| 合计 | 47 | 4 | 2 | 41 | 22 |

DeepSeek为4/47=8.51%的业务请求；分类/复核22次另计，线上主分类器仍是用户选定的Luna，按规则由Sol复核。不能将分类调用混入业务占比。

[首份快照](observed-users.json)在14:40时只有37次业务，全部Terra；[14:58追加核对](observed-users-followup.json)发现付晓镇14:41–14:45新增10次业务：4次DeepSeek、2次Luna、4次Terra，分类5次。这批属于v30，早于14:52的v31部署，不能归因本次格式修复。首份快照保留，不覆盖。

- 付晓镇新增4次DeepSeek为一次simple quick_qa及3次工具续接；新增4次Terra为一次audit/extraction、multi_step评估及3次工具续接。两次Luna分别是simple extraction/formatting，受structured能力限制；v30没有记录实际格式，无法断定是合法schema需求还是本次格式误判。[新增脱敏路由](observed-followup-routes.json)保留分类评估，不能拿评估标签代替真实任务正确性。
- 产爱军28次中，3次initial_selection、25次tool_loop_locked。27条debugging/multi_step，评估为跨模块、5个推理依赖、中不确定性；1条simple summary仍处于未完成工具回合。v30后的5次也是旧工具回合，不能据此认定新规则无效。UA为Bun/1.4.2，仅凭UA不能确定具体客户端。
- 付晓镇最早9次发生于v30之前，其中两次简单阶段被sticky_quality_floor保留Terra，已由R03修复。本轮新增的DeepSeek证明其真实流量可以选到低档；不代表全部复杂度评估已经逐题证明合理。

两份快照共69/69次调用与本人Key账单精确匹配（47业务+22分类），新增15/15且Token差异0。业务费用：付晓镇0.4515788 USD、产爱军1.1222452 USD；分类费用分别0.6440854/0.8044338 USD。长上下文分类成本仍高，本次未变更主分类器或扩大分类正文保存范围。

## 发现并修复的代码缺陷

Chat任意非空response_format，以及Responses任意text字段，原来都会要求structured。因此response_format.type=text、仅设置verbosity、空对象或null，都错误排除DeepSeek。相反，Messages的output_config.format未纳入能力判断，会漏掉实际JSON Schema要求。

现在三协议共用格式判定：只有JSON模式、JSON Schema以及未知/不合法格式要求结构化能力；普通文本、verbosity、effort本身不要求。原始请求参数保留。审计增加output_format安全枚举text/json_object/json_schema/unknown，不记录用户schema、名称或正文。Codex CLI0.154.0的TextControls也将verbosity与format分别设为可选字段；[OpenAI结构化输出文档](https://developers.openai.com/api/docs/guides/structured-outputs)说明Responses的schema在text.format中。

本次修复只排除能力误判，未降低debugging/multi_step质量门槛，未放开未完成工具回合的模型绑定。用户旧请求没有具体格式日志，因此不能断言产爱军全部28次Terra都由此导致。新增审计可用于后续逐请求区分。

## 验证与失败保留

| 范围 | 结果 |
| --- | --- |
| 旧源码定向回归 | 16种格式中7种失败，含6个普通文本误判及Messages schema漏判；[失败记录](red-tests.log) |
| 当前完整源码 | 736 Go（含子用例）、42 Python、race/vet和六构建通过；[验证摘要](verification.json) |
| 两地真实修复前 | Chat text、Responses verbosity共4次都选Luna；[旧结果](before-format.json) |
| 两地真实修复后 | 同样4种普通文本场景均DeepSeek；Responses/Messages schema共4种均Luna，JSON内容正确；[初验](after-format.json)、[补验](verification-format.json) |
| 初验脚本问题 | 初验两次Responses把reasoning_text混入最终output_text，导致内容断言假失败。合成诊断确认最终文本正确，脚本改为只取output_text；两地补验均正确。初始失败JSON保留，未重写成8/8首次通过 |
| 两地入口 | 东京17/17、美西17/17，鉴权、三协议、计数、凭据阻断通过；[入口结果](entrypoints.json) |
| 精确账单 | 修复前/后格式探针、诊断、补验及入口共46/46调用匹配，Token差异0；真实UA保持，[对账摘要](accounting-summary.json) |

[格式路由审计](format-routes.json)显示v31普通文本output_format=text且不再要求structured；JSON Schema仍保留该能力限制。这里只验合成内容和协议/路由，未重放用户真实项目正文，也未新增四客户端完整开发题、模型质量画像或Guard30分钟负载；此前证据保留对应版本范围。

## 采用与回退

- 两地release：candidate-20260917-r19-native-v31；源码SHA：e8bab6ab957acdb787f74461c84ef2e11362b06a189f494b808774a8d7496efc；[发布元数据](release.json)、[相对v30改动清单](changed-files.json)。
- Auto SHA：368d83b675c1065cc6851faf78df276db8b3a425d95ba0275cc7a0620bdc9351。Guard沿用v29/r19未重建。
- 美西备份release-20260917-145257-439490、东京release-20260917-145324-862409；[部署记录](deployments.json)确认只替换Auto，Key、状态和受保护服务保持。
- 分类提示词/schema及Luna/Sol选择不变；策略r4、业务修订v31使旧分类/工具评估保守失效，业务缓存按版本隔离。新增字段可选、状态兼容；回退v30会恢复格式能力缺陷。4000/4001/4003未切流。
