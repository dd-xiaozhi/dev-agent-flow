#!/usr/bin/env python3
"""
gc.py — 工作流熵管理脚本

扫描主流程产生的三类熵，输出 JSON 报告。
默认 dry_run（只报告，不操作）。

扫描项：
  1. stale_ticket_cache   — TAPD ticket JSON 超 N 天未更新
  2. orphaned_index_entry — _index.jsonl 中 task_id 对应目录不存在
  3. stale_task_report    — task report 目录超 N 天无更新且已 terminal phase
  4. stale_source_snapshots — story source/ 下超过 10 个 .md 文件

原则：
  - 永远不删除 source 快照（审计链）
  - 永远不自动删除（dry_run 优先）
  - 归档 > 删除
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

STALE_TICKET_DAYS = 30        # ticket cache 超过 N 天未更新 → stale
STALE_TASK_DAYS = 60          # task report 超 N 天未更新 → stale
ORPHAN_GRACE = 7              # _index 有但目录不存在超过 N 天 → orphaned
FLOW_LOG_STALE_DAYS = 60      # flow-log 超过 N 天且已提炼 → archive
INSIGHT_STALE_DAYS = 90       # orphaned insight 超过 N 天 → 清理

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import (  # noqa: E402
    PROJECT_DIR, CHATLABS_DIR, TAPD_TICKETS_DIR, TASK_REPORTS, TASK_INDEX,
    GC_REPORTS, STORIES_DIR, FLOW_LOGS_DIR, INSIGHTS_DIR, INSIGHTS_INDEX,
    EVOLUTION_PROPOSALS_DIR, PROPOSALS_PENDING_PATH, PROPOSALS_APPLIED_PATH
)
from ltm import LTM  # noqa: E402

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
    stories_dir = STORIES_DIR
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


def scan_stale_flow_logs():
    """
    扫描已提炼（已生成 insight）且超过 N 天的 flow-log。
    archive 到 reports/gc/（不删除原始文件，保留审计链）。
    """
    flow_logs_dir = FLOW_LOGS_DIR
    if not flow_logs_dir.exists():
        return []

    insights_index = INSIGHTS_INDEX
    refined_ids = set()
    if insights_index.exists():
        with open(insights_index) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    # 从 evidence 字段中提取 FL-ID
                    for ev in entry.get("evidence", []):
                        if ev.startswith("FL-"):
                            refined_ids.add(ev)
                except Exception:
                    pass

    cutoff = days_ago(FLOW_LOG_STALE_DAYS)
    results = []
    for month_dir in flow_logs_dir.glob("????"):
        if not month_dir.is_dir():
            continue
        for log_file in month_dir.glob("FL-*.json"):
            mtime = datetime.fromtimestamp(log_file.stat().st_mtime, tz=timezone.utc)
            if mtime >= cutoff:
                continue
            log_id = log_file.stem
            results.append({
                "path": str(log_file.relative_to(PROJECT_DIR)),
                "log_id": log_id,
                "mtime": mtime.isoformat(),
                "age_days": (utc_now() - mtime).days,
                "refined": log_id in refined_ids,
                "action": "archive_to_gc_reports",
                "reason": f"flow-log 超 {FLOW_LOG_STALE_DAYS} 天且已提炼，建议归档"
            })
    return results


def scan_orphaned_insights():
    """
    扫描 insights/_index.jsonl 中 proposal_id 指向不存在 proposal 的条目。
    安全的 index 清理（不删除原始 insight 文件，只从 index 移除）。
    """
    insights_index = INSIGHTS_INDEX
    if not insights_index.exists():
        return []

    # 收集所有有效的 proposal ID
    valid_proposal_ids = set()
    for proposals_file in [PROPOSALS_PENDING_PATH, PROPOSALS_APPLIED_PATH]:
        if proposals_file.exists():
            with open(proposals_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        pid = entry.get("id")
                        if pid:
                            valid_proposal_ids.add(pid)
                    except Exception:
                        pass

    results = []
    with open(insights_index) as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                pid = entry.get("proposal_id")
                if pid and pid not in valid_proposal_ids and pid != "discarded":
                    results.append({
                        "insight_id": entry.get("id"),
                        "pattern": entry.get("pattern", ""),
                        "proposal_id": pid,
                        "created_at": entry.get("created_at", ""),
                        "action": "remove_from_index",
                        "reason": f"proposal_id={pid} 不存在于 pending/applied，孤立条目"
                    })
            except Exception:
                pass
    return results


def scan_evolution_health() -> dict:
    """
    扫描进化机制健康度：
    - 提案采纳率：_applied / (_pending 累计 + _applied)
    - 进化频率：每月新增提案数
    """
    pending_count = 0
    if PROPOSALS_PENDING_PATH.exists():
        with open(PROPOSALS_PENDING_PATH) as f:
            for line in f:
                if line.strip():
                    pending_count += 1

    applied_count = 0
    applied_by_month = {}
    if PROPOSALS_APPLIED_PATH.exists():
        with open(PROPOSALS_APPLIED_PATH) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    applied_count += 1
                    at = entry.get("applied_at", "")
                    if at:
                        month = at[:7]  # YYYY-MM
                        applied_by_month[month] = applied_by_month.get(month, 0) + 1
                except Exception:
                    pass

    total = pending_count + applied_count
    adoption_rate = applied_count / total if total > 0 else 0.0

    # 本月新增提案数（从 pending 新增推断）
    this_month = utc_now().strftime("%Y-%m")
    this_month_pending = 0
    if PROPOSALS_PENDING_PATH.exists():
        with open(PROPOSALS_PENDING_PATH) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    created = entry.get("created_at", "")
                    if created.startswith(this_month):
                        this_month_pending += 1
                except Exception:
                    pass

    # 健康度判断
    if total == 0:
        health_status = "empty"
        recommendation = "尚无进化数据，继续积累 workflow-review 数据"
    elif adoption_rate < 0.2:
        health_status = "warn"
        recommendation = "提案采纳率过低，可能 spec 变更太激进或提案质量不足，建议 review _pending.jsonl"
    elif adoption_rate > 0.8:
        health_status = "ok"
        recommendation = None
    else:
        health_status = "ok"
        recommendation = None

    return {
        "adoption_rate": round(adoption_rate, 3),
        "pending_count": pending_count,
        "applied_count": applied_count,
        "this_month_new_proposals": this_month_pending,
        "applied_by_month": applied_by_month,
        "health_status": health_status,
        "recommendation": recommendation
    }


def run_ltm_consolidate(mode: str = "dry_run") -> dict:
    """LTM consolidate: ITM → LTM 提升 + GC"""
    ltm = LTM()
    consolidate_stats = ltm.consolidate(dry_run=(mode == "dry_run"))
    gc_stats = ltm.gc()
    health = ltm.get_health_status()
    return {
        "consolidate": consolidate_stats,
        "gc": gc_stats,
        "health": health
    }


def run_gc(mode: str = "dry_run") -> dict:
    """
    mode: dry_run | apply
    dry_run: 只产出报告
    apply:   执行归档/清理动作（目前仅限 remove_from_index）
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = utc_now().strftime("%Y-%m-%d")
    report_path = OUTPUT_DIR / f"{date_str}.json"

    findings = {
        "date": date_str,
        "mode": mode,
        "stale_ticket_cache": scan_stale_ticket_cache(),
        "orphaned_index_entries": scan_orphaned_index_entries(),
        "stale_task_reports": scan_stale_task_reports(),
        "stale_source_snapshots": scan_stale_source_snapshots(),
        "stale_flow_logs": scan_stale_flow_logs(),
        "orphaned_insights": scan_orphaned_insights(),
        "evolution_health": scan_evolution_health(),
        "ltm_consolidate": run_ltm_consolidate(mode),
    }

    total = sum(len(v) for v in findings.values() if isinstance(v, list))
    findings["summary"] = {
        "total_findings": total,
        "stale_ticket_count": len(findings["stale_ticket_cache"]),
        "orphaned_index_count": len(findings["orphaned_index_entries"]),
        "stale_task_count": len(findings["stale_task_reports"]),
        "excessive_source_count": len(findings["stale_source_snapshots"]),
        "stale_flow_log_count": len(findings["stale_flow_logs"]),
        "orphaned_insight_count": len(findings["orphaned_insights"]),
        "evolution_adoption_rate": findings["evolution_health"].get("adoption_rate", 0.0),
        "evolution_health_status": findings["evolution_health"].get("health_status", "unknown"),
    }

    if mode == "apply":
        index_path = TASK_INDEX
        if findings["orphaned_index_entries"] and index_path.exists():
            bak = index_path.with_suffix(".jsonl.bak")
            import shutil
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

    write_json(report_path, findings)
    return findings


