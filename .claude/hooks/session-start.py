#!/usr/bin/env python3
"""
session-start.py — 新 Session 启动时加载当前任务上下文

事件：SessionStart
行为：
  1. 检查 .chatlabs/state/current_task（当前 active task_id）
  2. 若存在：加载 workflow-state.json（单一状态源）
  3. 若 phase == waiting-consensus：输出自动恢复指令（事件驱动）
  4. 若为当天首次 session：触发 gc dry_run（静默，不阻断主流程）
  5. 正常输出任务摘要

前置：.chatlabs/state/current_task 由 /task-new 或 /task-resume 写入
依赖：workflow-state.json（Phase 1 引入，替代 meta.json）
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import (  # noqa: E402
    PROJECT_DIR, CURRENT_TASK, TASK_REPORTS, GC_LAST_RUN, SCRIPTS_DIR, STATE_DIR
)

CURRENT_TASK_FILE = CURRENT_TASK
REPORTS_DIR = TASK_REPORTS
GC_FLAG_FILE = GC_LAST_RUN
WORKFLOW_STATE_FILE = STATE_DIR / "workflow-state.json"
EVENTS_LOG_FILE = STATE_DIR / "events.jsonl"


def _run_gc_if_needed():
    """每天首次 session 自动 dry_run gc，不阻断主流程"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        last = GC_FLAG_FILE.read_text().strip()
        if last == today:
            return  # 今天已跑过，跳过
    except FileNotFoundError:
        pass

    gc_script = SCRIPTS_DIR / "gc.py"
    if not gc_script.exists():
        return  # gc.py 不存在，跳过

    try:
        result = subprocess.run(
            [sys.executable, str(gc_script)],
            capture_output=True, text=True, timeout=60,
            cwd=str(PROJECT_DIR)
        )
        GC_FLAG_FILE.write_text(today)
        # 只在有问题时输出（静默成功）
        if result.returncode != 0 or result.stderr:
            print(f"[session-start] gc: {result.stderr or result.stdout}", file=sys.stderr)
    except Exception as e:
        print(f"[session-start] gc skip: {e}", file=sys.stderr)


def main():
    # 每日首次 session 自动触发 gc（静默，不阻断）
    _run_gc_if_needed()

    # Phase 1：优先读 workflow-state.json（单一状态源）
    # Phase 0（向后兼容）：fallback 到 current_task + meta.json
    state_data = None
    try:
        if WORKFLOW_STATE_FILE.exists():
            state_data = json.loads(WORKFLOW_STATE_FILE.read_text())
    except Exception:
        pass

    if state_data:
        # 使用 workflow-state.json
        task_id = state_data.get("task_id", "?")
        story_id = state_data.get("story_id", "?")
        phase = state_data.get("phase", "?")
        agent = state_data.get("agent", "?")
        blocker_count = state_data.get("blocker_count", 0)
        verdicts = state_data.get("verdicts", {})
        verdict_summary = f"PASS({sum(1 for v in verdicts.values() if v == 'PASS')}/{len(verdicts)})" if verdicts else "WIP"
        tapd_enabled = state_data.get("integrations", {}).get("tapd", {}).get("enabled", False)
        ticket_id = state_data.get("integrations", {}).get("tapd", {}).get("ticket_id", None) if tapd_enabled else None
        contract_info = state_data.get("artifacts", {}).get("contract", {})
    else:
        # 向后兼容：读 current_task + meta.json
        try:
            task_id = CURRENT_TASK_FILE.read_text().strip()
        except FileNotFoundError:
            task_id = None

        if not task_id:
            print("[session-start] no active task")
            return

        task_dir = REPORTS_DIR / task_id
        meta_file = task_dir / "meta.json"

        if not meta_file.exists():
            print(f"[session-start] task dir not found: {task_dir}")
            return

        try:
            meta = json.loads(meta_file.read_text())
        except Exception:
            print(f"[session-start] failed to read meta.json")
            return

        task_id = meta.get("task_id", "?")
        story_id = meta.get("story_id", "?")
        phase = meta.get("phase", "?")
        agent = meta.get("agent", "?")
        blocker_count = meta.get("blocker_count", 0)
        verdict_summary = meta.get("verdict", "WIP")
        ticket_id = meta.get("tapd_ticket_id", None)
        contract_info = {}

    reports_base = str(TASK_REPORTS.relative_to(PROJECT_DIR))
    summary_path = f"{reports_base}/{task_id}/summary.md"
    blockers_path = f"{reports_base}/{task_id}/blockers.md"
    diff_path = f"{reports_base}/{task_id}/diff-log.md"
    reads_path = f"{reports_base}/{task_id}/file-reads.md"

    output = {
        "task_id": task_id,
        "story_id": story_id,
        "phase": phase,
        "agent": agent,
        "blocker_count": blocker_count,
        "verdict": verdict_summary,
        "tapd_ticket_id": ticket_id,
        "records": {
            "summary": summary_path,
            "blockers": blockers_path if blocker_count > 0 else None,
            "diff_log": diff_path,
            "file_reads": reads_path,
        },
        "message": (
            f"[session-start] Active task: {task_id} | story: {story_id} "
            f"| phase: {phase} | agent: {agent} | blockers: {blocker_count} "
            f"| verdict: {verdict_summary}"
        )
    }

    # 检测等待 PM 评审态 → 输出自动恢复指令（事件驱动）
    if phase == "waiting-consensus":
        ticket_info = f" TAPD ticket: {ticket_id}" if ticket_id else ""
        output["auto_action"] = "fetch-consensus"
        output["auto_action_message"] = (
            f"\n{'='*60}\n"
            f"[session-start] 检测到任务处于 waiting-consensus 态\n"
            f"  task: {task_id}{ticket_info}\n"
            f"  上次：契约已推送至 TAPD，等待 PM 评审\n"
            f"\n"
            f"→ 检查 events.jsonl 中是否有 tapd:consensus-approved 事件\n"
            f"  · 如有 APPROVED → 更新 phase = 'planner'，路由到 planner agent\n"
            f"  · 无 APPROVED → 执行 /tapd-consensus-fetch 检查评审结果\n"
            f"{'='*60}\n"
        )

    # 检查是否有 pending 事件需要处理
    if EVENTS_LOG_FILE.exists():
        try:
            events = []
            with EVENTS_LOG_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        events.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue

            # 检查最近的 tapd:consensus-approved
            for event in reversed(events):
                if event.get("type") == "tapd:consensus-approved" and event.get("story_id") == story_id:
                    output["auto_action"] = "route-to-planner"
                    output["auto_action_message"] = (
                        f"\n{'='*60}\n"
                        f"[session-start] 检测到 tapd:consensus-approved 事件\n"
                        f"  story: {story_id}\n"
                        f"  → 更新 phase = 'planner'，路由到 planner agent\n"
                        f"{'='*60}\n"
                    )
                    break
        except Exception:
            pass

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
