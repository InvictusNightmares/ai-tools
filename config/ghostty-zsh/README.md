# Ghostty 与 zsh 开发环境

这套配置用于 Apple Silicon Mac 的日常开发和 AI 编程工具：Ghostty 使用 One Dark Pro，zsh 提供补全、历史搜索、文件选择和项目跳转，非交互命令保持安静输出。它使用系统 zsh 和已有语言运行时，工具由 Homebrew 管理。

当前电脑已经配置完成。**仓库保存的是可复用模板，终端实际读取用户目录中的配置文件。** 修改本目录后，需要按下文同步到用户目录，再新开终端；本目录没有与用户配置建立符号链接。

- [文件与生效位置](#文件与生效位置)
- [常用快捷键](#常用快捷键)
- [找文件和搜索代码](#找文件和搜索代码)
- [切换项目](#切换项目)
- [配合 AI 编程工具](#配合-ai-编程工具)
- [配置详解](#配置详解)
- [安装与同步](#安装与同步)
- [备份的用途与当前状态](#备份的用途与当前状态)
- [检查与排错](#检查与排错)

## 文件与生效位置

本模板使用 Homebrew 的 `/opt/homebrew` 前缀和 Ghostty 1.4 的 macOS 默认配置位置。Intel Mac 或自定义配置目录需要先调整路径。

| 仓库文件 | 当前生效位置 | 内容 |
| --- | --- | --- |
| [Brewfile](Brewfile) | 通过 Homebrew 安装 | 9 个效率工具，不包含语言运行时和 AI CLI |
| [zsh/.zshenv](zsh/.zshenv) | `$HOME/.zshenv` | PATH 去重、补齐工具路径、沿用 Android SDK |
| [zsh/zprofile.snippet.zsh](zsh/zprofile.snippet.zsh) | 合并进 `$HOME/.zprofile` | Homebrew 登录初始化片段 |
| [zsh/.zshrc](zsh/.zshrc) | `$HOME/.zshrc` | 历史、补全、搜索、跳转、提示符和语法高亮 |
| [starship/starship.toml](starship/starship.toml) | `$HOME/.config/starship.toml` | 两行提示符和 One Dark Pro 配色 |
| [ghostty/config.ghostty](ghostty/config.ghostty) | `$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty` | 字号、主题、边距和 shell 集成 |
| [ghostty/themes/One Dark Pro](ghostty/themes/One%20Dark%20Pro) | `$HOME/.config/ghostty/themes/One Dark Pro` | 终端背景、文字、选择区域和 ANSI 色板 |

`.zprofile` 只提供公开的初始化片段。原文件中的私有环境设置、网络设置和其他开发配置应继续留在用户目录，不要用片段覆盖整个原文件。命令历史、本机日志和原配置备份也不放入仓库。

## 常用快捷键

下面的 zsh 快捷键在 shell 提示符处使用；进入 AI 工具、编辑器等全屏程序后，输入键由对应程序处理。

| 快捷键 | 用途 | 例子 |
| --- | --- | --- |
| `Tab` | 补全命令、路径和参数，支持文件名大小写匹配 | 输入 `cd con` 后按 `Tab` |
| `Ctrl-R` | 模糊搜索历史命令 | 输入 `git diff`，回车选中，再回车执行 |
| `Ctrl-T` | 选择文件并把路径插入当前命令行 | 输入 `bat `，再按 `Ctrl-T` |
| `Ctrl-/` | 在 `Ctrl-T` 文件选择器内开关内容预览 | 搜索文件时先看内容再选择 |
| 左 `Option-C` | 搜索当前目录下的子目录并进入 | 在项目根目录找到某个模块 |
| `→` | 光标在行末时接受灰色历史建议 | 输入以前用过的命令前缀 |
| `Ctrl-A` / `Ctrl-E` | 移到命令行开头 / 末尾 | 修改一条较长命令 |
| `Ctrl-U` / `Ctrl-K` | 删除光标前 / 后的内容 | 保留命令的一部分重新输入 |
| `Ctrl-W` | 删除光标前一个单词 | 改掉最后一个参数 |
| `Ctrl-C` | 取消当前输入或中断前台程序 | 停止运行中的测试或开发服务 |

左 Option 已映射为 Alt，因此这里的左 `Option-C` 就是 `Alt-C`。灰色建议来自本地命令历史。

Ghostty 的窗口快捷键沿用原生设置：

| 快捷键 | 用途 |
| --- | --- |
| `Cmd-T` | 新建标签页 |
| `Cmd-D` | 向右分屏 |
| `Cmd-Shift-D` | 向下分屏 |
| `Cmd-[` / `Cmd-]` | 切换到前一个 / 后一个分屏 |
| `Cmd-Shift-Enter` | 放大当前分屏，再按一次恢复 |
| `Cmd-↑` / `Cmd-↓` | 跳到前一处 / 后一处命令提示符 |
| `Cmd-Shift-,` | 重新加载 Ghostty 配置 |

## 找文件和搜索代码

`fd` 按文件名查找，`rg` 搜索文件内容。下面的命令都从当前目录开始。

```zsh
fd --type f login                  # 找文件名中包含 login 的文件
fd --type f -e ts -e tsx           # 找 TypeScript 文件
fd --type f -g '*test*'            # 用通配符找测试文件
rg -n 'login|auth' .               # 搜索代码内容，显示行号
rg -n 'TODO|FIXME' .               # 查找待办标记
rg -l 'useEffect' .                # 只列出包含该内容的文件名
```

想找到文件后直接阅读，可以这样操作：

1. 输入 `bat `，保留末尾空格。
2. 按 `Ctrl-T`，输入文件名关键词。
3. 按 `Ctrl-/` 打开或关闭预览；预览显示文件前 200 行。
4. 按回车选择文件，路径会自动插入命令行，含空格的路径也会被正确引用。
5. 再按回车运行 `bat`。如果进入分页阅读界面，按 `q` 退出。

`Ctrl-T` 的动作是插入路径，所以也能配合你已有的编辑器命令使用，例如先输入 `vim ` 再选文件。文件选择和历史搜索使用 [fzf 的 shell 快捷键](https://github.com/junegunn/fzf#key-bindings-for-command-line)。

### 隐藏文件与忽略规则

直接运行 `fd` 时默认跳过隐藏文件，并遵守项目的忽略规则。本配置的 `Ctrl-T` 已启用隐藏文件搜索，排除 `.git` 目录，同时仍遵守 `.gitignore` 等规则。[fd 官方说明](https://github.com/sharkdp/fd#hidden-and-ignored-files)

```zsh
fd --type f -H --exclude .git config   # 也查隐藏目录中的文件
fd --type f -HI --exclude .git config  # 也查被忽略的文件
```

第二条会扩大搜索范围，适合确实要找构建产物或被忽略文件的场景。

查看当前目录还有两个简写：

```zsh
ll       # 详细列表，包含隐藏项
lt       # 最多显示两层目录树
```

`ls`、`cat`、`cd` 保持系统原有行为。

## 切换项目

第一次进入项目使用普通 `cd`。zoxide 会记录访问过的目录，之后就可以按名称跳转。

```zsh
cd "$HOME/code/ai-tools"  # 首次进入项目
cd ~                     # 回到用户目录
z ai-tools               # 按名称跳回项目
zi                       # 从访问过的目录中交互选择
cd -                     # 返回上一个目录
```

多个项目名字相近时，用 `zi` 选择，或给 `z` 提供多个关键词。`z` 依赖本地访问记录；左 `Option-C` 搜索当前目录下的子目录。它们对应不同的查找范围。[zoxide 官方用法](https://github.com/ajeetdsouza/zoxide#getting-started)

## 配合 AI 编程工具

这套配置准备了终端环境和通用搜索工具。AI CLI 的安装、模型账号和认证由你使用的工具单独管理。

一个常用流程是：

1. 用 `z ai-tools` 进入项目根目录，或用 `cd` 进入实际要修改的子项目。
2. 按 `Cmd-D` 分屏。一侧启动已经安装的 AI CLI，另一侧执行搜索、测试和 Git 检查。
3. 让 AI 先定位相关代码、说明修改范围，再执行修改。
4. 修改后，在另一侧运行该项目已有的测试命令，并检查文件变化。

```zsh
git status --short        # 查看已修改和未跟踪的文件
rg -n '目标函数名' .       # 核对实现和调用位置
git diff --stat           # 查看已跟踪文件的改动规模
git diff                  # 阅读尚未暂存的具体差异
git diff --cached         # 阅读已暂存的差异
git diff --check          # 检查差异中的空白问题
```

`git diff` 不展示未跟踪文件；先用 `git status --short` 看全貌。运行测试时使用项目本身的命令，不假定每个项目都有 `npm test`。

可以直接交给 AI 的任务描述示例：

> 先用 rg 定位登录校验的实现和调用点，说明问题与修改范围。完成最小修复后，运行项目已有测试，列出改动文件和验证结果。

长输出时，使用 Ghostty 的 `Cmd-↑` / `Cmd-↓` 回到命令附近。复制多行命令到 shell 时，括号粘贴机制会先保留为输入，确认内容后再按回车执行。

## 配置详解

### 加载顺序与命令输出

| 阶段 | 文件 | 执行内容 |
| --- | --- | --- |
| zsh 环境初始化 | `.zshenv` | PATH 去重，补齐存在的工具目录，设置必要的 Android 环境 |
| 登录 shell | `.zprofile` | 运行 `brew shellenv zsh`，沿用原有私有设置 |
| 交互 shell | `.zshrc` | 配置历史；在终端 TTY 中加载交互功能 |

`.zshenv` 不启动外部命令，不打印欢迎语。它将缺失目录追加到 PATH，保留继承环境中的路径优先级；macOS 登录阶段仍按系统和 Homebrew 的规则初始化 PATH。已经设置的 `ANDROID_SDK_ROOT` 会被沿用，否则在标准 SDK 目录存在时使用它。

`.zshrc` 只有在交互模式、输入输出连接终端且 `TERM` 不是 `dumb` 时才加载插件。AI 执行 `zsh -c`、`zsh -lc` 等命令时不会收到交互提示符或欢迎语，也不会被全局强制彩色和分页设置干扰。

交互功能按下列顺序加载：原生补全、fzf、zoxide、历史建议、Starship、语法高亮。缺少某个工具时会跳过对应功能；语法高亮保持在插件初始化的最后。

### 命令历史

历史文件位于 `$HOME/.zsh_history`，安装时权限设置为 `600`，仅当前用户可读写。

- 内存历史和保存上限均为 100000 条。
- 多个窗口共享历史，搜索和保存时减少重复条目。
- 保存时间戳，方便按历史记录检索。
- 以空格开头的命令不进入保存的 zsh 历史；这项设置只管理 zsh 自身的历史文件。
- 自动建议只使用本地历史，不向模型服务发送命令。

### 提示符

Starship 使用两行提示符，第一行展示工作上下文，第二行留给命令输入。例如：

```text
ai-tools git:main !2 took 3s exit 1
>
```

| 内容 | 含义 |
| --- | --- |
| `ai-tools` | 当前目录，长路径会缩短 |
| `git:main` | 当前 Git 分支 |
| `!2` / `?2` / `+2` | 已修改 / 未跟踪 / 已暂存的状态计数 |
| `^2` / `v2` | 相对上游分支领先 / 落后的提交数 |
| `took 3s` | 命令耗时，达到 2 秒才显示 |
| `exit 1` | 上一条命令的非零退出状态 |

命令成功时输入符号为绿色，失败时为红色。提示符使用普通字符，无需安装 Nerd Font。目录扫描上限为 30 毫秒，提示符外部命令超时为 500 毫秒。[Starship 配置说明](https://starship.rs/config/)

### Ghostty 与 One Dark Pro

| 设置 | 值或行为 |
| --- | --- |
| 主题 | 固定 One Dark Pro 深色主题 |
| 背景 / 正文 | `#282c34` / `#abb2bf` |
| 选择背景 | `#41454e`，由官方透明选择色在背景上合成 |
| 字体 | Ghostty 默认字体，字号 14 |
| 水平 / 垂直边距 | 各 10 点 |
| 背景透明度 | 1，完全不透明 |
| Option | 左侧作为 Alt，右侧保留系统行为 |
| shell 集成 | 自动识别；开启光标、标题、Ghostty 命令路径功能 |
| 工作目录 | 开启新窗口目录继承；集成提供目录变化信息 |
| 关闭确认 | 保留运行中命令的关闭确认 |

16 个 ANSI 基础色对应 [One Dark Pro 官方终端配色](https://github.com/Binaryify/OneDark-Pro/blob/master/themes/OneDark-Pro.json)。fzf、提示符和 zsh 高亮使用相应配色；`Ctrl-T` 的 bat 预览使用终端 ANSI 主题。

Ghostty 自动注入 zsh 集成，不需要在 `.zshrc` 再手工加载一次。命令标记、目录继承等行为由这层集成提供。[Ghostty shell 集成说明](https://ghostty.org/docs/features/shell-integration)

## 安装与同步

### 安装工具

在仓库根目录执行。当前电脑已装好，无需重复安装。

```zsh
SHELL_CONFIG_DIR="$PWD/config/ghostty-zsh"
brew bundle install --no-upgrade --file="$SHELL_CONFIG_DIR/Brewfile"
```

`Brewfile` 包含 Starship、fzf、zoxide、ripgrep、fd、bat、eza、zsh-autosuggestions 和 zsh-syntax-highlighting。已有 `jq` 继续使用。

`--no-upgrade` 避免主动升级已安装工具；安装缺失工具所需的依赖仍可能由 Homebrew 更新。本清单不安装 Ghostty 应用、Node、Python、Ruby 或 AI CLI，也不锁定工具版本。

### 同步配置文件

下列命令会用仓库模板覆盖相应用户配置，适合重建本方案。已有自定义内容时，按文件对应表合并需要的部分。

```zsh
SHELL_CONFIG_DIR="$PWD/config/ghostty-zsh"
mkdir -p "$HOME/.config/ghostty/themes"
mkdir -p "$HOME/Library/Application Support/com.mitchellh.ghostty"

install -m 644 "$SHELL_CONFIG_DIR/zsh/.zshenv" "$HOME/.zshenv"
install -m 644 "$SHELL_CONFIG_DIR/zsh/.zshrc" "$HOME/.zshrc"
install -m 644 "$SHELL_CONFIG_DIR/starship/starship.toml" "$HOME/.config/starship.toml"
install -m 644 "$SHELL_CONFIG_DIR/ghostty/config.ghostty" "$HOME/Library/Application Support/com.mitchellh.ghostty/config.ghostty"
install -m 644 "$SHELL_CONFIG_DIR/ghostty/themes/One Dark Pro" "$HOME/.config/ghostty/themes/One Dark Pro"

(umask 077; touch "$HOME/.zsh_history")
chmod 600 "$HOME/.zsh_history"
```

随后将 `zsh/zprofile.snippet.zsh` 中的初始化逻辑合并进已有 `.zprofile`。已有 Homebrew 初始化行时，更新为显式的 `shellenv zsh` 即可，不要重复添加或覆盖原文件。

Ghostty 设置按 `Cmd-Shift-,` 重新加载；部分窗口设置需要新建窗口才能生效。zsh 设置更新后新开终端即可，也可以在空闲 shell 中执行：

```zsh
exec zsh -l
```

配置有重复加载保护，已有 shell 中反复 `source ~/.zshrc` 不会重新初始化全部插件。

## 备份的用途与当前状态

初次配置前，曾在用户私有目录保存原有 `.zprofile` 和 Ghostty 配置，并记录哪些配置文件是本次新建的。那份快照用于恢复修改前的状态：恢复原文件，移除本次新增的配置；它不参与日常 shell 启动，也不会在后台运行。

**按当前要求，初次安装的备份及其恢复脚本已经删除。** 当前生效配置、命令历史和已安装工具均保留。本目录没有原配置备份，也不会自动创建备份。

仓库中的模板可以重建这套开发环境，但不包含修改前的私有配置，不能用来恢复已经删除的原始快照。

## 检查与排错

配置同步后，可运行以下检查：

```zsh
/bin/zsh -n "$HOME/.zshenv"
/bin/zsh -n "$HOME/.zprofile"
/bin/zsh -n "$HOME/.zshrc"
/Applications/Ghostty.app/Contents/MacOS/ghostty +validate-config
/bin/zsh -lc 'printf "shell ready\n"'
command -v rg fd fzf zoxide starship bat eza
```

最后的 zsh 命令应只输出 `shell ready`。打开普通 Ghostty 终端，试用 `Ctrl-R`、`Ctrl-T` 和左 `Option-C`，确认字体、中文显示以及新分屏的工作目录符合预期。

| 现象 | 检查方法 |
| --- | --- |
| `z` 找不到项目 | 先用 `cd` 访问一次，再试 `z` 或 `zi` |
| `Ctrl-T` 选完没有打开文件 | 它只插入路径；先输入 `bat ` 等命令，选完后再回车执行 |
| 找不到某些文件 | 检查当前位置和忽略规则；按需使用 `fd -H` 或 `fd -HI` |
| 左 `Option-C` 无反应 | 确认在 shell 提示符处，已加载 Ghostty 配置，使用的是左 Option |
| 改完仓库模板没有生效 | 同步到用户目录；新开 shell，并重新加载 Ghostty 设置 |
| 提示符是简单文本 | 检查是否为普通交互式终端，以及 `command -v starship` 是否成功 |
| Homebrew 报未知 macOS 版本 | 先执行 `brew update` 更新 Homebrew，再重试安装 |

最近一次验证使用 Ghostty 1.4.0 和 zsh 5.9：四种 shell 启动方式的工具可用性、干净输出与退出码检查通过；独立终端环境中的 13 项交互检查通过，包括历史共享、文件名含空格、多行粘贴和错误提示。隔离终端环境中 5 次热启动的中位数约为 164 毫秒。
