# 独立采集 dev.9 性能回归

本目录记录 GPU `qiyuan-gpu` 隔离容器中的采集器优化回归。测试只使用合成回环上游，未连接4000/4001、8093/8094或Sub2API；临时容器在每次运行结束后清理。

- 完整场景：63组、8,820次转发、14,364条记录。
- HTTP/SSE/WS响应内容全部校验正确；采集计数无丢失、截断、投影错误或写入错误。
- 优化包含采集副本缓冲复用、完整WebSocket帧就地解掩码和DiskStore分段落盘，降低了大消息的平均采集开销。
- `bench_report.py` 的 `every_round_within_5_percent` 仍为 false：GPU共享负载下仍有若干单轮p95超过5%，所以本目录不能作为4000/4001接入许可。合并报告只用于观察趋势，不能覆盖单轮失败。

专项报告还保留了大WebSocket在较安静窗口的三轮结果；它的合并采集开销已低于5%，但正式验收仍要求完整场景连续满足门槛。

`semantic-preview-token-file-candidate.json` 记录了候选 Auto 的预览专用 semantic Key 文件方案：只有显式 route-preview 和 0600 文件时才允许使用，两地业务上游仍必须同源。`semantic-preview-candidate-deployed.json`记录了候选二进制在GPU隔离目录完成Go回归并切换8095/8096后的验证；这仍是预览部署，不能当成正式入口或员工样本分析。
