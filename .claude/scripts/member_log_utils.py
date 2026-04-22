#!/usr/bin/env python3
"""
member-log-utils.py — 成员活动日志共享工具

提供成员活动日志的读写接口，供其他 Hook/Skill 使用。
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Import centralized path constants
from paths import PROJECT_DIR, MEMBER_REPORTS, MEMBER_INDEX


def ts() -> str:
    """返回 ISO 8601 格式时间戳（UTC+8）"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")


def get_current_member() -> str:
    """获取当前成员身份（优先 git user.name，回退为 Claude Code 用户）"""
    # 尝试 git user.name
    try:
        import subprocess
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, timeout=5,
            cwd=str(PROJECT_DIR)
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    # 回退：从环境变量或默认用户
    return os.environ.get("CLAUDE_USER", "unknown")


def member_log_path(member_id: str) -> Path:
    """获取成员活动日志文件路径"""
    member_dir = MEMBER_REPORTS / member_id
    return member_dir / "activity.log"


def ensure_member_dir(member_id: str) -> Path:
    """确保成员目录存在，返回目录路径"""
    member_dir = MEMBER_REPORTS / member_id
    member_dir.mkdir(parents=True, exist_ok=True)
    return member_dir


def append_member_log(
    event_type: str,
    member: Optional[str] = None,
    task_id: Optional[str] = None,
    story_id: Optional[str] = None,
    files: Optional[list[str]] = None,
    summary: Optional[str] = None,
    phase: Optional[str] = None,
    cases_completed: Optional[int] = None,
    **extra: str,
):
    """追加成员活动日志（append-only JSONL）

    Args:
        event_type: 事件类型（session-start, session-end, file-changed, task-done, story-done, blocker-identified）
        member: 成员 ID（默认当前成员）
        task_id: 关联的任务 ID
        story_id: 关联的 Story ID
        files: 变更的文件列表
        summary: 活动摘要描述
        phase: 关联的阶段
        cases_completed: 完成的 case 数量
        **extra: 其他额外字段
    """
    if member is None:
        member = get_current_member()

    entry = {
        "ts": ts(),
        "type": event_type,
        "member": member,
    }

    if task_id:
        entry["task_id"] = task_id
    if story_id:
        entry["story_id"] = story_id
    if files:
        entry["files"] = files
    if summary:
        entry["summary"] = summary
    if phase:
        entry["phase"] = phase
    if cases_completed is not None:
        entry["cases_completed"] = cases_completed

    # 合并额外字段
    entry.update(extra)

    # 追加到成员活动日志
    log_path = member_log_path(member)
    ensure_member_dir(member)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 同步更新成员索引
    _update_member_index(member, event_type)

    return entry


def _update_member_index(member: str, event_type: str):
    """更新成员索引 _index.jsonl"""
    MEMBER_REPORTS.mkdir(parents=True, exist_ok=True)

    index_entries: dict[str, dict] = {}
    if MEMBER_INDEX.exists():
        try:
            for line in MEMBER_INDEX.read_text().strip().splitlines():
                if line.strip():
                    entry = json.loads(line)
                    index_entries[entry["member"]] = entry
        except Exception:
            pass

    # 更新或创建成员条目
    if member in index_entries:
        entry = index_entries[member]
    else:
        entry = {
            "member": member,
            "active_sessions": 0,
            "tasks_completed": 0,
            "stories_completed": 0,
            "last_active": ts(),
        }

    entry["last_active"] = ts()

    # 统计增量
    if event_type in ("session-start",):
        entry["active_sessions"] = entry.get("active_sessions", 0) + 1
    elif event_type in ("task-done",):
        entry["tasks_completed"] = entry.get("tasks_completed", 0) + 1
    elif event_type in ("story-done",):
        entry["stories_completed"] = entry.get("stories_completed", 0) + 1

    index_entries[member] = entry

    # 写回索引
    lines = [json.dumps(e, ensure_ascii=False) for e in index_entries.values()]
    MEMBER_INDEX.write_text("\n".join(lines) + "\n")


def load_member_activity(member_id: str, limit: int = 20) -> list[dict]:
    """加载指定成员的最近活动历史

    Args:
        member_id: 成员 ID
        limit: 返回最近 N 条记录（默认 20）

    Returns:
        活动记录列表（按时间倒序）
    """
    log_path = member_log_path(member_id)
    if not log_path.exists():
        return []

    activities: list[dict] = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        activities.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        return []

    # 返回最近 N 条（倒序，最新的在前）
    return activities[-limit:][::-1] if activities else []


def get_member_context(member_id: str, limit: int = 20) -> dict:
    """获取成员上下文（用于注入到 Agent prompt）

    Args:
        member_id: 成员 ID
        limit: 加载最近 N 条活动

    Returns:
        包含成员信息和最近活动的字典
    """
    activities = load_member_activity(member_id, limit)

    # 从索引获取统计数据
    stats = {"active_sessions": 0, "tasks_completed": 0, "stories_completed": 0}
    if MEMBER_INDEX.exists():
        try:
            for line in MEMBER_INDEX.read_text().strip().splitlines():
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("member") == member_id:
                        stats = {
                            "active_sessions": entry.get("active_sessions", 0),
                            "tasks_completed": entry.get("tasks_completed", 0),
                            "stories_completed": entry.get("stories_completed", 0),
                        }
                        break
        except Exception:
            pass

    return {
        "member_id": member_id,
        "stats": stats,
        "recent_activities": activities,
    }


def search_activities(
    member: Optional[str] = None,
    task_id: Optional[str] = None,
    story_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """搜索成员活动记录

    Args:
        member: 成员 ID 过滤
        task_id: 任务 ID 过滤
        story_id: Story ID 过滤
        event_type: 事件类型过滤
        limit: 返回上限

    Returns:
        匹配的活动记录列表
    """
    results: list[dict] = []

    # 确定要搜索的文件
    if member:
        log_path = member_log_path(member)
        if log_path.exists():
            _search_file(log_path, results, task_id, story_id, event_type, limit)
    else:
        # 搜索所有成员
        for member_dir in MEMBER_REPORTS.iterdir():
            if member_dir.is_dir():
                log_path = member_dir / "activity.log"
                if log_path.exists():
                    _search_file(log_path, results, task_id, story_id, event_type, limit)
                    if len(results) >= limit:
                        break

    return results[:limit]


def _search_file(
    log_path: Path,
    results: list[dict],
    task_id: Optional[str],
    story_id: Optional[str],
    event_type: Optional[str],
    limit: int,
):
    """在单个日志文件中搜索"""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                        if task_id and entry.get("task_id") != task_id:
                            continue
                        if story_id and entry.get("story_id") != story_id:
                            continue
                        if event_type and entry.get("type") != event_type:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            return
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass