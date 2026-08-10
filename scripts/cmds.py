"""命令处理:与 nvim 交互的辅助命令(--list 展示 conform 配置)。"""

import json
import subprocess
import sys

from nvim_env import lua_source, run_nvim


def cmd_list(env):
    try:
        proc = run_nvim(env, lua_source("list.lua"), timeout=60)
    except subprocess.TimeoutExpired:
        print("错误: --list 查询超时", file=sys.stderr)
        return 2
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    fts, err = None, None
    for line in out.splitlines():
        if line.startswith("FTS:"):
            try:
                fts = json.loads(line[4:])
            except ValueError:
                fts = None
        elif line.startswith("ERR:"):
            err = line[4:]
    if err:
        print(f"错误: {err}")
        return 2
    if fts is None:
        print(f"无法获取 conform.nvim 配置(nvim 退出码 {proc.returncode})")
        return 2
    print("nvim 配置的格式化工具 (conform.nvim formatters_by_ft):")
    if not fts:
        print("  (空:未配置任何 formatter)")
    for ft, fmt in sorted(fts.items()):
        if isinstance(fmt, list):
            print(f"  {ft:<16} → {', '.join(str(x) for x in fmt)}")
        else:
            print(f"  {ft:<16} → {fmt}")
    print()
    print(f"Mason 工具目录: {env.mason_bin}{'' if env.mason_ok else '  (不存在!)'}")
    if env.mason_ok:
        tools = sorted(p.name for p in env.mason_bin.iterdir() if p.is_file())
        if tools:
            print("  已安装: " + ", ".join(tools))
    print()
    print("说明:")
    print(
        "  - 上表是 nvim 内格式化时实际使用的工具列表(含 LazyVim 默认 + extras + 你的自定义配置)"
    )
    print(
        "  - 未在表中的文件类型:若 lsp_format 允许(默认 fallback),nvim 会走 LSP 格式化"
    )
    print(
        "    (例如某语言没有 conform formatter 时,由对应 LSP 格式化,本工具同样走这条路径)"
    )
    print("  - 工具缺失时请先在 nvim 内执行 :MasonInstall <工具>")
    return 0
