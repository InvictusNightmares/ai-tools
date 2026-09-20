# Guard 部署代码

这个目录对应 GPU 服务器上的 Guard 部署面。2026-09-14部署时服务器无法访问 `gcr.io`，因此 Dockerfile 选用当时已缓存的 `golang:1.27.1-bookworm` 和 `ubuntu:resolute-20260108` 基础镜像，并以非 root 用户运行 API：

- `guard/model/client.go`：Go 检查服务调用 Qwen3Guard vLLM 的 OpenAI 兼容客户端。
- `cmd/preflight-api`：提供 `/v1/preflight`、`/healthz`、`/readyz` 和 `/metrics`。
- `Dockerfile`：构建 Go Preflight API 镜像。
- `docker-compose.yaml`：GPU1 启动 Qwen3Guard vLLM，8011 启动 Preflight API。

Compose 的构建上下文是 `ai-gateway` 项目根目录，不能只在本目录单独执行 Docker build。正式部署前需要先准备模型权重目录，并按总计划验证私网 ACL、`/readyz`、压测和回滚。

客户端按 Qwen3Guard 的实际输出解析两行标签：`Safety: Safe|Unsafe|Controversial` 和 `Categories: ...`。其中 `Safe` 映射为放行，`Unsafe` 映射为高风险拦截，`Controversial` 映射为中风险并由 Go 的 strict 策略拦截；格式错误会触发 fail-closed。

与新版Auto联调时必须使用包含 `credential-redaction-v1` 正文契约且与发布清单匹配的Guard：先在独立端口构建并验证 Guard `/v1/preflight` 的摘要/脱敏字段，再启动对应 Auto。`/readyz` 只代表模型可达，不证明接口版本或脱敏验收通过。4004/4005当前使用独立8013/8014和r11规则，实际二进制版本见总计划。原8011不在本次更新范围；r4隔离结果仅为历史证据。

当前构建命令是在统一项目根目录执行 `CGO_ENABLED=0 go build -o bin/preflight-api ./cmd/preflight-api`，Docker使用同一个项目根上下文。原两模块构建路径只用于解释历史记录，不再作为执行命令。2026-09-16 11:59的临时端口清理与生产健康记录属于历史快照；后续4004/4005部署另见总计划和CHANGELOG。

项目根目录可执行 `docker compose -f deploy/guard/docker-compose.yaml config --quiet` 检查语法；构建使用整个项目上下文。此命令只校验配置，不执行服务器构建或重启。
