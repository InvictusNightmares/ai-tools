# 静态 Clash 订阅生成器

生成器直接使用宿主机 Python：定时拉取基础 Clash 订阅，从另一份原生 Clash 订阅选取指定的 Shadowsocks + obfs 节点，生成完整 YAML。现有 nginx 容器通过共享目录读取结果，提供订阅下载；生成器在宿主机调用 `docker exec` 检查、重载 nginx，然后退出。

## 合并行为

- 根据私有配置精确选取、重命名节点。基础订阅已有同名节点时原位替换，避免重复；完整保留原生 `plugin-opts`、UDP over TCP 等字段。
- 保留基础节点、DNS、规则和其他策略组，只扩展指定的手动选择组。`protected_groups` 中的自动选择组不得新增这些节点。
- `required_base_nodes` 列出必须保留的基础节点，防止上游意外返回缺失节点的配置。
- 发布前检查 YAML 结构、选定节点参数，以及策略组和规则引用。成功后原子切换 `current` 链接，替换 YAML 和统计文件；正常成功时删除上一代输出。
- 下载、解析或校验失败时保留仍有效的上一份结果。基础订阅明确拒绝访问、过期、耗尽额度，或旧结果超过 `max_stale_seconds` 时，撤下 YAML。保留统计 include 文件，避免影响 nginx 后续加载配置。
- nginx 检查或重载命令报错时，生成器恢复上一代文件。实际 HTTP 服务需部署后验收。

流量响应头只来自基础订阅，不能合并外部节点的流量。生成器不改变节点的 IPv4 / IPv6 出口行为，也不增加中转链路。

## 本地验证

运行依赖为 Python 3.10+ 和 PyYAML 6.x（最低 6.0.2），已安装兼容版本时直接复用。所有命令从仓库根目录执行；尖括号内容必须替换成私有环境中的值。

```sh
python3 -c 'import sys, yaml; print(sys.version.split()[0], yaml.__version__)'
install -m 600 script/clash/static-subscription/config.example.yaml '<PRIVATE_CONFIG_FILE>'
```

若目标环境缺少依赖，可以在仓库外创建独立 venv，再按 `requirements.txt` 安装；已有兼容环境无需执行安装步骤。

编辑私有配置，填入两个 HTTPS 订阅地址、源节点到目标名称的映射、必须保留的基础节点以及输出目录的绝对路径。配置文件和输出目录都必须放在 Git 工作区以外；不要把实际订阅、凭据或生成结果提交到仓库。私有配置权限须为 `0600` 或更严格。

`base_url` 必须是原始基础 YAML 订阅，不可填写本生成器的输出地址。`extra_url` 必须返回原生 Clash YAML。基础响应须有 `Subscription-Userinfo`，包含 `upload`、`download`、`total`，`expire` 可省略或为零。

```sh
python3 script/clash/static-subscription/generate.py \
  --config '<PRIVATE_CONFIG_FILE>' --dry-run
```

`--dry-run` 会下载、合并并做基础结构检查，不创建发布目录、不切换订阅、不执行 nginx 命令。日志只输出节点数量和经过脱敏的错误，不输出订阅地址、节点凭据或外部命令的原始日志。

这些检查不等同于代理内核的完整配置校验，也不测试节点连通性。生成器不下载 GeoIP、geosite 或规则集合数据；相关配置按原样交给客户端处理。

## 部署模板

以下是待适配的模板，运行仓库测试不会安装或启用它们。

### 首次生成

先不配置 nginx 命令，运行一次生成器，确保存在有效的 `current/headers.conf`，再添加 nginx 的 include：

```sh
python3 '<GENERATOR_FILE>' --config '<PRIVATE_CONFIG_FILE>'
```

输出目录布局如下，除 `current` 指向的当前一代外，不需要保留历史副本：

```text
<PRIVATE_PUBLISH_DIRECTORY>/
  .lock
  current -> generation-<RANDOM_ID>
  generation-<RANDOM_ID>/
    subscription.yaml
    headers.conf
    state.json
```

默认目录 `0700`、文件 `0600`。若 nginx 以不同身份读取，配置 `reader_gid` 为专用读取组的数字 ID，输出会使用目录 `0750`、文件 `0640`；父目录也要允许对应身份穿过。让现有 nginx 容器只读访问整个输出目录，优先复用已有挂载。若需新增挂载，应在部署时安排容器重建；仅重载 nginx 不会增加 Docker 挂载。不能只挂载单个 YAML 文件，否则原子替换无法可靠生效。

