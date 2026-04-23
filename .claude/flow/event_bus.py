"""结构化事件总线 - 替代 events.jsonl 的增强版"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Event:
    """结构化事件"""
    schema_version: str = "1.0"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    type: str = ""
    source: str = ""
    story_id: Optional[str] = None
    data: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(**d)

    @classmethod
    def from_json(cls, s: str) -> "Event":
        return cls.from_dict(json.loads(s))


class EventBus:
    """事件总线 - append-only 事件存储"""

    def __init__(self, events_file: Optional[Path] = None):
        """
        Args:
            events_file: 事件存储文件路径，默认 .chatlabs/state/events.jsonl
        """
        if events_file:
            self.events_file = events_file
        else:
            from .paths import STATE_DIR
            self.events_file = STATE_DIR / "events.jsonl"

    def append(self, event: Event) -> None:
        """追加事件到事件总线"""
        self.events_file.parent.mkdir(parents=True, exist_ok=True)
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    def query(
        self,
        story_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Event]:
        """
        查询事件

        Args:
            story_id: 按 story_id 过滤
            event_type: 按事件类型过滤
            limit: 返回数量限制
        """
        events = []
        if not self.events_file.exists():
            return events

        with self.events_file.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    e = Event.from_json(line)
                    if story_id and e.story_id != story_id:
                        continue
                    if event_type and e.type != event_type:
                        continue
                    events.append(e)
                    if len(events) >= limit:
                        break
                except (json.JSONDecodeError, TypeError):
                    continue

        return events

    def exists(self, story_id: str, event_type: str) -> bool:
        """检查是否存在指定类型的事件"""
        events = self.query(story_id=story_id, event_type=event_type, limit=1)
        return len(events) > 0

    def get_latest(self, story_id: str, event_type: str) -> Optional[Event]:
        """获取最新的指定类型事件"""
        events = self.query(story_id=story_id, event_type=event_type, limit=1)
        return events[0] if events else None
