# 部署验收记录

日期：2026-09-08，北京时间。以下是实际运行结果；飞书项另列，不能由容器健康代替。

| 项目 | 结果 |
|---|---|
| 官方镜像 | v2026.8.31 / 0.21.0；digest 与源码 revision 已核对 |
| 容器与隔离配置 | 应用 UID 10000，4 核 / 6 GiB；后台仅映射 Tailscale IPv4 的 9119，无管理 socket/SSH 私钥挂载 |
| 主模型 | 本人填写的 CPA Key；DeepSeek v4 Pro；Messages 流式回答与工具调用通过 |
| 备选模型 | Flash Vision、Sonnet、Opus、Gemini 3.8 Flash 均通过 Messages 简短回答测试 |
| 压缩调用 | Hermes 原生辅助调用成功；AnthropicAuxiliaryClient；模型 DeepSeek v4 Pro |
| 完整任务 | Python 计算 6×7，写文件、回读，最终 HERMES_E2E_OK；会话 20260908_110420_8959d7 |
| 搜索与浏览器 | 原生搜索、Bing 搜索、网页快照和截图通过；跨五分钟会话到期后重连通过，测试总时长 360 秒 |
| 持久化与 Cron | 重启后记忆、文件、会话和 Cron 保留；北京时间任务实际触发，延迟 59 秒，符合原生约 60 秒轮询 |
| Cron 模型 | 使用默认配置的真实 Agent Cron 输出 HERMES_CRON_MODEL_OK；已移除测试任务 |
| 原生审批引擎 | 批准一次、拒绝、超时、Cron 无人值守拒绝通过；未实际执行危险删除 |
| 备份 | 每天北京时间 04:30，保留七份；实际备份停止并恢复 Hermes 成功 |
| 恢复检查 | 归档文件恢复和六个 SQLite 完整性检查通过；缓存中的 241 个链接未在临时验证目录内创建，未做覆盖生产数据的完整回滚演练 |

首份一致性备份曾为 `/srv/agentbox/hermes/backups/hermes-20260908T030519Z.tar.gz`。所有本次备份及 `/srv/agentbox/hermes/workspace/acceptance/` 验收文件均在完成后按本人要求清理，见文末记录。部署验收写入的原生记忆标记和两项一次性 Cron 也已清理。

## 原企业飞书应用验收

以下结果对应企业应用 `cli_aa15cd2181b81cff`（太基保科技），不能作为新个人应用的验收结果。

- 应用「Hermes 个人助手」已创建并开启 Bot；App ID/Secret 已通过官方认证接口验证。
- 本人已明确批准四项权限及仅本人可用版本发布；四项权限已添加，可用范围页面仅列应用所有者。
- 本人已明确授权将凭据写入服务器运行配置并通过原生配对建立白名单；运行凭据权限为 0600，未创建新的本地临时凭据副本。
- Hermes 和飞书后台均确认长连接成功；`im.message.receive_v1` 事件及 `card.action.trigger` 审批回调已添加，均使用持久连接。
- 本人已批准并补充 `im:message.p2p_msg:readonly`（仅接收发给机器人的私聊）；未添加群消息事件权限。
- 飞书应用 `1.0.0` 于 11:33 发布，后台显示 Enabled / Released / Approved；可用范围只有应用所有者一人，外部私聊和外部群访问关闭。
- 已收到本人飞书私聊，使用本人提供的有效配对码批准账号；运行白名单与原生配对记录均只包含本人一人，已恢复 `unauthorized_dm_behavior: ignore`，关闭后续配对入口。
- 13:42 重启后批准记录仍为一人，飞书 WebSocket 已重新连接，无连接错误。
- `feishu_auth` 读取实际白名单并调用原生适配器：本人私聊放行、其他用户私聊拒绝、本人及其他用户群消息均拒绝；此项不向其他账号发送消息。
- 13:43 本人通过飞书发起 Python 计算任务，会话 `20260908_134311_13495d4d` 使用 DeepSeek v4 Pro，真实调用 `execute_code`，生成 `/workspace/result.txt`，最终回复带附件；文件内容为 `42`，本人已确认收到。
- 第二轮会话 `20260908_134359_6ab65f19` 引用机器人发送的附件，原生 `search_files` 和 `read_file` 成功读取工作目录中的结果文件，最终回复“文件内容只有一个数字：42”。此操作验证附件引用与已有文件读取，未验证独立上传附件的下载接收。
- 本人随后重新上传文件，并确认机器人已回复、读出内容；实际上传接收由本人确认通过。管理连接中断，尚未补查这一轮服务器日志。
- 已将 `FEISHU_HOME_CHANNEL` 写为已配对本人唯一私聊的 chat_id，并成功执行一致性备份及恢复服务。写入后加载与通知投递的管理端核验尚待恢复连接；当前不将其记为已验证。
- 飞书审批按钮回复尚未验收。上述适配器测试不代替实际飞书附件与卡片交互。

