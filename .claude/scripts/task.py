"""
task.py — 任务记录管理 CLI

子命令:
  new <story_id>     创建任务记录、分配 task_id、写 _index.jsonl + .current_task
  resume <task_id>   读 meta + flow 状态、写 .current_task、输出注入材料
  list               列 _index.jsonl(可 --story-id 过滤)

输出: stdout 单一 JSON 对象(ok/error/data/todo_hint),exit code=0 表示 ok=true
依赖: 仅 Python 标准库 + paths.py
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import (  # noqa: E402
    CURRENT_TASK,
    PROJECT_DIR,
    STATE_DIR,
    STORIES_DIR,
    TASK_INDEX,
    TASK_REPORT_TEMPLATE,
    TASK_REPORTS,
)

VALID_TRIGGERS = {"first-start", "requirement-change", "manual", "defect-fix",
                  "requirement-change-check"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(error: str, **extra) -> dict:
    out = {"ok": False, "error": error}
    out.update(extra)
    return out


# ─────────────────────────── _index.jsonl ────────────────────────────

def read_index() -> list[dict]:
    """读 _index.jsonl,损坏行自动跳过(并备份原文件一次)。"""
    if not TASK_INDEX.exists():
        return []
    rows: list[dict] = []
    bad_lines = 0
    for line in TASK_INDEX.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad_lines += 1
    if bad_lines and not Path(str(TASK_INDEX) + ".corrupt.bak").exists():
        shutil.copy(TASK_INDEX, str(TASK_INDEX) + ".corrupt.bak")
    return rows


def append_index(entry: dict) -> None:
    TASK_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with TASK_INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def next_task_nn(story_id: str) -> int:
    """扫 _index.jsonl,返回该 story 内下一个可用 NN(从 1 开始)。"""
    max_nn = 0
    prefix = f"TASK-{story_id}-"
    for row in read_index():
        tid = row.get("task_id", "")
        if not tid.startswith(prefix):
            continue
        try:
            nn = int(tid[len(prefix):])
        except ValueError:
            continue
        if nn > max_nn:
            max_nn = nn
    return max_nn + 1


# ─────────────────────────── new ────────────────────────────

def cmd_new(args: argparse.Namespace) -> dict:
    story_id = args.story_id
    if not story_id:
        return fail("story_id required",
                    usage="python task.py new <story_id> [--predecessor X] [--trigger Y]")

    # 校验模板存在
    meta_template = TASK_REPORT_TEMPLATE / "meta.json"
    audit_template = TASK_REPORT_TEMPLATE / "audit.jsonl"
    if not meta_template.exists() or not audit_template.exists():
        return fail(
            "task template missing (need meta.json + audit.jsonl)",
            template_dir=str(TASK_REPORT_TEMPLATE),
        )

    # 校验 trigger 取值
    trigger = args.trigger
    if trigger and trigger not in VALID_TRIGGERS:
        return fail(
            f"invalid trigger '{trigger}'",
            valid_triggers=sorted(VALID_TRIGGERS),
        )

    # 分配 task_id
    nn = next_task_nn(story_id)
    task_id = f"TASK-{story_id}-{nn:02d}"

    # 任务目录
    task_dir = TASK_REPORTS / task_id
    if task_dir.exists():
        # 目录已存在(并发或残留),追加时间戳后缀避让
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        task_id = f"{task_id}-{ts}"
        task_dir = TASK_REPORTS / task_id
    task_dir.mkdir(parents=True, exist_ok=False)

    # 填充 meta.json
    template_text = meta_template.read_text(encoding="utf-8")
    timestamp = now_iso()
    meta_text = (
        template_text
        .replace("{task_id}", task_id)
        .replace("{story_id}", story_id)
        .replace("{created_at}", timestamp)
        .replace("{updated_at}", timestamp)
    )
    meta = json.loads(meta_text)
    if args.predecessor:
        meta["predecessor_task_id"] = args.predecessor
    if trigger:
        meta["trigger_reason"] = trigger
    (task_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 复制 audit.jsonl(空文件)
    shutil.copy(audit_template, task_dir / "audit.jsonl")
    # blockers.md 不预创建,首次写入时 hook 自行 mkdir

    # Story 目录幂等创建
    story_dir = STORIES_DIR / story_id
    story_dir.mkdir(parents=True, exist_ok=True)

    # 注册 _index.jsonl
    append_index({
        "task_id": task_id,
        "story_id": story_id,
        "phase": "created",
        "keywords": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "blocker_count": 0,
        "verdict": None,
        "tags": [],
    })

    # 写 .current_task
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_TASK.write_text(task_id, encoding="utf-8")

    # 输出
    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "task_dir": str(task_dir.relative_to(PROJECT_DIR)),
        "story_dir": str(story_dir.relative_to(PROJECT_DIR)),
        "predecessor_task_id": args.predecessor,
        "trigger_reason": trigger,
        # 调用方据此创建平台原生 todo(可选)
        "todo_hint": {
            "subject": f"[{story_id}] 任务已创建,等待上游路由",
            "description": (
                f"任务记录已分配。Story: {story_id}。"
                f"后续由上游流程入口命令决定 phase 与 agent 路由。"
            ),
        },
    }


# ─────────────────────────── resume ────────────────────────────

def _load_flow_state(story_id: str) -> dict:
    """读 per-story workflow-state.json,缺失时回退全局 state。"""
    state_path = STORIES_DIR / story_id / "workflow-state.json"
    if not state_path.exists():
        # 兜底全局 state
        global_state = STATE_DIR / "workflow-state.json"
        if global_state.exists():
            try:
                return json.loads(global_state.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _flow_check(state: dict) -> dict:
    """从 state 提取 flow.current_step / next_step / is_terminal。"""
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow initialized"}
    steps = flow.get("steps", [])
    idx = flow.get("current_step_idx", 0)
    current = steps[idx] if 0 <= idx < len(steps) else None
    next_step = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None
    return {
        "ok": True,
        "flow_id": flow.get("flow_id"),
        "current_step_idx": idx,
        "current_step": current,
        "next_step": next_step,
        "is_terminal": bool(current and current.get("kind") == "terminal"),
        "history_count": len(flow.get("history", [])),
    }


def _tail_jsonl(path: Path, n: int) -> list:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            out.append({"_raw": line})
    return out


def _related_completed_tasks(story_id: str, current_task_id: str) -> list[dict]:
    related = []
    for row in read_index():
        if row.get("story_id") != story_id:
            continue
        if row.get("task_id") == current_task_id:
            continue
        if row.get("verdict") == "PASS":
            related.append({
                "task_id": row.get("task_id"),
                "verdict": row.get("verdict"),
                "updated_at": row.get("updated_at"),
            })
    return related


def cmd_resume(args: argparse.Namespace) -> dict:
    task_id = args.task_id
    if not task_id or not task_id.startswith("TASK-"):
        return fail(
            "invalid task_id",
            usage="python task.py resume <TASK-id>",
            example="TASK-04-30-wechat-login-01",
        )

    task_dir = TASK_REPORTS / task_id
    meta_path = task_dir / "meta.json"
    if not meta_path.exists():
        return fail("task not found", task_dir=str(task_dir.relative_to(PROJECT_DIR)))

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        return fail(f"failed to read meta.json: {e}")

    story_id = meta.get("story_id")
    if not story_id:
        return fail("meta.json missing story_id", task_id=task_id)

    # 读 flow 状态
    state = _load_flow_state(story_id)
    flow_check = _flow_check(state)

    # blockers
    blockers_path = task_dir / "blockers.md"
    blockers_content = None
    blocker_count = meta.get("blocker_count", 0)
    if blockers_path.exists() and blocker_count > 0:
        blockers_content = blockers_path.read_text(encoding="utf-8")

    # audit tail(--verbose)
    audit_tail: list = []
    if args.verbose:
        audit_tail = _tail_jsonl(task_dir / "audit.jsonl", 50)

    # 同 story 已完成 task
    related = _related_completed_tasks(story_id, task_id)

    # 更新 .current_task
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_TASK.write_text(task_id, encoding="utf-8")
    current_task_updated = True

    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "meta": {
            "phase": meta.get("phase"),
            "agent": meta.get("agent"),
            "verdict": meta.get("verdict"),
            "blocker_count": blocker_count,
            "tapd_ticket_id": meta.get("tapd_ticket_id"),
            "predecessor_task_id": meta.get("predecessor_task_id"),
            "trigger_reason": meta.get("trigger_reason"),
            "summary": meta.get("summary", {}),
        },
        "flow": flow_check,
        "blockers": blockers_content,
        "audit_tail": audit_tail,
        "related_completed_tasks": related,
        "current_task_updated": current_task_updated,
        "paths": {
            "task_dir": str(task_dir.relative_to(PROJECT_DIR)),
            "meta": str(meta_path.relative_to(PROJECT_DIR)),
            "blockers": (
                str(blockers_path.relative_to(PROJECT_DIR))
                if blockers_path.exists() else None
            ),
            "audit": str((task_dir / "audit.jsonl").relative_to(PROJECT_DIR)),
        },
        # 调用方据此更新平台原生 todo 状态(可选)
        "todo_hint": {
            "task_id": task_id,
            "status": "in_progress",
        },
    }


# ─────────────────────────── list ────────────────────────────

def cmd_list(args: argparse.Namespace) -> dict:
    rows = read_index()
    if args.story_id:
        rows = [r for r in rows if r.get("story_id") == args.story_id]
    return {
        "ok": True,
        "count": len(rows),
        "tasks": rows,
    }


# ─────────────────────────── main ────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Task record CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="创建任务记录")
    p_new.add_argument("story_id")
    p_new.add_argument("--predecessor", default=None,
                       help="前驱 task_id(用于追溯链)")
    p_new.add_argument("--trigger", default=None,
                       help=f"触发原因({'/'.join(sorted(VALID_TRIGGERS))})")
    p_new.set_defaults(func=cmd_new)

    p_resume = sub.add_parser("resume", help="续接已存在的任务")
    p_resume.add_argument("task_id")
    p_resume.add_argument("--verbose", action="store_true",
                          help="额外注入 audit.jsonl 末尾 50 行")
    p_resume.set_defaults(func=cmd_resume)

    p_list = sub.add_parser("list", help="列任务索引")
    p_list.add_argument("--story-id", default=None)
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
