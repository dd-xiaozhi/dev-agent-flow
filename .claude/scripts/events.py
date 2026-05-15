"""
events.py — 事件总线（events.jsonl 读写）

把 flow 中的关键事件追加到 .chatlabs/state/events.jsonl，
供 session-start / agent / gc 等消费方查询。

Usage:
    from events import emit_event, check_event, get_recent_events

    emit_event("session:start", {"task_id": "TASK-...", "story_id": "..."})
    if check_event("04-30-wechat-login", "planner:all-cases-ready"):
        ...
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import EVENTS_LOG


def emit_event(event_type: str, data: Optional[dict] = None) -> None:
    """追加事件到 events.jsonl。

    Args:
        event_type: 事件类型，如 "session:start"、"planner:all-cases-ready"
        data: 事件数据（包含 task_id / story_id / actor 等字段）
    """
    EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
    }
    if data:
        event.update(data)

    with EVENTS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def get_recent_events(
    story_id: str,
    event_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """读取指定 story 的最近事件（可按 event_type 过滤）。"""
    if not EVENTS_LOG.exists():
        return []

    events: list[dict] = []
    with EVENTS_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line.strip())
            except json.JSONDecodeError:
                continue
            if event.get("story_id") != story_id:
                continue
            if event_type is not None and event.get("type") != event_type:
                continue
            events.append(event)

    return events[-limit:]


def check_event(story_id: str, event_type: str) -> bool:
    """检查指定 story 是否存在某类型事件。"""
    return len(get_recent_events(story_id, event_type, limit=1)) > 0
