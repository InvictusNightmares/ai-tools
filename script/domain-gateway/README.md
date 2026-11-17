# 服务域名与 HTTPS 网关

保存公网与 Tailscale 私网域名入口的配置模板、ACME 维护工具和 HTTPS 验收脚本。架构、部署顺序和本次实施范围见 [实施记录](../../doc/domain-gateway/implementation.md)。

登录后功能、订阅来源链与遗漏修复见[后续复查](../../doc/domain-gateway/audit-followup.md)。页面返回成功不能代替应用内链接、外部订阅、分页读取和证书续期检查。

代理、面板后端和订阅后端的证书迁移、共同重载及旧证书清理结果见[域名证书迁移](../../doc/domain-gateway/certificate-migration.md)。其中列明已完成的验收及仍存在的直连网络波动。

原部署回滚备份已按用户要求删除，清理结果与当前备份状态见[三台主机清理记录](../../doc/domain-gateway/cleanup.md)。

这些文件供核对、维护和重新部署使用。`render.py` 只生成候选文件，不能直接覆盖已有网关；现有认证规则、订阅精确路径和旧监听必须合并保留。现用续期调度直接调用原 ACME 客户端，重载已使用 `reload_services.py`；`acme.py` 供维护和重新部署使用。

## 文件

| 文件 | 用途 |
| --- | --- |
| `render.py` | 从私有参数生成单个模板，拒绝覆盖现有文件 |
| `acme.py` | 注册、签发、安装与续期；默认只校验计划 |
| `verify.py` | 验证可信 HTTPS、状态码和可选内容摘要，不跟随跳转 |
| `reload_services.py` | 持有续期共用锁，验证证书后重新加载面板、代理和网页网关 |
| `templates/public-*` | SNI 分流、来源地址传递及公网网关挂载 |
| `templates/private-*` | 仅绑定 Tailscale 地址的网关及服务反向代理 |
| `templates/renew.*`、`reload.*` | 定时续期与证书安装后的检查、重载 |
| `templates/panel-host-renewal.patch` | 由宿主调度续期时，禁止面板启动脚本重新注册内部 ACME cron |
| `*.example.json` | 只有示例域名和占位符的配置结构 |
| `.private/` | 本地受控部署映射、一次性操作脚本；由 Git 忽略 |

本机保存的登录入口迁移步骤见[浏览器登录说明](../../doc/domain-gateway/browser-logins.md)。真实旧地址与新入口在 `.private/password-manager-migration.json`，不包含用户名或密码。

运行工具只依赖 Python 3.10+ 标准库。部署还需要官方 Nginx、Docker Compose、acme.sh 和 systemd。使用已核实的固定镜像版本或 digest；代码不会自动下载或安装依赖。

## 私有配置

将示例复制到仓库外的受控目录，或本目录的 `.private/`。目录使用 `0700`、配置使用 `0600`。替换全部尖括号占位符；端口字段改为 JSON 整数。

```sh
install -m 600 script/domain-gateway/values.example.json '<PRIVATE_VALUES_FILE>'
install -m 600 script/domain-gateway/acme.example.json '<PRIVATE_ACME_CONFIG>'
install -m 600 script/domain-gateway/verify.example.json '<PRIVATE_CHECK_CONFIG>'
```

生成结果、完整服务地址、安全路径、原有管理认证片段及操作日志同样属于私有文件。工具拒绝将生成内容写到项目的可跟踪目录，也拒绝覆盖现有文件或写入符号链接。

模板字段规则：

- `WEB_DOMAINS` 是网关要终止 TLS 的精确域名列表；其他 SNI 交给原代理后端。
- `HTTP_PORT`、`HTTPS_PORT`、`TLS_PORT`、`RAW_PORT` 是不同的监听端口；后两项只在公网容器内部使用。
- `RAW_BACKEND` 是现有代理的容器内地址；不能把它改成网页后端。
- `HTTP_POLICY_GLOB` 保存已有 `map`、限流及旧监听；`PRIVATE_LOCATIONS_INCLUDE` 保存原认证和 location 规则。
- `PRIVATE_BIND_IP` 只接受 Tailscale IPv4 地址。Compose 的 host 网络模式仍需依靠 Nginx 精确绑定地址和 Tailscale 访问规则。
- `PRIVATE_UPSTREAM` 指向已有的私网或回环应用入口。
- 路径、名称等模板标量不支持空白、引号和配置控制字符；复杂规则放入受控 include 文件。

## 生成候选配置

```sh
python3 script/domain-gateway/render.py \
  --template public-nginx.conf.template \
  --values '<PRIVATE_VALUES_FILE>' --output '<NEW_CANDIDATE_FILE>'
```

按同样方式生成所需的 Compose、vhost 或 systemd 模板。Compose 的 JSON 文件可通过 `docker compose -f '<COMPOSE_FILE>' config --quiet` 检查。模板目录中的路径是容器接口；实际宿主目录由私有参数指定。

