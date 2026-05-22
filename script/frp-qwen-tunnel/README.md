# FRP Qwen 反向隧道

这套脚本用于让一台有公网 IP 的新加坡服务器访问内网 GPU 机器 `192.168.64.16` 上的 Qwen/vLLM 服务，同时不把 vLLM 直接暴露到公网。

## 架构

```text
新加坡公网服务器
  运行 frps
  监听 :7000，等待 GPU 机器 frpc 连入
  只在新加坡本机暴露 127.0.0.1:18000
        ^
        | FRP 反向隧道
        |
GPU 机器 192.168.64.16
  运行 frpc
  主动连接 新加坡服务器:7000
  把新加坡 127.0.0.1:18000 转发到 GPU 本机 127.0.0.1:8000
```

最终新加坡服务器上的本地 API 地址是：

```text
http://127.0.0.1:18000/v1
```

这个地址等价于访问 GPU 机器上的：

```text
http://127.0.0.1:8000/v1
```

`18000` 默认只绑定新加坡本机回环地址，因为 `frps` 配置了：

```toml
proxyBindAddr = "127.0.0.1"
```

所以公网无法直接访问新加坡的 `18000`，只有新加坡服务器本机上的程序可以访问。

## 1. 新加坡公网服务器执行

先确保新加坡服务器的安全组/防火墙放通入站 TCP `7000`。只需要让 `192.168.64.16` 能连到新加坡的 `7000`。

然后在新加坡服务器上以 root 执行：

```bash
curl -fsSL https://raw.githubusercontent.com/InvictusNightmares/ai-tools/main/script/frp-qwen-tunnel/install-frps-server.sh -o install-frps-server.sh
chmod +x install-frps-server.sh
FRPS_BIND_PORT=7000 ./install-frps-server.sh
```

脚本会自动：

- 下载 `frps`
- 写入 `/opt/frp/frps.toml`
- 创建 systemd 服务 `frps-qwen.service`
- 启动并设置开机自启
- 生成并打印一个 `FRP_TOKEN`

保存脚本输出的 `FRP_TOKEN`，GPU 机器上的 `frpc` 必须使用同一个 token。

如果你想自己指定 token：

```bash
FRP_TOKEN='replace-with-a-long-random-token' FRPS_BIND_PORT=7000 ./install-frps-server.sh
```

查看新加坡 frps 状态：

```bash
systemctl status frps-qwen.service
journalctl -u frps-qwen.service -n 100 --no-pager
```

确认监听端口：

```bash
ss -ltnp | grep 7000
```

## 2. GPU 机器 `192.168.64.16` 执行

在 GPU 机器上以 root 执行。把 `SINGAPORE_PUBLIC_IP` 替换成新加坡公网 IP，把 `TOKEN_FROM_SERVER` 替换成新加坡脚本输出的 `FRP_TOKEN`。

```bash
curl -fsSL https://raw.githubusercontent.com/InvictusNightmares/ai-tools/main/script/frp-qwen-tunnel/install-frpc-gpu-client.sh -o install-frpc-gpu-client.sh
chmod +x install-frpc-gpu-client.sh
FRPS_SERVER_ADDR='SINGAPORE_PUBLIC_IP' \
FRP_TOKEN='TOKEN_FROM_SERVER' \
REMOTE_PORT=18000 \
SERVICE_NAME=frpc-qwen-singapore \
./install-frpc-gpu-client.sh
```

脚本会自动：

- 优先复用已有 `/usr/local/bin/frpc`
- 如果找不到 `frpc`，才会下载并安装
- 写入 `/opt/frp/frpc-qwen-singapore.toml`
- 创建 systemd 服务 `frpc-qwen-singapore.service`
- 启动并设置开机自启
- 将 GPU 本机 `127.0.0.1:8000` 映射到新加坡本机 `127.0.0.1:18000`

当前 `192.168.64.16` 已有东京隧道，现有结构是：

```text
/usr/local/bin/frpc
/opt/frp/frpc-qwen.toml
frpc-qwen.service
```

所以新加坡接入不会覆盖现有东京服务，只会新增：

```text
/opt/frp/frpc-qwen-singapore.toml
frpc-qwen-singapore.service
```

