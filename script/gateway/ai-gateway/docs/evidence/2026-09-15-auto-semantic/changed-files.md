# 相对 stage12 的源码变更

当前归档包含 69 个文件：新增 17、修改 28、未变 24。按文件内容与 stage12 比较，忽略 macOS 扩展属性，不以 Git 跟踪状态或上一次编辑数计数。

主要变更包括三语语义分类/独立复核、分类缓存、五模型 effort 参数、结果日志与用量、完整协议 payload、Claude Code 入口/工具续接/token 计数、真实测试工具和试运行配置。

新版仅在本地，GPU 尚未同步。源码包不含编译程序、凭据、运行日志或状态。哈希与完整文件清单见 [source-manifest.json](source-manifest.json)。

| 文件 | 相对 stage12 |
| --- | --- |
| [README.md](../../../auto/README.md) | 修改 |
| [analyze-evaluation.py](../../../tools/analyze-evaluation.py) | 新增 |
| [auto_gateway_test.go](../../../auto/auto_gateway_test.go) | 修改 |
| [cache_coalescing_test.go](../../../auto/cache_coalescing_test.go) | 修改 |
| [classifier.go](../../../auto/classifier.go) | 修改 |
| [client_compatibility.go](../../../auto/client_compatibility.go) | 新增 |
| [client_compatibility_test.go](../../../auto/client_compatibility_test.go) | 新增 |
| [cmd/auto-server/main.go](../../../cmd/auto-server/main.go) | 修改 |
| [cmd/effort-probe/main.go](../../../cmd/effort-probe/main.go) | 新增 |
| [cmd/semantic-eval/main.go](../../../cmd/semantic-eval/main.go) | 新增 |
| [config.example.yaml](../../../config/auto.example.yaml) | 修改 |
| [effort_matrix_test.go](../../../auto/effort_matrix_test.go) | 新增 |
| [gateway.go](../../../auto/gateway.go) | 修改 |
| [http.go](../../../auto/http.go) | 修改 |
| [http_test.go](../../../auto/http_test.go) | 修改 |
| [models.go](../../../auto/models.go) | 修改 |
| [phase_d_integration_test.go](../../../auto/phase_d_integration_test.go) | 修改 |
| [pilot_auth.go](../../../auto/pilot_auth.go) | 新增 |
| [pipeline.go](../../../auto/pipeline.go) | 修改 |
| [pipeline_cache.go](../../../auto/pipeline_cache.go) | 修改 |
| [pipeline_observability.go](../../../auto/pipeline_observability.go) | 新增 |
| [preflight_http.go](../../../auto/preflight_http.go) | 修改 |
| [protocol.go](../../../auto/protocol.go) | 修改 |
| [provider_adapter.go](../../../auto/provider_adapter.go) | 修改 |
| [provider_payload.go](../../../auto/provider_payload.go) | 修改 |
| [provider_payload_test.go](../../../auto/provider_payload_test.go) | 修改 |
| [reasoning.go](../../../auto/reasoning.go) | 修改 |
| [response_validation.go](../../../auto/response_validation.go) | 新增 |
| [route_audit.go](../../../auto/route_audit.go) | 修改 |
| [route_state.go](../../../auto/route_state.go) | 修改 |
| [run-pilot.sh](../../../tools/run-pilot.sh) | 新增 |
| [semantic_cache.go](../../../auto/semantic_cache.go) | 新增 |
| [semantic_classifier.go](../../../auto/semantic_classifier.go) | 新增 |
| [semantic_classifier_test.go](../../../auto/semantic_classifier_test.go) | 新增 |
| [semantic_regression_test.go](../../../auto/semantic_regression_test.go) | 新增 |
| [stream_observation.go](../../../auto/stream_observation.go) | 新增 |
| [token_count.go](../../../auto/token_count.go) | 新增 |
| [token_count_test.go](../../../auto/token_count_test.go) | 新增 |
| [upstream_http.go](../../../auto/upstream_http.go) | 修改 |
| [upstream_http_test.go](../../../auto/upstream_http_test.go) | 修改 |
| [upstream_stream.go](../../../auto/upstream_stream.go) | 修改 |
| [usage.go](../../../auto/usage.go) | 修改 |
| [usage_daily.go](../../../auto/usage_daily.go) | 修改 |
| [verify-on-linux.sh](../../../verify-on-linux.sh) | 修改 |
| [websocket_relay_test.go](../../../auto/websocket_relay_test.go) | 修改 |
