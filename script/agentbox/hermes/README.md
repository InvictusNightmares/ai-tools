# CTYun Hermes

使用官方 Docker 镜像运行个人助手，通过 DMIT CPA 调用模型，复用 CTYun 的代理和 Chrome。

## 固定版本与配置

- Hermes `0.21.0`，发布标签 `v2026.8.31`，源码提交 `29112bef099274229cadff79cdff7bf7b99c4b77`。
- 镜像 `nousresearch/hermes-agent:v2026.8.31`，amd64 digest `sha256:87af7c6a5ee383834f75eb9a3fb509ccaacbab5d54084b086b48b84917e28efc`。
- 默认模型 `deepseek-v4-pro`；备选 `deepseek-v4-flash-vision`、`claude-sonnet-4-6`、`claude-opus-4-6`、`gemini-3.8-flash`。
- CPA 地址 `https://179.253.245.229:8317`，`transport: messages`；Hermes 将其解析为 `anthropic_messages`，请求 `/v1/messages`。
- 主对话、压缩和 Cron 使用 CPA + `deepseek-v4-pro`；其余辅助模型目前为 CPA + Sonnet。`auxiliary` 指截图识别、标题、会话检索、压缩等辅助调用，不随主模型切换。
- 应用 UID/GID `10000`，4 核、6 GiB。官方 s6 启动过程需要 root，随后切换应用身份。
- 容器使用北京时间。宿主时区、原有代理分流、CTYun 保活和 Chrome 配置沿用现状。
- 数据目录 `/srv/agentbox/hermes/data` → `/opt/data`，工作目录 `workspace` → `/workspace`；容器 `/tmp` 可供内置验证器写临时脚本，不持久化。
- Dashboard 端口只映射到 CTYun 的 Tailscale 地址 `100.121.133.84:9119`；不挂载 Docker socket、宿主根目录或管理 SSH 密钥。

## 凭据

脱敏模板是 `.env.template`。当前本地 `.env.example` 由本人手动填写，已加入本目录 `.gitignore` 并设为 `0600`；不要加入 Git 或打入交付包。

运行凭据放在 CTYun 的 `/srv/agentbox/hermes/data/.env`，权限 `0600`，属主 `10000:10000`。`CPA_API_KEY` 使用本人提供的 Key。上游 OAuth 文件留在 DMIT。

`configure-credentials.py` 是本次首次部署的凭据导入辅助脚本：在 CTYun 以 root 运行，从标准输入接收凭据 JSON，先验证 CPA Key，再更新运行环境；飞书凭据先暂存到容器挂载范围外。当前运行凭据已启用，暂存文件已删除，无须再次运行该脚本。

## 安装与日常操作

`install.sh` 仅用于首次安装，要求既有网络 `agentbox-egress`、`agentbox-browser`、代理环境文件和 Chrome `client.env` 已存在。先按 `compose.yaml` 拉取固定 digest 镜像，把私有凭据放入目标 `data/.env`，再从单独的源码目录运行 `bash install.sh`。飞书字段一旦填写，必须同时有 App ID、Secret 和本人的 `FEISHU_ALLOWED_USERS`。

现有部署的管理命令：

```bash
ssh ctyun 'docker compose -f /srv/agentbox/hermes/compose.yaml ps'
ssh ctyun 'docker compose -f /srv/agentbox/hermes/compose.yaml restart hermes'
ssh ctyun 'systemctl list-timers agentbox-hermes-backup.timer'
```

模型可通过 `/model` 选择，或用命名 Provider 语法，例如 `/model custom:dmit-cpa:claude-opus-4-6`。修改 YAML 后重启 Hermes；修改 Compose 后执行 `up -d`。不要在运行中的容器内执行自更新，镜像版本由 Compose 管理。

飞书使用国内 WebSocket，应用可用范围和 `FEISHU_ALLOWED_USERS` 均限制本人，群消息禁用。当前已接入本人创建的个人应用 `cli_aa15144968381d27`，归属 Feishu Personal Edition，`1.0.0` 已发布。本人已批准并添加五项应用身份权限：`im:message`、`im:message:send_as_bot`、`im:resource`、`im:chat:readonly`、`im:message.p2p_msg:readonly`。最后一项用于接收发给机器人的私聊事件。`im.message.receive_v1` 与 `card.action.trigger` 均使用长连接。个人账号的配对、附件往返、审批按钮及默认通知已通过验收，详见 `ACCEPTANCE.md`。原企业应用仍保留，但 Hermes 已不再连接它。

新应用接入时，临时启用 `unauthorized_dm_behavior: pair`，未批准账号只能申请配对。收到本人提供的有效配对码后批准对应账号，将其 open_id 写入 `FEISHU_ALLOWED_USERS`，确保原生批准记录和白名单均只有一人，然后恢复 `ignore` 并重启。应用更换后必须重新核对 open_id 和私聊 chat_id，不能直接沿用旧企业应用身份。

`FEISHU_HOME_CHANNEL` 使用本人和机器人的私聊 chat_id（`oc_...`），作为 Cron 结果等主动通知的默认去向；它与白名单中的用户 open_id 不同。也可在本人私聊内发送原生命令 `/sethome` 设置当前会话。

## 网页后台

本人已要求启用官方 Dashboard，访问地址为 `http://100.121.133.84:9119`，访问设备须连接同一 Tailscale 私网。用户名为 `invictus`；密码保存在本地忽略文件 `.env.example` 的 `HERMES_DASHBOARD_BASIC_AUTH_PASSWORD` 字段，不能加入 Git 或发送到聊天。

