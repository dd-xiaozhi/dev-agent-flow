"""
events.py — 事件总线（task.json.events 读写）

任务级事件统一写入 `docs/task/store/<story_id>/task.json` 的 `events[]` 数组，
events.jsonl 已废弃。仅服务于业务任务（store），bug-fix 任务暂不支持事件。

session 级事件（无 story_id）已废弃 —— emit 时会 stderr warn 并丢弃。

两种入口：

1) Python 模块（hook 同进程使用，零启动开销）

    from events import emit_event, check_event, get_recent_events

    emit_event("planner:all-cases-ready", {"story_id": "...", "actor": "planner"})
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
from pathlib import Path
from typing import Optional

# task_store.py 位于 .claude/skills/task/scripts/（路径常量在本文件按需自行硬编码）
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parents[2] / "skills" / "task" / "scripts"))

from task_store import TaskJsonStore  # noqa: E402


def _warn(msg: str) -> None:
    print(f"[events] {msg}", file=sys.stderr)


def emit_event(event_type: str, data: Optional[dict] = None) -> None:
    """追加事件到对应 task.json.events。

    路由规则：
      - data 必须含 story_id，否则视为 session 事件直接丢弃（warn）
      - 对应 task.json 不存在时同样丢弃（warn）—— 避免凭空创建任务

    Args:
        event_type: 事件类型，如 "planner:all-cases-ready"
        data: 事件数据，必须含 story_id；其他字段（actor / task_id / 业务字段）合并进事件
    """
    data = data or {}
    story_id = data.get("story_id")
    if not story_id:
        _warn(f"drop event {event_type}: no story_id (session-scoped events deprecated)")
        return

    store = TaskJsonStore.load_by_story(story_id)
    if not store.data.get("task_id"):
        _warn(f"drop event {event_type}: task.json not found for story_id={story_id}")
        return

    store.append_event(event_type, data)
    store.save()


def get_recent_events(
    story_id: str,
    event_type: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """读取指定 story 的最近事件（可按 event_type 过滤），取末尾 limit 条。"""
    store = TaskJsonStore.load_by_story(story_id)
    if not store.data.get("task_id"):
        return []
    events = store.get_events(event_type)
    if limit > 0:
        return events[-limit:]
    return events


def check_event(story_id: str, event_type: str) -> bool:
    """检查指定 story 是否存在某类型事件。"""
    return len(get_recent_events(story_id, event_type, limit=1)) > 0


def _parse_ts(ts: str) -> Optional["datetime"]:
    from datetime import datetime
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def compute_durations(story_id: str) -> list[dict]:
    """从 task.json.events 的相邻事件 ts 差算每步墙钟耗时（token 遥测 proxy）。

    harness 拿不到真实 token 数，用「步骤墙钟时长」作为消耗/瓶颈 proxy：
    某步 on_complete_event 与上一步 on_complete_event 的 ts 差 ≈ 该步耗时。
    workflow-reviewer 聚合出「哪步最慢 / 哪步耗时异常」，指导后续上下文瘦身。

    返回 [{step_event, prev_event, duration_s, ts}]，无法解析 ts 的相邻对 duration_s=None。
    """
    events = get_recent_events(story_id, None, limit=0)
    out: list[dict] = []
    for i in range(1, len(events)):
        prev, cur = events[i - 1], events[i]
        t0, t1 = _parse_ts(prev.get("ts", "")), _parse_ts(cur.get("ts", ""))
        dur = round((t1 - t0).total_seconds(), 1) if (t0 and t1) else None
        out.append({
            "step_event": cur.get("type"),
            "prev_event": prev.get("type"),
            "duration_s": dur,
            "ts": cur.get("ts"),
        })
    return out


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
    if not data.get("story_id"):
        print(json.dumps(
            {"ok": False, "error": "缺少 story_id（session-scoped events 已废弃）"},
            ensure_ascii=False,
        ))
        return 1
    emit_event(args.type, data)
    # emit_event 内部已 warn；这里只回报“调用已发起”而非保证持久化（task.json 不存在时会被丢弃）
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


def cmd_durations(args: argparse.Namespace) -> int:
    durs = compute_durations(args.story_id)
    known = [d["duration_s"] for d in durs if d["duration_s"] is not None]
    slowest = max(durs, key=lambda d: d["duration_s"] or -1, default=None)
    print(json.dumps({
        "ok": True,
        "story_id": args.story_id,
        "steps": durs,
        "total_s": round(sum(known), 1) if known else None,
        "slowest_step": slowest,
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Events — 事件总线 CLI (task.json.events)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="追加事件到 task.json.events")
    p_emit.add_argument("type", help="事件类型，如 planner:all-cases-ready")
    p_emit.add_argument("--story-id", default=None,
                        help="必填：事件归属的 story_id")
    p_emit.add_argument("--task-id", default=None,
                        help="可选：附带的 task_id（仅作事件元数据）")
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

    p_dur = sub.add_parser("durations", help="按相邻事件 ts 差算每步墙钟耗时（token 遥测 proxy）")
    p_dur.add_argument("--story-id", required=True)
    p_dur.set_defaults(func=cmd_durations)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
