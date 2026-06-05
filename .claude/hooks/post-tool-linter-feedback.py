#!/usr/bin/env python3
"""
post-tool-linter-feedback — 每个错误 → 一条防护规则

事件: PostToolUse
Matcher: Edit | Write

触发条件:
  - tool_input.file_path 可推断出 fitness rule
  - fitness/ 脚本目录存在

行为:
  1. 按文件路径推断需要跑的 fitness rule
  2. 跑相关 fitness 脚本
  3. 失败 → 记录到 fitness-failures.log + 追加候选到 fitness-backlog.md

降级 / 阻断:
  - 阻断条件: 无
  - 失败兜底: fitness/ 目录不存在 → 静默跳过；任何异常 → 静默退出

产物:
  - .chatlabs/reports/fitness-failures.log
  - .chatlabs/reports/fitness/fitness-backlog.md
"""
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/hooks/ 回退 2 级）
# fallback 用 .absolute() 而非 .resolve()——.claude 常是 symlink，resolve() 会穿透
# 到 symlink 目标目录，导致定位到错误项目。详见 session-review 2026-06-05。
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[2])
))
CHATLABS_DIR = PROJECT_DIR / ".chatlabs"
REPORTS_DIR = CHATLABS_DIR / "reports"
FITNESS_DIR = REPORTS_DIR / "fitness"

FAILURES_LOG = REPORTS_DIR / "fitness-failures.log"
BACKLOG_FILE = REPORTS_DIR / "fitness" / "fitness-backlog.md"
# 业务级 fitness/ 脚本目录（与 paths.FITNESS_DIR 不同：paths.FITNESS_DIR 是报告目录）
SCRIPTS_DIR = CHATLABS_DIR.parent / "fitness"


def log_failure(msg: str):
    try:
        FAILURES_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILURES_LOG, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


def ensure_backlog_exists():
    """确保 fitness-backlog.md 存在，有头则追加，无则创建"""
    try:
        BACKLOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        if BACKLOG_FILE.exists():
            return
        BACKLOG_FILE.write_text(
            "# Fitness Rule Backlog\n\n"
            "| ID | 描述 | 证据 | 日期 | 状态 |\n"
            "|----|------|------|------|------|\n"
        )
    except Exception:
        pass


def infer_rules(tool: str, file_path: str) -> list[str]:
    """根据修改的文件推断需要跑的 fitness rule"""
    rules = []
    if not file_path:
        return rules
    # fitness/ 脚本目录不存在 → 无可跑的规则
    if not SCRIPTS_DIR.exists():
        return rules
    path_lower = file_path.lower()
    if path_lower.endswith((".yaml", ".yml")) and "openapi" in path_lower:
        rules.append("openapi-lint")
    if any(x in path_lower for x in ["/handlers/", "/agents/", "/skills/", "/hooks/"]):
        rules.append("layer-boundary")
    if "/handoffs/" in path_lower or path_lower.endswith("-artifact.md"):
        rules.append("handoff-lint")
    if not rules:
        rules = ["layer-boundary", "openapi-lint"]
    return rules


def run_rule(rule: str) -> tuple[int, str]:
    """跑单个 fitness rule，返回 (exit_code, stdout)"""
    script = SCRIPTS_DIR / f"{rule}.sh"
    if not script.exists():
        return 0, ""
    try:
        result = subprocess.run(
            ["bash", str(script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 0, str(e)


def append_backlog(rule_desc: str, evidence: str, file_path: str):
    """追加候选规则到 fitness-backlog.md"""
    ensure_backlog_exists()
    timestamp = datetime.now().strftime("%Y-%m-%d")
    entry = f"| pending-{timestamp} | {rule_desc} | {evidence} | {timestamp} | pending |\n"
    try:
        with open(BACKLOG_FILE) as f:
            content = f.read()
        if rule_desc in content:
            return
        with open(BACKLOG_FILE, "a") as f:
            f.write(entry)
        log_failure(f"backlog: added '{rule_desc}'")
    except Exception as e:
        log_failure(f"backlog: append failed: {e}")


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool = hook_input.get("tool", "")
    file_path = hook_input.get("file_path", "")

    # 只处理 Edit/Write
    if tool not in ("Edit", "Write"):
        sys.exit(0)

    rules = infer_rules(tool, file_path)
    if not rules:
        return

    any_fail = False
    failure_summary = []

    for rule in rules:
        exit_code, output = run_rule(rule)
        if exit_code != 0:
            any_fail = True
            first_line = output.strip().split("\n")[0] if output.strip() else rule
            failure_summary.append(f"{rule}: {first_line.strip()}")
            log_failure(f"{tool} {file_path} → {rule} FAILED: {output.strip()[:200]}")
            append_backlog(
                rule_desc=f"[{tool}] {file_path} → {rule}",
                evidence=first_line[:120],
                file_path=file_path,
            )

    if any_fail:
        summary = "; ".join(failure_summary[:3])
        print(f"[linter-feedback] {summary}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
