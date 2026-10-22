# 东京 4000 HTTPS 切换记录

2026-10-22 已将 GPU 到东京的链路切为 TLS，客户端仍使用 `http://192.168.64.16:4000`。东京应用、PostgreSQL、Redis 未重启；原夜间 API 限制及 Key 例外文件保持不变。

## 当前链路

客户端 HTTP 4000 → GPU `tokyo-sub2api-proxy` → HTTPS `106.14.254.110:9881` → GA TCP 透传 → 东京 ECS 8080 HTTPS → Sub2API。

| 项目 | 当前值 |
| --- | --- |
| GA 监听名称 | 张成日本端口 |
| 监听协议 / 端口 | TCP / 9881 |
| 监听 ID | `lsr-bp1el7bn9mpimtnc626sk` |
| 节点组名称 | 张成日本服务器 |
| 节点组 ID | `epg-bp141aso0vwk4qggq6gv9` |
| 回源 | 原 ECS `i-6we9by265zzaynk1dz9k`，日本（东京） |
| 端口映射 | 9881 → 8080 |
| 权重 / 流量 | 255 / 100% |
| 客户端亲和性 / 保持客户端源 IP | 关闭 / 不保持 |
| TCP 连接空闲超时 | 900 秒 |
| 健康检查 | TCP 8080，间隔 2 秒，阈值 3 次 |

本次使用原 ECS 作为回源，未更改安全组；GA 健康检查及 GPU 经 GA 的实际请求均通过。旧 HTTP 9881 监听和旧节点组已按确认删除重建。

## 服务器配置

东京配置源为 `/opt/sub2api-deploy/docker-compose.yml` 和 `/opt/sub2api-deploy/gateway/nginx.conf`，代理容器为 `sub2api-proxy`。外部 8080 只接收 HTTPS，支持 TLS 1.2/1.3；HTTP 请求返回 400。容器健康检查使用 `curl --cacert` 请求本机 HTTPS `/health`。

证书目录 `/opt/sub2api-deploy/gateway/tls` 以只读方式挂载。固定 TLS 名称为 `qiyuan-tokyo-gateway.internal`，服务器证书到期时间为 2027-11-23 14:09:46（Asia/Shanghai）。CA 私钥保留在本次运维备份的 `ca-private/` 目录中，仅 root 可读，不挂载到容器、不分发到 GPU。

GPU 配置为 `/data/tokyo-sub2api-proxy/nginx.conf`，CA 公钥为 `/data/tokyo-sub2api-proxy/tls/ca.crt`，以只读目录挂载到 `/etc/nginx/tls`。开启 `proxy_ssl_verify on`、SNI 和固定证书名称校验；请求/响应缓冲仍为 `off`，原鉴权头转发、200 MB 正文限制及 3600 秒读写超时保持不变。

## 本次验收

- 两端候选配置通过 `nginx -t`，东京 Compose 校验通过。
- GPU 4000 本机和内网地址的 `/health` 返回 200；经 GA 的无 Key `/v1/responses` 返回 401。
- 东京 `/health`、`/api/v1/settings/public`、`/admin/settings` 返回 200，代理容器为 healthy。
- GPU 隔离候选使用错误 TLS 名称时被 Nginx 拒绝；东京明文 HTTP 及错误证书名称也被拒绝。
- 430,337 字节、2,300,000 字节和 2,300,000 字节分块上传，通过正式 4000 的 `/api/v1/auth/login` 返回预期的缺少 Email/Password 字段错误。合成正文只含填充字段，没有账号、密码或 API Key。
- 对照请求故意删除 JSON 最后的闭合括号，收到 `unexpected EOF`，与完整正文的字段校验错误可区分。本次未调用推理模型。
- 东京应用、PostgreSQL、Redis 的容器 ID 和启动时间未变；GPU 其他原有容器未变化。

以上验证代理、证书和正文传输。真实 Codex 长会话的持续稳定性仍需客户端验证。

## 备份与回退

- 东京：`/opt/sub2api-deploy/ops/https-8080/20261022-140945/`，包含原配置、Compose、受限 Key 例外文件备份、证书及 `manifest.json`。目录仅 root 可访问。
- GPU：`/data/tokyo-sub2api-proxy/ops/https-upstream/20261022-141705/`，包含原配置、原容器信息、CA、候选验证及 `manifest.json`。
- GPU 原代理已停止并保留：`tokyo-sub2api-proxy-before-https-20261022-141705`。

两台服务器的运维目录中均保留 `ga-before.json`、`ga-after.json`、`upload-public-validation.json` 和本记录副本。服务器证书续期时需要保留固定 TLS 名称，并重新验证 CA 信任。

回退脚本会检查实例和文件状态，拒绝覆盖后续发生的配置漂移。退回原 HTTP 配置需要在维护窗口协调两端，以下命令仅作记录：

```sh
# 在东京执行
python3 /opt/sub2api-deploy/ops/https-8080/20261022-140945/manage_origin_https.py rollback /opt/sub2api-deploy/ops/https-8080/20261022-140945/manifest.json

# 在 GPU 执行
python3 /data/tokyo-sub2api-proxy/ops/https-upstream/20261022-141705/manage_https_upstream.py rollback /data/tokyo-sub2api-proxy/ops/https-upstream/20261022-141705/manifest.json
```
