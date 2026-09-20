# Auto 阶段 2：传输、持久化与共享缓存控制回归

验证时间：2026-09-15（服务器本地时间）

验证归档：`auto-gateway-stage6.tgz`

SHA-256：`460fa781bd2b7c2a8225b72c56525a91cbd4c18b4de5e569a408df92721b2508`

GPU 临时目录：`/tmp/auto-gateway-stage6/auto-gateway`

执行内容：

- Docker `golang:1.27.1-bookworm` 内执行 `gofmt`。
- `go test -v ./...`：通过。
- `go vet ./...`：通过。
- `go test -race -count=1 ./...`：通过。
- `CGO_ENABLED=0 go build -o auto-preview ./cmd/auto-preview`：通过。

覆盖内容包括 HTTP 上游鉴权和响应上限、Guard HTTP fail-closed 客户端、SSE relay、WebSocket 双向关闭边界、文件会话状态、0600 fsync usage/审计 spool、LRU 容量控制和同键并发 miss 合并。

本轮只在 GPU `/tmp` 临时目录运行，未启动 Auto 生产监听器，未修改 Guard 容器、东京、美西或业务数据库。服务器 tar 的 macOS provenance extended-header 提示不影响解压和哈希校验。