Dashboard 已启动。本人已批准新增一条 Tailscale 规则，仅允许 MacBook Pro (4)（`100.66.88.36`）与 iPhone 15 Pro Max（`100.68.13.52`）访问 CTYun（`100.121.133.84`）的 TCP 9119；原有 SSH 规则保持不变。已从 Mac 实测登录、管理接口、WebSocket 和退出，Chrome 登录页正常；iPhone 权限已下发，尚未在手机上实测。

Compose 开启 `HERMES_DASHBOARD=1`，容器内监听 `0.0.0.0:9119`，宿主仅绑定 Tailscale IPv4。现有 `AGENTBOX-DOCKER` 防火墙允许 `tailscale0` 入口，规则保持不变。官方 s6 同时管理 Gateway 和 Dashboard。

服务器 `data/.env` 使用官方 Basic Auth 的 scrypt 密码哈希及独立会话签名密钥，不保存后台明文密码。认证开启后，登录页面和精简状态接口可在私网访问，管理接口与聊天 WebSocket 需要登录。首次安装还须填写后台用户名、密码或哈希，以及至少 32 字符的会话签名密钥。

更换密码只更新后台专用凭据并重启 Dashboard；保留会话签名密钥可维持跨服务重启的登录会话。停用网页后台时将 `HERMES_DASHBOARD` 改为 `0`、移除 `ports` 映射，再执行 Compose `up -d`。部署启用与验收状态见 `ACCEPTANCE.md`。

## 权限与任务

若将来需要更换本人账号，先由管理端确认，再临时开启原生配对并按用户提供的配对码操作；不要批准其他请求。配对码有效期一小时，失效后重新私聊机器人取得新码。完成后恢复单人白名单与 `ignore`，重启并运行 `feishu_auth` 验证。

危险命令人工审批；Cron、无人值守和单次非交互调用默认拒绝。60 轮、API 重试 2 次和 30 分钟软预算已经配置；软预算不能保证严格费用上限。编码任务按工作目录指引串行执行；worktree 是文件和分支管理方式，不是系统安全隔离。

飞书审批卡片中的 `Allow Once` 只批准本次，`Session` 批准当前会话，`Always` 会保存该审批项的永久许可，`Deny` 拒绝。当前运行配置保留本人选择的 `execute_code` 和 `script execution via -e/-c flag` 两项永久许可；管理时不要用脱敏基础配置覆盖本人的运行选择。

## 备份、升级和回滚

每日北京时间 04:30 运行 `agentbox-hermes-backup.timer`。备份先停止 Hermes，打包 `compose.yaml`、`data` 和 `workspace`，校验压缩包后恢复服务，保留最近七份。备份含凭据，仅 root 可读；目前保存在同一台 CTYun 上。

2026-09-08 验收结束后，已按本人要求清理本次生成的五份备份和部署临时文件；Dashboard 验收后也已删除本次暂存 Compose 和临时回滚目录。当时 `backups/` 为空。自动备份任务仍启用，下一次为北京时间 2026-09-09 04:30。

```bash
ssh ctyun 'systemctl start agentbox-hermes-backup.service'
ssh ctyun 'journalctl -u agentbox-hermes-backup.service -n 10 --no-pager'
```

升级前手动执行一次备份，把这份归档另存至不被七份轮转清理的位置。核对新版本官方文档、digest 和迁移说明，拉取新镜像、更新 Compose，再运行 `up -d` 和验收。

回滚时停止 Hermes，将现有 `compose.yaml`、`data`、`workspace` 保留为故障快照；从同一份受信任备份恢复这三项并保留 UID/GID，再拉取归档中记录的镜像，运行 `up -d --force-recreate`。不要仅回退镜像却继续使用新版迁移过的数据。首次恢复先检查中断任务已产生的结果，再决定如何继续。

## 验收

从本目录将验证脚本通过标准输入送入容器。脚本仅输出验收状态，不输出凭据：

```bash
ssh ctyun 'docker exec -i -u 10000 agentbox-hermes /opt/hermes/.venv/bin/python - core' < verify.py
ssh ctyun 'docker exec -i -u 10000 agentbox-hermes /opt/hermes/.venv/bin/python - model' < verify.py
ssh ctyun 'docker exec -i -u 10000 agentbox-hermes /opt/hermes/.venv/bin/python - approvals' < verify.py
ssh ctyun 'docker exec -i -u 10000 agentbox-hermes /opt/hermes/.venv/bin/python - feishu_auth' < verify.py
ssh ctyun 'docker exec -i -u 10000 agentbox-hermes /opt/hermes/.venv/bin/python - browser' < verify.py
```

`browser_reconnect` 是约六分钟的会话重建测试。`persistence_prepare` 创建验收记忆和三分钟后触发的一次性本地任务；随后重启，等待到期及原生调度器最多约一分钟轮询延迟，再运行 `persistence_check`、`persistence_cleanup`。这组模式保留工作目录中的验收记录，再次执行前先检查已有记录。

`model` 使用 Messages 自动工具选择：DeepSeek 思考模式拒绝强制指定单个工具。`approvals` 只把危险命令字符串交给原生审批引擎检查，绝不实际执行删除。`feishu_auth` 在配对完成后读取实际白名单，检查原生适配器允许本人私聊、拒绝其他用户和群消息，不发送消息。飞书收发附件、审批回复仍需要真实飞书会话验收；配对阶段已验证重启后 WebSocket 重连。

参考：[官方 Docker 文档](https://hermes-agent.nousresearch.com/docs/user-guide/docker/)、[飞书接入](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/feishu)、[配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)、[安全与审批](https://hermes-agent.nousresearch.com/docs/user-guide/security/)。
