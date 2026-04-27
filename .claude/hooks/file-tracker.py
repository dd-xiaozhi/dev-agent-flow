#!/usr/bin/env python3
"""
file-tracker.py — 全量文件操作追踪（audit.jsonl writer）

事件:PostToolUse (Read / Edit / Write / Bash)
行为:每个事件追加一行 JSON 到 reports/tasks/<task_id>/audit.jsonl
  - Read  → {"type":"read","tool":"Read","path":...}
  - Edit  → {"type":"edit","tool":"Edit","path":...,"diff_lines":N}
  - Write → {"type":"write","tool":"Write","path":...}
  - Bash  → {"type":"bash","tool":"Bash","cmd":...,"exit":N,...}

不做事件级去重——audit.jsonl 是审计流,重复出现的 read 是正常信号。
消费方按需 dedup。

前置:.chatlabs/state/current_task 存在 + task 目录存在
降级:缺失任一条件直接退出,不阻断主流程。
"""
from __future__ import annotations
import sys
import json
from pathlib import Path
from datetime import datetime

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import CURRENT_TASK, TASK_REPORTS  # noqa: E402
from member_log_utils import get_current_member, append_member_log  # noqa: E402

CURRENT_TASK_FILE = CURRENT_TASK
REPORTS_DIR = TASK_REPORTS


def get_active_task_id() -> str | None:
    """从 .current_task 读取当前 task_id,不存在则返回 None"""
    try:
        return CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def task_dir(task_id: str) -> Path:
    return REPORTS_DIR / task_id


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def audit_log(task_id: str, event: dict) -> None:
    """追加一行 JSON 到 audit.jsonl,顺手刷新 meta.json/_index.jsonl 的 updated_at"""
    audit_file = task_dir(task_id) / "audit.jsonl"
    event.setdefault("ts", ts())
    line = json.dumps(event, ensure_ascii=False)
    with audit_file.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    _touch_updated_at(task_id, event["ts"])


def _diff_lines(old_string: str, new_string: str) -> int:
    """估算 diff 行数(基于换行符计数,粗粒度)"""
    old_n = old_string.count("\n") + (1 if old_string else 0)
    new_n = new_string.count("\n") + (1 if new_string else 0)
    return abs(new_n - old_n) + min(old_n, new_n)


def _touch_updated_at(task_id: str, updated_at: str) -> None:
    """刷新 meta.json + _index.jsonl 中的 updated_at(降级容错,失败不阻断)"""
    meta_file = task_dir(task_id) / "meta.json"
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            meta["updated_at"] = updated_at
            meta_file.write_text(
                json.dumps(meta, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    index_file = REPORTS_DIR / "_index.jsonl"
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


def _record_member_change(task_id: str, file_path: str) -> None:
    """成员活动日志(保留原行为)"""
    member = get_current_member()
    if file_path.endswith(".java"):
        summary = f"修改 Java 文件: {file_path}"
    elif file_path.endswith(".py"):
        summary = f"修改 Python 文件: {file_path}"
    else:
        summary = f"修改文件: {file_path}"

    append_member_log(
        event_type="file-changed",
        member=member,
        task_id=task_id,
        files=[file_path],
        summary=summary,
    )


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool = hook_input.get("tool", "")
    file_path = hook_input.get("file_path", "")
    command = hook_input.get("command", "")
    exit_code = hook_input.get("exit_code", 0)
    output = hook_input.get("output", "") or ""
    old_string = hook_input.get("old_string", "")
    new_string = hook_input.get("new_string", "")

    task_id = get_active_task_id()
    if not task_id:
        sys.exit(0)

    td = task_dir(task_id)
    if not td.exists():
        sys.exit(0)

    if tool == "Read" and file_path:
        audit_log(task_id, {"type": "read", "tool": "Read", "path": file_path})
    elif tool == "Edit" and file_path:
        audit_log(task_id, {
            "type": "edit",
            "tool": "Edit",
            "path": file_path,
            "diff_lines": _diff_lines(old_string, new_string),
        })
        _record_member_change(task_id, file_path)
    elif tool == "Write" and file_path:
        audit_log(task_id, {
            "type": "write",
            "tool": "Write",
            "path": file_path,
        })
        _record_member_change(task_id, file_path)
    elif tool == "Bash" and command:
        event: dict = {
            "type": "bash",
            "tool": "Bash",
            "cmd": command[:500],
            "exit": exit_code,
        }
        if output and exit_code != 0:
            first_line = output.strip().splitlines()
            if first_line:
                event["stderr_first_line"] = first_line[0][:200]
        audit_log(task_id, event)


if __name__ == "__main__":
    main()