此前本人主动关闭本机 Tailscale，远程核验暂时停止；本人随后重新开启并通知继续，已恢复 SSH，Hermes 为 running / healthy。

## 个人飞书应用验收

- 本人已在个人身份 Invictus- 下创建新应用 `cli_aa15144968381d27`；开发者后台显示“正式应用@Feishu Personal Edition”。
- 机器人能力已开启；本人已批准与原部署相同的五项应用身份权限，页面显示全部已开通。未申请用户身份权限。
- 本人填写的新 App ID/Secret 已通过容器现有代理调用飞书官方认证接口验证。已写入服务器 0600 运行环境并重启 Hermes，旧应用配对已移除。
- 飞书后台验证新应用长连接成功，`im.message.receive_v1` 和 `card.action.trigger` 均已通过长连接订阅。
- 本人确认个人版发布及官方文档中已发布个人应用暂无法删除的限制。已核对 `1.0.0` 于 14:38 发布，页面显示“已启用 / 已发布 / 审核通过 / 当前修改均已发布”；可用范围只有 Invictus-，外部群与外部私聊关闭。
- 已使用本人提供的新配对码批准个人账号；原生批准记录与 `FEISHU_ALLOWED_USERS` 均只有此账号，已关闭后续配对入口并恢复 `ignore`。重启后 `feishu_auth` 通过：本人私聊放行，其他账号和全部群消息拒绝；WebSocket 为 connected，无连接错误。
- 本人已通过 `/sethome` 设置新个人私聊。管理端核对实际 chat_id 与唯一批准账号的 DM 会话一致，重启后仍匹配；14:48 备份停机时原生默认通知实际投递成功。
- 14:44 的个人会话 `20260908_144414_e8d39562` 使用 DeepSeek v4 Pro，真实调用 `terminal` 执行 Python 计算 7×8，将 `56` 写入 `/workspace/result.txt` 并通过原生 MEDIA 附件发送。本人实际输入的文件名为 `result.txt`。
- 本人重新上传的文件独立保存为 `/opt/data/cache/documents/doc_3039ea69ec0c_result.txt`，原生 `read_file` 从此路径读出 `56`；服务器核对两份文件内容一致，本人确认往返完成。
- 14:44:25 飞书日志明确记录审批按钮回调 `choice=always`，对应 Python 命令成功执行。当前永久许可为本人选择的 `execute_code` 和 `script execution via -e/-c flag`；已保留选择，未开启 YOLO。原生引擎的单次批准、拒绝、超时及无人值守拒绝结果见上表，不另声称所有分支都做了真实飞书点击。
- 迁移前一致性备份 `hermes-20260908T062823Z.tar.gz` 与迁移后 `hermes-20260908T064820Z.tar.gz` 均运行成功；后者备份服务 Result=success、退出码 0。两份现均依本人要求清理。切换前无 Cron 任务，旧默认通知会话已清空并换为新个人私聊。
- 备份重启后 Gateway running、Feishu connected，无连接错误；会话数据库 quick_check 为 ok，主模型、压缩、Cron 和 Messages 配置不变。
- 切换时保留 Hermes 数据、记忆与工作目录；应用凭据、应用范围内的用户 open_id、私聊 chat_id 和定时任务投递目标须核对更新，不能直接沿用企业身份。

