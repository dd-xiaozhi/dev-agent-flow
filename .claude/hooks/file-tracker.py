#!/usr/bin/env python3
"""
file-tracker.py — 全量文件操作追踪（audit.jsonl writer）

事件:PostToolUse (Read / Edit / Write / Bash)
行为:每个事件追加一行 JSON 到 reports/tasks/<task_id>/audit.jsonl

不做事件级去重——audit.jsonl 是审计流,重复出现的 read 是正常信号。
消费方按需 dedup。

前置:.chatlabs/state/current_task 存在 + task 目录存在
降级:缺失任一条件直接退出,不阻断主流程。
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional, Union

# ── 集中路径常量 ──────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parents[2]
_CHATLABS_DIR = _PROJECT_DIR / ".chatlabs"
_REPORTS_DIR = _CHATLABS_DIR / "reports" / "tasks"
_CURRENT_TASK_FILE = _CHATLABS_DIR / "state" / "current_task"


# ── 类型定义 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReadEvent:
    """Read 工具事件。"""
    type: Literal["read"] = "read"
    tool: Literal["Read"] = "Read"
    path: str
    ts: str = field(default="")

    def __post_init__(self):
        if not self.ts:
            object.__setattr__(self, "ts", ts())

    def to_dict(self) -> dict:
        return {"type": self.type, "tool": self.tool, "path": self.path, "ts": self.ts}


@dataclass(frozen=True)
class EditEvent:
    """Edit 工具事件。"""
    type: Literal["edit"] = "edit"
    tool: Literal["Edit"] = "Edit"
    path: str
    diff_lines: int
    ts: str = field(default="")

    def __post_init__(self):
        if not self.ts:
            object.__setattr__(self, "ts", ts())

    def to_dict(self) -> dict:
        return {
            "type": self.type, "tool": self.tool,
            "path": self.path, "diff_lines": self.diff_lines, "ts": self.ts,
        }


@dataclass(frozen=True)
class WriteEvent:
    """Write 工具事件。"""
    type: Literal["write"] = "write"
    tool: Literal["Write"] = "Write"
    path: str
    ts: str = field(default="")

    def __post_init__(self):
        if not self.ts:
            object.__setattr__(self, "ts", ts())

    def to_dict(self) -> dict:
        return {"type": self.type, "tool": self.tool, "path": self.path, "ts": self.ts}


@dataclass(frozen=True)
class BashEvent:
    """Bash 工具事件。"""
    type: Literal["bash"] = "bash"
    tool: Literal["Bash"] = "Bash"
    cmd: str
    exit: int
    stderr_first_line: Optional[str] = None
    ts: str = field(default="")

    def __post_init__(self):
        if not self.ts:
            object.__setattr__(self, "ts", ts())

    def to_dict(self) -> dict:
        result = {"type": self.type, "tool": self.tool, "cmd": self.cmd, "exit": self.exit, "ts": self.ts}
        if self.stderr_first_line:
            result["stderr_first_line"] = self.stderr_first_line
        return result


# Union type for all audit events
AuditEvent = Union[ReadEvent, EditEvent, WriteEvent, BashEvent]


# ── 辅助函数 ──────────────────────────────────────────────────────

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def get_active_task_id() -> Optional[str]:
    """从 .current_task 读取当前 task_id,不存在则返回 None。"""
    try:
        return _CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def task_dir(task_id: str) -> Path:
    return _REPORTS_DIR / task_id


def _diff_lines(old_string: str, new_string: str) -> int:
    """估算 diff 行数(基于换行符计数,粗粒度)。"""
    old_n = old_string.count("\n") + (1 if old_string else 0)
    new_n = new_string.count("\n") + (1 if new_string else 0)
    return abs(new_n - old_n) + min(old_n, new_n)


def _extract_stderr_first_line(output: str) -> Optional[str]:
    """从 stderr 输出提取第一行（截断到 200 字符）。"""
    first_line = output.strip().splitlines()
    return first_line[0][:200] if first_line else None


# ── Audit 写入 ─────────────────────────────────────────────────────

def audit_log(task_id: str, event: AuditEvent) -> None:
    """追加一条 audit 事件到 audit.jsonl。"""
    audit_file = task_dir(task_id) / "audit.jsonl"
    line = json.dumps(event.to_dict(), ensure_ascii=False)
    with audit_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    touch_updated_at(task_id, event.ts)


def touch_updated_at(task_id: str, updated_at: str) -> None:
    """刷新 meta.json + _index.jsonl 中的 updated_at(降级容错,失败不阻断)。"""
    meta_file = task_dir(task_id) / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["updated_at"] = updated_at
            meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        except Exception:
            pass

    index_file = _REPORTS_DIR / "_index.jsonl"
    if not index_file.exists():
        return
    try:
        lines = index_file.read_text(encoding="utf-8").strip().splitlines()
        new_lines: list[str] = []
        for line in lines:
            try:
                entry = json.loads(line)
                if entry.get("task_id") == task_id:
                    entry["updated_at"] = updated_at
                new_lines.append(json.dumps(entry, ensure_ascii=False))
            except json.JSONDecodeError:
                new_lines.append(line)
        index_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    except Exception:
        pass


# ── 事件工厂 ──────────────────────────────────────────────────────

def create_read_event(path: str) -> ReadEvent:
    return ReadEvent(path=path)


def create_edit_event(path: str, old_string: str, new_string: str) -> EditEvent:
    return EditEvent(path=path, diff_lines=_diff_lines(old_string, new_string))


def create_write_event(path: str) -> WriteEvent:
    return WriteEvent(path=path)


def create_bash_event(command: str, exit_code: int, output: str) -> BashEvent:
    stderr = None
    if output and exit_code != 0:
        stderr = _extract_stderr_first_line(output)
    return BashEvent(cmd=command[:500], exit=exit_code, stderr_first_line=stderr)


# ── Hook 接口 ─────────────────────────────────────────────────────

@dataclass
class HookInput:
    """Hook 输入数据结构。"""
    tool: str
    file_path: str
    command: str
    exit_code: int
    output: str
    old_string: str
    new_string: str


def parse_hook_input(stdin_data: dict) -> HookInput:
    return HookInput(
        tool=stdin_data.get("tool", ""),
        file_path=stdin_data.get("file_path", ""),
        command=stdin_data.get("command", ""),
        exit_code=stdin_data.get("exit_code", 0),
        output=stdin_data.get("output", "") or "",
        old_string=stdin_data.get("old_string", ""),
        new_string=stdin_data.get("new_string", ""),
    )


# ── 主逻辑 ──────────────────────────────────────────────────────

def main() -> None:
    try:
        hook_input = parse_hook_input(json.load(sys.stdin))
    except Exception:
        sys.exit(0)

    task_id = get_active_task_id()
    if not task_id:
        sys.exit(0)

    td = task_dir(task_id)
    if not td.exists():
        sys.exit(0)

    # 根据工具类型创建对应事件
    event: Optional[AuditEvent] = None
    if hook_input.tool == "Read" and hook_input.file_path:
        event = create_read_event(hook_input.file_path)
    elif hook_input.tool == "Edit" and hook_input.file_path:
        event = create_edit_event(
            hook_input.file_path, hook_input.old_string, hook_input.new_string
        )
    elif hook_input.tool == "Write" and hook_input.file_path:
        event = create_write_event(hook_input.file_path)
    elif hook_input.tool == "Bash" and hook_input.command:
        event = create_bash_event(
            hook_input.command, hook_input.exit_code, hook_input.output
        )

    if event:
        audit_log(task_id, event)


if __name__ == "__main__":
    main()