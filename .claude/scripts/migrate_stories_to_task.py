"""
migrate_stories_to_task.py — 一次性迁移：stories/ → task/store/，整合 task.json

迁移逻辑：
1. 遍历 .chatlabs/stories/<story_id>/
2. 对每个 story:
   a) 整个目录搬到 .chatlabs/task/store/<story_id>/（保留 contract.md / spec.md / cases/ 等）
   b) 读原 workflow-state.json → 写入 task.json.workflow
   c) 读 reports/tasks/<task_id>/meta.json（通过 workflow-state 的 task_id）→ 写入 task.json 顶层 + tapd
   d) 读 .chatlabs/tapd/tickets/<ticket_id>.json（如果有）→ 写入 task.json.tapd
   e) 删除原 workflow-state.json（其内容已并入 task.json）
3. 写迁移日志 .chatlabs/task/_migration_<ts>.log
4. 保留旧 .chatlabs/stories/ 目录 7 天（手工 mv 操作；本脚本只做内容复制）

特性：
- 幂等：检测 task.json 已含完整字段则跳过
- --dry-run：预览迁移计划，不动任何文件
- 单向：不支持回滚（备份请用 git）

Usage:
    python .claude/scripts/migrate_stories_to_task.py --dry-run
    python .claude/scripts/migrate_stories_to_task.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import (  # noqa: E402
    CHATLABS_DIR,
    PROJECT_DIR,
    STORE_DIR,
    TASK_DIR,
    TASK_REPORTS,
)
from task_store import TaskJsonStore  # noqa: E402

LEGACY_STORIES_DIR = CHATLABS_DIR / "stories"
LEGACY_TAPD_TICKETS_DIR = CHATLABS_DIR / "tapd" / "tickets"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def plan_migration() -> list[dict]:
    """扫描旧 stories/ 目录，返回迁移计划列表。"""
    plan: list[dict] = []
    if not LEGACY_STORIES_DIR.exists():
        return plan
    for story_dir in sorted(LEGACY_STORIES_DIR.iterdir()):
        if not story_dir.is_dir():
            continue
        story_id = story_dir.name
        wf_path = story_dir / "workflow-state.json"
        wf = _read_json(wf_path) or {}
        task_id = wf.get("task_id")
        ticket_id = (
            wf.get("integrations", {})
              .get("tapd", {})
              .get("ticket_id")
        )
        plan.append({
            "story_id": story_id,
            "src_dir": str(story_dir.relative_to(PROJECT_DIR)),
            "dst_dir": str((STORE_DIR / story_id).relative_to(PROJECT_DIR)),
            "task_id": task_id,
            "tapd_ticket_id": ticket_id,
            "has_workflow_state": wf_path.exists(),
            "has_meta_json": bool(task_id and (TASK_REPORTS / task_id / "meta.json").exists()),
            "has_tapd_ticket": bool(ticket_id and (LEGACY_TAPD_TICKETS_DIR / f"{ticket_id}.json").exists()),
        })
    return plan


def _build_task_json(
    story_id: str,
    wf: Optional[dict],
    meta: Optional[dict],
    ticket: Optional[dict],
) -> dict:
    """从三处旧数据构造 task.json 内容。"""
    wf = wf or {}
    meta = meta or {}
    ticket = ticket or {}

    task_type = "store"

    # ── meta section（顶层）─────────────────────────────────────
    out = {
        "task_id": wf.get("task_id") or meta.get("task_id"),
        "task_type": task_type,
        "story_id": story_id,
        "created_at": meta.get("created_at") or wf.get("created_at") or now_iso(),
        "updated_at": now_iso(),
        "trigger": meta.get("trigger_reason"),
        "dev_mode": meta.get("dev_mode"),
    }

    # ── workflow section ──────────────────────────────────────
    workflow = {
        "flow": wf.get("flow"),
        "phase": wf.get("phase"),
        "verdicts": wf.get("verdicts") or {},
        "blocker_count": wf.get("blocker_count", 0),
        "artifacts": wf.get("artifacts"),
    }
    if any(v not in (None, {}, 0) for v in workflow.values()):
        out["workflow"] = workflow
    else:
        out["workflow"] = None

    # ── tapd section ──────────────────────────────────────────
    integ_tapd = wf.get("integrations", {}).get("tapd", {})
    ticket_id = integ_tapd.get("ticket_id") or ticket.get("id") or ticket.get("ticket_id")
    if ticket_id or ticket:
        out["tapd"] = {
            "ticket_id": ticket_id,
            "entity_type": ticket.get("entity_type") or "stories",
            "wiki_id": (ticket.get("local_mapping") or {}).get("wiki_id"),
            "wiki_url": (ticket.get("local_mapping") or {}).get("wiki_url"),
            "consensus_version": integ_tapd.get("consensus_version", 0),
            "subtasks": ticket.get("subtasks") or [],
            "subtask_emitted": integ_tapd.get("subtask_emitted", False),
            "total_estimated_hours": (ticket.get("local_mapping") or {}).get("total_estimated_hours", 0),
            "comments_cache": ticket.get("comments_cache") or [],
            "last_synced_at": integ_tapd.get("last_synced_at"),
            # 保留原 ticket 全量字段以防丢失（嵌套 raw 子节，便于回查）
            "raw": ticket if ticket else None,
        }
    else:
        out["tapd"] = None

    # ── git section（迁移时为空，由 Phase B 流程后续填充）──────────
    out["git"] = None

    # ── bug_fix section（store 类型不存在）─────────────────────
    out["bug_fix"] = None

    return out


def _copy_story_dir(src: Path, dst: Path, dry_run: bool) -> None:
    """复制 story 目录到 task/store/<id>/。已存在则只增量复制不覆盖。"""
    if dry_run:
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if target.exists():
            continue  # 不覆盖已存在文件
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)


def migrate_one(entry: dict, dry_run: bool) -> dict:
    """迁移单个 story。"""
    story_id = entry["story_id"]
    src_dir = PROJECT_DIR / entry["src_dir"]
    dst_dir = STORE_DIR / story_id

    # 1. 读三处旧数据
    wf = _read_json(src_dir / "workflow-state.json")
    task_id = entry.get("task_id")
    meta = _read_json(TASK_REPORTS / task_id / "meta.json") if task_id else None
    ticket_id = entry.get("tapd_ticket_id")
    ticket = (
        _read_json(LEGACY_TAPD_TICKETS_DIR / f"{ticket_id}.json")
        if ticket_id else None
    )

    # 2. 复制目录（contract.md / spec.md / cases/ 等保留）
    _copy_story_dir(src_dir, dst_dir, dry_run)

    # 3. 写 task.json
    task_json = _build_task_json(story_id, wf, meta, ticket)
    result = {
        "story_id": story_id,
        "task_id": task_json.get("task_id"),
        "tapd_ticket_id": ticket_id,
        "merged_sections": [
            s for s in ("workflow", "tapd") if task_json.get(s) is not None
        ],
    }

    if dry_run:
        result["dry_run"] = True
        return result

    store = TaskJsonStore.load(dst_dir)
    if store.data.get("task_id") and store.data.get("workflow") is not None:
        # 已迁移过：幂等跳过
        result["skipped"] = "already migrated"
        return result

    # 注入 task.json（绕过 update_* 接口直接整体写入）
    store._data.update(task_json)  # noqa: SLF001 — 单次迁移授权直写
    store.save()

    # 4. 删除原 workflow-state.json（已并入 task.json，避免双源）
    legacy_wf = dst_dir / "workflow-state.json"
    if legacy_wf.exists():
        legacy_wf.unlink()
    result["wrote"] = str((dst_dir / "task.json").relative_to(PROJECT_DIR))
    return result


def write_log(results: list[dict], dry_run: bool) -> Path:
    TASK_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = ".dryrun" if dry_run else ""
    log_path = TASK_DIR / f"_migration_{ts}{suffix}.log"
    log_path.write_text(
        json.dumps({
            "migrated_at": now_iso(),
            "dry_run": dry_run,
            "count": len(results),
            "results": results,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate .chatlabs/stories/ to .chatlabs/task/store/")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览迁移计划，不动任何文件")
    args = parser.parse_args()

    plan = plan_migration()
    if not plan:
        print(json.dumps({
            "ok": True,
            "message": "no legacy stories/ found, nothing to migrate",
            "legacy_dir": str(LEGACY_STORIES_DIR.relative_to(PROJECT_DIR)),
        }, ensure_ascii=False, indent=2))
        return 0

    results = [migrate_one(entry, args.dry_run) for entry in plan]
    log_path = write_log(results, args.dry_run)

    print(json.dumps({
        "ok": True,
        "dry_run": args.dry_run,
        "count": len(results),
        "log": str(log_path.relative_to(PROJECT_DIR)),
        "results": results,
        "next_steps": [
            "review log file",
            "if dry-run looks good: re-run without --dry-run",
            "after real migration: verify .chatlabs/task/store/<id>/task.json contents",
            "after 7d stable: rm -rf .chatlabs/stories/ .chatlabs/tapd/tickets/",
        ] if args.dry_run else [
            "verify task.json files under .chatlabs/task/store/",
            "test /task-resume to confirm workflow recovery",
            "after 7d stable: rm -rf .chatlabs/stories/ .chatlabs/tapd/tickets/",
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
