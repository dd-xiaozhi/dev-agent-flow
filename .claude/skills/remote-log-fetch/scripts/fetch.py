"""fetch.py — 远程日志获取脚本

通过 SSH 拉日志，自动清洗 + 落盘。
直接调 sshpass + ssh，无需主 Claude 介入 MCP。

CLI:
  python fetch.py grep <env> --keyword <kw> [--date YYYY-MM-DD] [--output <path>]
      grep 关键字 / traceId，结果清洗后落盘
      stdout: {"ok": bool, "output_path": "...", "matched_lines": N}

  python fetch.py tail <env> [--lines 200] [--date YYYY-MM-DD] [--output <path>]
      看最新 N 行
      stdout: {"ok": bool, "output_path": "..."}

  python fetch.py ls <env> [--limit 20]
      列日志目录最新 N 个文件
      stdout: {"ok": bool, "files": [...]}

配置依赖 .chatlabs/project-config.json：
  ssh_servers[] — env / host / port / user / password_env
  log.paths[]   — env / dir / pattern（{date} {seq} 占位）
  log.output_dir — 落盘目录（相对项目根）

清洗规则：
  1. 移除远程路径前缀（sed 's|.*/log_debug_.*\\.log:||'）
  2. 移除行号前缀（sed 's/^[0-9]*://'）
  3. 移除 locale 警告（grep -v "setlocale"）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[4])
))
PROJECT_CONFIG = PROJECT_DIR / ".chatlabs" / "project-config.json"


# ── 配置加载 ──────────────────────────────────────────────────

def _load_config() -> dict:
    if not PROJECT_CONFIG.exists():
        return {}
    try:
        return json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _resolve_server(env: str) -> dict:
    cfg = _load_config()
    servers = cfg.get("ssh_servers") or []
    for s in servers:
        if s.get("env") == env:
            return s
    raise SystemExit(json.dumps({"ok": False, "error": f"no ssh_server for env={env}"}, ensure_ascii=False))


def _resolve_log_path(env: str, date: str | None = None) -> tuple[str, str]:
    cfg = _load_config()
    log_cfg = cfg.get("log") or {}
    paths = log_cfg.get("paths") or []
    output_dir = log_cfg.get("output_dir", "./logs_query")
    for p in paths:
        if p.get("env") == env:
            d = date or datetime.now().strftime("%Y-%m-%d")
            pattern = p.get("pattern", "*.log").replace("{date}", d).replace("{seq}", "*")
            full = f"{p['dir'].rstrip('/')}/{pattern}"
            return full, output_dir
    raise SystemExit(json.dumps({"ok": False, "error": f"no log.path for env={env}"}, ensure_ascii=False))


# ── SSH 执行 ─────────────────────────────────────────────────

def _ssh_run(server: dict, remote_cmd: str) -> str:
    pwd_env = server.get("password_env")
    if not pwd_env:
        raise SystemExit(json.dumps({"ok": False, "error": "ssh_server.password_env missing"}, ensure_ascii=False))
    password = os.environ.get(pwd_env)
    if not password:
        raise SystemExit(json.dumps({"ok": False, "error": f"env var ${pwd_env} not set"}, ensure_ascii=False))

    cmd = [
        "sshpass", "-p", password,
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", "LogLevel=ERROR",
        "-p", str(server.get("port", 22)),
        f"{server['user']}@{server['host']}",
        remote_cmd,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0 and not proc.stdout:
        raise SystemExit(json.dumps({
            "ok": False, "error": "ssh failed",
            "stderr": proc.stderr.strip()[-500:],
        }, ensure_ascii=False))
    return proc.stdout


# ── 输出清洗 ─────────────────────────────────────────────────

_PREFIX_RE = re.compile(r".*/log_[a-z]+_[^:]*\.log:")
_LINENO_RE = re.compile(r"^\d+:")


def _clean(raw: str) -> tuple[str, int]:
    """清洗远程输出，返回 (cleaned, line_count)"""
    out: list[str] = []
    for line in raw.splitlines():
        if "setlocale" in line.lower() or "warning: setting locale" in line.lower():
            continue
        line = _PREFIX_RE.sub("", line)
        line = _LINENO_RE.sub("", line)
        out.append(line)
    return "\n".join(out), len(out)


def _resolve_output(output_dir: str, env: str, tag: str) -> Path:
    base = PROJECT_DIR / output_dir if not output_dir.startswith("/") else Path(output_dir)
    base.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    safe_tag = re.sub(r"[^a-zA-Z0-9_-]", "_", tag)
    return base / f"{env}-{date}-{safe_tag}.log"


# ── 子命令 ───────────────────────────────────────────────────

def cmd_grep(args) -> int:
    server = _resolve_server(args.env)
    log_glob, output_dir = _resolve_log_path(args.env, args.date)
    kw = args.keyword.replace("'", "'\\''")
    # 单引号包 glob 防本地 shell 展开
    remote_cmd = f"grep -n -H '{kw}' '{log_glob}' 2>/dev/null || true"
    raw = _ssh_run(server, remote_cmd)
    cleaned, n = _clean(raw)

    output_path = Path(args.output) if args.output else _resolve_output(output_dir, args.env, args.keyword)
    output_path.write_text(cleaned, encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "output_path": str(output_path.relative_to(PROJECT_DIR) if output_path.is_relative_to(PROJECT_DIR) else output_path),
        "matched_lines": n,
    }, ensure_ascii=False))
    return 0


def cmd_tail(args) -> int:
    server = _resolve_server(args.env)
    log_glob, output_dir = _resolve_log_path(args.env, args.date)
    # glob 需要 shell 展开,用 sh -c 包一层
    remote_cmd = f"sh -c \"tail -n {args.lines} {log_glob}\" 2>/dev/null || true"
    raw = _ssh_run(server, remote_cmd)
    cleaned, n = _clean(raw)

    output_path = Path(args.output) if args.output else _resolve_output(output_dir, args.env, f"tail{args.lines}")
    output_path.write_text(cleaned, encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "output_path": str(output_path.relative_to(PROJECT_DIR) if output_path.is_relative_to(PROJECT_DIR) else output_path),
        "lines": n,
    }, ensure_ascii=False))
    return 0


def cmd_ls(args) -> int:
    server = _resolve_server(args.env)
    cfg = _load_config()
    paths = (cfg.get("log") or {}).get("paths") or []
    target = next((p for p in paths if p.get("env") == args.env), None)
    if not target:
        print(json.dumps({"ok": False, "error": f"no log.path for env={args.env}"}, ensure_ascii=False))
        return 1
    remote_cmd = f"ls -lht '{target['dir']}/' | head -n {args.limit + 1}"
    raw = _ssh_run(server, remote_cmd)

    files: list[dict] = []
    for line in raw.splitlines()[1:]:  # skip "total" line
        parts = line.split()
        if len(parts) < 9:
            continue
        files.append({"size": parts[4], "mtime": " ".join(parts[5:8]), "name": " ".join(parts[8:])})

    print(json.dumps({"ok": True, "dir": target["dir"], "files": files}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Remote log fetch helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_g = sub.add_parser("grep", help="grep keyword/traceId")
    p_g.add_argument("env")
    p_g.add_argument("--keyword", required=True)
    p_g.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p_g.add_argument("--output", help="output file path (default: <output_dir>/<env>-<date>-<kw>.log)")
    p_g.set_defaults(func=cmd_grep)

    p_t = sub.add_parser("tail", help="tail last N lines")
    p_t.add_argument("env")
    p_t.add_argument("--lines", type=int, default=200)
    p_t.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p_t.add_argument("--output")
    p_t.set_defaults(func=cmd_tail)

    p_l = sub.add_parser("ls", help="list log directory")
    p_l.add_argument("env")
    p_l.add_argument("--limit", type=int, default=20)
    p_l.set_defaults(func=cmd_ls)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
