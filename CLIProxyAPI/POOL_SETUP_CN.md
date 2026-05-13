# CLIProxyAPI 号池落地说明

这个目录已经放好了 CLIProxyAPI 源码，适合先把它作为 `Codex/OpenAI` 号池底座，再按需要接管理面板和统计看板。

## 目录位置

- 项目目录：`/Users/invictus/Github/ai-tools/openai/CLIProxyAPI`
- 凭据目录：`/Users/invictus/Github/ai-tools/openai/CLIProxyAPI/auths`
- 号池配置模板：`/Users/invictus/Github/ai-tools/openai/CLIProxyAPI/config.pool.example.yaml`
- Compose 环境模板：`/Users/invictus/Github/ai-tools/openai/CLIProxyAPI/.env.pool.example`

## 推荐部署方式

建议先用 Docker Compose 跑起来，因为官方 `docker-compose.yml` 已经把 API 端口、OAuth 回调端口和 `auths` 挂载都配好了。

当前我这边的执行环境里没有 `docker` 命令，所以代码和配置模板已经准备好，但真正启动容器还需要你本机先装好 Docker Desktop 或 Docker Engine。

如果你的最终目标是放到云服务器或独立机器上，建议直接把整个目录迁到服务器，然后让服务器长期持有 `config.pool.yaml` 和 `auths/`。

## 平移到服务器的两种方式

### 方式 A：先本地导号，再把整套目录拷到服务器

这是最省事的方式，适合你已经在本机浏览器里能顺利完成 Codex 登录。

你真正需要带走的核心资产只有这几样：

- `config.pool.yaml`
- `.env`
- `auths/`
- `logs/` 可以不带，属于运行日志

可以直接把整个目录同步到服务器，例如：

```bash
rsync -avz /Users/invictus/Github/ai-tools/openai/CLIProxyAPI/ user@your-server:/opt/CLIProxyAPI/
```

同步过去后，在服务器执行：

```bash
cd /opt/CLIProxyAPI
docker compose up -d
```

### 方式 B：直接在服务器部署，然后在服务器上完成导号

这是更适合正式环境的方式，尤其当你不想先在本地生成凭据文件时。

对 `Codex` 来说，优先推荐设备码登录，而不是普通浏览器回调登录，因为它更适合 SSH 和远程服务器场景。

## 快速启动

在项目目录执行：

```bash
cp .env.pool.example .env
cp config.pool.example.yaml config.pool.yaml
docker compose up -d
```

`docker-compose.yml` 会自动读取 `.env`，并把 `config.pool.yaml` 当成运行配置挂进容器。

如果你是在服务器上首次部署，建议目录使用类似：

```bash
/opt/CLIProxyAPI
```

这样后面做 systemd、备份和日志清理都比较顺手。

## 首次必须修改的配置

编辑 `config.pool.yaml`，至少改这两项：

```yaml
remote-management:
  secret-key: "换成你自己的管理密钥"

api-keys:
  - "换成给客户端用的访问密钥"
```

含义：

- `remote-management.secret-key`：管理接口和管理面板的登录密钥
- `api-keys`：你的业务客户端访问 `/v1/...` 时要带的 API Key

## 启动后访问地址

- OpenAI 兼容接口：`http://127.0.0.1:8317/v1`
- 管理接口：`http://127.0.0.1:8317/v0/management/...`
- 管理面板：`http://127.0.0.1:8317/management.html`

如果你的业务程序要从别的机器接入，把 `127.0.0.1` 换成部署机器的 IP 或域名即可。

如果你把它放到服务器上，建议：

- API 入口可以按需对内网或业务机器开放
- 管理面板先不要直接暴露公网
- 管理操作优先走 SSH 隧道

## 号池怎么加账号

最适合你的方式是把每个 Codex 账号作为一个 OAuth 凭据导入到 `auths` 目录里。CLIProxyAPI 会自动把这些文件视为一个池子，并按配置做轮询和失败切换。