公网 vhost 通过私有 include 合并原有登录、管理界面、限流及订阅 location，不能用无条件 `proxy_pass` 取代这些规则。私网服务沿用应用原有认证，网关为上游 Cookie 增加 Secure 属性。

私网模板使用 `Referrer-Policy: same-origin`，让同源登录表单保留有效来源；不要将其改成会导致浏览器表单发送 `Origin: null` 的策略。JSON 等文本响应启用压缩，避免大列表分页占满前端读取时限。应用自己的来源、认证和会话检查仍须保留。

所有候选配置都必须执行 `nginx -t`。新增 Docker 挂载或发布端口需要重建容器；单独 reload 不会应用 Compose 变更。公网端口移交和回滚顺序见实施记录。

## 证书维护

`acme_command` 使用参数数组，可指定宿主 acme.sh，或 `docker exec` 加容器内 acme.sh。`home` 是该命令实际看到的 ACME 目录。

公网使用 `validation: "http"`，增加绝对路径 `webroot`；私网使用 `validation: "dns"`、`challenge_alias` 和 `dns_env_file`。DNS 文件只接受：

```sh
CF_Token='<ZONE_SCOPED_DNS_TOKEN>'
CF_Zone_ID='<AUTHORIZED_ZONE_IDENTIFIER>'
```

DNS Token 仅授予单一区域的 DNS 编辑及必要读取权限；不能使用全账户 API Key。验证别名的关系为：

```text
_acme-challenge.<SERVICE_DOMAIN>
  CNAME _acme-challenge.<VALIDATION_ALIAS>
```

这只委托证书验证，不转移业务域名的权威 DNS，也不会把私网服务发布到公网。CNAME 必须长期保留，临时 TXT 由证书客户端添加和清理。

```sh
# 默认只校验参数，不注册账号、不签发、不执行外部命令。
python3 script/domain-gateway/acme.py issue --config '<PRIVATE_ACME_CONFIG>'

# 已获授权后显式执行对应步骤。
python3 script/domain-gateway/acme.py register --config '<PRIVATE_ACME_CONFIG>' --apply
python3 script/domain-gateway/acme.py issue --config '<PRIVATE_ACME_CONFIG>' --apply
python3 script/domain-gateway/acme.py install --config '<PRIVATE_ACME_CONFIG>' --apply
python3 script/domain-gateway/acme.py renew --config '<PRIVATE_ACME_CONFIG>' --apply
```

`install` 安装独立的 key/fullchain，并记录 `reload_command` 参数数组。容器内 ACME 可通过共享目录中的 marker 通知宿主 `.path` 单元；宿主 ACME 可调用检查后重载脚本。必须使用 `--install-cert` 记录安装路径，不能只手工复制初次证书。

同一证书供面板、原生订阅和代理共同使用时，只重载 Nginx 不足以完成更新。使用 `reload.example.json` 配置 `reload_services.py`，让续期单元与重载工具共用 `lock_file`。安装回调只更新 marker；path 单元和定时补偿调用重载工具，避免在容器内 ACME 尚未退出时重启容器。部署时同时复制其依赖 `common.py`。工具输出仅包含状态或错误类型；真实域名和路径只写入权限为 `0600` 的私有配置。

若面板镜像启动时会自动注册 ACME cron，迁移到宿主调度后还需处理其启动逻辑，防止重建或重启恢复重复任务。`panel-host-renewal.patch` 只展示该段变更；应针对实际镜像的完整启动脚本应用并只读挂载，保留其他启动逻辑。每次升级镜像都须重新核对脚本和测试重启，不能盲目沿用旧脚本。

测试签发使用 `server: "letsencrypt_test"` 和不同于生产 `home` 的独立 `config_home`。测试证书不投入服务。生产签发遇到配额限制时尊重返回的重试时间；更换签发机构和注册账号应先获得授权。

工具的公开输出只包含步骤、状态和错误类型；客户端原始输出写入指定的私有 `log_file`。`--apply renew` 不强制重签，尚未到期时正常跳过。使用已有调度即可，不要另装一套并发续期任务。

## 验收

```sh
python3 script/domain-gateway/verify.py --config '<PRIVATE_CHECK_CONFIG>'
python3 -m unittest discover -s script/domain-gateway -p 'test_*.py' -v
```

验收配置包含 `checks` 数组，每项设置通用 `label`、私有 `url` 和预期 `status`；可加 `sha256` 检查固定内容。会自动刷新的订阅应与当前发布文件比较，不能长期使用首次发布的固定摘要。安全路径只放在私有配置中。标签不要包含地址或账号。

验证器使用系统信任库并检查证书主机名，不提供忽略 TLS 错误的开关。它不登录后台，也不证明所有业务功能或代理节点都正常。公网入口、私网入口、原有代理协议及证书续期应分别验收。
