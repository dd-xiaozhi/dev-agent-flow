#!/usr/bin/env python3
"""
gc.py — 工作流熵管理脚本

扫描主流程产生的熵，输出 JSON 报告。
默认 dry_run（只报告，不操作）。

扫描项：
  1. stale_ticket_cache   — TAPD ticket JSON 超 N 天未更新
  2. orphaned_index_entry — _index.jsonl 中 task_id 对应目录不存在
  3. stale_task_report    — task report 目录超 N 天无更新且已 terminal phase
  4. stale_source_snapshots — story source/ 下超过 10 个 .md 文件
  5. archivable_tasks     — completed_at 超 N 天的任务可归档到 archive/YYYY-QN/(仅 --archive 模式扫描+执行)

原则：
  - 永远不删除 source 快照（审计链）
  - 永远不自动删除（dry_run 优先）
  - 归档 > 删除
  - 归档动作必须 --apply --archive 双开关显式触发
"""

import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

STALE_TICKET_DAYS = 30        # ticket cache 超过 N 天未更新 → stale
STALE_TASK_DAYS = 60          # task report 超 N 天未更新 → stale
ORPHAN_GRACE = 7              # _index 有但目录不存在超过 N 天 → orphaned
ARCHIVE_THRESHOLD_DAYS = 90   # task 完成超 N 天 → 可归档

# Import centralized path constants
# 文件位置：.claude/skills/gc/scripts/gc.py → parents[3] = .claude/
# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
CHATLABS_DIR = PROJECT_DIR / ".chatlabs"
TAPD_TICKETS_DIR = CHATLABS_DIR / "tapd" / "tickets"
TASK_REPORTS = CHATLABS_DIR / "reports" / "tasks"
TASK_INDEX = TASK_REPORTS / "_index.jsonl"
GC_REPORTS = CHATLABS_DIR / "reports" / "gc"
STORE_DIR = CHATLABS_DIR / "task" / "store"
BUG_FIX_DIR = CHATLABS_DIR / "task" / "bug-fix"
ARCHIVE_DIR = CHATLABS_DIR / "task" / "archive"

