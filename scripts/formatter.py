"""格式化执行引擎:解析 nvim 输出、格式化单文件或批量文件。

逐文件模式(format_one):每个文件一个 nvim 会话,可靠、错误隔离好;
批量模式(run_batch):单个 nvim 会话处理所有文件,适合大项目。
"""

import difflib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from nvim_env import lua_source, run_nvim


def _rm(path):
    """静默删除文件(path 为 None 时不操作)。"""
    if not path:
        return
    try:
        os.unlink(path)
    except OSError:
        pass


def nvim_fatal(proc):
    """nvim 异常退出时生成错误描述:退出码 + 末尾输出片段。"""
    snippet = (proc.stderr or proc.stdout or "").strip()[-400:]
    return f"nvim 异常退出(rc={proc.returncode})" + (f": {snippet}" if snippet else "")


def parse_markers(out):
    parsed = {}
    for line in out.splitlines():
        for key in (
            "NAMES",
            "INFO",
            "LSP_MODE",
            "CLIENTS",
            "LSP_ATTACHED",
            "FMT",
            "WROTE",
        ):
            if line.startswith(key + ":"):
                payload = line[len(key) + 1 :]
                if key in ("NAMES", "INFO", "CLIENTS", "WROTE"):
                    try:
                        parsed[key] = json.loads(payload)
                    except ValueError:
                        parsed[key] = payload
                elif key in ("LSP_ATTACHED",):
                    parsed[key] = payload == "true"
                else:
                    parsed[key] = payload
                break
    return parsed


def describe(parsed):
    names = parsed.get("NAMES") or []
    infos = parsed.get("INFO") or []
    clients = parsed.get("CLIENTS") or []
    parts = []
    if names:
        warn = []
        for i in infos:
            if i.get("available") is False:
                warn.append(f"{i.get('name')}({i.get('msg') or '不可用'})")
        s = "conform[" + ", ".join(names) + "]"
        if warn:
            s += "  ⚠ " + "; ".join(warn)
        parts.append(s)
    if clients:
        parts.append("LSP[" + ", ".join(clients) + "]")
    return " ".join(parts) if parts else "?"


def format_one(env, path, check, allow_lsp, wait_ms, fmt_timeout_ms, verbose):
    f = Path(path).expanduser().resolve()
    if not f.is_file():
        return ("error", str(path), "不是文件或不存在", None)
    try:
        old_bytes = f.read_bytes()
    except OSError as e:
        return ("error", str(path), f"无法读取: {e}", None)

    out_tmp = None
    if check:
        with tempfile.NamedTemporaryFile(
            prefix=".nvfmt-out-", suffix=".txt", delete=False
        ) as tmp:
            out_tmp = tmp.name
    path_file = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".path", delete=False) as pf:
            pf.write(str(f))
            path_file = pf.name
        lua = lua_source(
            "per_file.lua",
            PATH_FILE=path_file,
            OUT_FILE=f"'{out_tmp}'" if out_tmp else "nil",
            ALLOW_LSP="true" if allow_lsp else "false",
            WAIT_MS=str(wait_ms),
            FMT_TIMEOUT_MS=str(fmt_timeout_ms),
        )
        try:
            proc = run_nvim(
                env, lua, cwd=str(f.parent), timeout=wait_ms + fmt_timeout_ms + 20000
            )
        except subprocess.TimeoutExpired:
            return ("error", str(path), "超时(nvim 未在限时内完成,可能 LSP 卡住)", None)

        parsed = parse_markers((proc.stdout or "") + "\n" + (proc.stderr or ""))
        fmt = parsed.get("FMT")
        if fmt is None:
            return ("error", str(path), nvim_fatal(proc), None)
        if isinstance(fmt, str):
            try:
                fmt = json.loads(fmt)
            except ValueError:
                fmt = {"ok": False, "err": fmt}
        if not fmt.get("ok"):
            return ("error", str(path), f"格式化失败: {fmt.get('err')}", None)

        names = parsed.get("NAMES") or []
        if not names and not parsed.get("LSP_ATTACHED"):
            return ("skipped", str(path), "nvim 未配置该文件类型的格式化工具", None)

        tool = describe(parsed)
        if check:
            if not fmt.get("modified"):
                return ("ok", str(path), tool, None)
            new_bytes = Path(out_tmp).read_bytes()
        else:
            new_bytes = f.read_bytes()
        if new_bytes == old_bytes:
            if not check and fmt.get("modified"):
                wrote = parsed.get("WROTE") or {}
                if not wrote.get("ok"):
                    return (
                        "error",
                        str(path),
                        "nvim 报告已修改但写入失败(文件只读?)",
                        None,
                    )
            return ("ok", str(path), tool, None)
        if check:
            diff = None
            if verbose:
                diff = "".join(
                    difflib.unified_diff(
                        old_bytes.decode("utf-8", "replace").splitlines(True),
                        new_bytes.decode("utf-8", "replace").splitlines(True),
                        fromfile=str(f),
                        tofile=str(f),
                    )
                )
            return ("needs-format", str(path), tool, diff)
        return ("formatted", str(path), tool, None)
    finally:
        _rm(path_file)
        _rm(out_tmp)


