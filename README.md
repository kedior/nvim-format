# nvim-format

> 用 Neovim(conform.nvim) 配置的**同一套格式化工具**,格式化任何语言的代码。
> **nvim 怎么格式化,这里就怎么格式化。**

把你在 nvim 里配好的格式化能力(conform.nvim + Mason + LSP 兜底)带到命令行,
支持 nvim 已配置的全部语言(Python、TypeScript/JavaScript、JSON/YAML/Markdown、Lua、Shell…),
具体用什么工具完全由你的 nvim 配置决定,本工具不预设任何工具。

## 快速开始

依赖:python3 + nvim(配置里有 conform.nvim)。平台:Linux / macOS。

```bash
# 1. clone 本仓库到当前目录
git clone <本仓库地址> .

# 2. 用(skill 自包含,相对路径调用,无需安装到 PATH)
./scripts/nvim-format app.py     # 格式化单个文件
./scripts/nvim-format .          # 整个项目
./scripts/nvim-format --check .  # 只检查(CI 用,有变化退出码 1)
```

或直接调用 Python 入口:

```bash
python3 scripts/nvim_format.py app.py
```

## 用法

```bash
$ ./scripts/nvim-format app.py                 # 格式化单个文件
$ ./scripts/nvim-format src/                   # 格式化目录(跳过 .git/node_modules/venv;git 仓库内尊重 .gitignore)
$ ./scripts/nvim-format .                      # 整个项目
$ ./scripts/nvim-format --lang python .        # 只格式化 python(接受 filetype 或扩展名:.py/python/.ts/typescript)
$ ./scripts/nvim-format --lang python,typescript src/   # 多种语言
$ ./scripts/nvim-format --lang lua --batch .   # 只格式化 lua,批量模式
$ ./scripts/nvim-format --check .              # 只检查(CI:有变化退出码 1)
$ ./scripts/nvim-format --list                 # 查看 nvim 为哪些语言配置了什么工具
$ ./scripts/nvim-format --batch .              # 大项目:单 nvim 会话批量处理(更快)
$ ./scripts/nvim-format --no-lsp .             # 不用 LSP 兜底
$ ./scripts/nvim-format -j 8 .                 # 并行度(默认 4)
```

## 作为 skill 使用

本仓库是符合 [Agent Skills 规范](https://agentskills.io/specification) 的自包含 skill
(SKILL.md + scripts/ 一起分发,全部用相对路径,拷贝到任何目录都能运行)。
把整个目录放进所用 agent 的 skills 目录即可,或直接按上文相对路径调用。

## 原理

以 nvim 为唯一事实来源:

1. headless 启动 nvim(`-u 用户配置`),加载 conform.nvim,取出合并后的 `formatters_by_ft`;
2. 对每个文件执行与交互式 nvim 完全相同的 `require("conform").format()`;
3. 有 conform formatter 就用它,没有则等格式化 LSP 附加后格式化(`lsp_format=fallback`);
4. 仅当 buffer 真实修改时由 nvim 写回(保留 fileformat/eol,无变化不触碰文件)。

## 许可证

MIT
