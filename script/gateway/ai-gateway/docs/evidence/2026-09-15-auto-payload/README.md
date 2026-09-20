# Auto 协议 payload GPU 回归（2026-09-15）

本次只验证本地协议适配 seam，运行在 `qiyuan-gpu` 临时目录 `/tmp/auto-payload-verify-20260915.sNSK3L`，上游仍为 mock provider，没有调用东京、美西业务模型。

- Chat Completions、Responses、Anthropic Messages 均能从同一份规范化请求生成对应 envelope。
- 模型、stream 和 Auto 生成的 reasoning 参数进入 payload；客户端 reasoning 没有可透传入口。
- Responses 使用嵌套 `reasoning.effort`，兼容 Chat/Anthropic 使用适配器声明的 `reasoning_effort`。
- 原始内容片段和工具 schema 保留，图片字段不会在归一化后静默丢失。
- `verify-on-linux.sh`、`go vet`、`go test -race` 和静态构建全部通过；race JSON 记录中 71 个测试/子测试通过、0 失败。

证据文件：

- [全量测试与构建日志](verify.log)
- [race 逐测试记录](test-race.jsonl)
- [GPU 格式化源码 SHA-256](verified-go-sha256.json)

这仍不是供应商真实网络请求验证。下一步接入前必须为每个真实供应商补充鉴权、超时、错误响应、SSE/WebSocket 生命周期和响应 envelope 对账测试。