sys.path.insert(0, str(PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
import task_index  # noqa: E402

OUTPUT_DIR = GC_REPORTS

# ── 辅助 ─────────────────────────────────────────────────────────
def utc_now():
    return datetime.now(timezone.utc)

def days_ago(n: int):
    return utc_now() - timedelta(days=n)

def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

# ── 扫描器 ───────────────────────────────────────────────────────

def scan_stale_ticket_cache():
    """ticket JSON 超 STALE_TICKET_DAYS 未更新"""
    tickets_dir = TAPD_TICKETS_DIR
    if not tickets_dir.exists():
        return []

    results = []
    cutoff = days_ago(STALE_TICKET_DAYS)
    for fp in tickets_dir.glob("*.json"):
        if fp.name == "_index.jsonl":
            continue
        mtime = datetime.fromtimestamp(fp.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            data = read_json(fp)
            story_id = None
            if data:
                story_id = data.get("local_mapping", {}).get("story_id")
            results.append({
                "path": str(fp.relative_to(PROJECT_DIR)),
                "mtime": mtime.isoformat(),
                "story_id": story_id,
                "age_days": (utc_now() - mtime).days,
                "action": "archive_to_gc_reports",
                "reason": f"ticket cache 未更新超过 {STALE_TICKET_DAYS} 天"
            })
    return results


def scan_orphaned_index_entries():
    """_index.jsonl 中 task_id 对应目录不存在"""
    index_path = TASK_INDEX
    if not index_path.exists():
        return []

    results = []
    tasks_dir = TASK_REPORTS
    cutoff = days_ago(ORPHAN_GRACE)

    with open(index_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue

            task_id = entry.get("task_id")
            if not task_id:
                continue

            task_dir = tasks_dir / task_id
            if task_dir.exists():
                continue

            updated_at_str = entry.get("updated_at", "")
            try:
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                if updated_at > cutoff:
                    continue
            except Exception:
                pass

            results.append({
                "task_id": task_id,
                "story_id": entry.get("story_id"),
                "phase": entry.get("phase"),
                "updated_at": updated_at_str,
                "action": "remove_from_index",
                "reason": f"task 目录不存在超过 {ORPHAN_GRACE} 天，_index 残留条目"
            })
    return results


def scan_stale_task_reports():
    """task report 超 STALE_TASK_DAYS 未更新且已 terminal phase"""
    tasks_dir = TASK_REPORTS
    if not tasks_dir.exists():
        return []

    TERMINAL_PHASES = {"done", "blocked", "cancelled"}
    results = []
    cutoff = days_ago(STALE_TASK_DAYS)

    for meta_path in tasks_dir.glob("*/meta.json"):
        meta = read_json(meta_path)
        if not meta:
            continue

        task_id = meta.get("task_id")
        phase = meta.get("phase", "")
        if phase not in TERMINAL_PHASES:
            continue

        updated_at_str = meta.get("updated_at", "")
        try:
            updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if updated_at > cutoff:
                continue
        except Exception:
            pass

        results.append({
            "task_id": task_id,
            "story_id": meta.get("story_id"),
            "phase": phase,
            "verdict": meta.get("verdict"),
            "updated_at": updated_at_str,
            "action": "archive_to_gc_reports",
            "reason": f"task 已 {phase} 且超过 {STALE_TASK_DAYS} 天无更新"
        })
    return results


def scan_stale_source_snapshots():
    """
    source 快照超量检测（不删除，只报警）。
    策略：单个 story 的 source/ 下超过 10 个 .md 文件 → 报警。
    """
    stories_dir = STORE_DIR
    if not stories_dir.exists():
        return []

    results = []
    for source_dir in stories_dir.glob("*/source"):
        mds = list(source_dir.glob("*.md"))
        if len(mds) <= 10:
            continue

        results.append({
            "story_id": source_dir.parent.name,
            "count": len(mds),
            "files": [str(p.relative_to(PROJECT_DIR)) for p in sorted(mds)[-3:]],
            "action": "review_snapshots",
            "reason": f"source 快照超过 10 个文件（{len(mds)} 个），建议手动 review"
        })
    return results


def scan_archivable_tasks():
    """completed_at 超 ARCHIVE_THRESHOLD_DAYS 的任务,候选归档到 archive/YYYY-QN/。

    判据:
      - 主 _index.jsonl 中有 completed_at
      - completed_at 早于 cutoff
      - task 目录存在(store/<id>/ 或 bug-fix/<id>/),否则属 orphan(走另一通道清理)
    """
    if not TASK_INDEX.exists():
        return []

    cutoff = days_ago(ARCHIVE_THRESHOLD_DAYS)
    results = []

    for entry in task_index.read_index(TASK_INDEX):
        completed_at_str = entry.get("completed_at")
        if not completed_at_str:
            continue
        try:
            completed_at = datetime.fromisoformat(completed_at_str.replace("Z", "+00:00"))
        except Exception:
            continue
        if completed_at > cutoff:
            continue

        story_id = entry.get("story_id") or entry.get("task_id")
        task_type = entry.get("task_type") or "store"
        source_dir = (BUG_FIX_DIR if task_type == "bug-fix" else STORE_DIR) / story_id
        if not source_dir.exists():
            continue  # orphan,留给 scan_orphaned_index_entries 处理

        quarter = task_index.quarter_of(completed_at)
        results.append({
            "task_id": entry.get("task_id"),
            "story_id": story_id,
            "task_type": task_type,
            "verdict": entry.get("verdict"),
            "completed_at": completed_at_str,
            "quarter": quarter,
            "source_dir": str(source_dir.relative_to(PROJECT_DIR)),
            "target_dir": f".chatlabs/task/archive/{quarter}/{story_id}",
            "age_days": (utc_now() - completed_at).days,
            "action": "archive_to_quarter",
            "reason": f"completed_at 早于 {ARCHIVE_THRESHOLD_DAYS} 天",
        })
    return results


def apply_archive(items: list) -> dict:
    """执行归档:移目录 + 移 entry。返回统计。"""
    moved = 0
    skipped = 0
    errors: list[dict] = []

    # 先备份主索引
    if TASK_INDEX.exists():
        bak = TASK_INDEX.with_suffix(".jsonl.archive.bak")
        shutil.copy(TASK_INDEX, bak)

    # 读全量主索引,定位待归档 entry
    all_entries = task_index.read_index(TASK_INDEX)
    archive_targets = {it["task_id"]: it for it in items}

    for entry in all_entries:
        task_id = entry.get("task_id")
        if task_id not in archive_targets:
            continue

        item = archive_targets[task_id]
        source = PROJECT_DIR / item["source_dir"]
        target = PROJECT_DIR / item["target_dir"]
        quarter = item["quarter"]

        if target.exists():
            errors.append({"task_id": task_id, "error": f"target 已存在: {target}"})
            skipped += 1
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        except Exception as e:
            errors.append({"task_id": task_id, "error": str(e)})
            skipped += 1
            continue

        # append entry 到 archive/YYYY-QN/_index.jsonl
        try:
            task_index.append_index(entry, path=task_index.archive_quarter_index(quarter))
        except Exception as e:
            errors.append({"task_id": task_id, "error": f"写归档索引失败: {e}"})
            # 已经搬移目录,继续处理主索引清理

        moved += 1

    # 从主索引清除已归档 entry
    if moved:
        removed = task_index.remove_index_entries(
            [it["task_id"] for it in items if it["task_id"] not in {e["task_id"] for e in errors}],
            path=TASK_INDEX,
        )
    else:
        removed = 0

    # 重建归档总索引
    master_count = task_index.rebuild_archive_master_index()

    return {
        "moved": moved,
        "skipped": skipped,
        "removed_from_main_index": removed,
        "archive_master_index_count": master_count,
        "errors": errors,
    }


def run_gc(mode: str = "dry_run", archive_mode: bool = False) -> dict:
    """
    mode: dry_run | apply
    dry_run: 只产出报告
    apply:   执行归档/清理动作（目前仅限 remove_from_index）
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = utc_now().strftime("%Y-%m-%d")

    # 归档模式独立分支:只扫归档候选,不扫其他熵项
    if archive_mode:
        archivable = scan_archivable_tasks()
        findings: dict = {
            "date": date_str,
            "mode": mode,
            "archive_mode": True,
            "archivable_tasks": archivable,
            "summary": {
                "archivable_count": len(archivable),
                "threshold_days": ARCHIVE_THRESHOLD_DAYS,
            },
        }
        if mode == "apply" and archivable:
            findings["apply_log"] = apply_archive(archivable)
        report_path = OUTPUT_DIR / f"{date_str}-archive.json"
        if archivable:
            write_json(report_path, findings)
        return findings

    # 常规扫描模式(原行为)
    report_path = OUTPUT_DIR / f"{date_str}.json"
    findings = {
        "date": date_str,
        "mode": mode,
        "archive_mode": False,
        "stale_ticket_cache": scan_stale_ticket_cache(),
        "orphaned_index_entries": scan_orphaned_index_entries(),
        "stale_task_reports": scan_stale_task_reports(),
        "stale_source_snapshots": scan_stale_source_snapshots(),
    }

    total = sum(len(v) for v in findings.values() if isinstance(v, list))
    findings["summary"] = {
        "total_findings": total,
        "stale_ticket_count": len(findings["stale_ticket_cache"]),
        "orphaned_index_count": len(findings["orphaned_index_entries"]),
        "stale_task_count": len(findings["stale_task_reports"]),
        "excessive_source_count": len(findings["stale_source_snapshots"]),
    }

    if mode == "apply":
        index_path = TASK_INDEX
        if findings["orphaned_index_entries"] and index_path.exists():
            bak = index_path.with_suffix(".jsonl.bak")
            shutil.copy(index_path, bak)

            orphan_ids = {e["task_id"] for e in findings["orphaned_index_entries"]}
            lines = []
            with open(index_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("task_id") not in orphan_ids:
                            lines.append(line)
                    except Exception:
                        continue
            index_path.write_text("".join(lines))
            findings["apply_log"] = f"备份到 {bak.name}，移除 {len(orphan_ids)} 条 orphan 条目"

    if total > 0:
        write_json(report_path, findings)
    return findings


def print_summary(findings: dict):
    s = findings["summary"]
    print(f"\n{'='*60}")
    mode_tag = "archive" if findings.get("archive_mode") else "scan"
    print(f"  GC Report  {findings['date']}  [{findings['mode']}/{mode_tag}]")
    print(f"{'='*60}")

    if findings.get("archive_mode"):
        print(f"  archivable tasks     : {s['archivable_count']:>3}")
        print(f"  threshold            : {s['threshold_days']} 天")
        print(f"{'='*60}")
        log = findings.get("apply_log")
        if log:
            print(f"  moved                : {log['moved']:>3}")
            print(f"  skipped              : {log['skipped']:>3}")
            print(f"  removed_from_main    : {log['removed_from_main_index']:>3}")
            print(f"  archive_index_total  : {log['archive_master_index_count']:>3}")
            if log["errors"]:
                print(f"  errors               : {len(log['errors'])}")
                for e in log["errors"]:
                    print(f"    - {e['task_id']}: {e['error']}")
        elif s["archivable_count"] == 0:
            print("  无可归档任务,跳过")
        else:
            print(f"  默认 dry_run,不执行实际归档")
            print(f"  手动确认后执行: python .claude/skills/gc/scripts/gc.py --archive --apply")
        return

    print(f"  stale ticket cache   : {s['stale_ticket_count']:>3}")
    print(f"  orphaned index entries: {s['orphaned_index_count']:>3}")
    print(f"  stale task reports   : {s['stale_task_count']:>3}")
    print(f"  excessive snapshots  : {s['excessive_source_count']:>3}")
    print(f"  ─────────────────────────────────────────")
    print(f"  total findings      : {s['total_findings']:>3}")
    print(f"{'='*60}")

    if s["total_findings"] == 0:
        print("  无需清理，工作流状态健康")
        print(f"  当天无熵，不产生报告文件")
    else:
        print(f"  报告已写入: {GC_REPORTS.relative_to(PROJECT_DIR)}/{findings['date']}.json")
        print("  默认 dry_run，不执行实际清理")
        print("  手动确认后执行: python .claude/skills/gc/scripts/gc.py --apply")


if __name__ == "__main__":
    mode = "apply" if "--apply" in sys.argv else "dry_run"
    archive_mode = "--archive" in sys.argv
    findings = run_gc(mode=mode, archive_mode=archive_mode)
    print_summary(findings)
    sys.exit(0)
