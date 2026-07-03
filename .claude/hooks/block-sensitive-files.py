#!/usr/bin/env python3
"""
block-sensitive-files — 拦截 AI 读取敏感文件

事件: PreToolUse
Matcher: Read|Edit|Write|MultiEdit

触发条件:
  - tool_input.file_path 命中 BLOCKED_PATTERNS 之一

行为:
  1. 解析 tool_input.file_path 与 basename
  2. 不含 "/" 的模式按 basename 匹配，含 "/" 的模式按完整路径匹配（** 等价 *）
  3. 命中 → deny；否则静默放行

降级 / 阻断:
  - 阻断条件: 命中敏感模式 → 输出 stderr + 拒绝
  - 失败兜底: stdin 解析失败 / 无 file_path → 静默退出（exit 0）

产物:
  - stderr（命中时输出阻断说明）
"""
import sys
import json
import os
import fnmatch

BLOCKED_PATTERNS = [
    "application-live*",
    "application-prod*",
    ".env.production",
    ".env.prod",
    "secrets.yml",
    "credentials*",
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
