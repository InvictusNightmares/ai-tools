# Gateway 真实缓存探测记录

日期：2026-09-11  
入口：`http://106.14.254.110:9880/v1`  
认证：使用本地 `key.yaml` 的 `key` 字段；Key 未写入报告、日志或输出。

## 测试方法

使用同一段约 2.3 万 token 的稳定 system 前缀，按以下顺序发送 Chat Completions 请求：

```text
deepseek-flash 1 → deepseek-flash 2
→ gpt-5.6-terra 1 → gpt-5.6-terra 2
→ deepseek-flash 3 → deepseek-flash 4
```

每轮只改变 user turn 编号，`temperature=0`、`max_tokens=32`、非流式。`run-id=20260911-cache-a` 用于保证本轮前缀与历史探测不同。

## 结果

| 请求 | 返回模型 | 总时延 | prompt tokens | cached tokens | 推导出的 miss tokens | usage 字段 |
|---|---|---:|---:|---:|---:|---|
| Flash 1 | `deepseek-flash` | 1606 ms | 23445 | — | — | 无缓存字段 |
| Flash 2 | `deepseek-flash` | 2083 ms | 23445 | 23296 | 149 | `prompt_tokens_details.cached_tokens` |
| Terra 1 | `gpt-5.6-terra` | 1967 ms | 21624 | — | — | 无缓存字段 |
| Terra 2 | `gpt-5.6-terra` | 1997 ms | 21624 | — | — | 无缓存字段 |
| Flash 3 | `deepseek-flash` | 1744 ms | 23445 | 23296 | 149 | `prompt_tokens_details.cached_tokens` |
| Flash 4 | `deepseek-flash` | 1676 ms | 23445 | 23296 | 149 | `prompt_tokens_details.cached_tokens` |

## 结论

1. 该入口的 `deepseek-flash` 会返回 `prompt_tokens_details.cached_tokens`，稳定前缀在第二轮可以命中约 99.4%。
2. 切换到 Terra 后再切回 Flash，Flash 仍保持相同的缓存命中量。因此网关不应把模型切换视为“旧模型缓存必然清空”，而应把它视为“新模型需要建立自己的缓存；旧模型缓存可能保留”。
3. Terra 的兼容层没有返回缓存字段，无法证明命中或未命中。网关必须将此类结果标为 `unknown`，成本估算按 miss 保守计算。
4. 本次只验证缓存行为，不验证模型质量，也不能推导供应商缓存的长期 TTL。需要在不同时间间隔和更大样本下继续复测。
