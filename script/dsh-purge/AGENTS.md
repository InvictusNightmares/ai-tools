# dsh-purge 本地维护

- 本目录保留原版 1.1.47 的历史基线；先读 `MAINTENANCE.md`。当前社区版维护源是 `../dsh-purge-community`。上游 README 保留原文，版本和 profile 示例可能不适用于本机。
- `upstream.json` 记录导入基线及原文件哈希，不随本地修改重写；更换上游基线时明确记录版本、来源和差异。
- 保留原作者署名、LICENSE 和上游来源；本地行为修改使用可区分的版本并更新维护记录。
- 不把 Downloads、`~/.dsh/plugins` 或 profile 下的 `node_modules` 当作源码修改位置。
- `scripts/local-install-desktop.sh --install` 只安装或更新 desktop 的依赖，保留 bundle 选择；插件已启用时先停止，避免自动执行宿主补丁。
- 安装、启用、宿主补丁应用和实际会话验证是不同阶段。不要把安装成功或静态匹配结果写成运行验收通过。
- 修改补丁前读取当前目标版本源码，在临时副本复现；禁止用 `skipped` 或跳过版本检查掩盖不兼容。
- 检查 ASAR 内补丁时先解到临时目录；本插件的 `hostFs` 对 ASAR 路径使用真实磁盘访问，直接检查归档路径会产生假缺失。
- 改 `lib/redteam/client.js` 后运行 `node scripts/build-client.mjs`，同时检查生成的 `client.js`。
- 不提交本机 `.dsh`、凭据、会话、补丁备份、宿主安装包或解包目录。
