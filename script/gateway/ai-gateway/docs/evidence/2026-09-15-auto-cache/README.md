# Auto 缓存管线 GPU 回归（2026-09-15）

环境为 `qiyuan-gpu` 的临时目录 `/tmp/auto-cache-fixed-20260915.y6g6aG`，使用 `golang:1.27.1-bookworm`。上游为测试替身，没有调用东京、美西业务模型，也没有对真实供应商 Prompt Cache 命中率作结论。

上传包的 31 个普通文件逐文件 SHA-256 与本地一致。原有测试通过，但补充真实边界断言后复现了缓存记账与隔离问题，修复后全量测试、静态构建、`go vet` 和 race 检测全部通过。

## 验证结果

| 项目 | 结果 |
| --- | --- |
| `./verify-on-linux.sh` | 退出码 0，全量测试和静态构建通过 |
| `go vet ./...` | 退出码 0 |
| `go test -race -count=1 -json ./...` | 38 个顶层测试，含子用例共 66 个通过，0 失败 |
| 源码同步 | 29 份 Go 文件与服务器格式化版本一致 |
| Guard 状态 | 10:18（UTC+8）只读检查：两个容器运行中，`/readyz` 返回 ready |

## 缓存记账对比

测试发送两次相同请求，mock 上游实际调用一次，第二次命中响应缓存。下表的修复后数值由回归测试的完整断言确认；这是固定测试样本，不是生产成本估算。

| 统计项 | 修复前 | 修复后 |
| --- | ---: | ---: |
| 请求数 | 2 | 2 |
| 上游 attempt | 1 | 1 |
| 输入 token | 20 | 10 |
| 输出 token | 4 | 2 |
| 供应商 Prompt Cache hit token | 12 | 6 |
| 供应商 Prompt Cache miss token | 8 | 4 |
| 单独记录响应缓存命中 | 未提供 | 1 |

同时验证了 HTTP 503/429/302、传输错误和超大响应不缓存；Guard block/unavailable/无效 verdict 不进入业务链路；协议/模型/reasoning/区域/Key/版本隔离；缺少缓存身份时跳过缓存；TTL 过期；缓存响应体和嵌套 usage 不共享可变对象；32 个并发 worker 读写缓存无 race。

## 原始证据

- [机器可读摘要](summary.json)
- [修复前失败日志](cache-regression-before.log)
- [修复后全量测试与构建日志](verify.log)
- [race 检测的逐测试 JSON 记录](test-race.jsonl)
- [已验收 Go 源码 SHA-256](verified-go-sha256.json)

当前路由状态仍由单会话 Pipeline 持有；内存缓存与 usage 不持久化。真实协议完整请求转发、生产鉴权/会话隔离、SSE/WebSocket 转发、审计 sink 和数据库尚未接入。
