# PerkRadar 与青龙飞书私聊推送

PerkRadar 常驻独立容器；青龙用 `*/15 * * * *` 全天触发一次完整采集，采集完成后将未推送的优惠发送给已有飞书个人机器人。没有新增时不发消息。不是每日汇总，也不依赖浏览器或本地电脑在线。

## 文件与部署

- `compose.yaml`：以固定上游提交 `2688cc5c396b318c4b2b151b98c0153b8bc514e0` 构建；从相邻 `source/` 目录读取源码，数据保存在相邻 `data/`。只绑定回环地址，并接入青龙现有 Docker 网络。`feed-egress` 是仅供指定 RSS 使用的网络辅助容器。
- `perkradar_notify.js`：采集、筛选、持久化去重和发送队列。
- `perkradar_feishu.js`：使用专用飞书应用和接收人，也兼容青龙已有的共享通知配置。
- `perkradar_notify.test.js`：去重、重试、部分失败和并发行为测试。

私密 `.env` 放在实际部署目录，不加入版本控制，权限设为 `0600`，包含 `PERKRADAR_ACCESS_TOKEN`（至少 32 位随机字符）和 `PERKRADAR_NETWORK`（青龙现有 Docker 网络名）。构建阶段使用主机网络下载官方 npm 依赖，运行时仍使用独立容器网络。`DISABLE_SCHEDULER=1` 只关闭上游内置定时器，采集由青龙统一调度，避免两套定时器重复触发。

小众软件与异次元 RSS 使用已授权的现有代理出口。辅助容器复用采集器基础镜像，挂载已有 Mihomo 二进制和私密配置，不发布宿主端口。私密 `.env` 还需设置 `PERKRADAR_FEED_PROXY_URL`、`PERKRADAR_FEED_PROXY_PORT`、`PERKRADAR_PROXY_BINARY` 和 `PERKRADAR_PROXY_CONFIG`。真实地址、路径、端口与凭据只保存在部署端。

辅助代理配置须启用认证，只允许 `www.appinn.com`、`www.iplaysoft.com`、`feed.iplaysoft.com` 走既有出口，末尾使用 `MATCH,REJECT`。配置文件只读挂载，并仅向容器运行用户开放读取；其余五个来源和内部健康请求通过 `NO_PROXY` 保持原有路径。替换上游代理凭据时同步更新这份私密配置。采集器使用 Node 22.21+ 的[原生环境代理支持](https://nodejs.org/download/release/v22.23.0/docs/api/cli.html#node_use_env_proxy1)，保持官方源代码与来源地址。

容器网络若要求使用宿主提供的出网中继，在辅助配置中通过 `dialer-proxy` 连接该既有中继，再连接已授权的上游节点。不要为此放宽主机转发规则；先分别验证容器能否连接中继和抓取指定 RSS。中继地址与上游节点配置同样只保存在私密文件中。

```sh
docker compose build web
docker compose up -d
```

上线验收须分别核对两个 RSS 的有效内容、其他来源的绕行规则、辅助代理认证和拒绝规则，再检查青龙完整采集与去重推送；进程健康不能代替这些检查。

将两个运行脚本放入同一个青龙脚本目录。运行环境需要支持 `node:sqlite` 的 Node.js。青龙任务命令为 `task perkradar_notify.js`。私密配置示例：

```json
{
  "baseUrl": "http://<collector-service>:<container-port>",
  "accessToken": "<random-access-token>",
  "stateFile": "<persistent-config-dir>/perkradar-notify/state.sqlite",
  "includeOther": false,
  "messageBytes": 7000
}
```

通过 `PERKRADAR_NOTIFY_CONFIG` 指定该文件路径；未设置时使用脚本中的青龙默认位置。配置权限为 `0600`。专用机器人在该私密 JSON 中增加 `feishu` 对象，字段为 `appId`、`appSecret`、`openId`；Open ID 必须属于这个新应用。凭据不加入版本控制或日志。

未配置 `feishu` 时，兼容原有环境变量 `QL_FEISHU_APP_ID`、`QL_FEISHU_APP_SECRET`、`QL_FEISHU_OPEN_ID`。配置了专用机器人但字段不完整时任务报错，不退回共享机器人。切换机器人前确认没有未确认的旧消息，保留原去重数据库；原机器人已经推送的优惠不会因更换机器人重新发送。其他任务的共享飞书环境变量不需要更改。

## 推送行为

首次运行发送当前在架且符合筛选条件的条目，较多时分批发送。之后按规范化原文链接去重，忽略常见跟踪参数和锚点；同一链接改标题不会再次推送。去重状态持久保存在独立 SQLite 文件中，重启容器和青龙不会重置。

默认不推送上游标题规则归为“其他”的条目；设 `includeOther: true` 可包含这些线索，但也会增加闲聊、求购和推广。已明确过期的条目不推送。上游分类和发布时间不代表已经核实优惠真实、仍可领取，也无法保证覆盖所有平台或即时更新。

发送前先落盘消息和稳定 UUID，飞书确认消息 ID 后才记为已发送。暂时失败保留队列；结果不确定时，55 分钟内使用相同 UUID 重试，利用飞书一小时的消息幂等窗口。超过窗口则标为 `uncertain`，不自动重发，任务日志提示人工核对，以避免重复通知。人工核对前不要删除数据库或重建相关记录。

部分来源失败时仍推送其他来源有效线索，并注明不可用来源；全部失败时任务报错，不把缓存当成本轮成功采集。单实例租约防止并发发送。没有新增不发送常规空报告。

## 验证与维护

```sh
node --test perkradar_notify.test.js
node perkradar_notify.js --dry-run
node perkradar_notify.js --no-refresh
```

`--dry-run` 只读取现有看板并报告可推送数量，不发送、不预占条目；`--no-refresh` 不重新采集，但会发送尚未推送的条目，不能当作只读命令。正常任务不带参数。实际验收需检查采集来源状态、飞书返回的消息 ID、第二次运行发送数量为零，以及青龙任务已启用；健康检查成功仅说明 API 和数据库可用。

停用时先禁用青龙任务，再停止采集器与辅助容器；保留采集数据目录、私密配置和推送状态数据库。升级前备份这些数据及专用网络配置，并重新核对上游 API、分类和调度行为。只恢复采集库而丢失推送状态可能导致旧内容重新发送。

上游：[PerkRadar](https://github.com/luobinger/PerkRadar)。飞书幂等字段参见[官方发送消息接口](https://open.feishu.cn/document/server-docs/im-v1/message/create)。
