# 阶段 D 固定顺序端到端回归

验证时间：2026-09-15 14:28（UTC+8）

验证归档：`auto-gateway-stage7.tgz`，SHA-256 `fcc3f7f9301dfae688e25332b5e8f28b6bc51b6792a9172182cb7a8b01d16940`。

`TestPhaseDOrderGuardThenAutoThenUpstream` 使用两个本地 HTTP 测试服务模拟 Guard 和 provider：

- `allow`：Guard 返回 allow，Auto 生成模型/推理参数并调用上游一次。
- `block`：返回 403，上游调用数保持不变。
- `unavailable`：Guard 返回 503，上游调用数保持不变。

同一归档在 qiyuan-gpu 的 Docker `golang:1.27.1-bookworm` 内通过 `gofmt`、`go test -v ./...`、`go vet ./...`、`go test -race -count=1 ./...` 和静态构建。

这只是阶段 D 的本地端到端顺序证明，尚未使用东京/美西真实测试 Key，也没有修改两地生产入口。
