# 东京4004与美西4005独立入口部署

两区域来自同一源码项目，冻结制品按区域验证后推广；各自独立Nginx、Auto、Guard API、内部密钥、状态与日志，共用既有Qwen3Guard8001。新增/更新边界不包含原4000/4001/4003、Guard8011或vLLM。

| 区域 | VPN入口 | Auto / Guard | Sub2API前置 | 部署目录 |
| --- | --- | --- | --- | --- |
| 东京 | 192.168.64.16:4004 | 8093 / 8013 | 106.14.254.110:9881 | /data/ai-gateway/acceptance-tokyo |
| 美西 | 192.168.64.16:4005 | 8094 / 8014 | 106.14.254.110:9880 | /data/ai-gateway/acceptance-us |

当前两地release、Auto/Guard各自二进制版本及区域验收结果以总计划和运行目录current-release.json为准；Guard规则修复仅重建Guard，复用未变化的Auto。两地上游既有23:00–06:30停用策略保持。当前验收进度与制品哈希见总计划及CHANGELOG。

## 认证与缓存

使用每位用户自己对应区域的Sub2API Key，支持`Authorization: Bearer ...`和Claude Code的`X-API-Key`。没有网关账号、Key白名单或复制的额度规则；每次调用对应区域`/v1/models`复用Sub2API认证/余额/额度检查。只有通过校验才进入Guard、分类缓存和路由；无效Key返回401，区域拒绝返回403，限流429，认证接口异常503，均写入不含凭据的审计。冲突的认证头拒绝，重定向不跟随。

Sub2API的用户Key接口不返回数据库Key ID。网关`api_key_id`字段在regional模式使用`key-hmac-v1:`加HMAC，含区域且不存原Key；这是**网关隔离标识，不是Sub2API数字ID**。已有pilot测试程序仍用显式数字ID，不能混为一谈。各区域自身的实际模型用量继续归属原Key；网关按HMAC记录分类/业务用量，通过各区域受限SSH在当地读取Key并计算HMAC，数字ID映射进入独立gateway_usage库；分类/业务/动作审核及安全模型分用途统计，逐attempt对账使用上游独立X-Client-Request-ID。历史没有该字段的记录不补造关联。

与现有入口`proxy_cache off`一致，区域模式关闭整段业务响应缓存，每次业务请求均经过Sub2API最终模型权限/计费检查；供应商Prompt Cache不受影响，分类缓存仍按Key/区域/会话隔离。不得用`/v1/usage`替换认证检查，该接口跳过部分计费限制。网关不承诺额度预留或跨请求原子扣减，最终以Sub2API为准。

## 准备与启动

`prepare.py`校验统一项目源码清单、镜像digest、端口，按`--region tokyo|us`创建对应的全新目录，不覆盖目录或启动服务。参数为`--verified-root`、`--manifest`、`--region tokyo --port 4004`或`--region us --port 4005`、`--runtime-image`、`--nginx-image`，绑定地址默认`192.168.64.16`。不需要用户Key文件；仅生成内部`secrets/cache-secret`，UID10001、0400，必须持久保存。更换此密钥会改变隔离标识，使旧分类缓存和会话状态失效，历史用量需分段对账。

运行生成目录中的`sh deploy.sh`，校验Compose、静态构建、检查Nginx，后端ready后开放入口；部署失败会停止本次新增服务，独立日志保留。运行身份UID10001，根文件系统只读，日志/状态独立挂载，容器自动重启。`regional`启动拒绝固定Key/ID、分类或业务共享token，以及跨区域的上游地址。

## 客户端与日志

OpenAI兼容客户端Base URL：东京`http://192.168.64.16:4004/v1`，美西`http://192.168.64.16:4005/v1`，模型`auto`；Claude Code Base URL去掉`/v1`。使用对应区域已有且具备所需模型权限的Key，网关不扩大Key权限、不更改分组。Messages兼容已有Claude模型名并进入Auto策略。浏览器直接打开`/v1/models`不带Key会返回401；`/healthz`仅检查Auto进程。

保留Sub2API网页、账号/Key管理、公开设置、用量和计费查询。models、Chat、Responses、Messages、count_tokens经过Auto+Guard；兼容`/models`、`/responses`、`/chat/completions`与`/backend-api/codex/`别名，不允许别名绕过Guard。不开放metrics或路由预览；继承原认证头、3600秒超时、无缓冲/无自动重试，入口写入可信客户端IP，供区域认证/分类/业务使用。

