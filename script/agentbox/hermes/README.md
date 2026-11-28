# 私网 Hermes 助手

使用官方 Docker 镜像运行个人助手，通过私有配置中的 API 上游调用模型，并复用已有的出网代理和浏览器。实际地址、账户、部署路径和凭据仅保存在受控配置中。

## 配置来源

- `compose.yaml`：镜像、资源约束、挂载与服务编排；更新版本前核对官方发布信息和 digest。
- `config.yaml`：模型、工具、会话和审批的基础配置；运行端可能有用户批准的调整，不能直接覆盖。
- `.env.template`：凭据字段说明。已忽略的本地凭据文件不能提交、打包或复制进文档。
- `workspace-instructions.md`：工作目录内的执行约束。
- `verify.py`：分项验收工具；只输出状态，不输出凭据。

镜像与模型的具体运行版本以部署端为准。本次域名迁移没有升级应用或改变模型选择。持久数据和工作目录继续使用既有挂载，不挂载 Docker socket、宿主根目录或管理 SSH 私钥。

## 私网 HTTPS 后台

网页入口为 `https://<ASSISTANT_DOMAIN>`。访问设备须连接 Tailscale，并在现有访问规则的允许范围内。2026-11 重构后 Hermes 升级为官方稳定版 `v0.23.5` 全新部署，容器仅发布至宿主机回环地址 `127.0.0.1:9119`，统一由 `private-domain-gateway` 在 Tailscale 地址转发并为 Cookie 增加 Secure 属性（已移除旧版 `agentbox-container-ready.service`）。证书通过 DNS-01 自动续期，无需将应用公开到互联网。完整架构、留空凭据接入步骤及验收记录见 [2026-11 重构手册](../../../doc/agentbox/refactor-2026-11.md)，网关部署、访问规则及客户端 DNS 配置见[服务域名实施记录](../../../doc/domain-gateway/implementation.md)。

备份脚本 `backup.sh` 会在停机并以 `10000:10000` 递归对 `data/` 下全部 SQLite 数据库执行 WAL checkpoint 后归档 `compose.yaml`、`data`、`workspace` 与 `/srv/agentbox/ctyun/data`，自动排除日志、缓存、锁文件与 WAL/SHM 文件，最多保留 3 份。

后续复查已验证可信 TLS、域名匹配、登录后的会话列表及 Gateway 运行状态，并将当前选中上游的 `providers.<selected>.api` 改为新 API 域名。使用现有出网配置读取模型列表成功，专属服务重载后运行配置仍使用新入口；模型选择、协议和凭据保持原样。检查必须以部署端选中的 provider 为准，不能照抄基础模板中的名称。

聊天 WebSocket、飞书消息、写入管理操作及手机访问没有在本次复查中重新验收。历史验收结果不能代替当前版本的业务验收。完整边界见[后续复查](../../../doc/domain-gateway/audit-followup.md)。

Dashboard 使用官方认证。运行凭据保存密码哈希及独立会话签名密钥，配置权限为 `0600`；明文密码不进入仓库或日志。停用后台时同步关闭应用开关并移除宿主发布，再执行 Compose 重建。

## 安装与日常维护

`install.sh` 用于首次部署，依赖既有出网、浏览器网络及私有环境文件。先按部署端配置核对镜像和挂载，再从独立源码目录执行；不要在运行中的容器内自更新。

`configure-credentials.py` 是首次导入凭据的辅助脚本，通过标准输入接收 JSON、验证上游凭据并更新运行环境。现有环境不需要重复执行；临时文件不得进入版本控制。

以下命令中的占位符须替换为受控配置中的值：

```sh
ssh '<PRIVATE_SSH_TARGET>' 'docker compose -f <PRIVATE_COMPOSE_FILE> ps'
ssh '<PRIVATE_SSH_TARGET>' 'docker compose -f <PRIVATE_COMPOSE_FILE> restart <ASSISTANT_SERVICE>'
```

