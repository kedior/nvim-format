"""nvim 环境发现与 Lua 脚本执行。

- NvimEnv:定位 nvim 可执行文件、用户配置、Mason 工具目录;
- lua_source / run_nvim:把 scripts/lua/ 下的 Lua 脚本注入参数后,在 headless nvim 中执行。
"""

import os
import shutil
import subprocess
from pathlib import Path

# 与 nvim 交互的 Lua 脚本都放在 scripts/lua/ 下(独立文件,便于阅读、编辑与复用),
# 运行时读取并用 __TOKEN__ 占位符注入参数。
# 两种执行方式:每文件一个 nvim 会话(可靠、错误隔离好,默认)或单会话批量(大项目更快)。
LUA_DIR = Path(__file__).resolve().parent / "lua"


def lua_source(name, **tokens):
    """读取 lua/ 下的脚本,并把 __TOKEN__ 占位符替换为实际值。"""
    src = (LUA_DIR / name).read_text(encoding="utf-8")
    for key, val in tokens.items():
        src = src.replace(f"__{key}__", val)
    return src


def run_nvim(env, lua, cwd=None, timeout=60):
    """headless 启动 nvim(-u 用户配置)执行一段 Lua,返回 subprocess 结果。"""
    cmd = [
        env.nvim,
        "--headless",
        "-u",
        env.init_file,
        "-c",
        "set noswapfile",
        "-c",
        "lua " + lua,
        "+qa!",
    ]
    sub_env = os.environ.copy()
    if env.mason_bin:
        sub_env["PATH"] = str(env.mason_bin) + os.pathsep + sub_env.get("PATH", "")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        errors="replace",
        cwd=cwd,
        env=sub_env,
        timeout=timeout,
        check=False,
    )


class NvimEnv:
    def __init__(self):
        self.nvim = os.environ.get("NVIM") or shutil.which("nvim")
        self.config_dir = None
        self.init_file = None
        self.data_dir = None
        self.mason_bin = None
        self.mason_ok = False

    def headless_none(self, lua_code):
        r = subprocess.run(
            [self.nvim, "--headless", "-u", "NONE", "-c", lua_code, "+qa!"],
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
        )
        return r.stdout.strip()

    def detect(self):
        if not self.nvim:
            return (
                "未找到 nvim(请先安装 Neovim,或设置 NVIM 环境变量指向 nvim 可执行文件)"
            )
        cfg = self.headless_none(
            "lua io.stdout:write(vim.fn.stdpath('config')); vim.cmd('qa!')"
        )
        self.config_dir = Path(cfg or os.path.expanduser("~/.config/nvim")).expanduser()
        for name in ("init.lua", "init.vim"):
            f = self.config_dir / name
            if f.is_file():
                self.init_file = str(f)
                break
        if not self.init_file:
            return f"在 {self.config_dir} 未找到 init.lua / init.vim(nvim 配置)"
        data = self.headless_none(
            "lua io.stdout:write(vim.fn.stdpath('data')); vim.cmd('qa!')"
        )
        self.data_dir = Path(
            data or os.path.expanduser("~/.local/share/nvim")
        ).expanduser()
        m = os.environ.get("MASON")
        cands = []
        if m:
            cands.append(Path(m) / "bin")
        cands += [
            self.data_dir / "mason" / "bin",
            Path.home() / ".local/share/mason" / "bin",
        ]
        for c in cands:
            if c.is_dir():
                self.mason_bin = c
                break
        if not self.mason_bin:
            self.mason_bin = cands[0] if cands else self.data_dir / "mason" / "bin"
        self.mason_ok = self.mason_bin.is_dir()
        return None
