# 异常记录设计

本目录保留异常记录功能的设计文档、[构建与升级技术文档](技术文档.md)、[source/](source/) 中的 54 个相关源码文件、[完整补丁](policy-log.patch)、[上游版本信息](upstream.json)及 [许可证](LICENSE)。源码以 Sub2API 基线 `aa236488351eb71e120fc2b6fb32e36b0374c918` 为基础，包含采集、存储、管理接口、页面、接入改动、保留定制功能的升级入口及相关测试。[upgrade/](upgrade/) 保存自动构建、分发和首次接入脚本。

`source/` 按原项目路径保存功能相关文件，构建前需按技术文档拉取指定版本的官方源码并应用补丁。

## 目标与范围

当上游返回明确的安全政策或拒绝信号时，保存对应请求正文和归属信息，供管理员按 Key、用户、模型和时间复核。直接使用转发过程中可见的上游信号，无需审计接口或审计模型。

美西和东京各自保存、查询本机记录。管理员通过左侧菜单 **异常记录** 进入 `/admin/policy-requests`，该入口独立于风控开关。菜单使用手写的 [文档与感叹号 SVG 图标](source/frontend/src/assets/icons/exception-records.svg)，颜色随菜单状态变化。

普通成功请求和普通错误不触发正文留存；本功能不增加自动通知或封禁规则，原有 cyber 处理逻辑保持独立。

## 触发规则

| 归一化信号 | 必须满足的上游条件 |
| --- | --- |
| `cyber_policy` | `error.code` / `error.type` 精确命中，兼容既有 cyber 标记 |
| `content_policy` | `error.code` / `error.type` 精确命中 |
| `content_policy_violation` | `error.code` / `error.type` 精确命中 |
| `invalid_prompt` | 上游提示同时包含 `flagged` 和 `violating our usage policy` |
| `content_filter` | 上游错误码、Responses 的 `incomplete_details.reason` 或 Chat 的 `finish_reason` 命中 |
| `structured_refusal` | 非空的结构化 refusal 字段、内容项或 refusal 事件 |

仅解析上游结构化字段，不扫描提问、工具参数或普通回答中的关键词。HTTP 200 内的 SSE 拒绝也可触发留存。

以下情况单独出现时不保存正文：

- 限流、额度不足、认证或权限错误、地区限制、WAF 拦截。
- 服务端错误、超时、EOF、连接中断等传输故障。
- 普通 `invalid_prompt`、参数错误、上下文超长。
- 空输出、缺少用量等推断信号，包括 `openai_silent_refusal`。
- 通用 `policy_violation` 或 WebSocket 1008；这些也可能来自本地 Fast / service_tier 限制。

## 捕获与归属

处理流程：接收请求并保留本次转发所需正文 → 观察上游响应 → 确认安全信号并关联请求 → 异步写入压缩日志 → 管理后台读取元数据和正文。

覆盖 OpenAI Responses、Chat Completions、Messages 兼容转发、Images，以及 WebSocket 转发。每次上游尝试或每个 WebSocket turn 记录首个明确证据；重试可能产生多条不同尝试记录，可通过请求标识关联。

WebSocket 必须关联到具体 turn。连接中断后，仅在已有明确拒绝且只剩一个可归属请求时保留正文；存在多个候选请求则跳过。

记录包含以下信息：

| 类别 | 字段 |
| --- | --- |
| 时间与请求关联 | `recorded_at`、`request_id`、`client_request_id`、`upstream_request_id`、`upstream_response_id` |
| Key 与用户归属 | `user_id`、`api_key_id`、`api_key_name`、`group_id`、`group_name` |
| 转发信息 | `account_id`、`provider`、`endpoint`、`protocol`、`model`、`stage` |
| 触发证据 | `error_code`、`error_type`、`signal_path`、固定描述的 `reason`、`upstream_status` |
| 请求正文 | `body_bytes`、`body_sha256`、`body_encoding`、`body` |

Key 名称使用捕获时快照；`user_id` 表示所属后台账户。共享 Key 无法进一步识别实际操作者。认证请求头、API Key 密钥和 OAuth 凭证不作为独立字段采集；用户主动写入正文的内容会随正文留存。

`body_bytes` 和 `body_sha256` 按收到的原始字节计算。JSON 正文经过序列化，可能压缩空白或转义 HTML 字符，因此下载字节不保证与原始请求逐字节相同。非 JSON 正文以 base64 存储，下载时还原原始字节。查询侧提供的 `stored_body_bytes` 表示实际可下载内容长度。

