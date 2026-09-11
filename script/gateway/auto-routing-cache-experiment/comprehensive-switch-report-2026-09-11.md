# 复杂任务多模型切换真实测试报告

测试入口：`http://106.14.254.110:9880/v1`
认证：`key.yaml` 的 `key`（未写入报告）

## 测试设计

- 3 类复杂任务：网关架构、生产故障诊断、跨包代码迁移。
- 每类按 `deepseek-flash → gpt-5.6-luna → gpt-5.6-terra → gpt-5.6-sol → gpt-6-astra` 逐级切换。
- 每个模型连续 2 轮，保留完整前序回答，合计 30 次真实请求。
- `temperature=0`、`max_tokens=700`、非流式；记录返回模型、时延、prompt/output token 和缓存字段。

## 总体结果

- 请求数：30；成功：25；失败：5。
- 失败：Terra 1 次 HTTP 502（上游 HTTP/2 stream failed），Sol 4 次超时。
- 所有成功请求返回模型与请求模型一致。

## 按模型汇总

| 模型 | 请求 | 成功 | 失败 | 平均成功时延 | P95 成功时延 | 有缓存字段 | 第二轮最大 cached tokens |
|---|---:|---:|---:|---:|---:|---:|---:|
| `deepseek-flash` | 6 | 6 | 0 | 5257 ms | 5429 ms | 3 | 128 |
| `gpt-5.6-luna` | 6 | 6 | 0 | 86354 ms | 88450 ms | 0 | — |
| `gpt-5.6-terra` | 6 | 5 | 1 | 129893 ms | 133355 ms | 3 | 8960 |
| `gpt-5.6-sol` | 6 | 2 | 4 | 125632 ms | 104716 ms | 0 | — |
| `gpt-6-astra` | 6 | 6 | 0 | 107178 ms | 129304 ms | 3 | 29440 |

## 按场景逐轮数据

| 场景 | 阶段模型 | 状态 | 时延 | prompt | cache hit | cache miss | output | finish |
|---|---|---|---:|---:|---:|---:|---:|---|
| gateway_architecture | `deepseek-flash` | ok | 4729 | 268 | None | None | 700 | length |
| gateway_architecture | `deepseek-flash` | ok | 5487 | 327 | 128 | 199 | 700 | length |
| gateway_architecture | `gpt-5.6-luna` | ok | 77767 | 459 | None | None | 4039 | stop |
| gateway_architecture | `gpt-5.6-luna` | ok | 107299 | 4395 | None | None | 5686 | stop |
| gateway_architecture | `gpt-5.6-terra` | http_502 | — | — | — | — | — | — |
| gateway_architecture | `gpt-5.6-terra` | ok | 113159 | 10165 | 8960 | 1205 | 6137 | stop |
| gateway_architecture | `gpt-5.6-sol` | ok | 146547 | 16354 | None | None | 8042 | stop |
| gateway_architecture | `gpt-5.6-sol` | TimeoutError | — | — | — | — | — | — |
| gateway_architecture | `gpt-6-astra` | ok | 100641 | 23329 | None | None | 3242 | stop |
| gateway_architecture | `gpt-6-astra` | ok | 138476 | 26650 | 23168 | 3482 | 4404 | stop |
| production_debug | `deepseek-flash` | ok | 5187 | 268 | None | None | 700 | length |
| production_debug | `deepseek-flash` | ok | 5403 | 323 | 128 | 195 | 700 | length |
| production_debug | `gpt-5.6-luna` | ok | 88450 | 437 | None | None | 4656 | stop |
| production_debug | `gpt-5.6-luna` | ok | 77230 | 5047 | None | None | 4151 | stop |
| production_debug | `gpt-5.6-terra` | ok | 118677 | 9083 | None | None | 6516 | stop |
| production_debug | `gpt-5.6-terra` | ok | 133355 | 15640 | 8960 | 6680 | 7321 | stop |
| production_debug | `gpt-5.6-sol` | TimeoutError | — | — | — | — | — | — |
| production_debug | `gpt-5.6-sol` | TimeoutError | — | — | — | — | — | — |
| production_debug | `gpt-6-astra` | ok | 65407 | 23151 | None | None | 2095 | stop |
| production_debug | `gpt-6-astra` | ok | 109075 | 25285 | 22912 | 2373 | 3552 | stop |
| agent_workflow | `deepseek-flash` | ok | 5429 | 244 | None | None | 700 | length |
| agent_workflow | `deepseek-flash` | ok | 5307 | 299 | 128 | 171 | 700 | length |
| agent_workflow | `gpt-5.6-luna` | ok | 84515 | 416 | None | None | 4571 | stop |
| agent_workflow | `gpt-5.6-luna` | ok | 82860 | 4693 | None | None | 4421 | stop |
| agent_workflow | `gpt-5.6-terra` | ok | 116248 | 9000 | None | None | 6367 | stop |
| agent_workflow | `gpt-5.6-terra` | ok | 168026 | 15398 | 7936 | 7462 | 9228 | stop |
| agent_workflow | `gpt-5.6-sol` | ok | 104716 | 24666 | None | None | 5254 | stop |
| agent_workflow | `gpt-5.6-sol` | TimeoutError | — | — | — | — | — | — |
| agent_workflow | `gpt-6-astra` | ok | 100165 | 29612 | None | None | 3167 | stop |
| agent_workflow | `gpt-6-astra` | ok | 129304 | 32822 | 29440 | 3382 | 4212 | stop |

## 观察

1. Flash 的短输出阶段约 5 秒，首轮通常没有缓存字段，第二轮只观察到约 128 cached tokens；在本次完整会话中，Flash 的上下文较短，缓存优势有限。
2. Terra 在架构和故障场景的第二轮分别观察到约 8,960 cached tokens；但第一轮没有缓存字段，且出现一次上游 502，网关必须支持重试和同能力降级。
3. Astra 在三个场景的第二轮分别观察到约 23,168、22,912、29,440 cached tokens，说明长会话稳定使用同一模型时，上游缓存可以覆盖大部分历史前缀。
4. Sol 出现 4 次超时，说明静态“高档模型一定可用”不成立；升级策略必须同时看区域实时健康度、超时率和降级链。
5. 多次低到高切换会让每个新模型第一次看到较大的历史输入；是否产生实际成本，要以该模型返回的 cache usage 为准，字段缺失时按 miss 保守估算。

完整原始统计（不含 Key）见：`comprehensive-switch-result.json`。