修改应用 YAML 后重启对应服务；修改 Compose 的挂载、环境或端口后执行 `up -d`。保留已授权的网络范围和运行配置，不用脱敏示例替代线上值。

模型可通过 `/model` 或 `/model custom:<provider-name>:<model-name>` 选择。辅助模型设置独立于主对话模型；修改默认模型时同时检查压缩和定时任务使用的配置。

## 飞书与审批

飞书凭据、允许用户和默认私聊目标均由私有配置管理。应用使用长连接接收私聊与审批事件；群消息默认拒绝。更换应用后须重新核对应用范围内的用户身份和私聊目标，不能沿用旧应用标识。

新增或更换允许用户时，先获得授权，再临时开启原生配对。仅批准用户提供的有效请求，将批准记录与 `FEISHU_ALLOWED_USERS` 对齐，完成后恢复 `unauthorized_dm_behavior: ignore`。`FEISHU_HOME_CHANNEL` 是默认通知会话，与用户白名单标识不同。

审批卡片的 `Allow Once` 只批准当前操作，`Session` 作用于当前会话，`Always` 保存该项永久许可，`Deny` 拒绝。维护时保留用户已批准的选择，不用基础模板覆盖，也不扩大至所有操作自动批准。无人值守任务的审批失败应拒绝执行。

预算、最大轮次和重试次数属于应用限制，不能保证严格费用上限。worktree 只隔离文件与分支，不构成系统安全边界。

## 备份、升级与回滚

使用部署端已有备份任务。备份应在一致性停机或应用支持的快照条件下覆盖 Compose、持久数据和工作目录，校验后恢复服务。归档含凭据，只允许受控身份读取；保留策略以实际定时器与脚本为准。

```sh
ssh '<PRIVATE_SSH_TARGET>' 'systemctl start <BACKUP_SERVICE>'
ssh '<PRIVATE_SSH_TARGET>' 'journalctl -u <BACKUP_SERVICE> -n 10 --no-pager'
```

升级前手动备份并另存一份不参与轮转的归档，核对官方迁移说明后更新镜像与编排。回滚时先保留故障快照，再从同一份受信任归档恢复编排、数据和工作目录及文件属主。只回退镜像却保留已经迁移的数据，可能无法恢复。

恢复后先检查中断任务是否已产生结果，再决定是否重跑。不要因文档中的历史清理记录假定当前备份目录为空。

2026-11-17 已按用户要求删除当时存在的历史归档及内部备份，既有备份定时器继续运行，详见[三台主机清理记录](../../../doc/domain-gateway/cleanup.md)。已删除的副本不能用于恢复。

## 分项验收

可将 `verify.py` 经标准输入送入容器：

```sh
ssh '<PRIVATE_SSH_TARGET>' 'docker exec -i -u <APP_UID> <ASSISTANT_CONTAINER> <PYTHON_BINARY> - core' < script/agentbox/hermes/verify.py
```

按需要将末尾模式换为 `model`、`approvals`、`feishu_auth` 或 `browser`。模型测试会调用实际上游；浏览器测试使用现有浏览器会话。`feishu_auth` 检查允许本人私聊、拒绝其他用户和群消息，不发送消息。

`browser_reconnect` 是较长的会话重建测试。`persistence_prepare` 会创建持久验收记录和一次性定时任务；重启并等待调度后使用 `persistence_check`，最后执行 `persistence_cleanup`。运行前先核对已有记录，不把这些模式当作只读健康检查。

飞书收发附件、审批按钮和默认通知需要真实会话验收；容器健康、网页可达或适配器检查均不能代替它们。后台验收应覆盖匿名拒绝、正确登录、管理接口、WebSocket 和退出后的权限恢复。

参考：[官方 Docker 文档](https://hermes-agent.nousresearch.com/docs/user-guide/docker/)、[飞书接入](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/feishu)、[配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)、[安全与审批](https://hermes-agent.nousresearch.com/docs/user-guide/security/)。
