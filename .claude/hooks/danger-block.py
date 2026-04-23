#!/usr/bin/env python3
"""
danger-block — 拦截破坏性 Bash 命令
事件：PreToolUse (matcher: Bash)
依据：AGENTS.md 禁止清单、~/.claude/CLAUDE.md 删除操作确认规则

原则：黑名单最小集（KISS / YAGNI）；命中即 exit 2 block
"""
import sys
import json
import re
import subprocess

# 危险命令黑名单（ERE 正则，大小写不敏感）
DANGEROUS_PATTERNS = [
    r'rm\s+-rf\s+/(\s|$)',
    r'rm\s+-rf\s+/\*',
    r'rm\s+-rf\s+~',
    r'rm\s+-rf\s+\$HOME',
    r'git\s+reset\s+--hard',
    r'git\s+push\s+(-f|--force)',
    r'git\s+clean\s+-[a-z]*f',
    r'git\s+branch\s+-D',
    r'git\s+commit\s+.*--no-verify',
    r'DROP\s+(TABLE|DATABASE|SCHEMA)',
    r'TRUNCATE\s+TABLE',
    r'kill\s+-9\s+1(\s|$)',
    r'mkfs\.',
    r'dd\s+if=.*of=/dev/',
    r':\(\)\s*\{.*\}\s*;',
    r'>\s*/dev/sda',
]

compiled_patterns = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_input = hook_input.get("tool_input", {})
    command = tool_input.get("command", "")

    if not command:
        sys.exit(0)

    for pattern in compiled_patterns:
        if pattern.search(command):
            msg = (
                "[danger-block] 命令被拦截\n"
                f"  命令：{command}\n"
                f"  规则：{pattern.pattern}\n"
                "→ 此类破坏性操作需先向用户输出风险提示方案并获得明确确认。\n"
                "→ 依据：AGENTS.md 禁止清单、~/.claude/CLAUDE.md 删除操作确认规则"
            )
            print(msg, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()