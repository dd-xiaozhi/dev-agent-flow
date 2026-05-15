#!/usr/bin/env python3
"""
session-end.py — Session 结束时记录活动日志

事件：SessionEnd（Claude Code 每次退出时触发）
行为：
  1. 读取当前任务上下文
  2. 写入 session:end 事件到事件总线
  3. 更新任务报告（完成时长、文件变更统计）
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── 集中路径常量 ──────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parents[2]
_CHATLABS_DIR = _PROJECT_DIR / ".chatlabs"
_STATE_DIR = _CHATLABS_DIR / "state"
_REPORTS_DIR = _CHATLABS_DIR / "reports" / "tasks"
_CURRENT_TASK_FILE = _STATE_DIR / "current_task"
_WORKFLOW_STATE_FILE = _STATE_DIR / "workflow-state.json"

# 加载事件总线工具函数（events 已迁入 flow-engine skill）
sys.path.insert(0, str(_PROJECT_DIR / ".claude" / "skills" / "flow-engine" / "scripts"))
from events import emit_event


# ── 类型定义 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class SessionInfo:
    """会话信息。"""
    task_id: Optional[str]
    story_id: Optional[str]
    phase: Optional[str]
    session_start: Optional[str]
    session_duration: Optional[int]
    files_changed: list[str] = field(default_factory=list)


@dataclass
class SessionEndOutput:
    """session-end 输出结构。"""
    task_id: Optional[str]
    story_id: Optional[str]
    phase: Optional[str]
    session_duration: Optional[int]
    files_changed_count: int
    session_start: Optional[str]

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ── 辅助函数 ──────────────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_current_task_id() -> Optional[str]:
    """获取当前活跃的 task_id。"""
    try:
        return _CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def read_workflow_state() -> dict:
    """读取 workflow-state.json 获取 story_id 和 phase。"""
    if not _WORKFLOW_STATE_FILE.exists():
        return {}
    try:
        return json.loads(_WORKFLOW_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_session_start_time() -> Optional[str]:
    """从环境变量获取会话开始时间。"""
    return os.environ.get("CLAUDE_SESSION_START")


def compute_session_duration(session_start: Optional[str]) -> Optional[int]:
    """计算会话时长（秒）。"""
    if not session_start:
        return None
    try:
        start_dt = datetime.fromisoformat(session_start)
        return int((utc_now() - start_dt).total_seconds())
    except Exception:
        return None


# ── 文件变更追踪 ──────────────────────────────────────────────────

@dataclass(frozen=True)
class FileChange:
    """文件变更记录。"""
    path: str
    tool: str
    type: str


def get_files_changed(task_id: str) -> list[str]:
    """从 audit.jsonl 读取本次会话修改的文件列表（去重）。"""
    audit_file = _REPORTS_DIR / task_id / "audit.jsonl"
    if not audit_file.exists():
        return []

    paths: set[str] = set()
    for line in audit_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") in ("edit", "write") and ev.get("path"):
            paths.add(ev["path"])

    return sorted(paths)


# ── 任务会话更新 ──────────────────────────────────────────────────

def update_task_session_end(
    task_id: str,
    duration: Optional[int],
    files: list[str],
) -> None:
    """更新任务的会话结束信息。"""
    meta_file = _REPORTS_DIR / task_id / "meta.json"
    if not meta_file.exists():
        return

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))

        # 更新会话历史
        sessions = meta.get("sessions", [])
        sessions.append({
            "end_time": utc_now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "duration_seconds": duration,
            "files_changed": len(files),
        })
        meta["sessions"] = sessions

        # 更新统计
        total_duration = sum(s.get("duration_seconds") or 0 for s in sessions)
        meta["total_duration_seconds"] = total_duration

        meta_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    except Exception:
        pass  # 降级：更新失败不阻断


# ── 主逻辑 ──────────────────────────────────────────────────────

def build_session_info() -> SessionInfo:
    """构建会话信息。"""
    # 获取当前任务
    task_id = get_current_task_id()

    # 读取工作流状态
    state = read_workflow_state()
    story_id = state.get("story_id")
    phase = state.get("phase")

    # 计算会话时长
    session_start = get_session_start_time()
    session_duration = compute_session_duration(session_start)

    # 统计文件变更
    files_changed = get_files_changed(task_id) if task_id else []

    return SessionInfo(
        task_id=task_id,
        story_id=story_id,
        phase=phase,
        session_start=session_start,
        session_duration=session_duration,
        files_changed=files_changed,
    )


def main() -> None:
    # 构建会话信息
    info = build_session_info()

    # 写入事件日志
    emit_event("session:end", {
        "task_id": info.task_id,
        "story_id": info.story_id,
        "phase": info.phase,
        "files_changed": info.files_changed,
    })

    # 更新任务报告的会话结束信息
    if info.task_id:
        update_task_session_end(
            info.task_id,
            info.session_duration,
            info.files_changed,
        )

    # 输出结果
    output = SessionEndOutput(
        task_id=info.task_id,
        story_id=info.story_id,
        phase=info.phase,
        session_duration=info.session_duration,
        files_changed_count=len(info.files_changed),
        session_start=info.session_start,
    )

    print(json.dumps(output.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()