#!/usr/bin/env python3
"""
contract-path-guard — 强制契约文件输出位置

事件：PreToolUse (matcher: Write|Edit)

规则：
  - 契约文件（contract.md / openapi.yaml/.yml）只能写在 .chatlabs/stories/<story_id>/
  - 禁止写到 docs/、.claude/tasks/、.claude/ 等其他目录

原则：KISS — 命中受保护文件名且路径不合法即 deny；否则静默放行
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# 受保护文件名（basename）
PROTECTED_BASENAMES = {"contract.md", "openapi.yaml", "openapi.yml"}

# 允许的契约输出目录前缀
ALLOWED_CONTRACT_PREFIX = ".chatlabs/stories/"

# 明确禁止的契约输出目录前缀
FORBIDDEN_CONTRACT_PREFIXES = ("docs/", ".claude/tasks/")


def normalize(path: str) -> str:
    """统一为正斜杠相对路径；优先剥离 CLAUDE_PROJECT_DIR 前缀"""
    proj = os.environ.get("CLAUDE_PROJECT_DIR", "")
    p = path.replace("\\", "/")
    if proj:
        proj_norm = proj.replace("\\", "/").rstrip("/")
        if p.startswith(proj_norm + "/"):
            p = p[len(proj_norm) + 1:]
    return p.lstrip("/")


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)

    tool_input = hook_input.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not file_path:
        sys.exit(0)

    rel = normalize(file_path)

    # ── 契约文件位置强制 ───────────────────────────────────────
    basename = os.path.basename(rel)
    if basename not in PROTECTED_BASENAMES:
        sys.exit(0)  # 非契约文件，放行

    # 合法路径：放行
    if rel.startswith(ALLOWED_CONTRACT_PREFIX):
        sys.exit(0)

    # 命中禁区：详细报错
    forbidden_hit = next((p for p in FORBIDDEN_CONTRACT_PREFIXES if rel.startswith(p)), None)
    if forbidden_hit:
        reason = (
            f"❌ 契约文件位置违规：{rel}\n"
            f"禁止写入前缀：{forbidden_hit}\n"
            f"唯一合法位置：{ALLOWED_CONTRACT_PREFIX}<story_id>/{basename}\n"
            "依据：.claude/artifacts-layout.md「stories/ 结构」\n"
            "如确需调整该约定，请先修改约定文档与本 hook，再重试"
        )
    else:
        reason = (
            f"❌ 契约文件位置违规：{rel}\n"
            f"唯一合法位置：{ALLOWED_CONTRACT_PREFIX}<story_id>/{basename}\n"
            "依据：.claude/artifacts-layout.md「stories/ 结构」"
        )
    _deny(reason, hook_input)


def _deny(reason: str, hook_input: dict) -> None:
    """输出 deny 决定并退出"""
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
