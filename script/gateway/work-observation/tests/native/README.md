# 四原生客户端隔离验收

运行真实Codex 0.154.0、OpenCode 1.18.4、Claude Code 2.1.233、Hermes 0.21.0，使用独立临时配置和确定性回环上游。无生产Key、员工正文、外部模型或生产工具。驱动来源见`driver-provenance.json`，该清单是初始来源SHA，不是修改后驱动SHA。

```sh
python3 tests/native/codex_workflow.py --gateway-bin /绝对路径/observe --region isolated
python3 tests/native/opencode_workflow.py --gateway-bin /绝对路径/observe --region isolated
python3 tests/native/claude_workflow.py --gateway-bin /绝对路径/observe --region isolated
python3 tests/native/hermes_workflow.py --gateway-bin /绝对路径/observe --region isolated
python3 tests/native/codex_websocket.py --binary /绝对路径/observe
```

前三者从PATH寻找原生客户端；Hermes使用已隔离安装的`/private/tmp/gateway-hermes-20260916/.venv/bin/hermes`，迁移执行机时应修改为对应已验证安装，不要加载日常个人配置。WebSocket驱动需要Python websockets 16.0。`--gateway-bin`沿用原驱动参数名，实际传入独立采集器，不接Guard或Auto。

四端覆盖普通文件读取、多个工具、原生压缩及记忆恢复、子任务、取消恢复；Codex/OpenCode另含fork。图片通过各客户端原生输入送入，按上游收到的请求SHA核对字节一致，再检查采集记录仅有附件元数据、无图片负载，文本和工具标记保留。Hermes/OpenCode的隔离模型配置声明图片能力，避免客户端在发送前走其他视觉服务；不修改日常配置。

HTTP与WS分别运行。WS包含真实工具续接、取消、后续回答标记；未完成原生WS远端压缩与opaque状态组合验证。macOS通过不能替代夏斯建Windows现场故障闭环；确定性上游通过不能代表真实模型理解图片或完成开发任务的质量。

完整原始记录只写驱动打印的受限`RESULT_ROOT`。仓库证据保留结果、计数、版本和SHA。脚本检查失败返回非零；采集缺失、解析错误和元数据遗漏不得计为通过。Claude额外`/api/hello`由合成服务返回501，是单列的夹具探测结果。
