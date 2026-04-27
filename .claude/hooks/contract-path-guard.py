#!/usr/bin/env python3
"""
contract-path-guard — 强制契约文件输出位置 + source 目录只读保护

事件：PreToolUse (matcher: Write|Edit)

规则（优先级从高到低）：

  1. source/ 只读保护
     - 禁止对 .chatlabs/stories/<story_id>/source/ 目录下任何文件做 Write/Edit
     - source/ 是原始需求档案（来自 TAPD / Figma / 口述），不可覆写
     - 唯一例外：模板文件 .claude/templates/ 不在保护范围

  2. 契约/OpenAPI 位置强制
     - 契约文件（contract.md / openapi.yaml/.yml）只能写在 .chatlabs/stories/<story_id>/
     - 禁止写到 docs/、.claude/tasks/、.claude/ 等其他目录

原则：KISS — 优先检查 source/ 路径（最严格）；命中即 deny；否则静默放行
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# source/ 目录中允许写入的前缀（source/ 本身禁止写入内容文件）
ALLOWED_SOURCE_PREFIXES = (
    ".claude/templates/",
    ".claude/skills/",
    ".claude/commands/",
    ".claude/agents/",
    ".claude/hooks/",
)

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


def is_source_protected(rel: str) -> bool:
    """
    判断路径是否落入 source/ 只读保护范围。
    保护：.chatlabs/stories/<story_id>/source/<任意文件>
    排除：.claude/templates/ 等白名单前缀（这些模板目录本身可写）
    """
    if not rel.startswith(".chatlabs/stories/"):
        return False
    parts = rel.split("/")
    # 格式：.chatlabs/stories/<story_id>/source/...
    if len(parts) < 4:
        return False
    # parts[0]=".chatlabs", parts[1]="stories", parts[2]="<story_id>", parts[3]="source"
    return parts[3] == "source"


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

    # ── 规则 1：source/ 只读保护（最高优先级）──────────────────────────────
    if is_source_protected(rel):
        reason = (
            "❌ source/ 目录只读，禁止写入\n"
            f"  目标路径：{rel}\n"
            "  source/ 是原始需求档案（TAPD / Figma / 口述），不可覆写\n"
            "  doc-librarian 只能读取 source/ 来理解需求，产出只能写到 contract.md / openapi.yaml\n"
            "  依据：.claude/artifacts-layout.md「source/ 只读档案」\n"
            "  如需添加新 source 文件，请通过 /tapd-story-start 或 /story-start 入口命令归档"
        )
        _deny(reason, hook_input)
        return

    # ── 规则 2：契约文件位置强制 ───────────────────────────────────────
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