def print_summary(findings: dict):
    s = findings["summary"]
    print(f"\n{'='*60}")
    print(f"  GC Report  {findings['date']}  [{findings['mode']}]")
    print(f"{'='*60}")
    print(f"  stale ticket cache   : {s['stale_ticket_count']:>3}")
    print(f"  orphaned index entries: {s['orphaned_index_count']:>3}")
    print(f"  stale task reports   : {s['stale_task_count']:>3}")
    print(f"  excessive snapshots  : {s['excessive_source_count']:>3}")
    print(f"  stale flow-logs      : {s['stale_flow_log_count']:>3}")
    print(f"  orphaned insights    : {s['orphaned_insight_count']:>3}")
    print(f"  ─────────────────────────────────────────")
    print(f"  total findings      : {s['total_findings']:>3}")
    print(f"  进化健康度           : {s['evolution_health_status']} "
          f"(采纳率 {s['evolution_adoption_rate']:.0%})")
    print(f"{'='*60}")
    print(f"  报告已写入: {GC_REPORTS.relative_to(PROJECT_DIR)}/{findings['date']}.json")

    if s["total_findings"] == 0:
        print("  无需清理，工作流状态健康")
    else:
        print("  默认 dry_run，不执行实际清理")
        print("  手动确认后执行: .claude/scripts/gc-run.sh --apply")


if __name__ == "__main__":
    mode = "apply" if "--apply" in sys.argv else "dry_run"
    findings = run_gc(mode=mode)
    print_summary(findings)
    sys.exit(0)