### 方式一：管理面板导入

1. 打开 `http://127.0.0.1:8317/management.html`
2. 使用 `config.pool.yaml` 里的 `remote-management.secret-key` 进入管理面板
3. 在面板里发起 Codex OAuth 登录
4. 每完成一个账号登录，`auths/` 目录里就会新增一个凭据文件
5. 重复多次，直到把你的账号都导进去

这个方式最省心，也最适合后续维护。

如果管理面板跑在远程服务器上，不要直接裸开公网管理。推荐本机建立 SSH 隧道后再访问：

```bash
ssh -L 8317:127.0.0.1:8317 -L 1455:127.0.0.1:1455 user@your-server
```

然后在你本机浏览器打开：

```text
http://127.0.0.1:8317/management.html
```

这里额外转发 `1455` 很重要，因为 Codex 默认 OAuth 回调会落到 `localhost:1455`。

### 方式二：命令行登录

如果你后面打算自己编译二进制，也可以直接走官方登录参数，把 OAuth 凭据写进 `auths/`：

```bash
./cli-proxy-api --config ./config.pool.yaml --codex-login
```

Codex 默认会用本地 `1455` 端口接 OAuth 回调；如果端口冲突，可以额外指定：

```bash
./cli-proxy-api --config ./config.pool.yaml --codex-login --oauth-callback-port 2455
```

### 方式三：服务器上用设备码导号

如果你是纯服务器场景，最推荐这个方式。它不依赖浏览器回调端口，更适合 SSH。

CLIProxyAPI 已经内置了 `--codex-device-login` 流程。你在服务器上执行后，它会打印一个设备码和访问地址；你只要在自己电脑浏览器里输入这个设备码确认登录，服务器就会自动把凭据写进 `auths/`。

示例：

```bash
./cli-proxy-api --config ./config.pool.yaml --codex-device-login --no-browser
```

如果你用的是 Docker 镜像，比较实用的做法是临时起一个交互容器来完成导号，仍然挂载当前目录的 `auths/` 和配置文件。

## 号池关键配置建议

当前模板已经按号池场景给你设好了这些默认值：

- `routing.strategy: "round-robin"`：多账号轮询
- `routing.session-affinity: true`：同一会话尽量固定到同一个账号，减少上下文漂移
- `request-retry: 3`：请求失败时自动重试
- `max-retry-credentials: 3`：单次失败最多切换 3 个凭据
- `usage-statistics-enabled: true`：为后续接统计看板留好基础

如果你的业务更偏“优先榨干一个号，再切下一个号”，可以把：

```yaml
routing:
  strategy: "fill-first"
```

## 业务客户端怎么接

把它当成 OpenAI 兼容接口来接就行。

示例：

```bash
curl http://127.0.0.1:8317/v1/models \
  -H "Authorization: Bearer pool-client-key-change-me"
```

如果你用 OpenAI SDK，核心就是：

- `base_url` 指向 `http://你的地址:8317/v1`
- `api_key` 使用你在 `config.pool.yaml` 里填的客户端密钥

## 安全建议

- 第一版先保持 `remote-management.allow-remote: false`
- 如果一定要远程管理，优先走 Nginx + Basic Auth / VPN / Tailscale，不建议裸露在公网
- `api-keys` 和 `remote-management.secret-key` 不要复用
- `auths/` 目录是核心资产，务必做好备份和访问控制
- 服务器迁移时，最关键的是保住 `auths/`；丢了它，就等于整池账号都要重新登录

## 后续扩展

基础号池跑稳后，你可以再补两类外围能力：

- 管理运维：`CPA-Manager`
- 配额看板：`CLIProxyAPI Usage Dashboard` 或 `CLIProxyAPI Quota Inspector`

这些项目在上游 `README_CN.md` 里都已经列出来了，比较适合号池规模上来之后再接。
