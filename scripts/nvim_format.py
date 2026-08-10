#!/usr/bin/env python3
"""nvim-format — 用 Neovim(conform.nvim) 配置的同一个格式化工具格式化任何语言的代码。

原理:以 nvim 为唯一事实来源——
1. 加载用户的 nvim 配置,取出 conform.nvim 合并后的 formatters_by_ft;
2. 对每个文件,让 nvim 在 headless 会话里执行与交互式 nvim 完全相同的
   require("conform").format()(含 LSP 兜底 lsp_format="fallback");
3. 写模式:格式化后由 nvim 直接写回(保留 fileformat/eol);
   --check 模式:写到临时文件,只比较不写入。

格式化工具本体来自 Mason(nvim 的 stdpath('data')/mason/bin,Linux/macOS 通用),
与 nvim 内完全一致;具体用什么工具完全由你的 nvim 配置决定。

用法:
  nvim_format.py <file|dir>...     # 格式化(目录递归;git 仓库内尊重 .gitignore)
  nvim_format.py .                 # 整个项目(覆盖 nvim 配置的全部语言)
  nvim_format.py --check .         # 只检查哪些文件会变化(CI 用,有变化退出码 1)
  nvim_format.py --list            # 查看 nvim 为哪些语言配置了什么工具
  nvim_format.py --batch .         # 大项目:单个 nvim 会话批量处理(更快)
"""

import argparse
import concurrent.futures
import os
import sys
from pathlib import Path

from cmds import cmd_list
from formatter import format_one, run_batch
from nvim_env import NvimEnv
from targets import files_from_args, filter_files_by_filetype, normalize_langs


def main():
    ap = argparse.ArgumentParser(
        prog="nvim-format",
        description="用 Neovim(conform.nvim) 配置的同一个格式化工具格式化任何语言的代码。",
    )
    ap.add_argument("targets", nargs="*", help="文件或目录;缺省为当前目录")
    ap.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="只检查哪些文件需要格式化,不写入(有变化退出码 1)",
    )
    ap.add_argument(
        "--list", action="store_true", help="查看 nvim 为哪些语言配置了什么格式化工具"
    )
    ap.add_argument(
        "--batch",
        action="store_true",
        help="单个 nvim 会话批量处理(大项目更快);与 --check 互斥",
    )
    ap.add_argument(
        "-j", "--jobs", type=int, default=4, help="并行 nvim 进程数(默认 4)"
    )
    ap.add_argument(
        "--no-lsp",
        action="store_true",
        help="不使用 LSP 兜底(只格式化 conform 显式配置的文件类型)",
    )
    ap.add_argument(
        "--lang",
        "--ft",
        dest="langs",
        action="append",
        metavar="FILETYPE",
        help="只格式化指定语言,可多次或逗号分隔(如 --lang python / --lang .ts / --lang python,typescript);"
        "接受 nvim filetype 名或常见扩展名",
    )
    ap.add_argument(
        "--timeout", type=int, default=3000, help="等待 LSP 附加的毫秒数(默认 3000)"
    )
    ap.add_argument(
        "--fmt-timeout",
        type=int,
        default=10000,
        help="conform 格式化超时毫秒数(默认 10000)",
    )
    ap.add_argument(
        "-v", "--verbose", action="store_true", help="详细输出(--check 时打印 diff)"
    )
    ap.add_argument("--mason-dir", default=None, help="覆盖 Mason 安装目录")
    ap.add_argument("--nvim", default=None, help="覆盖 nvim 可执行文件路径")
    args = ap.parse_args()

    if args.nvim:
        os.environ["NVIM"] = args.nvim
    env = NvimEnv()
    perr = env.detect()
    if perr:
        print(f"错误: {perr}", file=sys.stderr)
        return 2
    if args.mason_dir:
        env.mason_bin = Path(args.mason_dir).expanduser().resolve()
        env.mason_ok = env.mason_bin.is_dir()

    if args.list:
        return cmd_list(env)

    if not env.mason_ok:
        print(
            f"警告: Mason 工具目录不存在({env.mason_bin}),将无法使用格式化工具,"
            "请在 nvim 内 :MasonInstall 安装",
            file=sys.stderr,
        )

    if args.batch and args.check:
        print("错误: --batch 与 --check 互斥(--check 使用逐文件模式)", file=sys.stderr)
        return 2

    targets = args.targets or ["."]
    files = files_from_args(targets)
    if args.langs:
        langs = normalize_langs(args.langs)
        files, ferr = filter_files_by_filetype(env, files, langs)
        if ferr:
            print(f"错误: {ferr}", file=sys.stderr)
            return 2
        if not files:
            print(f"没有找到匹配语言 {', '.join(sorted(langs))} 的文件")
            return 0
        print(f"已按语言过滤: {', '.join(sorted(langs))} → {len(files)} 个文件")
    if not files:
        print("没有找到可处理的文件")
        return 0
    if args.batch:
        print(f"批量格式化 {len(files)} 个文件(单个 nvim 会话)…")
        results = run_batch(env, files, not args.no_lsp, args.timeout, args.fmt_timeout)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as ex:
            futures = [
                ex.submit(
                    format_one,
                    env,
                    f,
                    args.check,
                    not args.no_lsp,
                    args.timeout,
                    args.fmt_timeout,
                    args.verbose,
                )
                for f in files
            ]
            results = [fut.result() for fut in concurrent.futures.as_completed(futures)]

    results.sort(key=lambda r: r[1])
    icons = {
        "formatted": "[已格式化]",
        "ok": "[无变化]",
        "skipped": "[跳过]",
        "needs-format": "[需格式化]",
        "error": "[错误]",
    }
    counts = {}
    for status, path, tool, diff in results:
        counts[status] = counts.get(status, 0) + 1
        print(f"{icons[status]} {path}  {tool}")
        if diff and args.verbose:
            print(diff)
    print()
    parts = [f"{icons[s].strip('[]')} {n}" for s, n in sorted(counts.items())]
    print("汇总: " + " | ".join(parts))
    if args.check:
        if counts.get("error"):
            return 2
        if counts.get("needs-format"):
            return 1
    elif counts.get("error"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
