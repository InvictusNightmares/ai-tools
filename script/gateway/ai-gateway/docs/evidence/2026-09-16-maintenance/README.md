# 2026-09-16 项目合并维护验证

本轮仅在本地进行。将 Auto、Guard、部署、工具、总计划和历史证据统一至 `script/gateway/ai-gateway`，单一 Go module 为 `local/ai-gateway`，运行时仍为 Auto、Guard API 与独立 vLLM。

迁移前两模块 `go test ./...` 均通过。首次沙箱测试因禁止本机 httptest 监听失败；获得本机临时监听权限后通过，没有用此错误判断业务回归。

第一次职责拆分后，Go AST比较确认 Auto394个、Guard104个非import声明不变；合并Go module后[498个非import声明再次对比](declaration-comparison.json)完全相同，包含函数、类型、常量、规则和测试；仅目录/import改变。固定题集与原有Go测试逻辑保留，没有为适配重构降低断言。

统一回归于2026-09-16 14:03（北京时间）通过：[摘要](summary.json)、[最终Go race结果](go-race.jsonl)、[Python结果](python-tests.log)、[源码清单](source-manifest.json)。Auto303、Guard31、Guard模型客户端2项，共336项含子测试；vet通过，五个Linux amd64程序静态构建通过，Python8项通过。未运行真实供应商请求、Docker部署或任何SSH命令；此前GPU/r4证据仍只适用于其原版本。

首次统一验证在vet发现历史证据 `probe_test.go` 被Go自动发现为测试包；它是旧阶段嵌入包的探针，不能独立编译。改名为 `.go.txt` 保持内容不变，将历史资料与可执行测试分开，再执行完整回归。

Markdown本地文件链接检查无断链，三份YAML可解析，联合部署tmpfs确认为一个完整参数字符串，Guard Docker构建上下文及Dockerfile路径有效。运行环境没有Docker，因此没有把YAML解析写成 `docker compose config` 或容器运行验证。未进行本轮Linux容器运行或GPU验收。

源码清单以统一项目为根，覆盖Go代码/冻结题集、配置、工具、部署和根维护文件，不能与旧99文件清单混用。验证完成后只更新文档与证据的结果/哈希；既有Go和脚本没有再变更。

## 2026-09-16 14:10 文档补齐

本轮仅修正文档，补具体迁移/部署脚本记录、统一module命令和本地/旧GPU/拟部署状态。此前[源码清单](source-manifest.json)保留原样，作为14:03回归及14:04文档快照；本轮README变更不回写旧哈希。本轮变动文件、当前文档哈希和代码/脚本未变核对见[补录核对](documentation-followup.json)。此前测试时间与真实上游结果不改写。
