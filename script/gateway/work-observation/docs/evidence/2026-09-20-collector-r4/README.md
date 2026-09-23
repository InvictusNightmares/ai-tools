# GPU v5 bounded Auto 离线复核证据

日期：2026-09-20。范围是已经接入正式 4000/4001 的采集数据在私有 Guard/Auto 预览端点上的离线复核；不改变正式网关路由，也不代表训练或灰度发布结论。

- `semantic.py` v5 SHA-256：`5dad38212846626768a80fd38faff6f6a69bb3117fd5262369f785a5e0d657cf`；远端 release 为 `/opt/work-observation/releases/observation-review-20260920-v5`。分析 systemd 单元已备份后切换到该 release，dashboard 仍使用已验证的 v4 静态页面代码。
- Auto 回放只取请求上下文，保留 system/developer 和最近消息；单条消息 48 KiB、消息 320 KiB、工具 48 KiB、结构化输出 32 KiB、最终回放 384 KiB。超出范围写入 `metadata.replay=bounded_request_context` 和截断标记；Guard 的完整归一化回放路径不变。
- v5 手动批次 `20260920-093946` 处理 20 条，终态 13 条、暂不可用 7 条；随后定时批次 `20260920-094500`、`20260920-095000`、`20260920-095500` 分别处理 20 条，终态 10/13/11 条。不可用任务仍留在 pending，未伪造模型选择。
- 复核页快照（2026-09-20 09:55 UTC）：`total_jobs=10136`、`pending_jobs=9989`、`semantic_reviews_total=251`、`auto_with_model=70`、`auto_blocked=78`、`auto_unavailable=103`。该快照随采集增长，不是质量或训练集结论。
- 私有端点 `8013/8014/8095/8096` 健康均为 HTTP 200；正式 `4000/4001` 健康均为 HTTP 200，Nginx 仍分别指向 `127.0.0.1:18400/18401`。18400/18401 在各自 collector 网络命名空间内探针均为 HTTP 200。
- 采集状态复核：Tokyo/US `capture_enabled=true`，`dropped=0`、`write_errors=0`、`loss_persist_errors=0`、`truncated=0`、`unavailable_bypassed_requests=0`；历史 `projection_errors` 计数为 Tokyo 11、US 5，未见本轮新增。统一采集卷可用空间约 186.3 GB。
- 本证据文件未保存认证值、请求正文、回复正文或工具参数；受限采集源仍按既定生命周期保存正文，证据只记录版本、状态、计数和路径。
