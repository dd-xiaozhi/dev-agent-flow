"""
events.py — 事件总线（events.jsonl 读写）

把 flow 中的关键事件追加到 .chatlabs/state/events.jsonl，
供 session-start / agent / gc 等消费方查询。

两种入口：

1) Python 模块（hook 同进程使用，零启动开销）

    from events import emit_event, check_event, get_recent_events

    emit_event("session:start", {"task_id": "TASK-...", "story_id": "..."})
    if check_event("04-30-wechat-login", "planner:all-cases-ready"):
        ...

2) CLI（command / agent 隔离调用）

    python events.py emit <type> --story-id <id> [--task-id <id>] [--data '<json>']
    python events.py check <type> --story-id <id>              # 退出码 0=存在 / 1=不存在
    python events.py recent --story-id <id> [--type <t>] [--limit 20]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 共享基础设施位于 .claude/scripts/，本脚本位于 .claude/skills/flow-engine/scripts/
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parents[2] / "scripts"))

from paths import EVENTS_LOG  # noqa: E402


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


# ── CLI ────────────────────────────────────────────────────────────


def cmd_emit(args: argparse.Namespace) -> int:
    data: dict = {}
    if args.story_id:
        data["story_id"] = args.story_id
    if args.task_id:
        data["task_id"] = args.task_id
    if args.data:
        try:
            extra = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(json.dumps({"ok": False, "error": f"--data 不是合法 JSON: {e}"},
                             ensure_ascii=False))
            return 1
        if not isinstance(extra, dict):
            print(json.dumps({"ok": False, "error": "--data 必须是 JSON 对象"},
                             ensure_ascii=False))
            return 1
        data.update(extra)
    emit_event(args.type, data or None)
    print(json.dumps({"ok": True, "type": args.type, "data": data},
                     ensure_ascii=False))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    exists = check_event(args.story_id, args.type)
    print(json.dumps({"ok": True, "exists": exists,
                      "story_id": args.story_id, "type": args.type},
                     ensure_ascii=False))
    return 0 if exists else 1


def cmd_recent(args: argparse.Namespace) -> int:
    events = get_recent_events(args.story_id, args.type, args.limit)
    print(json.dumps({"ok": True, "count": len(events), "events": events},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Events — 事件总线 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="追加事件到 events.jsonl")
    p_emit.add_argument("type", help="事件类型，如 session:start")
    p_emit.add_argument("--story-id", default=None)
    p_emit.add_argument("--task-id", default=None)
    p_emit.add_argument("--data", default=None,
                        help="额外字段（JSON 对象字符串）")
    p_emit.set_defaults(func=cmd_emit)

    p_check = sub.add_parser("check", help="检查事件是否存在（退出码 0/1）")
    p_check.add_argument("type")
    p_check.add_argument("--story-id", required=True)
    p_check.set_defaults(func=cmd_check)

    p_recent = sub.add_parser("recent", help="读取最近事件")
    p_recent.add_argument("--story-id", required=True)
    p_recent.add_argument("--type", default=None)
    p_recent.add_argument("--limit", type=int, default=20)
    p_recent.set_defaults(func=cmd_recent)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
