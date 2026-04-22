#!/usr/bin/env python3
"""
file-tracker.py — 全量文件操作追踪

事件：PostToolUse（Read / Edit / Write / Bash）
行为：
  - Read → 追加到 reports/tasks/<task_id>/file-reads.md（去重，同文件只记首次）
  - Edit / Write → 追加到 reports/tasks/<task_id>/diff-log.md（每次 diff 都记）
  - Bash → 追加到 reports/tasks/<task_id>/diff-log.md（命令 + exit code）

前置条件：.chatlabs/state/current_task 文件存在（由命令层写入 task_id）
降级：若无 active task 或文件路径，直接退出（不阻断流程）
"""
from __future__ import annotations
import sys
import json
import os
from pathlib import Path
from datetime import datetime

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import PROJECT_DIR, CURRENT_TASK, TASK_REPORTS  # noqa: E402
from member_log_utils import get_current_member, append_member_log  # noqa: E402

CURRENT_TASK_FILE = CURRENT_TASK
REPORTS_DIR = TASK_REPORTS


def get_active_task_id() -> str | None:
    """从 .current_task 读取当前 task_id，不存在则返回 None"""
    try:
        return CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def task_dir(task_id: str) -> Path:
    return REPORTS_DIR / task_id


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def _read_seen_files(reads_file: Path) -> set[str]:
    """从 file-reads.md 解析 _seen_files 集合"""
    seen: set[str] = set()
    if not reads_file.exists():
        return seen
    content = reads_file.read_text()
    in_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "<!-- _seen_files_start -->":
            in_section = True
            continue
        if stripped == "<!-- _seen_files_end -->":
            in_section = False
            continue
        if in_section and stripped.startswith("- "):
            seen.add(stripped[2:])
    return seen


def _write_seen_files(reads_file: Path, seen: set[str], task_id: str):
    """将 _seen_files 写回 file-reads.md 的注释块中"""
    lines: list[str] = []
    if reads_file.exists():
        content = reads_file.read_text()
        in_section = False
        for line in content.splitlines():
            if line.strip() == "<!-- _seen_files_start -->":
                lines.append(line)
                lines.append(f"总读取文件数: {len(seen)}")
                for f in sorted(seen):
                    lines.append(f"- {f}")
                in_section = True
                continue
            if line.strip() == "<!-- _seen_files_end -->":
                in_section = False
            if not in_section:
                lines.append(line)
    else:
        lines = [
            f"# {task_id} 文件读取记录",
            "> ⚠️ **由 file-tracker.py Hook 自动追加，Agent 不编辑本文件**。",
            "",
            "## 已读取文件清单",
            "<!-- _seen_files_start -->",
            f"总读取文件数: {len(seen)}",
        ]
        for f in sorted(seen):
            lines.append(f"- {f}")
        lines.extend(["<!-- _seen_files_end -->", ""])
    reads_file.write_text("\n".join(lines))


def track_read(task_id: str, file_path: str):
    """追加 Read 到 file-reads.md，去重"""
    if not file_path:
        return
    td = task_dir(task_id)
    reads_file = td / "file-reads.md"
    seen = _read_seen_files(reads_file)

    if file_path in seen:
        return  # 已记录，跳过

    seen.add(file_path)
    entry = f"- {ts()} {file_path}\n"

    if reads_file.exists():
        content = reads_file.read_text()
        marker = "<!-- _seen_files_start -->"
        if marker in content:
            idx = content.index(marker)
            content = content[:idx] + entry + content[idx:]
        else:
            content += entry
        reads_file.write_text(content)
    else:
        reads_file.write_text(
            f"# {task_id} 文件读取记录\n\n"
            f"> 由 file-tracker.py 自动生成\n\n"
            f"{entry}"
        )

    _write_seen_files(reads_file, seen, task_id)
    _update_meta_field(task_id, "file_read_count", len(seen))