查看 GPU 机器 frpc 状态：

```bash
systemctl status frpc-qwen-singapore.service
journalctl -u frpc-qwen-singapore.service -n 100 --no-pager
```

确认 GPU 本机 vLLM 正常：

```bash
curl http://127.0.0.1:8000/v1/models
```

## 3. 在新加坡服务器验证

在新加坡服务器上执行：

```bash
curl http://127.0.0.1:18000/v1/models
```

正常应该看到模型：

```text
qy-coder:latest
```

新加坡服务器上的客户端应使用这个 OpenAI-compatible base URL：

```text
http://127.0.0.1:18000/v1
```

例如 OpenAI SDK、LiteLLM、Hermes、OpenCode 等都可以把 base URL 配成上面这个地址。

## 常用命令

新加坡服务器：

```bash
systemctl status frps-qwen.service
journalctl -u frps-qwen.service -n 100 --no-pager
systemctl restart frps-qwen.service
```

GPU 机器：

```bash
systemctl status frpc-qwen-singapore.service
journalctl -u frpc-qwen-singapore.service -n 100 --no-pager
systemctl restart frpc-qwen-singapore.service
```

新加坡验证隧道：

```bash
curl http://127.0.0.1:18000/v1/models
```

GPU 机器验证 vLLM：

```bash
curl http://127.0.0.1:8000/v1/models
```

## 安全说明

- 不要把新加坡的 `18000` 直接暴露公网。
- 保持新加坡 `frps.toml` 里的 `proxyBindAddr = "127.0.0.1"`。
- vLLM/Qwen 默认没有强鉴权，不应该裸露公网。
- 如果必须让其他机器访问新加坡的模型入口，请在前面加鉴权代理，例如 LiteLLM、nginx basic auth、API gateway 等。
- `FRP_TOKEN` 不要发到公开聊天、文档或仓库里。

## 和东京现有隧道的关系

这套新加坡隧道不会影响东京现有隧道。

东京已有：

```text
东京 frps-qwen.service
GPU frpc-qwen.service
东京 127.0.0.1:18000 -> GPU 127.0.0.1:8000
```

新加坡新增：

```text
新加坡 frps-qwen.service
GPU frpc-qwen-singapore.service
新加坡 127.0.0.1:18000 -> GPU 127.0.0.1:8000
```

GPU 机器可以同时运行多个 `frpc` 服务，分别连接东京、新加坡或其他公网服务器。只要每个服务使用不同的 systemd 名称和配置文件即可。

## 参数说明

新加坡 `install-frps-server.sh` 常用参数：

```bash
FRP_VERSION=0.61.1
FRP_DIR=/opt/frp
FRPS_BIND_PORT=7000
FRPS_PROXY_BIND_ADDR=127.0.0.1
FRP_TOKEN='your-token'
SERVICE_NAME=frps-qwen
```

GPU `install-frpc-gpu-client.sh` 常用参数：

```bash
FRP_VERSION=0.61.2
FRP_DIR=/opt/frp
FRPC_BIN=/usr/local/bin/frpc
FRPS_SERVER_ADDR='新加坡公网IP'
FRPS_SERVER_PORT=7000
FRP_TOKEN='your-token'
LOCAL_IP=127.0.0.1
LOCAL_PORT=8000
REMOTE_PORT=18000
PROXY_NAME=qwen-vllm
SERVICE_NAME=frpc-qwen-singapore
```

## 故障排查

如果新加坡 `curl http://127.0.0.1:18000/v1/models` 失败，按顺序检查：

1. GPU 机器 vLLM 是否正常：

```bash
curl http://127.0.0.1:8000/v1/models
```

2. GPU 机器 frpc 是否连上新加坡：

```bash
systemctl status frpc-qwen-singapore.service
journalctl -u frpc-qwen-singapore.service -n 100 --no-pager
```

3. 新加坡 frps 是否正常：

```bash
systemctl status frps-qwen.service
journalctl -u frps-qwen.service -n 100 --no-pager
```

4. 新加坡安全组是否放通 `7000/tcp` 给 GPU 机器。

5. 两边 `FRP_TOKEN` 是否一致。

6. 新加坡是否监听了本机 `18000`：

```bash
ss -ltnp | grep 18000
```
