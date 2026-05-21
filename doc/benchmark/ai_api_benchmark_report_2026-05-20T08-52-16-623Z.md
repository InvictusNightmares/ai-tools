# AI API 压测报告

- 目标地址：`http://192.168.64.16:4000`
- 模型：`gpt-5.5`
- 生成时间：`2026-05-20T08:52:16.637Z`
- 压测模式：`mapped`
- Prompt 档位：`large`
- Agent 映射：`chat=opencode`，`responses=codex`，`messages=claude code`
- 压测矩阵：3 种 API/Agent 映射 × 3 种输入长度
- 每场景请求数：`1`，全局并发：`1`，超时：`600000ms`
- 原始结果：`/Users/invictus/Github/ai-tools/doc/ai_api_benchmark_raw_2026-05-20T08-52-16-623Z.json`

## 总览

- 总请求：9
- 成功：9
- 总成功率：100.0%
- 最佳稳定场景：`messages / 短(~100k tokens) / claude code`，P95 15825ms，成功率 100.0%
- 最慢场景：`responses / 中(~150k tokens) / codex`，P95 49167ms，成功率 100.0%

## 按 API 格式汇总

| 维度 | 请求 | 成功率 | 平均ms | 平均P95ms |
|---|---:|---:|---:|---:|
| chat | 3 | 100.0% | 27269 | 27269 |
| responses | 3 | 100.0% | 35274 | 35274 |
| messages | 3 | 100.0% | 28191 | 28191 |

## 按 Agent 工作负载汇总

| Agent | 请求 | 成功率 | 平均ms | 平均P95ms |
|---|---:|---:|---:|---:|
| opencode | 3 | 100.0% | 27269 | 27269 |
| codex | 3 | 100.0% | 35274 | 35274 |
| claude code | 3 | 100.0% | 28191 | 28191 |

## 按输入长度汇总

| 输入 | 请求 | 成功率 | 平均ms | 平均P95ms |
|---|---:|---:|---:|---:|
| 短(~100k tokens) | 3 | 100.0% | 18196 | 18196 |
| 中(~150k tokens) | 3 | 100.0% | 37035 | 37035 |
| 长(~200k tokens) | 3 | 100.0% | 35503 | 35503 |

## 明细

| API格式 | 输入 | 目标输入tokens | Prompt字符 | Agent | 请求 | 成功率 | 平均ms | P50ms | P95ms | 平均tokens | 错误样例 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| chat | 短(~100k tokens) | 100000 | 421223 | opencode | 1 | 100.0% | 18912 | 18912 | 18912 | 95943.0 | - |
| chat | 中(~150k tokens) | 150000 | 631088 | opencode | 1 | 100.0% | 27775 | 27775 | 27775 | 143412.0 | - |
| chat | 长(~200k tokens) | 200000 | 841107 | opencode | 1 | 100.0% | 35121 | 35121 | 35121 | 190864.0 | - |
| responses | 短(~100k tokens) | 100000 | 421223 | codex | 1 | 100.0% | 19851 | 19851 | 19851 | 95947.0 | - |
| responses | 中(~150k tokens) | 150000 | 631088 | codex | 1 | 100.0% | 49167 | 49167 | 49167 | 143482.0 | - |
| responses | 长(~200k tokens) | 200000 | 841107 | codex | 1 | 100.0% | 36805 | 36805 | 36805 | 191006.0 | - |
| messages | 短(~100k tokens) | 100000 | 421223 | claude code | 1 | 100.0% | 15825 | 15825 | 15825 | 95979.0 | - |
| messages | 中(~150k tokens) | 150000 | 631088 | claude code | 1 | 100.0% | 34164 | 34164 | 34164 | 143577.0 | - |
| messages | 长(~200k tokens) | 200000 | 841107 | claude code | 1 | 100.0% | 34584 | 34584 | 34584 | 190879.0 | - |

## 结论

本次压测覆盖 OpenAI Chat Completions、OpenAI Responses、Anthropic Messages 三种兼容格式，并按实际 agent 工具映射统计：chat 对应 opencode，responses 对应 codex，messages 对应 claude code。结果主要反映网关在轻量并发下的端到端非流式响应延迟、成功率和 token 计量表现；它不是极限容量测试。

建议下一轮把 `REQUESTS_PER_SCENARIO` 提高到 20-50，并分别测试并发 5、10、20，以观察错误率和 P95/P99 是否出现拐点。生产验收时还应补充流式 TTFT、长输出、工具调用和多模型路由场景。
