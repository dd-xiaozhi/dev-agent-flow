#!/usr/bin/env python3
"""
session-end.py — Session 结束时记录活动日志

事件：SessionEnd（Claude Code 每次退出时触发）
行为：
  1. 读取当前任务上下文
  2. 记录 session-end 事件到成员活动日志
  3. 更新任务报告（完成时长、文件变更统计）

前置：.chatlabs/state/current_task 文件存在
依赖：member_log_utils.py（共享工具）
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import (  # noqa: E402
    PROJECT_DIR, CURRENT_TASK, TASK_REPORTS, STATE_DIR
)
from member_log_utils import (  # noqa: E402
    get_current_member, append_member_log
)
from workflow_state import emit_event  # noqa: E402

CURRENT_TASK_FILE = CURRENT_TASK
REPORTS_DIR = TASK_REPORTS


def get_session_start_time() -> str | None:
    """从 session-start hook 的输出或环境变量获取会话开始时间"""
    # 尝试从环境变量获取（session-start.py 可以设置）
    return os.environ.get("CLAUDE_SESSION_START")


def get_files_changed(task_id: str) -> list[str]:
    """从 diff-log.md 读取本次会话修改的文件列表"""
    diff_file = REPORTS_DIR / task_id / "diff-log.md"
    if not diff_file.exists():
        return []

    files = set()
    for line in diff_file.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("**文件**: `") and stripped.endswith("`"):
            # 提取文件名
            start = len("**文件**: `")
            end = stripped.rindex("`")
            files.add(stripped[start:end])

    return sorted(files)


def get_cases_completed(task_id: str) -> int | None:
    """从 meta.json 读取完成的 case 数量"""
    meta_file = REPORTS_DIR / task_id / "meta.json"
    if not meta_file.exists():
        return None

    try:
        meta = json.loads(meta_file.read_text())
        verdicts = meta.get("verdicts", {})
        if verdicts:
            return sum(1 for v in verdicts.values() if v == "PASS")
    except Exception:
        pass
    return None


def main():
    # 获取当前成员
    member = get_current_member()

    # 获取当前任务
    try:
        task_id = CURRENT_TASK_FILE.read_text().strip()
    except FileNotFoundError:
        task_id = None

    # 读取工作流状态获取更多信息
    workflow_state_file = STATE_DIR / "workflow-state.json"
    story_id = None
    phase = None
    if workflow_state_file.exists():
        try:
            state = json.loads(workflow_state_file.read_text())
            story_id = state.get("story_id")
            phase = state.get("phase")
        except Exception:
            pass

    # 计算会话时长
    session_start = get_session_start_time()
    session_duration = None
    if session_start:
        try:
            start_dt = datetime.fromisoformat(session_start)
            duration = datetime.now(timezone.utc) - start_dt
            session_duration = int(duration.total_seconds())
        except Exception:
            pass

    # 统计文件变更
    files_changed = get_files_changed(task_id) if task_id else []

    # 追加成员活动日志
    log_entry = {
        "member": member,
        "task_id": task_id,
        "story_id": story_id,
        "phase": phase,
        "session_duration": session_duration,
        "files_changed": len(files_changed),
        "session_start": session_start,
    }

    append_member_log(
        event_type="session-end",
        member=member,
        task_id=task_id,
        story_id=story_id,
        phase=phase,
        summary=f"会话结束，修改了 {len(files_changed)} 个文件" if files_changed else "会话结束，无文件修改",
        session_duration=session_duration,
        session_start=session_start,
    )

    # 写入事件日志
    emit_event("session:end", {
        "member": member,
        "task_id": task_id,
        "story_id": story_id,
        "phase": phase,
        "files_changed": files_changed,
    })

    # 更新任务报告的会话结束信息
    if task_id:
        _update_task_session_end(task_id, member, session_duration, files_changed)

    print(json.dumps(log_entry, ensure_ascii=False))


def _update_task_session_end(task_id: str, member: str, duration: int | None, files: list[str]):
    """更新任务的会话结束信息"""
    meta_file = REPORTS_DIR / task_id / "meta.json"
    if not meta_file.exists():
        return

    try:
        meta = json.loads(meta_file.read_text())

        # 更新会话历史
        if "sessions" not in meta:
            meta["sessions"] = []

        session_info = {
            "member": member,
            "end_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "duration_seconds": duration,
            "files_changed": len(files),
        }
        meta["sessions"].append(session_info)

        # 更新统计
        total_duration = sum(s.get("duration_seconds") or 0 for s in meta["sessions"])
        meta["total_duration_seconds"] = total_duration

        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    except Exception:
        pass  # 降级：更新失败不阻断


if __name__ == "__main__":
    main()