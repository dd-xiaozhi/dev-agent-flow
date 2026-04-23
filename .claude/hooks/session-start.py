#!/usr/bin/env python3
"""
session-start.py — 新 Session 启动时加载当前任务上下文

事件：SessionStart
行为：
  1. 检测 worktree 模式（若是，加载独立 .chatlabs/）
  2. 检查 .chatlabs/state/current_task（当前 active task_id）
  3. 若存在：加载 workflow-state.json（单一状态源）
  4. 若 phase == waiting-consensus：输出自动恢复指令（事件驱动）
  5. 若为当天首次 session：触发 gc dry_run（静默，不阻断主流程）
  6. 正常输出任务摘要

前置：.chatlabs/state/current_task 由 /task-new 或 /task-resume 写入
依赖：workflow-state.json（Phase 1 引入，替代 meta.json）
支持：worktree 模式（Phase 2 引入，每个 worktree 独立 .chatlabs/）
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
    PROJECT_DIR, CURRENT_TASK, TASK_REPORTS, GC_LAST_RUN, SCRIPTS_DIR, STATE_DIR, CHATLABS_DIR,
    TASK_INDEX, EVENTS_LOG, PROPOSALS_PENDING_PATH, PROPOSALS_APPLIED_PATH
)
from workflow_state import emit_event, check_event, get_recent_events  # noqa: E402
from member_log_utils import (  # noqa: E402
    get_current_member, append_member_log, get_member_context
)

# Flow Orchestrator（可选，无则静默）
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from flow import FlowOrchestrator, Event
    HAS_FLOW_ORCHESTRATOR = True
except ImportError:
    HAS_FLOW_ORCHESTRATOR = False


def detect_worktree_mode() -> tuple[bool, Path]:
    """
    检测是否在 worktree 内运行

    Returns:
        (is_worktree, worktree_root) 元组
        - is_worktree: 是否在 worktree 内
        - worktree_root: worktree 根目录（若在 worktree 内）或 PROJECT_DIR（若不在）
    """
    cwd = Path.cwd()

    # 方式 1: 检查 .git 文件（git worktree 标志）
    git_file = cwd / ".git"
    if git_file.exists() and git_file.is_file():
        try:
            content = git_file.read_text().strip()
            if content.startswith("gitdir:"):
                # 这是 worktree 的 .git 文件
                # 提取 worktree 根目录
                git_dir = Path(content.replace("gitdir:", "").strip())
                worktree_root = git_dir.parent.parent  # .git 是 worktrees/story-001/.git
                return True, worktree_root
        except Exception:
            pass

    # 方式 2: 检查 .worktrees/ 目录结构
    # 如果当前目录在 .worktrees/ 下，则是 worktree
    for parent in cwd.parents:
        if parent.name == ".worktrees":
            return True, parent.parent  # 返回 PROJECT_DIR

    return False, PROJECT_DIR


def get_worktree_state_paths(worktree_root: Path) -> dict:
    """获取 worktree 模式的路径（独立 .chatlabs/）"""
    return {
        "chatlabs_dir": worktree_root / CHATLABS_DIR.name,
        "current_task": worktree_root / CHATLABS_DIR.name / "state" / "current_task",
        "workflow_state": worktree_root / CHATLABS_DIR.name / "state" / "workflow-state.json",
        "events_log": worktree_root / CHATLABS_DIR.name / "state" / "events.jsonl",
        "reports_dir": worktree_root / CHATLABS_DIR.name / "reports",
    }


# 检测 worktree 模式
IS_WORKTREE, WORKTREE_ROOT = detect_worktree_mode()

# 根据模式选择路径
if IS_WORKTREE:
    WT_PATHS = get_worktree_state_paths(WORKTREE_ROOT)
    CURRENT_TASK_FILE = WT_PATHS["current_task"]
    REPORTS_DIR = WT_PATHS["reports_dir"]
    WORKFLOW_STATE_FILE = WT_PATHS["workflow_state"]
    EVENTS_LOG_FILE = WT_PATHS["events_log"]
else:
    CURRENT_TASK_FILE = CURRENT_TASK
    REPORTS_DIR = TASK_REPORTS
    WORKFLOW_STATE_FILE = STATE_DIR / "workflow-state.json"
    EVENTS_LOG_FILE = STATE_DIR / "events.jsonl"

GC_FLAG_FILE = GC_LAST_RUN


def utc_now():
    return datetime.now(timezone.utc)


def _dispatch_pending_events(state_data: dict, story_id: str) -> dict | None:
    """
    扫描 events.jsonl 中尚未处理的待消费事件，分发到对应处理器。
    幂等保证：每个事件 type 只在当前 session 处理一次。

    支持两种模式：
    1. Flow Orchestrator 模式（优先）：由 Orchestrator 调度适配器
    2. 兼容模式（无 Orchestrator）：直接提示用户执行命令

    返回 dict 包含 auto_action 和 auto_action_message，或 None（无待处理事件）。
    """
    if not story_id or story_id == "?":
        return None

    events = get_recent_events(story_id, limit=100)
    if not events:
        return None

    tapd_state = state_data.get("integrations", {}).get("tapd", {}) if state_data else {}
    tapd_enabled = tapd_state.get("enabled", False)
    ticket_id = tapd_state.get("ticket_id", None)

    # 检查 contract:frozen 事件
    for event in reversed(events):
        if event.get("type") == "contract:frozen" and event.get("story_id") == story_id:
            if tapd_enabled and ticket_id:
                # 检查是否已推送过（consensus_version > 0）
                consensus_version = tapd_state.get("consensus_version", 0)
                if consensus_version == 0:
                    ticket_info = f" TAPD ticket: {ticket_id}"
                    # 优先使用 Flow Orchestrator
                    if HAS_FLOW_ORCHESTRATOR:
                        try:
                            orchestrator = FlowOrchestrator()
                            orchestrator.emit(Event(
                                type="contract:frozen",
                                source="session-start",
                                story_id=story_id,
                                data=event,
                            ))
                            return None  # Orchestrator 会处理，这里不提示
                        except Exception:
                            pass  # fallback 到兼容模式
                    # 兼容模式
                    return {
                        "auto_action": "tapd-consensus-push",
                        "auto_action_message": (
                            f"\n{'='*60}\n"
                            f"[session-start] 检测到 contract:frozen 事件\n"
                            f"  story: {story_id}{ticket_info}\n"
                            f"  → 契约已冻结，建议推送至 TAPD 进行 PM 评审\n"
                            f"  → 执行 /tapd-consensus-push {story_id}\n"
                            f"{'='*60}\n"
                        )
                    }
            break

    return None


def _check_workflow_review_trigger() -> dict | None:
    """
    条件触发 workflow-review 检查。

    触发条件（满足任一即提示）：
    1. 距上次 workflow-review 超过 7 天
    2. 新增 task 数超过 20（从 TASK_INDEX 计数）
    3. pending 提案超过 5 条
    4. blocker 堆积超过 10 条（跨所有 task）

    返回 trigger_info 或 None（不满足条件）。
    """
    reasons = []

    # 条件 2: 新增 task 数超过 20
    task_count = 0
    if TASK_INDEX.exists():
        try:
            with TASK_INDEX.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        task_count += 1
        except Exception:
            pass
    if task_count > 20:
        reasons.append(f"task 数已达 {task_count} 条")

    # 条件 3: pending 提案超过 5 条
    pending_count = 0
    if PROPOSALS_PENDING_PATH.exists():
        try:
            with PROPOSALS_PENDING_PATH.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        pending_count += 1
        except Exception:
            pass
    if pending_count > 5:
        reasons.append(f"pending 提案 {pending_count} 条")

    # 条件 4: blocker 堆积超过 10 条
    blocker_total = 0
    if TASK_INDEX.exists():
        try:
            with TASK_INDEX.open("r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entry = json.loads(line)
                            blocker_total += entry.get("blocker_count", 0)
                        except Exception:
                            pass
        except Exception:
            pass
    if blocker_total > 10:
        reasons.append(f"blocker 堆积 {blocker_total} 条")

    # 条件 1: 距上次 workflow-review 超过 7 天
    # 通过检查 reports/workflow/blockers-summary.md 的 mtime 判断
    summary_file = REPORTS_DIR.parent / "workflow" / "blockers-summary.md"
    if summary_file.exists():
        mtime = datetime.fromtimestamp(summary_file.stat().st_mtime, tz=timezone.utc)
        days_since = (utc_now() - mtime).days
        if days_since > 7:
            reasons.append(f"距上次 workflow-review {days_since} 天")
    else:
        # 不存在 summary，说明从未执行过 workflow-review
        reasons.append("尚未执行过 workflow-review")

    if not reasons:
        return None

    return {
        "reasons": reasons,
        "suggestion": (
            f"\n{'='*60}\n"
            f"[session-start] 🔔 建议触发 workflow-review\n"
            f"  原因：{' + '.join(reasons)}\n"
            f"  → 执行 /workflow-review\n"
            f"{'='*60}\n"
        )
    }


def _run_gc_if_needed():
    """每天首次 session 自动 dry_run gc，不阻断主流程"""
    today = utc_now().strftime("%Y-%m-%d")
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

    # 获取当前成员身份并写入 session-start 事件
    member = get_current_member()
    current_task_id = None
    try:
        if CURRENT_TASK_FILE.exists():
            current_task_id = CURRENT_TASK_FILE.read_text().strip() or None
    except Exception:
        pass

    # 获取工作流状态信息
    story_id_from_state = None
    phase_from_state = None
    if WORKFLOW_STATE_FILE.exists():
        try:
            state = json.loads(WORKFLOW_STATE_FILE.read_text())
            story_id_from_state = state.get("story_id")
            phase_from_state = state.get("phase")
        except Exception:
            pass

    # 加载成员上下文（用于后续 prompt 注入）
    member_context = get_member_context(member, limit=20)

    # 写入 session-start 事件到成员活动日志
    append_member_log(
        event_type="session-start",
        member=member,
        task_id=current_task_id,
        story_id=story_id_from_state,
        phase=phase_from_state,
        summary=f"会话开始，活跃任务: {current_task_id or '无'}",
    )

    # 写入事件总线
    emit_event("session:start", {
        "member": member,
        "task_id": current_task_id,
        "story_id": story_id_from_state,
        "phase": phase_from_state,
    })

    # 将成员上下文注入到环境变量，供 Agent prompt 使用
    import os
    os.environ["CLAUDE_MEMBER_ID"] = member
    os.environ["CLAUDE_MEMBER_STATS"] = json.dumps(member_context.get("stats", {}), ensure_ascii=False)

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
        "member": {
            "id": member,
            "stats": member_context.get("stats", {}),
            "recent_activities": member_context.get("recent_activities", [])[:5],
        },
        "records": {
            "summary": summary_path,
            "blockers": blockers_path if blocker_count > 0 else None,
            "diff_log": diff_path,
            "file_reads": reads_path,
        },
        "worktree_mode": IS_WORKTREE,
        "worktree_root": str(WORKTREE_ROOT) if IS_WORKTREE else None,
        "message": (
            f"[session-start] Active task: {task_id} | story: {story_id} "
            f"| phase: {phase} | agent: {agent} | blockers: {blocker_count} "
            f"| verdict: {verdict_summary} | member: {member}"
            + (f" | worktree: {WORKTREE_ROOT.name}" if IS_WORKTREE else "")
        )
    }

    # 分发待处理事件（event dispatch）
    event_result = _dispatch_pending_events(state_data, story_id)
    if event_result:
        output["auto_action"] = event_result.get("auto_action", "unknown")
        output["auto_action_message"] = event_result.get("auto_action_message", "")

    # 检查 workflow-review 触发条件（不阻断，仅提示）
    review_trigger = _check_workflow_review_trigger()
    if review_trigger:
        output["review_suggestion"] = review_trigger.get("suggestion", "")

    # 检测等待 PM 评审态 → 输出自动恢复指令（事件驱动）
    if phase == "waiting-consensus":
        ticket_info = f" TAPD ticket: {ticket_id}" if ticket_id else ""
        # 优先使用 Flow Orchestrator 检查共识状态
        if HAS_FLOW_ORCHESTRATOR:
            try:
                from flow.paths import CONSENSUS_DIR
                consensus_status_file = CONSENSUS_DIR / story_id / "status"
                if consensus_status_file.exists():
                    status = consensus_status_file.read_text().strip()
                    if status == "approved":
                        output["auto_action"] = "route-to-planner"
                        output["auto_action_message"] = (
                            f"\n{'='*60}\n"
                            f"[session-start] 检测到共识已达成\n"
                            f"  story: {story_id}\n"
                            f"  → 更新 phase = 'planner'，路由到 planner agent\n"
                            f"{'='*60}\n"
                        )
                    elif status == "rejected":
                        output["auto_action"] = "route-to-doc"
                        output["auto_action_message"] = (
                            f"\n{'='*60}\n"
                            f"[session-start] 检测到共识被打回\n"
                            f"  story: {story_id}\n"
                            f"  → 更新 phase = 'doc'，请修订契约\n"
                            f"{'='*60}\n"
                        )
                    else:
                        output["auto_action"] = "fetch-consensus"
                        output["auto_action_message"] = (
                            f"\n{'='*60}\n"
                            f"[session-start] 任务处于 waiting-consensus 态\n"
                            f"  task: {task_id}{ticket_info}\n"
                            f"  状态：{status}\n"
                            f"  → 等待外部评审结果\n"
                            f"{'='*60}\n"
                        )
                else:
                    output["auto_action"] = "fetch-consensus"
                    output["auto_action_message"] = (
                        f"\n{'='*60}\n"
                        f"[session-start] 任务处于 waiting-consensus 态\n"
                        f"  task: {task_id}{ticket_info}\n"
                        f"  → 等待外部评审结果\n"
                        f"{'='*60}\n"
                    )
            except Exception:
                pass  # fallback 到兼容模式
        else:
            # 兼容模式
            output["auto_action"] = "fetch-consensus"
            output["auto_action_message"] = (
                f"\n{'='*60}\n"
                f"[session-start] 检测到任务处于 waiting-consensus 态\n"
                f"  task: {task_id}{ticket_info}\n"
                f"  上次：契约已推送，等待评审\n"
                f"\n"
                f"→ 检查 events.jsonl 中是否有 consensus-approved 事件\n"
                f"  · 如有 APPROVED → 更新 phase = 'planner'，路由到 planner agent\n"
                f"  · 无 APPROVED → 执行 /tapd-consensus-fetch 检查评审结果\n"
                f"{'='*60}\n"
            )

    # 检查是否有 pending 事件需要处理（tapd:consensus-approved / planner:all-cases-ready）
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

            # 检查 planner:all-cases-ready → 自动派发 TAPD 子工单 + 路由到 generator
            if check_event(story_id, "planner:all-cases-ready"):
                ticket_info = f" TAPD ticket: {ticket_id}" if ticket_id else ""
                output["auto_action"] = "planner-to-generator"
                output["auto_action_message"] = (
                    f"\n{'='*60}\n"
                    f"[session-start] 检测到 planner:all-cases-ready 事件\n"
                    f"  story: {story_id}{ticket_info}\n"
                    f"  → 自动触发 /tapd-subtask-emit 派发子工单\n"
                    f"  → 更新 phase = 'generator'，路由到 generator agent\n"
                    f"{'='*60}\n"
                )
        except Exception:
            pass

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
