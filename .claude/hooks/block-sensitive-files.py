#!/usr/bin/env python3
"""
block-sensitive-files — 拦截 AI 读取敏感文件
事件：PreToolUse (matcher: Read|Edit|Write|MultiEdit)

规则说明：
  - 不含路径分隔符的模式 → 匹配文件名 (basename)，支持 * 通配符
  - 含路径分隔符的模式   → 匹配完整路径，** 等价于 *（fnmatch 的 * 本身匹配含 / 的任意字符）

原则：KISS — 纯标准库 fnmatch；命中即 deny；否则静默放行
"""
import sys
import json
import os
import fnmatch

BLOCKED_PATTERNS = [
    "application-live.yml",
    "application-prod.yml",
    ".env.production",
    ".env.prod",
    "secrets.yml",
    "credentials.yml",
    "cert/**",
]


def matches_blocked(path: str, file_name: str, pattern: str) -> bool:
    """
    路径模式: 含 "/"，** → *，匹配完整路径的四种场景(与 bash 版本对齐)
    文件名模式: 不含 "/"，仅匹配 basename
    """
    if "/" in pattern:
        bp = pattern.replace("**", "*")
        return (
            fnmatch.fnmatchcase(path, f"*/{bp}")
            or fnmatch.fnmatchcase(path, f"*/{bp}/*")
            or fnmatch.fnmatchcase(path, bp)
            or fnmatch.fnmatchcase(path, f"{bp}/*")
        )
    return fnmatch.fnmatchcase(file_name, pattern)


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = (hook_input.get("tool_input") or {}).get("file_path") or ""
    if not file_path:
        sys.exit(0)

    file_name = os.path.basename(file_path)

    matched = next(
        (p for p in BLOCKED_PATTERNS if matches_blocked(file_path, file_name, p)),
        None,
    )
    if not matched:
        sys.exit(0)

    reason = (
        f"❌ 禁止读取敏感文件: {file_name}\n"
        f"匹配规则: {matched}\n"
        f"完整路径: {file_path}\n"
        "如需访问，请修改 .claude/hooks/block-sensitive-files.py"
    )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    json.dump(output, sys.stdout, ensure_ascii=False)
    sys.exit(0)


if __name__ == "__main__":
    main()
