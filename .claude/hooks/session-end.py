#!/usr/bin/env python3
"""
session-end — Session 结束时记录活动日志

事件: SessionEnd
Matcher: ""（空，全匹配）

触发条件:
  - Claude Code 每次退出时触发
  - 存在 active task_id

行为:
  1. 读当前 task_id 与 story_id（通过 _index.jsonl 反查）
  2. 通过 TaskJsonStore 加载 task.json
  3. 更新会话时长 + 会话历史并写回

降级 / 阻断:
  - 阻断条件: 无
  - 失败兜底: 无 active task → 静默退出；任务元数据全部从 task.json 读写（meta.json 已废）

产物:
  - .chatlabs/reports/handoffs/（可选；更新任务报告）
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── 集中路径常量 ──────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parents[2]
_CHATLABS_DIR = _PROJECT_DIR / ".chatlabs"
_STATE_DIR = _CHATLABS_DIR / "state"
_REPORTS_DIR = _CHATLABS_DIR / "reports" / "tasks"
_STORE_DIR = _CHATLABS_DIR / "task" / "store"
_CURRENT_TASK_FILE = _STATE_DIR / "current_task"
_TASK_INDEX = _REPORTS_DIR / "_index.jsonl"

# 加载 TaskJsonStore（task.json 单写者门面）
sys.path.insert(0, str(_PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
from task_store import TaskJsonStore  # noqa: E402

# session 级事件已废弃；本 hook 不再调用事件总线。


# ── 类型定义 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class SessionInfo:
    """会话信息。"""
    task_id: Optional[str]
    story_id: Optional[str]
    phase: Optional[str]
    session_start: Optional[str]
    session_duration: Optional[int]


@dataclass
class SessionEndOutput:
    """session-end 输出结构。"""
    task_id: Optional[str]
    story_id: Optional[str]
    phase: Optional[str]
    session_duration: Optional[int]
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


def lookup_story_id(task_id: str) -> Optional[str]:
    """通过 _index.jsonl 反查 task_id → story_id；未命中时兜底用 task_id 探测。"""
    if _TASK_INDEX.exists():
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
    probe = TaskJsonStore.load_by_story(task_id)
    if probe.data.get("task_id") == task_id:
        return task_id
    return None


def read_per_story_state(story_id: str) -> dict:
    """读取 task.json.workflow 的扁平视图（task.json 是 SSOT）。"""
    store = TaskJsonStore.load_by_story(story_id)
    if not store.data.get("task_id"):
        return {}
    td = store.data
    wf = td.get("workflow") or {}
    return {
        "story_id": td.get("story_id") or story_id,
        "phase": wf.get("phase"),
    }


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


# ── 任务会话更新 ──────────────────────────────────────────────────

def update_task_session_end(
    task_id: str,
    duration: Optional[int],
) -> None:
    """更新任务的会话结束信息到 task.json.workflow.sessions[]。"""
    story_id = lookup_story_id(task_id)
    if not story_id:
        return
    try:
        store = TaskJsonStore.load_by_story(story_id)
        if not store.data.get("task_id"):
            return
        wf = store.get_workflow() or {}
        sessions = list(wf.get("sessions") or [])
        sessions.append({
            "end_time": utc_now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "duration_seconds": duration,
        })
        total_duration = sum(s.get("duration_seconds") or 0 for s in sessions)
        store.update_workflow({
            "sessions": sessions,
            "total_duration_seconds": total_duration,
        })
        store.save()
    except Exception:
        pass  # 降级：更新失败不阻断


# ── 主逻辑 ──────────────────────────────────────────────────────

def build_session_info() -> SessionInfo:
    """构建会话信息。"""
    # 获取当前任务
    task_id = get_current_task_id()

    # 通过 task_id → _index.jsonl 反查 story_id → task.json.workflow 取 phase
    story_id: Optional[str] = None
    phase: Optional[str] = None
    if task_id:
        story_id = lookup_story_id(task_id)
        if story_id:
            state = read_per_story_state(story_id)
            phase = state.get("phase")

    # 计算会话时长
    session_start = get_session_start_time()
    session_duration = compute_session_duration(session_start)

    return SessionInfo(
        task_id=task_id,
        story_id=story_id,
        phase=phase,
        session_start=session_start,
        session_duration=session_duration,
    )


def main() -> None:
    # 构建会话信息
    info = build_session_info()

    # session 级事件已废弃（events 仅承载任务级事件，写入 task.json.events）。

    # 更新任务报告的会话结束信息
    if info.task_id:
        update_task_session_end(
            info.task_id,
            info.session_duration,
        )

    # 输出结果
    output = SessionEndOutput(
        task_id=info.task_id,
        story_id=info.story_id,
        phase=info.phase,
        session_duration=info.session_duration,
        session_start=info.session_start,
    )

    print(json.dumps(output.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()