---
name: nvim-format
description: "用 Neovim(conform.nvim) 配置的同一套格式化工具格式化任何语言的代码,与 nvim 内格式化结果完全一致。支持 nvim 已配置的全部语言(如 Python、TypeScript/JavaScript、JSON/YAML/Markdown、Lua、Shell,具体用什么工具由用户的 nvim 配置决定):有 conform formatter 就用它,没有则走 LSP 兜底(lsp_format=fallback)。在用户要求格式化代码、整理代码风格、检查未格式化文件时使用。"
license: MIT
---

# nvim-format — 用 nvim 的格式化工具格式化任何语言

用户 nvim 通过 conform.nvim + Mason 管理格式化工具。本工具把同一套工具带到命令行:
**nvim 怎么格式化,这里就怎么格式化** —— 每种语言用什么工具完全由用户的 nvim 配置决定
(conform formatter 或 LSP 兜底),本工具不预设任何工具。

> 这是「在项目里统一跑格式化」的通用版:不只针对某一种语言,而是覆盖 nvim 配置的全部语言。

## 目录结构(自包含)

本 skill 自包含:SKILL.md + scripts/。
脚本通过自身位置定位配套文件(Python 用 `__file__`、bash 入口用 `BASH_SOURCE`),
整个目录拷到任何位置都能运行。

```
nvim-format/
├── SKILL.md              # 本文件(agent 入口)
├── README.md             # 仓库首页(给人看)
├── LICENSE               # MIT
└── scripts/
    ├── nvim-format       # 可执行入口(推荐)
    ├── nvim_format.py    # Python 入口(参数解析 + 主流程)
    ├── nvim_env.py       # nvim 环境发现 + Lua 执行
    ├── targets.py        # 目标文件收集 + 语言过滤
    ├── formatter.py      # 格式化引擎(单文件 + 批量)
    ├── cmds.py           # --list 命令
    └── lua/              # 与 nvim 交互的 Lua 脚本
```

依赖:python3 + nvim(用户的 nvim 配置里要有 conform.nvim;格式化工具本体从
nvim 的 `stdpath('data')/mason/bin` 取,与 nvim 内完全一致,可用 MASON 环境变量覆盖)。

平台:支持 Linux / macOS(两平台下 nvim 的 `stdpath('data')` 均为 `~/.local/share/nvim`)。

## 用法

本工具通过相对路径调用(skill 目录自包含,拷贝到任何位置都能运行):

```bash
$ ./scripts/nvim-format app.py                 # 格式化单个文件
$ ./scripts/nvim-format src/                   # 格式化目录(自动跳过 .git/node_modules/venv 等;git 仓库内尊重 .gitignore)
$ ./scripts/nvim-format .                      # 整个项目(覆盖 nvim 配置的全部语言)
$ ./scripts/nvim-format --lang python .        # 只格式化 python 文件(接受 filetype 名或扩展名:python/.py/typescript/.ts)
$ ./scripts/nvim-format --lang python,typescript src/   # 只格式化 python + typescript
$ ./scripts/nvim-format --lang lua --batch .   # 只格式化 lua,用批量模式
$ ./scripts/nvim-format --check .              # 只检查哪些文件会变化(CI 用:有变化退出码 1)
$ ./scripts/nvim-format --list                 # 查看 nvim 为哪些语言配置了什么工具
$ ./scripts/nvim-format --batch .              # 大项目:单个 nvim 会话批量处理(更快)
$ ./scripts/nvim-format --no-lsp .             # 不用 LSP 兜底,只格式化 conform 显式配置的文件类型
$ ./scripts/nvim-format -j 8 .                 # 并行度(默认 4)
```

或直接调用 Python 入口:

```bash
$ python3 scripts/nvim_format.py app.py
```

> 若 `scripts/nvim-format` 无可执行权限(某些环境下 clone 后丢 `+x`),
> 用 `bash scripts/nvim-format ...` 或上面的 Python 入口即可,功能完全一致。

## 执行流程

1. **检测环境**:定位 nvim 可执行文件、用户配置(init.lua/init.vim)、Mason bin 目录
   (`$MASON/bin` → `nvim stdpath('data')/mason/bin` → `~/.local/share/mason/bin`)。
2. **headless 启动 nvim**(`-u 用户配置`),通过 lazy.nvim 加载 conform.nvim,
   取出**合并后**的 `formatters_by_ft`(含发行版默认 + extras + 用户自定义覆盖),
   并对每个 formatter 用 `get_formatter_info` 检查可用性(condition、二进制是否存在)。
3. **对每个文件执行 `require("conform").format()`** —— 与交互式 nvim 完全相同的调用:
   - 有 conform formatter → 直接运行(Mason 里用户安装的格式化工具);
   - 没有 → 若 `lsp_format` 允许(默认 fallback),等待有格式化能力的 LSP 附加后格式化。
4. **结果**:格式化后仅当 buffer 真实修改时由 nvim 直接写回(保留 fileformat/eol;无变化不触碰
   文件、保持 mtime);`--check` 把结果写到临时文件,只比较不写入。

## 输出说明

```
[已格式化] /path/to/a.py  LSP[<格式化 LSP>]      # 工具报告:conform 或 LSP
[无变化]   /path/to/a.ts   conform[<工具名>]
[跳过]     /path/to/a.txt  nvim 未配置该文件类型的格式化工具
[需格式化] /path/to/a.go   conform[<工具名>]      # --check 模式
[错误]     /path/to/a.py   格式化失败: ...
```

> 具体的工具名(如 prettier、stylua、shfmt、gofmt 或对应 LSP)取决于用户的 nvim 配置,
> 与本工具无关;运行 `--list` 可查看本机实际生效的配置。

## 注意事项

- **以 nvim 配置为准**:本工具不预设任何格式化工具,一切以用户 nvim 里 conform.nvim 的
  `formatters_by_ft`(及 LSP 兜底)为唯一依据。想换工具/加语言,直接在 nvim 里配置即可。
- **工具缺失**:报告里出现「⚠ xxx(Command 'xxx' not found)」时,请在 nvim 内
  `:MasonInstall xxx` 后重试。
- **首次运行较慢**属正常(加载 nvim 配置/插件);之后每次单文件约 0.1~0.3s,
  大项目建议 `--batch`。
- 文件类型没被 nvim 配置任何格式化方式时,显示「跳过」,不报错。
- `--check` 适合 CI:有文件需要格式化时退出码 1,有错误时退出码 2。

## 故障排查

| 现象                        | 处理                                            |
| --------------------------- | ----------------------------------------------- |
| 未找到 nvim                 | 安装 Neovim,或 `NVIM=/path/to/nvim`             |
| 未找到 init.lua             | 检查 `~/.config/nvim` 配置目录                  |
| 无法加载 conform.nvim       | nvim 未使用 conform.nvim,本工具以它为格式化依据 |
| 提示工具不可用              | nvim 内 `:MasonInstall <工具>` 安装             |
| 格式化无变化但报告 did_edit | 文件只读,检查文件权限                           |
