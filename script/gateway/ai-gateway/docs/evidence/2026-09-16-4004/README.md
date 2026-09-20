# 2026-09-16 东京4004部署与验证

4004在北京时间14:33:34启动；14:40完成17/17真实检查，14:41完成Guard不可用演练，14:43完成恢复请求。它是正式替换候选入口，尚未满足全部4000/4001切换条件。

- [本地验证](local-summary.json)：357项Go（含子测试）、Python8项、vet及五个Linux构建；[源码清单](local-source-manifest.json)冻结117个文件。
- [部署状态](deployment-state.json)：GPU117文件哈希匹配，Linux同357项通过；新增Auto8093、Guard8013与Nginx4004均运行，私有文件只有内部cache-secret，没有用户Key。
- [归档信息](package.json)：源码包SHA及大小。运行目录`/data/ai-gateway/acceptance-tokyo`；4004绑定VPN私网IP，后端只监听loopback。
- [入口检查](entrypoint-checks.json)：网页/设置、个人用量/计费、缺失/无效/冲突认证、两种Key头、模型别名、中文Chat、英文Responses SSE、混合语言Claude Messages SSE、计数和Guard凭据使用拦截，17/17。
- [Guard故障](guard-unavailable.json)：仅停新增Guard；4004返回503、写preflight_unavailable、无分类/业务usage，随后恢复ready。[恢复请求](guard-recovered-checks.json)真实200。
- [关联日志](correlated-logs.json)：19条路由事件、9条usage、入口状态按本次request_id关联；故障请求在Nginx为503。只保留白名单字段，不保存正文或Key。
- [原服务对照](protected-comparison.json)：4000/4001/4003、原Guard8011、vLLM8001共5个服务的容器ID/镜像/启动时间及原Nginx配置SHA均未变；只有新增Guard参与故障演练。

真实链路只使用一把用户授权的东京Key。两把不同Key的缓存/身份隔离、撤销/额度边界来自本地和Linux模拟回归，不冒充多人实流量测试。此次业务均命中Deepseek Flash，检查入口兼容和安全顺序，不代表重新完成五档选型、最高effort或业务产物质量验收；此前对应版本的阶梯测试保留原证据。

浏览器管理操作、完整Codex/Claude工具流程、图片/视频/Gemini、Responses WebSocket/compact、超长输入、多实例状态和自动升级回退继续列为待办。区域模式整段业务响应缓存关闭，Prompt Cache保留。业务日志按HMAC隔离标识记账，不能当作Sub2API数字Key ID。

14:45后仅补文档；冻结源码清单和测试时间保持原值，文档差异另见documentation-check.json。