**现有能力与边界**：Nginx保留200m管理请求限制，Auto原生请求64MiB，Guard检查附件元数据和普通文本；视频/Gemini不在当前能力内；Responses WebSocket和原生v2压缩两地已验收，旧compact和v2压缩均已完成两地原生客户端复验。图片/PDF/普通文件和Flare/Sunburst生成编辑已有两地内容证据；音频按用户决定暂不支持。两地四端高级工具/压缩/取消/子agent已补齐，原生动作审核允许、模型真实拒绝及账单均已闭环，见总计划。4004启动不代表这些能力已与4000/4001完全等价，不能直接切流。常规模型入口为auto，另列原生专用codex-auto-review；Claude名称作为Auto兼容入口，实际业务候选不公开为固定选择。

服务器日志：`logs/nginx/access.jsonl`（状态/时延/request_id）、`logs/auto/route-audit.jsonl`（鉴权/Guard/分类/路由及异常）、`logs/auto/usage.jsonl`（分类/业务分账）、`logs/guard/guard-security.jsonl`（安全决策，受限数据）。另有guard/security-usage.jsonl逐Qwen分块用量及security-decisions.jsonl检查决策。目录0700、文件0600，仅授权运维可读；不记录认证头或原Key。业务JSONL达到32MiB按稳定锁轮转，进程每次追加重新打开；默认只归档不删除。当前保留期不设置删除期限；需要自动删除时由用户另行指定。

## 升级、回退与运维

首次创建使用prepare/deploy；后续统一使用不可变制品和`python3 -B tools/deploy-release.py upgrade|rollback|status --region tokyo|us --release /data/ai-gateway/releases/<release_id>`。它校验制品、兼容状态和Guard契约，备份配置、排空请求，按实际变化重建组件；失败恢复旧配置/指针，不覆盖新的用户状态。仅Guard回退时先解除未重启Auto的drain状态，再检查就绪；入口此时仍关闭。回退失败保持入口关闭并报告失败，不能宣称已恢复。

v10.1还将Nginx模板纳入升级/回退，先确认当前模板无漂移，限定区域端口与VPN绑定；两地已明确拒绝`/_gateway/`和`/logs/`。内部Auto、区域Guard和vLLM仅监听回环，公开入口不开放metrics。

`deployment/install-operations.py --region <region>`验证当前制品后安装`gateway-ops@<region>.timer`和`gateway-usage@<region>.timer`。健康与日志维护每分钟独立运行；用量导出单独调度、加锁和断点重放，区域网络/数据库故障不能拖住Guard检查。状态/告警在`ops/status.json`、`ops/alerts.json`、`ops/usage-status.json`，无默认外部消息接收人。导出180秒没有成功或仍有待传事件时告警；重复导出按event_id去重。

当前两地入口已采用Basic/认证模板、Kotlin代码引用误报及SSE工具绑定修复。OpenCode、Hermes、Claude Code、Codex CLI已各自完成小源退出登录历史任务，四份最终HAP构建及行为检查通过；Hermes使用隔离官方原生CLI，既有CTYun连通性没有因此修复。首版问题、原生评审修正和各轮部署版本见[客户端证据](../../docs/evidence/2026-09-16-client-compatibility/README.md)。OpenCode早期语义误判和旧Codex终止审计的失败记录保留；当前两地高级矩阵、取消/恢复和审核已完成对应验收。正式4000/4001切流由用户排除，本次不执行。

4004完整输入检查配置为`PREFLIGHT_REQUEST_TIMEOUT=30s`和`AUTO_GUARD_TIMEOUT_SECONDS=35`，队列仍1秒/128。该调整来自小源真实长上下文503，不改变其他入口默认值，完整输入r11已有30分钟/长输入负载证据，范围和性能边界见总计划。当前版本和源码哈希以总计划及最新证据为准。

新版转发保留客户端原User-Agent，覆盖区域鉴权、主分类/复核、计数、同步和SSE业务调用；缺失UA保持缺失，不冒充其他客户端。分类配置为Luna主分类、Sol独立复核；DeepSeek分类尚未达到95%门槛，继续离线优化。简单业务仍可选DeepSeek。
