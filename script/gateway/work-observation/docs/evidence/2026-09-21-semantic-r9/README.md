# GPU 语义复核 v9 证据

日期：2026-09-21。范围是正式 4000/4001 采集事件的离线 Guard/Auto 复核；本次只更新分析 worker，不改变正式网关、Sub2API、采集器或 4004/4005 路由。

- GPU release：`/opt/work-observation/releases/observation-review-20260921-v9`
- `semantic.py` SHA-256：`aa4cdc72b2e6777f9c0d244845402cd77386839f03e155b699f712ad32441e17`
- `rolling.py` SHA-256：`f6a0303ee85acbe683c3370e67f01b01a56d3622c76eb7e5618f86953fbebf6c`
- 配置：`max_jobs=80`、`max_workers=4`、`stage_reuse_ttl_seconds=3600`；v5、v6、v7、v8 release、systemd unit 和配置回退副本保留。
- 本地验证：78 项 Python 回归通过、1 项按环境跳过；`git diff --check` 通过。
- 运行批次：每 5 分钟最多处理 80 条；最近 01:30 UTC 批次处理 80 条，35 条完成、45 条暂不可用，队列约 9968 条。不可用任务保持 pending，不伪造模型选择。
- 阶段复用：一个真实待复核元数据样本的不写库诊断显示 `guard_reused=true`、`auto_reused=false`，只调用 Auto 失败阶段；批次复用计数仍在升级旧 v5 结果指纹，不能提前当作长期吞吐结论。
- 候选 Auto：8095/8096 健康探针 HTTP 200；离线审计累计约 2154 条 `classifier_unavailable`，其中 Guard 仍多为 HTTP 200，Auto 多为 HTTP 503。直连两地分类器的最小模型探针 HTTP 200，因此分类器输出兼容性/请求形状仍是未关闭问题，不能归因采集器或网络。
- 正式入口：Nginx 仍为 Tokyo `4000→127.0.0.1:18400`、US `4001→127.0.0.1:18401`；两地 `capture_enabled=true`，`dropped=0`、`truncated=0`、`write_errors=0`。历史 `projection_errors` 继续作为质量告警单独记录。

本证据不保存请求正文、回复正文、工具参数、Key 或其他凭据；正文仍只存在既定受限采集卷，分析库只保存元数据。