### 现有 nginx

在已有的 HTTPS `server` 中添加精确路径。使用独立的随机订阅令牌，只开放 YAML，不能公开整个输出目录。

```nginx
location = /<PRIVATE_RANDOM_TOKEN>.yaml {
    alias <NGINX_VISIBLE_PUBLISH_DIRECTORY>/current/subscription.yaml;
    include <NGINX_VISIBLE_PUBLISH_DIRECTORY>/current/headers.conf;
    types { }
    default_type application/yaml;
    add_header Cache-Control "private, no-store" always;
    open_file_cache off;
    etag off;
    if_modified_since off;
    access_log off;
    log_not_found off;
}
```

部署时检查该 location 是否需要重复已有的安全响应头：nginx 在下层定义 `add_header` 后，默认不继承上层的 `add_header`。`alias` 用法见 [nginx core 文档](https://nginx.org/en/docs/http/ngx_http_core_module.html#alias)，响应头继承规则见 [headers 模块文档](https://nginx.org/en/docs/http/ngx_http_headers_module.html#add_header)。

验证 `nginx -t` 并加载 location 后，在私有配置中同时设置 `nginx_check_command` 和 `nginx_reload_command`，使用示例中的 `docker exec` 参数数组。命令由宿主机生成器直接执行，不经过 shell；容器名及 Docker 可执行文件路径放在私有配置中。

每次发布切换完成后，生成器执行 nginx 检查、重载，让 nginx 重新读取统计响应头；其中任何命令报错都会恢复上一代文件。不要另在 systemd 的 `ExecStartPost` 中重复执行这两个步骤，否则无法由生成器统一处理失败回退。不配置这两个命令时，YAML 会更新，但 nginx 内已加载的流量数字不会自动更新。

各客户端需一次性改用这个静态订阅 URL。仅生成静态文件不会改变原有面板订阅 URL 的响应。客户端通过节点原地址连接，静态分发服务器仅提供订阅下载。

### systemd 定时运行

`static-subscription.service`：

```ini
[Unit]
Description=Generate a static subscription with host Python
Wants=network-online.target
Requires=docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
User=<GENERATOR_SERVICE_USER>
UMask=0077
ExecStart="<PYTHON_BINARY>" -B "<GENERATOR_FILE>" --config "<PRIVATE_CONFIG_FILE>"
```

`<PYTHON_BINARY>` 填宿主机现有 Python 的绝对路径。服务身份需要读取私有配置、写入输出目录，并有权限通过 Docker 控制现有 nginx 容器。Docker 依赖用于 nginx 检查与重载，生成器进程由 Python 直接运行。

`static-subscription.timer`：

```ini
[Unit]
Description=Refresh the static subscription

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Unit=static-subscription.service

[Install]
WantedBy=timers.target
```

安装到服务管理目录后执行 `systemctl daemon-reload`、`systemctl enable --now static-subscription.timer`。此示例的刷新间隔约为 15 分钟，必须短于私有配置中的最大缓存时间；定时字段语义见 [systemd 官方手册源码](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml)。撤下过期 YAML 发生在生成器下次运行时；定时器停用或进程始终无法运行时，静态文件不会自行过期。已被客户端下载的节点配置也不会被远程删除。

部署后验收：HTTPS 下载得到完整 YAML，客户端可以导入，新增节点出现在手动组而自动组成员不变，`Subscription-Userinfo` 与基础订阅一致。故障演练应使用独立临时输出目录。

## 测试

```sh
python3 -m unittest discover -s script/clash/static-subscription -p 'test_*.py' -v
```

测试使用合成订阅，检查替换、去重、组过滤、规则引用、原配置保留、失败回退、过期撤下、权限与日志脱敏，并验证不调用外部程序也能完成生成和发布。

组过滤扩展遵循 Mihomo 的多段 filter 语法，见 [代理组字段文档](https://wiki.metacubex.one/config/proxy-groups/#filter)。生成器对当前选定的 SS + obfs 场景做严格检查；上游改为其他协议或链式依赖时需要重新评估，不会静默发布不完整节点。