def run_batch(env, files, allow_lsp, wait_ms, fmt_timeout_ms):
    with tempfile.NamedTemporaryFile("w", suffix=".list", delete=False) as lf:
        for f in files:
            lf.write(str(f) + "\n")
        list_file = lf.name
    out_file = list_file + ".out"
    try:
        lua = lua_source(
            "batch.lua",
            LIST_FILE=list_file,
            OUT_FILE=out_file,
            ALLOW_LSP="true" if allow_lsp else "false",
            WAIT_MS=str(wait_ms),
            FMT_TIMEOUT_MS=str(fmt_timeout_ms),
        )
        cwd = Path(files[0]).parent if files else Path.cwd()
        timeout = int(len(files) * (wait_ms + fmt_timeout_ms + 2000) / 1000 + 90)
        try:
            proc = run_nvim(env, lua, cwd=str(cwd), timeout=timeout)
        except subprocess.TimeoutExpired:
            return [("error", str(f), "批处理超时", None) for f in files]
        if not Path(out_file).is_file():
            return [("error", str(f), nvim_fatal(proc), None) for f in files]
        try:
            data = json.loads(Path(out_file).read_text(errors="replace"))
        except ValueError:
            return [("error", str(f), "批处理结果解析失败", None) for f in files]
        if isinstance(data, dict) and data.get("fatal"):
            return [("error", str(f), data["fatal"], None) for f in files]
        results = []
        for item in data:
            path = item.get("path", "?")
            status = item.get("status")
            if status == "error":
                results.append(("error", path, item.get("msg", "?"), None))
            elif status == "skipped":
                results.append(
                    ("skipped", path, "nvim 未配置该文件类型的格式化工具", None)
                )
            else:  # done:比较临时文件与原件,决定是否替换
                tmp = item.get("tmp")
                if not tmp or not Path(tmp).is_file():
                    results.append(("error", path, "格式化结果文件缺失", None))
                    continue
                try:
                    old = Path(path).read_bytes()
                    new = Path(tmp).read_bytes()
                except OSError as e:
                    _rm(tmp)
                    results.append(("error", path, f"读取失败: {e}", None))
                    continue
                if new == old:
                    _rm(tmp)
                    results.append(("ok", path, "batch(无变化)", None))
                elif item.get("wrote") is False:
                    _rm(tmp)
                    results.append(("error", path, "写入失败(文件只读?)", None))
                else:
                    try:
                        os.replace(tmp, path)
                    except OSError as e:
                        results.append(("error", path, f"替换文件失败: {e}", None))
                        continue
                    results.append(("formatted", path, "batch", None))
        return results
    finally:
        _rm(list_file)
        _rm(out_file)