## 实施中修正

- 根据本人后续要求，将原方案 Chat Completions + Sonnet 改为 Messages，主对话、压缩、Cron 均改用 DeepSeek v4 Pro。
- 实际 CPA 模型名为 `deepseek-v4-flash-vision`，已修正输入中的 `vr`。
- DeepSeek 思考模式不支持强制单个工具，验收使用自动工具选择；不改变协议。
- 官方镜像默认文件写入范围仅 `/opt/data`，已补充 `/workspace` 和容器 `/tmp`，支持持久化交付物及内置验证脚本。
- `web_extract` 在此版本不调用模型，已移除多余辅助配置。

## 验收后清理

本人明确要求验证完成后清理 CTYun 的备份与临时文件。本次清理范围为 Hermes 部署产生的文件：

- 删除五份部署归档、六份旧配置/凭据快照、已用完的服务器根目录凭据导入脚本，以及源码目录中的旧 `.env.example` 和 macOS 打包残留；共五份备份和十六个其他部署文件。
- 删除八份专用验收文件及其目录、容器 `/tmp/hermes-verify-model-tool.py`；本轮未使用的审批测试夹具也已删除。
- 共释放约 466 MiB；部署 `backups/` 和 `verification/` 为空。未清理 Hermes 的运行缓存、聊天、记忆或本人工作文件，上传附件仍可回读。
- 运行 `.env` 权限仍为 0600；每日备份定时器继续启用，下一次为北京时间 2026-09-09 04:30，未来保留最近七份。

## 网页后台验收

- 本人要求启用 Dashboard，并明确等待 X 新闻任务完成后部署；本人确认任务结束后，管理端核对 active_agents=0 才重建容器。
- 官方后台已启动，Compose 仅将容器 9119 映射到宿主 Tailscale IPv4 `100.121.133.84:9119`；容器 running / healthy。
- 后台使用官方 Basic Auth。密码仅写入本地忽略文件 `.env.example`，服务器 `data/.env` 保存 scrypt 哈希和独立会话签名密钥，权限 0600。
- 经 SSH 管理链路验证：状态接口要求认证且提供 basic 登录，匿名管理请求和错误密码均返回 401，正确密码登录成功，登录后管理接口及带一次性票据的 WebSocket 均通过，退出后管理请求恢复 401。
- 飞书启动时一次 TLS 连接失败，官方客户端随后自动重连成功；`feishu_auth` 再次通过，未修改白名单、模型或审批选择。
- 首次从本机访问 Tailscale 9119 超时，原因是原有 Tailnet 规则只允许 SSH。本人批准增加访问后，已在管理后台保存独立规则：来源仅 `100.66.88.36/32`（MacBook Pro (4)）和 `100.68.13.52/32`（iPhone 15 Pro Max），目标仅 `100.121.133.84/32`，协议和端口仅 `tcp:9119`。原有 SSH 规则及其他策略内容保持不变，CTYun 实际收到的 PacketFilter 与新规则一致。
- 从 Mac 通过 Tailscale 地址实测：TCP 9119 可连接，状态接口 HTTP 200 且要求认证，匿名管理请求返回 401，正确密码登录和管理接口成功，WebSocket 通过升级握手，退出后管理请求恢复 401。Chrome 实际打开登录页；iPhone 权限已下发，尚未做手机端访问测试。
- 验收后已清理 `.dashboard-enable-backup/` 中的旧 Compose、旧运行凭据及目录本身，并删除 `.compose-dashboard.yaml`。容器仍为 running / healthy，运行凭据权限 0600，`backups/` 和 `verification/` 为空，每日备份定时器仍 active。
