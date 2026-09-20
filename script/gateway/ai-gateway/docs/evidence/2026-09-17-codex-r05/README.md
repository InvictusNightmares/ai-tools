# R05：Codex CLI 0.146.0超时排查

状态：未解决；没有修改用户客户端或网关。2026-09-17两地仍为release v31。

用户报告夏斯建在15点多使用Windows Codex CLI 0.146.0、4005、auto、xhigh、Responses且WebSocket开启时超时；先提示缺auto模型元数据，再从WebSocket降为HTTP并继续重试。截图其他配置含凭据，不复制进仓库。

维护映射为美西Key77，查询时有效且未过期；最近直接Sub2API成功记录为14:55:14，UA为Windows `codex-tui/0.146.0`。查询窗口未在4005 Auto/Guard发现其15点后的请求，不能据此判断用户没有发送，也不能单凭健康端点通就排除进程代理、认证或配置路径差异。用户已确认其电脑能访问health；不再把私网不通作为已证实结论。

## 同版原生对照

隔离下载官方0.146.0 macOS arm64版，以独立临时配置匹配auto/xhigh/100万上下文/90万压缩阈值、API Key认证及4005 Responses，分别启用和禁用WebSocket。通过原生app-server执行合成短请求；没有覆盖现有0.154.0安装。两组均出现相同auto元数据警告，但业务成功，不能把警告本身当作这次超时的充分原因。

| 方式 | 耗时 | 结果 | 网关业务request ID |
| --- | --- | --- | --- |
| WebSocket | 8.73秒 | 预期内容正确，DeepSeek，200 | `651376c32761d8c716db959bb8a2676a` |
| HTTP/SSE | 6.35秒 | 预期内容正确，DeepSeek，200 | `28af11ed0e79429870996959b7b07e49` |

WebSocket预热request ID为 `cec9db91f7cc48559c69226c02f76eba`。原始合成验收结果分别在本机 `/private/tmp/gateway-r05-native-us-websocket-151927/result.json`、`/private/tmp/gateway-r05-native-us-http-151949/result.json`，临时认证文件验收后移除。

本结果证明同版客户端在本机能完成4005两种传输；不是Windows本人环境通过，也不是其原会话恢复。已提出只在同一PowerShell终端追加192.168.64.16到NO_PROXY后重新启动Codex的对照，尚无返回结果，不能宣称代理已确认为根因。后续需按本人新尝试时间关联入口日志或取得客户端脱敏错误；不要求发送Key，不关闭既有WebSocket能力。