def track_diff(
    task_id: str,
    tool: str,
    file_path: str,
    old_string: str = "",
    new_string: str = "",
    command: str = "",
    exit_code: int = 0,
    output: str = "",
):
    """追加 Edit/Write/Bash 到 diff-log.md"""
    td = task_dir(task_id)
    diff_file = td / "diff-log.md"

    lines: list[str] = [f"## {ts()}", ""]

    if tool in ("Edit", "Write"):
        lines.append(f"**文件**: `{file_path}`")
        lines.append(f"**工具**: `{tool}`")
        op: list[str] = []
        if old_string:
            truncated = old_string[:80] + ("..." if len(old_string) > 80 else "")
            op.append(f"~ 修改（旧）: `{truncated}`")
        if new_string:
            truncated = new_string[:80] + ("..." if len(new_string) > 80 else "")
            op.append(f"+ 新增: `{truncated}`")
        lines.append(f"**操作**: {' | '.join(op)}")
        if tool == "Edit":
            old_snippet = old_string[:200] if old_string else "(empty)"
            new_snippet = new_string[:200] if new_string else "(empty)"
            lines.append(f"\n```diff\n- {old_snippet}\n+ {new_snippet}\n```")

    elif tool == "Bash":
        cmd_trunc = command[:200] + ("..." if len(command) > 200 else "")
        exit_icon = "✅" if exit_code == 0 else "❌"
        lines.append(f"**命令**: `{cmd_trunc}`")
        lines.append(f"**Exit**: `{exit_code}` {exit_icon}")
        if output and exit_code != 0:
            out_trunc = output[:200].strip() + ("..." if len(output) > 200 else "")
            lines.append(f"**输出**: `{out_trunc}`")

    lines.extend(["\n---", ""])
    entry = "\n".join(lines)

    if diff_file.exists():
        diff_file.write_text(diff_file.read_text() + entry)
    else:
        diff_file.write_text(
            f"# {task_id} 文件改动记录\n\n"
            f"> ⚠️ **由 file-tracker.py Hook 自动追加，Agent 不编辑本文件**。\n\n"
            f"{entry}"
        )

    _update_diff_count(task_id)

    # 写入成员活动日志（Edit/Write 时记录文件变更）
    if tool in ("Edit", "Write") and file_path:
        member = get_current_member()
        summary = f"修改文件: {file_path}"
        if file_path.endswith(".java"):
            summary = f"修改 Java 文件: {file_path}"
        elif file_path.endswith(".py"):
            summary = f"修改 Python 文件: {file_path}"

        append_member_log(
            event_type="file-changed",
            member=member,
            task_id=task_id,
            files=[file_path],
            summary=summary,
        )


def _update_diff_count(task_id: str):
    """更新 diff-log.md 中的条目数"""
    td = task_dir(task_id)
    diff_file = td / "diff-log.md"
    if not diff_file.exists():
        return
    text = diff_file.read_text()
    count = sum(1 for line in text.splitlines() if line.startswith("## "))
    _update_meta_field(task_id, "diff_file_count", count)


def _update_meta_field(task_id: str, field: str, value: int):
    """原子更新 meta.json 中的指定数字字段"""
    td = task_dir(task_id)
    meta_file = td / "meta.json"
    index_file = REPORTS_DIR / "_index.jsonl"
    if not meta_file.exists():
        return
    try:
        import json as _json
        meta = _json.loads(meta_file.read_text())
        meta[field] = value
        meta["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        meta_file.write_text(_json.dumps(meta, indent=2, ensure_ascii=False))

        if index_file.exists():
            lines = index_file.read_text().strip().splitlines()
            new_lines: list[str] = []
            for line in lines:
                try:
                    entry = _json.loads(line)
                    if entry.get("task_id") == task_id:
                        entry[field] = value
                        entry["updated_at"] = meta["updated_at"]
                    new_lines.append(_json.dumps(entry, ensure_ascii=False))
                except _json.JSONDecodeError:
                    new_lines.append(line)
            index_file.write_text("\n".join(new_lines) + "\n")
    except Exception:
        pass  # 降级：meta 更新失败不阻断主流程


def main():
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
        sys.exit(0)  # 无 active task，跳过追踪

    td = task_dir(task_id)
    if not td.exists():
        sys.exit(0)  # task 目录不存在，跳过

    if tool == "Read":
        track_read(task_id, file_path)
    elif tool in ("Edit", "Write"):
        track_diff(task_id, tool, file_path, old_string, new_string)
    elif tool == "Bash" and command:
        track_diff(task_id, tool, file_path,
                   command=command, exit_code=exit_code, output=output)


if __name__ == "__main__":
    main()
