# dsh-purge 在 ai-tools 中的维护

这里是本项目后续修改、修复和更新 dsh-purge 的源码位置。原作者的 `README.md`、`README.zh-CN.md` 和 `LICENSE` 保持原样；本机安装和维护以本文为准。

## 导入来源

| 项目 | 值 |
| --- | --- |
| 导入日期 | 2026-10-21 |
| 原包 | 下载目录中的 `dsh-purge.zip`，与解压目录逐文件核对一致 |
| 上游版本 | 1.1.47 |
| 上游目标宿主 | 0.2.0-rc.2 |
| 原仓库 | <https://github.com/YuJunZhiXue/dsh-purge> |
| 原 ZIP SHA-256 | `d587e51e73b93d38087ee707c9f487f6594abf2d53ac4bffb2d7eecce46efbd0` |

`upstream.json` 保存原始 102 个文件的 SHA-256。导入时没有修改插件运行代码。上游 GitHub 仓库和 npm 同名包在 2026-10-21 的实时查询中均返回 404；这是当次检查结果，不表示永久不可用。

## 本机状态与兼容边界

- 宿主：macOS 官方 DeepSeek Harness `0.2.1-rc.2`，profile 是 `desktop`。上游旧 README 中的 `default` 示例不适用于这台机器。
- 插件已安装，保持未选入 `dsh.profile.bundles`，因此尚未启用；没有应用宿主补丁。
- 后续安装依赖指向本项目目录；修改源码后运行下面的同步命令，不能仅凭源码文件已修改就认为桌面端已更新。
- 插件 `lib/index.js` 的启动逻辑会调用 `settleInstalledPatches()`，可能改写宿主文件并触发重启，启用前必须单独核对。
- 在当前宿主的临时解包副本上，静态检查得到 `pending: 47`、`applied: 7`、`na: 7`、`skipped: 4`。这些是插件匹配器的状态标签，不是实际应用补丁或会话验收结果。
- 第 40 项 `COMPLETE_PROMPT_KEEP_INJECT` 未匹配，且上游没有将它标记为 optional；尚未修复。完整结果见 `docs/local-compatibility-2026-10-21.json`。

## 安装与同步到桌面版

从 ai-tools 根目录运行：

```sh
# 只读查看项目源码、安装版本和启用状态
bash script/dsh-purge/scripts/local-install-desktop.sh --status

# 安装或重新同步项目中的源码，保持未启用
bash script/dsh-purge/scripts/local-install-desktop.sh --install
```

脚本使用 `/Applications/DeepSeek Harness.app` 自带的 Node、pnpm 和插件管理接口，执行兼容检查并持有 profile 文件锁。它使用 `DSH_HOME`（未设置时为 `~/.dsh`）下的 `profiles/desktop`，不会创建其他 profile。

同步前会备份 `package.json`、`pnpm-lock.yaml` 和 `pnpm-workspace.yaml` 到 profile 的 `.plugin-manager/backups/dsh-purge-*`。脚本只接受已停用的 dsh-purge，保留其他依赖和 bundle 选择，使用离线模式并禁用安装脚本。离线依赖缺失时应检查具体错误，不要绕过兼容检查或自动转成启用安装。

此次原本位于 `~/.dsh/plugins/dsh-purge` 的副本保留作旧安装来源，项目中的代码才是后续维护源。脚本成功后用 `--status` 核对安装路径和版本。

## 后续维护流程

1. 在本目录修改源码。先修复并验证当前宿主兼容问题，再决定是否启用；本次导入不包含第 40 项补丁修复。
2. 行为发生变化时使用可区分的本地版本，并同步 `package.json` 和发布说明。不要覆盖原始 `upstream.json` 基线来隐藏本地差异。
3. 对改动文件运行 `node --check`。客户端源变更还要运行 `node scripts/build-client.mjs`，检查生成文件；补丁修复需要在当前宿主的临时副本上验证，并补有意义的回归用例。
4. 停用插件后执行 `--install`，核对版本和安装内容。启用、自动补丁应用和实际桌面会话验证另行记录，不以安装返回 0 代替。
5. 若上游恢复，先获取明确版本到独立临时目录，比较来源、许可证、安装脚本、宿主版本要求和本地差异，再合并。不要直接覆盖本目录或桌面运行目录。

按用户要求，后续在项目内维护和修复，不设置定时任务，也不自动拉取或应用上游更新。

## 本地维护记录

- 2026-10-21：导入 1.1.47 原始源码及文件哈希；增加本机同步脚本、接手规则和兼容状态记录。插件代码未修复，保持未启用。
