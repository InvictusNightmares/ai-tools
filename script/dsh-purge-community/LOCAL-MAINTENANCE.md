# dsh-purge-community 本机维护

本目录是用户指定的 [kingcharleslzy-ai/dsh-purge](https://github.com/kingcharleslzy-ai/dsh-purge) 社区版源码，作为后续在 ai-tools 中手动维护和修复的位置。原版 `../dsh-purge` 保留为 1.1.47 历史基线。

## 来源

- 导入日期：2026-10-22；版本：`1.6.41`；标签：`v1.6.41`。
- `upstream.json` 记录源码归档、发行 TGZ 的 SHA-256，以及 326 个上游文件的原始哈希；不要随本地修改重写基线。
- 本机安装的是 GitHub Release TGZ，已同时核对 `SHA256SUMS.txt` 和 GitHub release asset digest。206 个发行文件与本目录源码、实际安装文件逐一一致。
- 上游代码、README、AGENTS、LICENSE 和署名保持原样。本机状态和额外维护约定以本文及安装记录为准；上游文档中的验收结论不能代替本机验证。

## 2026-10-22 安装结果

- 宿主：`/Applications/DeepSeek Harness.app`，版本 `0.2.1-rc.2`；profile：`~/.dsh/profiles/desktop`。
- 安装包名：`dsh-purge-community@1.6.41`；已加入 `dsh.profile.bundles`。原版 `dsh-purge` 在本次安装前已不在 desktop 依赖中。
- 依赖指向持久发行包 `~/.dsh/dsh-purge-community/pkgs/dsh-purge-community-1.6.41.tgz`。本目录是维护源码，不是运行时软链接；修改源码后需重新打包并安装，不能认为文件修改会即时生效。
- 安装器创建了 `Resources/app/runtime -> ../runtime`，补齐当前解包布局所需的 pnpm 路径。
- 修复了 `Resources/runtime/cli/bin/dsh`：有 `app.asar` 时沿用归档，归档不存在时使用 `app`。`dsh --version` 和 desktop 插件列表均验证通过。
- 宿主 `Resources/app` 内 18,365 个普通文件与安装前逐一核对无变化；其余插件依赖和 bundle 选择保持一致。
- 按用户的手动维护要求，`~/.dsh/dsh-purge/update-preferences.json` 中 `autoCheck` 和 `autoInstall` 均为 `false`；不添加定时任务。

安装器快照：`~/.dsh/dsh-purge-community/backups/2026-10-22T01-33-30-883Z-f4479e6f`。额外的 profile 配置及原 CLI 启动器备份：`~/.dsh/dsh-purge-community/manual-backups/20261022-093315-before-1.6.41`。备份仅存本机，不提交到项目。

## 验收边界

本次执行了安装和只读诊断，没有应用社区版宿主补丁，也没有退出或重启桌面应用。需要用户方便时完整退出并重开，才能确认界面加载；安装成功不代表实际会话功能全部通过。

`selfcheck` 返回 `broken`，当前宿主含此前的旧版补丁。进一步 `diagnose` 检查了 80 项：必需补丁锚点没有漂移，两处可选项 `#56`、`#84` 不匹配，`#88` 依赖待应用的 `#87`；另有 `#71` 目标缺失、权限状态未知及多项待应用。不能把这些状态写成全绿，也不能据此直接改权限或强行重锚。完整摘要见 `docs/local-desktop-install-2026-10-22.json`。

`host-status` 在独立 CLI 中返回 `unknown_runtime`，未证明运行中的桌面进程已加载新版。后续应用补丁与真实会话验证单独记录。

## 手动维护

先查看实际安装状态：

```sh
dsh --version
dsh plugin --profile desktop list
```

重新安装已核验的同版本发行包时，从本目录执行：

```sh
sh scripts/install.sh --profile=desktop --version=1.6.41 \
  --archive="$HOME/.dsh/dsh-purge-community/pkgs/dsh-purge-community-1.6.41.tgz" \
  --sha256=53fd0c14990b23effd4bce50a8e33b9061ce57005444e704fadbb0d8e8032185 \
  --dry-run
# 核对结果后去掉 --dry-run 才安装；安装器会备份，但不会 apply 或重启。
```

更新上游时先在独立目录下载明确版本，核对来源、摘要、宿主要求和本地差异，再合并。修改本地运行行为时采用可区分的版本，运行相关回归测试并生成发行包，再用安装器的 `--archive`、`--sha256` 和 `--version` 安装。安装包版本和仓库身份必须匹配，不能跳过校验。

修改补丁前，先在当前宿主的临时副本复现和验证；不要直接编辑运行目录或用 `skipped` 掩盖不兼容。客户端构建和测试遵循本版本的 `package.json`，源码中的 `packages/` 与 `test/` 均已保留。
