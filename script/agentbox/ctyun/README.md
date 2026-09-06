# Agentbox 平台保活

在 Agentbox 上构建并运行经过限定的 [CtYun](https://github.com/leleji/CtYun) 保活客户端。上游固定为 `975f0cb85780e135e620d851d943a7ab65e5021e`，保留 MIT 许可；本目录只维护运行入口、固定源码转换和部署配置。它补充 Debian 防休眠，不能在云平台已关闭整台虚拟机后自行唤醒。

## 运行约束

- 一个账号只允许连接 `accounts.json` 指定的一个 DesktopId；列表无匹配、重复匹配或连接返回 ID 不符均拒绝。当前 Agentbox 的授权目标是 `23698108`，安装时必须核对。
- 按天翼官方客户端顺序先校验一字节代理确认，再完成 SPICE 链接和认证；按声明长度读取有界字节流，支持跨 WebSocket 消息拆包、合包。 链接、认证及业务消息是不同记录，格式参见 [SPICE 协议](https://www.spice-space.org/spice-protocol.html)。
- 每 60 秒重新获取目标连接信息并建立 WebSocket。只有收到服务端完整 103 帧并发送用户信息响应后才报告握手成功；容器运行或 API 返回成功本身不算保活验收。
- 登录及短信验证码由人手动输入，不回显。没有 OCR、验证码第三方上传或后台自动尝试登录。登录/API/WebSocket 均保留 TLS 验证并禁止 HTTP 自动重定向。
- 账号密码、固定设备码和登录会话存于私密 `/data`，不放到镜像、环境变量或日志。会话绑定账号和设备码，后台及重启复用。平台使会话失效后，需执行人工登录命令重新认证；不能承诺永远无需人工。
- 登录和后台进程互斥。`agentbox-ctyun login` 实际执行停止后台、交互登录、成功后启动；登录失败时保持停止，修正后重试该命令，或确定旧会话仍有效时显式 `start`。
- 容器无宿主机端口、无 Docker socket、无额外 capability，根文件系统只读。使用既有 `agentbox-egress` 网络和 7898 出口，Docker 拉镜像仍用宿主机既有 7897 配置。

## 构建

在实体电脑从仓库根目录准备构建包（Python 3、Git；不读取任何凭据）：

```sh
python3 script/agentbox/ctyun/prepare-build.py --output /tmp/agentbox-ctyun-build --archive
```

可通过 `--upstream /path/to/CtYun` 使用已有 Git 对象，始终读取固定 commit，不采用工作区改动。输出目录和归档必须尚不存在。归档用 Python 生成，不携带 macOS AppleDouble 元数据；生成上下文还会排除 `._*`。输出含每个源码文件的 SHA256 清单。SDK 和 runtime 也固定到 Microsoft 官方 `linux/amd64` 镜像摘要，编译步骤禁止联网，不安装第三方 NuGet 包。

将构建包经已经验证的密钥 SSH 上传到云电脑。管理员先复制到 root 私有目录并核对本机构建命令输出的 SHA256，再解压及构建：

```sh
docker build --progress=plain -t agentbox-ctyun:975f0cb-agentbox2 /root/agentbox-ctyun-build
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges agentbox-ctyun:975f0cb-agentbox2 self-test
```

镜像构建自动运行测试，包含单目标选择、无效 ID、错误/截断协议帧、全零尾部填充和一个真实 loopback 跨源 302 WebSocket 拒绝测试。该测试不连接天翼平台。

## 安装配置

宿主机只使用 root 管理账号；容器内部 UID/GID 1654 是服务身份，不依赖宿主机 agent 账号。

在管理员终端安装本目录已核验的 `compose.yaml` 和 `manage.sh`：

```sh
install -d -o root -g root -m 0755 /srv/agentbox/ctyun
install -d -o 1654 -g 1654 -m 0700 /srv/agentbox/ctyun/data
install -d -o 1654 -g 1654 -m 0750 /srv/agentbox/ctyun/challenges
install -o root -g root -m 0644 compose.yaml /srv/agentbox/ctyun/compose.yaml
install -o root -g root -m 0755 manage.sh /usr/local/sbin/agentbox-ctyun
```

在本机私密 `pas.yaml` 增加 `ctyun_user` 和 `ctyun_pass`，分别填天翼平台账号和密码。不要把值发到聊天；不要混用已有 Windows/Alpine 密码或 Tailscale key。实体电脑需有 PyYAML，然后执行：

```sh
python3 script/agentbox/ctyun/prepare-config.py --desktop-id 23698108
```

它只读取上述两个明确字段，输出到 Git 忽略的 `.agentbox-staging/ctyun/accounts.json`（0600）。通过已验证的密钥 SSH 私密上传该文件；管理员安装后删除上传副本：

```sh
install -o 1654 -g 1654 -m 0600 /root/accounts.json /srv/agentbox/ctyun/data/accounts.json
rm /root/accounts.json
agentbox-ctyun check
```

安装时另用本地 JSON 解析只检查 `DesktopId == "23698108"` 和 `KeepAliveSeconds == 60`，不要输出账号或密码。没有凭据或未完成初次登录时，不启动后台容器。

## 人工登录与后台运行

在保留的云电脑管理员终端执行：

```sh
agentbox-ctyun login
```

看到 `HUMAN_CAPTCHA_REQUIRED` 时，把 `/srv/agentbox/ctyun/challenges/captcha.png` 经密钥 SSH 下载到实体电脑，由用户查看并在该终端输入；程序不会识别验证码。图像由容器内部 UID/GID 1654 持有，宿主机管理员通过 root SSH 读取，提交答案后自动删除。首次绑定可能需要短信验证码，同样由用户输入且不回显。不要把验证码或图片纳入持久日志/仓库，查看后删除本机临时图片。

`LOGIN_OK` 表示目标可见且会话已私密保存；管理命令随后启动后台。以下检查通过后才算部署完成：

```sh
agentbox-ctyun status
docker inspect --format '{{.State.Health.Status}}' agentbox-ctyun
docker inspect --format '{{.RestartCount}} {{.State.Running}} {{json .HostConfig.PortBindings}}' agentbox-ctyun
```

须观察至少三个 60 秒周期的 `KEEPALIVE_HANDSHAKE_OK target=23698108`，容器健康检查为 `healthy`，再重启容器验证复用会话无需登录，并确认原来的 Tailscale/SSH/代理/浏览器仍正常。暂时只有单目标协议握手证据，不代表平台永不关机；还需按主手册断开天翼客户端 2 小时和 26 小时验证。

## 清理与维护

验收后，删除本次上传的压缩包、构建上下文、编译日志、验证码图片与临时凭据副本。保留 `/srv/agentbox/ctyun/data` 中正在使用的账号、设备码和会话。它们是保活运行状态，删除会中断重启后的自动恢复。构建缓存和不用的 SDK 镜像需先核对只属于本次构建，再按具体镜像 ID 清理，不清理其他容器/卷。

`agentbox-ctyun status` 查看健康和脱敏日志；`stop` 停止保活，`start` 用已有会话启动。连续 `KEEPALIVE_RETRY` 时先检查代理和官方平台连通性；网络正常但会话过期时执行 `login`。不通过循环登录、短信或验证码自动识别绕过人工认证。
