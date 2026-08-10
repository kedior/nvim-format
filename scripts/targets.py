"""目标文件收集与语言过滤。

- files_from_args:把命令行参数展开为文件列表(git 仓库内尊重 .gitignore);
- normalize_langs / filter_files_by_filetype:--lang 过滤(接受 filetype 名或扩展名)。
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from nvim_env import lua_source, run_nvim

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "venv",
    ".venv",
    "env",
    ".env",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    ".next",
    ".nuxt",
    ".cache",
    "vendor",
    ".terraform",
    ".idea",
    ".vscode",
    "coverage",
    "htmlcov",
    "site-packages",
    ".dart_tool",
    ".gradle",
    ".stack-work",
    "bazel-out",
}

# 常见扩展名 → filetype(方便 --lang .py / --lang python 两种写法)
EXT_TO_FT = {
    ".py": "python",
    ".pyi": "python",
    ".pyw": "python",
    ".ts": "typescript",
    ".tsx": "typescriptreact",
    ".js": "javascript",
    ".jsx": "javascriptreact",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".json": "json",
    ".jsonc": "jsonc",
    ".json5": "json5",
    ".lua": "lua",
    ".sh": "sh",
    ".bash": "sh",
    ".zsh": "zsh",
    ".md": "markdown",
    ".mdx": "markdown.mdx",
    ".markdown": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".html": "html",
    ".vue": "vue",
    ".svelte": "svelte",
    ".java": "java",
    ".kt": "kotlin",
    ".swift": "swift",
    ".cs": "cs",
    ".dart": "dart",
    ".sol": "solidity",
}


def files_from_args(args):
    out = []
    for a in args:
        p = Path(a).expanduser().resolve()
        if p.is_file():
            out.append(p)
        elif p.is_dir():
            # git 仓库内:尊重 .gitignore(跟踪 + 未忽略的未跟踪文件)
            try:
                r = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(p),
                        "ls-files",
                        "--cached",
                        "--others",
                        "--exclude-standard",
                        "-z",
                    ],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=30,
                    check=False,
                )
                if r.returncode == 0 and r.stdout.strip():
                    for rel in r.stdout.split("\0"):
                        if not rel:
                            continue
                        parts = Path(rel).parts
                        if any(part in SKIP_DIRS for part in parts):
                            continue
                        if Path(rel).name.startswith("."):
                            continue
                        out.append(p / rel)
                    continue
            except (OSError, subprocess.TimeoutExpired):
                pass
            # 普通遍历
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [
                    d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
                ]
                for fn in filenames:
                    if fn.startswith("."):
                        continue
                    out.append(Path(dirpath) / fn)
        else:
            out.append(p)
    seen, uniq = set(), []
    for f in out:
        s = str(f)
        if s not in seen:
            seen.add(s)
            uniq.append(f)
    return sorted(uniq, key=str)


def normalize_langs(raw_list):
    out = set()
    for r in raw_list:
        for part in r.split(","):
            p = part.strip().lower()
            if not p:
                continue
            if p.startswith("."):
                out.add(EXT_TO_FT.get(p, p))
            else:
                out.add(p)
    return out


def filter_files_by_filetype(env, files, langs):
    """用一次 headless nvim 批量查询每个文件的 filetype,过滤出匹配语言的文件。"""
    with tempfile.NamedTemporaryFile("w", suffix=".list", delete=False) as lf:
        for f in files:
            lf.write(str(f) + "\n")
        list_file = lf.name
    out_file = list_file + ".out"
    try:
        lua = lua_source("filetype.lua", LIST_FILE=list_file, OUT_FILE=out_file)
        try:
            run_nvim(env, lua, timeout=60)
        except subprocess.TimeoutExpired:
            return None, "filetype 查询超时"
        if not Path(out_file).is_file():
            return None, "nvim 未产出 filetype 查询结果"
        try:
            data = json.loads(Path(out_file).read_text(errors="replace"))
        except ValueError:
            return None, "filetype 查询结果解析失败"
        if isinstance(data, dict) and data.get("fatal"):
            return None, data["fatal"]
        matched = [item["f"] for item in data if item.get("ft") in langs]
        return matched, None
    finally:
        for f in (list_file, out_file):
            try:
                os.unlink(f)
            except OSError:
                pass
