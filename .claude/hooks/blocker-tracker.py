#!/usr/bin/env python3
"""
blocker-tracker — 工具层 Blocker 自动追踪

事件: PostToolUse
Matcher: Bash

触发条件:
  - tool_response.exit_code != 0
  - docs/state/current_task 文件存在（active task_id）

行为:
  1. 读取当前 task_id 与 story_id
  2. 推断 Blocker 类型（环境/执行/未知）
  3. 追加条目到 blockers.md 并更新 task.json.workflow.blocker_count

降级 / 阻断:
  - 阻断条件: 无
  - 失败兜底: exit_code == 0 或无 active task → 直接退出

产物:
  - docs/reports/tasks/<task_id>/blockers.md
  - task.json.workflow.blocker_count（递增）
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

# ── 集中路径常量 ──────────────────────────────────────────────────
# CLAUDE_PROJECT_DIR 优先（settings.json hook 命令始终带该变量）；fallback 用
# .absolute() 而非 .resolve()——项目 .claude 常是 symlink，resolve() 会穿透到
# symlink 目标目录，导致 blocker 写到错误项目。详见 session-review 2026-06-05。
_PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[2])
))
_CHATLABS_DIR = _PROJECT_DIR / "docs"
_REPORTS_DIR = _CHATLABS_DIR / "reports" / "tasks"
_CURRENT_TASK_FILE = _CHATLABS_DIR / "state" / "current_task"
_TASK_INDEX = _REPORTS_DIR / "_index.jsonl"

# 加载 TaskJsonStore（task.json 单写者门面）
sys.path.insert(0, str(_PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
from task_store import TaskJsonStore  # noqa: E402


# ── 类型定义 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class BlockerType:
    """Blocker 类型标识。"""
    category: str  # 环境 / 执行 / 未知
    subcategory: str

    def format(self) -> str:
        return f"{self.category}-{self.subcategory}"


@dataclass(frozen=True)
class BlockerEntry:
    """Blocker 条目完整数据。"""
    timestamp: str
    source: str
    blocker_type: BlockerType
    tool: str
    command: str
    exit_code: int
    description: str
    hint_category: str = "Hook-auto"

    def format_markdown(self) -> str:
        """格式化为 markdown 条目。"""
        cmd_display = self.command[:150] + "..." if len(self.command) > 150 else self.command
        return (
            f"## {self.timestamp} [Hook-auto]\n"
            f"- **类型**: {self.blocker_type.format()}\n"
            f"- **工具**: {self.tool}\n"
            f"- **命令**: `{cmd_display}`\n"
            f"- **Exit**: `{self.exit_code}`\n"
            f"- **描述**: {self.description}\n"
            f"- **根因**: （待 Agent 补充）\n"
            f"- **解决状态**: 待解决\n"
            f"- **解决方案**: （待 Agent 填写）\n\n"
            f"---\n"
        )


# ── Blocker 类型推断 ─────────────────────────────────────────────

# 类型匹配规则：正则模式 → (category, subcategory)
_BLOCKER_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # 环境-编译
    (re.compile(r"\b(mvn|gradle|javac|ant|sbt)\b"), "环境", "编译"),
    # 执行-测试
    (re.compile(r"\bpytest\b|\bjest\b|\bunittest\b|\bjunit\b"), "执行", "测试"),
    # 环境-权限
    (re.compile(r"permission denied|chmod|chown"), "环境", "权限"),
    # 环境-网络
    (re.compile(r"connection refused|connectionerror|econnrefused|etimedout|network is unreachable"), "环境", "网络"),
    # 环境-命令不存在
    (re.compile(r"not found|command not found|enoent|file does not exist"), "环境", "命令不存在"),
    # 环境-配置错误
    (re.compile(r"jsondecodeerror|yamlerror|syntaxerror|parse error"), "环境", "配置错误"),
    # 执行-版本控制
    (re.compile(r"git (merge|conflict|rebase)"), "执行", "版本控制"),
]


def infer_blocker_type(command: str, output: str) -> BlockerType:
    """从命令和输出推断 Blocker 类型。"""
    combined = (command + " " + output).lower()

    # 编译工具优先检测
    if re.search(r"\b(mvn|gradle|javac|ant|sbt)\b", combined):
        sub = "测试" if "test" in combined else "编译"
        return BlockerType(category="环境", subcategory=sub)

    for pattern, category, subcategory in _BLOCKER_PATTERNS:
        if pattern.search(combined):
            return BlockerType(category=category, subcategory=subcategory)

    return BlockerType(category="未知", subcategory="未知")


# ── 文件操作 ──────────────────────────────────────────────────────

def task_dir(task_id: str) -> Path:
    return _REPORTS_DIR / task_id


def blockers_file(task_id: str) -> Path:
    return task_dir(task_id) / "blockers.md"


def count_blockers(blockers_file: Path) -> int:
    """统计 blockers.md 中的总条目数（排除统计行）。"""
    if not blockers_file.exists():
        return 0
    return sum(
        1 for line in blockers_file.read_text().splitlines()
        if line.startswith("## ") and "[Hook-auto]" in line
    )


def _build_description(output: str) -> str:
    """从输出提取简短描述。"""
    if not output.strip():
        return "(无输出)"
    first_line = output.strip().splitlines()[0]
    return first_line[:300]


def append_blocker(
    task_id: str,
    command: str,
    exit_code: int,
    output: str,
) -> int:
    """追加 Blocker 条目到 blockers.md，返回总 blocker 数。"""
    # 创建 entry
    entry = BlockerEntry(
        timestamp=ts(),
        source="Hook-auto",
        blocker_type=infer_blocker_type(command, output),
        tool="Bash",
        command=command,
        exit_code=exit_code,
        description=_build_description(output),
    )

    bf = blockers_file(task_id)
    if bf.exists():
        content = bf.read_text()
        marker = "## 统计"
        if marker in content:
            idx = content.index(marker)
            content = content[:idx] + entry.format_markdown() + content[idx:]
        else:
            content = content + entry.format_markdown()
        bf.write_text(content)
    else:
        bf.write_text(
            f"# {task_id} 阻塞点记录\n\n"
            f"> 由 blocker-tracker.py 自动生成\n\n"
            + entry.format_markdown()
            + "\n## 统计\n"
            f"- **总 blocker 数**: 1\n"
            "- **已解决**: 0\n"
            "- **待解决**: 1\n"
        )

    total = count_blockers(bf)
    update_stats(bf, total)
    return total


def update_stats(blockers_file: Path, total: int) -> None:
    """更新 blockers.md 的统计行。"""
    if not blockers_file.exists():
        return
    content = blockers_file.read_text()
    lines = content.splitlines()
    new_lines = [
        line.replace("**总 blocker 数**: 0", f"**总 blocker 数**: {total}")
            .replace("**待解决**: 0", f"**待解决**: {total}")
        for line in lines
    ]
    blockers_file.write_text("\n".join(new_lines))

    task_id = blockers_file.parent.name
    update_meta(task_id, total)


def _lookup_story_id(task_id: str) -> Optional[str]:
    """通过 _index.jsonl 反查 task_id → story_id。"""
    if not _TASK_INDEX.exists():
        return None
    try:
        for line in _TASK_INDEX.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("task_id") == task_id:
                sid = entry.get("story_id")
                if sid:
                    return sid
    except Exception:
        pass
    return None


def update_meta(task_id: str, blocker_count: int) -> None:
    """把 blocker_count 写到 task.json.workflow 与 _index.jsonl。"""
    index_file = _TASK_INDEX
    now = ts()

    # 1) 更新 task.json.workflow.blocker_count
    story_id = _lookup_story_id(task_id)
    if story_id:
        try:
            store = TaskJsonStore.load_by_story(story_id)
            if store.data.get("task_id"):
                store.update_workflow({"blocker_count": blocker_count})
                store.save()
        except Exception:
            pass  # 降级：写失败不阻断 blocker 记录

    # 2) 更新 _index.jsonl（保留以便快速扫表）
    if index_file.exists():
        try:
            lines = index_file.read_text().strip().splitlines()
            new_lines = []
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("task_id") == task_id:
                        entry["blocker_count"] = blocker_count
                        entry["updated_at"] = now
                    new_lines.append(json.dumps(entry, ensure_ascii=False))
                except json.JSONDecodeError:
                    new_lines.append(line)
            index_file.write_text("\n".join(new_lines) + "\n")
        except Exception:
            pass


# ── 辅助函数 ──────────────────────────────────────────────────────

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def get_active_task_id() -> Optional[str]:
    """获取当前活跃的 task_id。"""
    try:
        return _CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


# ── Hook 接口 ─────────────────────────────────────────────────────

@dataclass
class HookInput:
    """Hook 输入数据结构。"""
    tool: str
    exit_code: int
    command: str
    output: str


def parse_hook_input(stdin_data: dict) -> HookInput:
    return HookInput(
        tool=stdin_data.get("tool", ""),
        exit_code=stdin_data.get("exit_code", 0),
        command=stdin_data.get("command", ""),
        output=stdin_data.get("output", "") or "",
    )


# ── 主逻辑 ──────────────────────────────────────────────────────

def main() -> None:
    try:
        hook_input = parse_hook_input(json.load(sys.stdin))
    except Exception:
        sys.exit(0)

    if hook_input.tool != "Bash" or hook_input.exit_code == 0:
        sys.exit(0)

    task_id = get_active_task_id()
    if not task_id:
        sys.exit(0)

    td = task_dir(task_id)
    if not td.exists():
        sys.exit(0)

    append_blocker(task_id, hook_input.command, hook_input.exit_code, hook_input.output)


if __name__ == "__main__":
    main()