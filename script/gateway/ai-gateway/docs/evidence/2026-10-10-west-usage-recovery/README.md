# 美西独立用量恢复与旧任务退役

2026-10-10，用户授权修复美西用量同步、移除旧构建的美西目标并清理旧采集自启动；东京 4000 夜间策略和林枝 Key 9 的全天例外保持。

## 数据恢复

- 原因：`gateway-usage@us` 仍查询已经删除的旧 PostgreSQL 容器，新官方实例未包含独立 `gateway_usage` 库。该任务与每日客户邮件统计是两个独立任务。
- 数据源：GPU 原有 SQLite 元数据账本，共 39,399 条，其中 39,392 条 region=us；5 条 gpu-local-us 和 2 条 synthetic 夹具保留本地，不向美西导出。
- 恢复：新库创建在 `sub2api-next-postgres` 内，业务库 `sub2api_next` 只读 Key 映射。保留历史 Key 映射，不复活已删除 Key。暂停该区域定时导出，使用原导出锁和 SQLite backup API 留恢复点；仅首轮重置该区域的导出标记。
- 首轮普通恢复导出 10,000 条；其余 29,392 条通过同一 `export_batch` 的有界批次恢复，压缩 SSH 传输。未更改常规分钟任务每轮最多 10,000 条的限制。
- 对账：远端 39,392 个事件 ID 与本地集合一致；全部 110 个每日桶逐字段一致，待传 0，异区域事件 0。原始本地 payload 校验值与恢复前快照一致。

| Token 计数 | 恢复值 |
| --- | ---: |
| input_tokens | 249158099 |
| cache_hit_tokens | 13270385 |
| cache_miss_tokens | 229032053 |
| output_tokens | 290741 |

各列保留原始账本含义，未重新估算费用或修改客户余额、GPT 周限额。

## 部署与保护范围

- `/data/ai-gateway/operations/releases/usage-sync-us-20261010-r1` 为 root 所有的只读版本包，仅 `gateway-usage@us.service` 的实例 drop-in 使用它。
- API 的 `current-release.json`、原 v31 制品、共享 wrapper 和 Go 二进制保持。新启动器校验清单及来源 release，升级 API 后必须移除或重验该覆盖，详见[维护指南](../../维护指南.md)。
- GPU builder `NODES` 仅含东京；原定时器保留。本次只核验目标变更，未重新验证或激活新的东京定制 Sub2API 包。
- 两地 live-capture、collector、旧 semantic-preview 及 analysis/token-sync 两个 timer，共 8 项 disabled/inactive；两个旧采集器已停止。实际开机链接仅保留独立 review-dashboard。历史受限数据和现有 candidate 预览保留，未回放正文或恢复失效凭据。
- 操作前后比较：两地正式 Sub2API、GPU 业务容器的 ID、StartedAt、RestartCount 相同。东京 Nginx 与林枝放行文件、美西 Nginx 与放行文件、GPU 两入口 Nginx 配置、日报 cron、共享 wrapper 的 SHA 不变。
- 不处理 4003 代理、旧历史程序包及历史分析数据的退役；未改变 Auto/Guard 业务路由或缓存。

## 验证

- GPU 隔离验证：Go vet、738 项 race 测试（含子测试）、六个 Linux 构建、46 项 Python 测试通过。源码归档 SHA256：`3170d715bfdc110f90045c600704f2c6c378235b66b953bcf15ca53233ab98bd`；验证源码 manifest SHA：`2c59e09794ffe741205968bc746a6ab265a460e99649ee1e27fe3cc27d8a0fda`。
- policy builder 14 项测试通过。新增回归在原 exporter 上复现美西目标错误、无法完整回补的问题；包校验覆盖 API 升级、文件篡改、额外文件、错误区域及原样依赖变化的拒绝。
- 美西 PostgreSQL 会话临时表验证 COPY、同批两次提交、失败用量和每日聚合，结果通过；业务和独立统计正式表未混入测试夹具。
- macOS 全量 Python 首次运行因沙箱禁止临时 HTTP 监听而失败；GPU Linux 全量通过。SSH 中断时先检查实际执行状态再重试；collector 停止后的 failed 状态在确认 MainPID=0 后清除。
- 11:13:51 首次手动运行成功；11:14:52、11:16:29 两次真正的 timer 触发分别在 11:15:25、11:16:58 完成（北京时间），均 completed、remaining=0、exported=0。4000/4001 健康及登录均 200，无 Key 请求均 401，两代理 `nginx -t` 通过。完整脱敏结果见 [verification.json](verification.json)。本次未调用真实模型。
- 两轮后再次查询独立库仍为 39,392 条、异区域事件 0，`usage_export_pending` 告警已清除。11:19 完成清理：本次 GPU SQLite 回退副本（含读取时产生的 WAL/SHM）、旧 builder 临时副本及隔离验证目录已按精确路径删除；保留运行中的修复包与服务器脱敏摘要 `/data/ai-gateway/operations/usage-repair-20261010.json`，美西未生成本次业务库备份。
