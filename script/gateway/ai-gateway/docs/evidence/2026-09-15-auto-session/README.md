# Auto 会话路由状态 GPU 回归（2026-09-15）

运行目录：`qiyuan-gpu:/tmp/auto-session-verify-20260915.fpy2vk`。验证使用 mock preflight 和 mock upstream，仅检查路由状态，不接东京、美西生产入口。

- `MemorySessionStateStore` 按 `PipelineMeta.SessionID` 保存状态，不保存 prompt、API Key 或凭据。
- 不同会话各自执行初始选择；同一会话的后续 turn 保持当前模型和升级冷却。
- 会话 TTL 到期后清除旧状态并重新选择，不会读取共享 `Gateway.State`。
- 32 个并发会话同时执行，race 检测无状态竞争。

GPU 临时目录的全量测试、静态构建、`go vet` 和 `go test -race -count=1 -json ./...` 均通过：74 个测试/子测试通过，0 失败。

证据文件：[全量测试日志](verify.log)、[race 记录](test-race.jsonl)、[格式化 Go 源码 SHA-256](verified-go-sha256.json)。

生产接入仍需把内存实现替换为可过期的共享/持久化存储，并以真实鉴权主体生成稳定的会话 ID。