## 存储与资源控制

配置文件：`/opt/sub2api-deploy/data/policy-request-log.json`。

```json
{
  "enabled": true,
  "retention_days": 30,
  "max_disk_mb": 1024
}
```

日志目录为 `/opt/sub2api-deploy/data/policy-requests/`，对应容器内 `/app/data/policy-requests/`，可由数据目录配置调整。

| 项目 | 规则 |
| --- | --- |
| 日志格式 | `requests-*.jsonl.gz`；每条记录为一个完整 gzip 成员，成员串联组成分段文件 |
| 分段 | 按小时或压缩后达到 128 MiB 切换 |
| 保留 | 默认 30 天、每端最多 1024 MiB，任一上限触发即清理旧分段 |
| 写入队列 | 最多 256 条，正文和元数据合计最多 64 MiB |
| 磁盘余量 | 至少预留 2 GiB |
| 权限 | 目录 `700`、文件 `600` |
| 异常处理 | 队列满、磁盘不足或写入失败时丢弃记录并计数，API 转发继续 |

`status.json` 提供 `written`、`dropped`、`write_errors`、`queued_bytes`、`pruned_files`、`pruned_bytes` 和更新时间。计数从当前进程启动时开始累计。清理仅针对本目录识别出的日志分段。

上游观察器对单个 JSON 响应或单行 SSE 事件最多保留 8 MiB 内存；超限内容无法保证识别，后续正常大小的 SSE 事件仍继续解析。未触发留存的正文没有磁盘暂存。

## 管理接口与读取

使用既有管理员认证组，并复核管理员角色；响应设置 `Cache-Control: no-store` 和 `X-Content-Type-Options: nosniff`。

| 接口 | 行为 |
| --- | --- |
| `GET /api/v1/admin/policy-requests` | 分页返回元数据、索引状态和写入状态，不返回正文 |
| `GET /api/v1/admin/policy-requests/:id` | 返回记录信息及最多 256 KiB 的正文预览，标记是否截断 |
| `GET /api/v1/admin/policy-requests/:id/body` | 以附件流式下载完整留存正文 |

时间筛选采用开始包含、结束不含的区间；Key 支持名称包含匹配或 ID 精确匹配，模型支持包含匹配，触发类型精确匹配。记录按时间倒序排列。

读取侧直接使用压缩日志，不新增数据库表或外部服务。索引只缓存元数据，按 gzip 成员偏移增量扫描，最多保留最新 50,000 条；达到上限后继续推进扫描并淘汰旧索引，日志本身仍按保留规则清理。

每次列表扫描预算为 2 秒或 256 MiB，单个成员处理可能超过扫描时间预算，整体受请求期限约束。扫描未完成、索引达到上限或存在不可读取分段时，接口与页面明确提示。尚未写完的成员在后续请求中重试。

文件访问限制在日志目录内，校验文件名及身份，拒绝符号链接和非普通文件。记录 ID 根据分段与成员位置生成；详情和下载只接受当前索引中的 ID，记录过期或未入索引时返回 404。

同一时刻最多执行一个文件读取任务，包括下载全程；并发读取返回忙碌提示。正文以受限流式方式读取，下载发送已校验的 `Content-Length`，并设置 30 秒写入期限，避免中断内容被当作完整文件。

详情读取和下载接入现有管理员操作日志，只记录访问行为，不复制请求正文。

## 后台交互

页面提供时间范围、Key、模型和触发类型筛选，时间明确使用浏览器本地时区，每页 20 条。

列表展示记录时间、Key 名称及 ID、所属用户 ID、分组、模型、上游账号、协议和触发类型，并显示保留规则及写入、丢弃、错误计数。

详情弹窗展示归属与触发信息、正文预览和完整下载按钮。正文按转义后的纯文本渲染，完整有效的 JSON 可格式化展示；截断内容明确标记。页面支持加载、空结果、读取失败、忙碌及索引未完成状态，筛选变化或关闭详情时取消旧请求，避免显示过期结果。

## 判断边界

- 命中规则只表示上游返回了安全政策或拒绝信号，需要结合正文与上下文复核，不能直接认定某人违规。
- 没有当场可见信号、仅事后收到警告邮件的请求无法通过本方案补录；历史未保存正文也无法恢复。
- 队列或磁盘限制、响应解析上限、WebSocket 归属不明确均可能导致遗漏；状态计数和页面提示用于呈现已知限制。
- 两端独立查询，后台索引上限与日志保留上限分别生效。
