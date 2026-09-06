# Agentbox site-check

从 DMIT 的 `/root/site-check` 迁移 `playwright-core` 1.62.1 及其锁文件，为 Agentbox 补上可重复执行的公共网站环境检测入口。DMIT 原目录没有独立检测脚本；迁移保留该依赖环境，新增入口通过 Node 原生 WebSocket 直接使用 Chrome DevTools Protocol。

直接 CDP 采集是为了保留浏览器实际环境：Playwright 1.62.1 连接 Headless Chrome 时会设置默认字体，`noDefaults` 并不跳过该操作。本入口不设置时区、locale、UA、字体、视口或 WebRTC 模拟；浏览器启动仅沿用已部署 `client.env` 中的 7898 代理和语言参数。截图裁取不改变浏览器视口。

## 检测目标

- [Net.Coffee Claude AI IP 检测](https://ip.net.coffee/claude/)：页面自动运行，检查实际出口、页面信任评分、DNS/UDP 和设备信息。
- [Fuck Claude](https://fuck-claude.vercel.app/)：点击页面的 Start scan，等待实际完成标记，保留各项浏览器环境结果。

这两个网站的评分属于各自检测逻辑，不是 Anthropic 的官方风控结论，也不证明 Claude 账号或 Claude Code 可以登录。检测失败、接口失败及超时需在报告中保留，不能把 HTTP 200、截图保存成功或加载中的初始分数当作完成。

## 部署

宿主机复用既有 Docker 和 `/srv/agentbox/headless-chrome`，不再安装 Node/Chromium，不发布额外端口。检测容器只连接内部 `agentbox-browser` 网络，与常驻浏览器共用本机 `agentbox-chrome-us:v2.56.2-1` 定制镜像中的 Node；真实网页仍由云电脑的 Chrome 通过 7898 访问。

Compose 固定已验收镜像的摘要，并设置 `pull_policy: never`，缺少该本机镜像时直接失败。首次部署前先按 [US environment](../us-environment/README.md) 构建浏览器镜像；重新构建后，通过 `docker image inspect` 核对实际摘要并更新检测 Compose。网站检测仅临时创建容器，退出后自动删除；日常保留保活、定制浏览器两个镜像即可。原版 Browserless 镜像用于构建定制版，构建及验收完成后可删除其独立镜像引用，共享层仍由定制镜像保留。

运行目录：

```text
/srv/agentbox/site-check/
  compose.yaml
  app/
    check.mjs
    cdp.mjs
    completion.mjs
    test-completion.mjs
    package.json
    package-lock.json
    node_modules/          # DMIT 原有 Playwright 环境
  output/                  # root:root，0750
```

`app` 与配置归 root 管理、只读挂载。管理员从 DMIT 仅复制 `package.json`、`package-lock.json`、`node_modules`，再加入本目录入口文件；上传包需核对 SHA256 后安装。不得复制 DMIT 其他服务配置、账号或浏览器历史。以后需要重建依赖时，在独立暂存目录执行 `npm ci --ignore-scripts --omit=dev`，使用仓库锁文件，不运行 `npm update`。

容器从既有 `/srv/agentbox/headless-chrome/client.env` 读取 Browserless token；不要运行会展开秘密的 `docker compose config`（可用 `config --quiet`），不要打印容器完整环境或完整连接 URL。token 不进入网页，不写入检测结果。

将 `manage.sh` 安装为 root 所有的 `/usr/local/bin/site-check`，模式 0755。入口只允许 `run` 和 `inspect`，用 `flock` 防止重叠检测。检测入口容器为 UID/GID 0，仅拥有检测输出目录的写权限、根文件系统只读、无 capabilities、无 Docker socket；退出即删除容器。

## 使用与证据

在云电脑管理员终端执行：

```sh
site-check
```

通过 `ssh ctyun` 以 root 执行管理命令。如需先查看页面结构而不点击 Fuck Claude 的扫描按钮，用 `site-check inspect`；此模式只表示采集完成，不判定检测通过。宿主机不再创建 agent 账号，SSH 始终只接受密钥。

每次生成独立 UTC 时间戳目录，打印 `report.json` 的绝对路径。目录包含原始页面文字、页面结构、视口与整页截图，以及实际浏览器语言、时区、UA、网络请求失败信息。凭据不放入输出。使用现有密钥 SSH 下载该目录即可查看。

保留用户需要的检测报告；清理上传包、安装脚本和临时日志。`output` 是用户请求的检测结果，不应当作安装垃圾自动删除。

## 验证

语法检查：`npm run check`；完成判定测试：`npm test`。迁移验收需在云电脑实际执行 `site-check inspect`、`site-check run`，检查两个页面最终结果和截图，确认原有 Chrome/代理/Tailscale/SSH 仍正常。完成标记不匹配或超时的 `run` 必须非零退出。
