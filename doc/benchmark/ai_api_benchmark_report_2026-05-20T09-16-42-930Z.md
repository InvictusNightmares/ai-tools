# AI API 压测报告

- 目标地址：`http://192.168.64.16:4000`
- 模型：`gpt-5.5`
- 生成时间：`2026-05-20T09:16:42.940Z`
- 压测模式：`mapped`
- Prompt 档位：`large`
- Agent 映射：`chat=opencode`，`responses=codex`，`messages=claude code`
- 压测矩阵：3 种 API/Agent 映射 × 3 种输入长度
- 每场景请求数：`20`，全局并发：`20`，超时：`600000ms`
- 原始结果：`/Users/invictus/Github/ai-tools/doc/ai_api_benchmark_raw_2026-05-20T09-16-42-930Z.json`

## 总览

- 总请求：180
- 成功：178
- 总成功率：98.9%
- 最佳稳定场景：`messages / 短(~110k tokens) / claude code`，P95 29967ms，成功率 100.0%
- 最慢场景：`responses / 中(~160k tokens) / codex`，P95 64897ms，成功率 95.0%

## 按 API 格式汇总

| 维度 | 请求 | 成功率 | 平均ms | 平均P95ms |
|---|---:|---:|---:|---:|
| chat | 60 | 100.0% | 37876 | 49899 |
| responses | 60 | 96.7% | 38149 | 55481 |
| messages | 60 | 100.0% | 36654 | 45769 |

## 按 Agent 工作负载汇总

| Agent | 请求 | 成功率 | 平均ms | 平均P95ms |
|---|---:|---:|---:|---:|
| opencode | 60 | 100.0% | 37876 | 49899 |
| codex | 60 | 96.7% | 38149 | 55481 |
| claude code | 60 | 100.0% | 36654 | 45769 |

## 按输入长度汇总

| 输入 | 请求 | 成功率 | 平均ms | 平均P95ms |
|---|---:|---:|---:|---:|
| 短(~110k tokens) | 60 | 100.0% | 26960 | 40017 |
| 中(~160k tokens) | 60 | 98.3% | 39032 | 51856 |
| 长(~220k tokens) | 60 | 98.3% | 46687 | 59276 |

## 明细

| API格式 | 输入 | 目标输入tokens | Prompt字符 | Agent | 请求 | 成功率 | 平均ms | P50ms | P95ms | 平均tokens | 错误样例 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| chat | 短(~110k tokens) | 110000 | 462933 | opencode | 20 | 100.0% | 30596 | 24841 | 48635 | 105379.6 | - |
| chat | 中(~160k tokens) | 160000 | 672798 | opencode | 20 | 100.0% | 36962 | 37702 | 43947 | 152971.9 | - |
| chat | 长(~220k tokens) | 220000 | 924527 | opencode | 20 | 100.0% | 46072 | 47126 | 57115 | 209778.7 | - |
| responses | 短(~110k tokens) | 110000 | 462933 | codex | 20 | 100.0% | 25978 | 24987 | 41449 | 105396.4 | - |
| responses | 中(~160k tokens) | 160000 | 672798 | codex | 20 | 95.0% | 42209 | 39277 | 64897 | 152978.9 | litellm.RateLimitError: RateLimitError: OpenAIException - {"error":{"type":"usage_limit_reached","message":"The usage limit has been reached","plan_type":"plus","resets_at":1779273816,"eligible_promo":null,"resets_in_seconds":5438}}. Received Model Group=gpt-5.5
Available Model Group Fallbacks=None |
| responses | 长(~220k tokens) | 220000 | 924527 | codex | 20 | 95.0% | 46261 | 48481 | 60096 | 209768.5 | litellm.RateLimitError: RateLimitError: OpenAIException - {"error":{"type":"usage_limit_reached","message":"The usage limit has been reached","plan_type":"plus","resets_at":1779274993,"eligible_promo":null,"resets_in_seconds":6538}}. Received Model Group=gpt-5.5
Available Model Group Fallbacks=None |
| messages | 短(~110k tokens) | 110000 | 462933 | claude code | 20 | 100.0% | 24306 | 25060 | 29967 | 105403.6 | - |
| messages | 中(~160k tokens) | 160000 | 672798 | claude code | 20 | 100.0% | 37925 | 37952 | 46723 | 152988.7 | - |
| messages | 长(~220k tokens) | 220000 | 924527 | claude code | 20 | 100.0% | 47729 | 46790 | 60616 | 209768.6 | - |

## 结论

本次压测覆盖 OpenAI Chat Completions、OpenAI Responses、Anthropic Messages 三种兼容格式，并按实际 agent 工具映射统计：chat 对应 opencode，responses 对应 codex，messages 对应 claude code。压测使用大上下文输入，单次实际 token 约 105k、153k、210k，每场景 20 次请求、并发 20。

整体成功率为 98.9%。chat/opencode 与 messages/claude code 在本轮 20 并发下均为 100% 成功；responses/codex 在 160k 和 220k token 档各出现 1 次 `usage_limit_reached`，说明当前瓶颈更像上游额度/限流，而不是请求体解析或本地脚本超时。

建议下一轮针对 responses/codex 单独做阶梯压测：并发 10、15、20、25，每档保留相同 token 规模，观察 `usage_limit_reached` 从哪个并发开始出现。生产验收时还应补充流式 TTFT、长输出、工具调用和多模型路由场景。
