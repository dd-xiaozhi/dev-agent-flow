#!/usr/bin/env python3
"""
session-start.py — 新 Session 启动时加载当前任务上下文

事件:SessionStart
行为:
  1. 检测 worktree 模式(若是,加载独立 .chatlabs/)
  2. 检查 .chatlabs/state/current_task(当前 active task_id)
  3. 若存在:加载 workflow-state.json(单一状态源)
  4. 读 workflow-state.json.flow,输出当前 step + 下一步建议(不再做 phase-based 自动路由)
  5. 若为当天首次 session:触发 gc dry_run(静默,不阻断主流程)
  6. 正常输出任务摘要

前置:.chatlabs/state/current_task 由 /task-new 或 /task-resume 写入
依赖:workflow-state.json(单一状态源,含 flow 子对象)
支持:worktree 模式(每个 worktree 独立 .chatlabs/)
"""
import json
import os
import subprocess
import sys
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import (  # noqa: E402
    PROJECT_DIR, CURRENT_TASK, TASK_REPORTS, GC_LAST_RUN, SCRIPTS_DIR, STATE_DIR, CHATLABS_DIR,
    STORIES_DIR, TASK_INDEX, EVENTS_LOG, PROPOSALS_PENDING_PATH, PROPOSALS_APPLIED_PATH
)

# Load workflow-state.py (filename has hyphen, cannot use normal import)
_spec = importlib.util.spec_from_file_location(
    "workflow_state", SCRIPTS_DIR / "workflow-state.py"
)
_wf_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wf_module)
emit_event = _wf_module.emit_event
check_event = _wf_module.check_event
get_recent_events = _wf_module.get_recent_events


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

    目前支持的事件：
    - contract:frozen：若 TAPD enabled，提示推送契约到 TAPD

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

    # 阶段 1:不再自动派发 tapd-consensus-push。是否推送由 flow 模板的下一个 step 决定,
    # 这里只在事件存在时记录信息(用于诊断 / debug),不写 auto_action。
    # 完整的"建议下一步"输出已迁移到 main() 中读 flow.current_step 的统一入口。
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

    # 写入事件总线
    emit_event("session:start", {
        "task_id": current_task_id,
        "story_id": story_id_from_state,
        "phase": phase_from_state,
    })

    # 阶段 1:state 数据加载顺序
    #   1. 先读全局 .chatlabs/state/workflow-state.json(向后兼容,旧 task)
    #   2. 若有 story_id 且 story 目录下存在 workflow-state.json,优先取 per-story 版本
    #      (flow_advance.py 默认写 per-story,这是真正的"当前 task 状态")
    state_data = None
    try:
        if WORKFLOW_STATE_FILE.exists():
            state_data = json.loads(WORKFLOW_STATE_FILE.read_text())
    except Exception:
        pass

    # 尝试从 .current_task → meta.json 找 story_id,然后读 per-story state
    try:
        if CURRENT_TASK_FILE.exists():
            _task_id = CURRENT_TASK_FILE.read_text().strip()
            _meta_path = TASK_REPORTS / _task_id / "meta.json"
            if _meta_path.exists():
                _meta = json.loads(_meta_path.read_text())
                _story_id = _meta.get("story_id")
                if _story_id:
                    _story_state = STORIES_DIR / _story_id / "workflow-state.json"
                    if _story_state.exists():
                        _per_story_data = json.loads(_story_state.read_text())
                        # per-story 版本优先(尤其是 flow 子对象)
                        if state_data:
                            state_data.update(_per_story_data)
                        else:
                            state_data = _per_story_data
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
    blockers_path = f"{reports_base}/{task_id}/blockers.md"
    audit_path = f"{reports_base}/{task_id}/audit.jsonl"
    blockers_file = TASK_REPORTS / task_id / "blockers.md"

    output = {
        "task_id": task_id,
        "story_id": story_id,
        "phase": phase,
        "agent": agent,
        "blocker_count": blocker_count,
        "verdict": verdict_summary,
        "tapd_ticket_id": ticket_id,
        "records": {
            # summary 现在在 meta.json.summary 字段中,无独立文件
            "blockers": blockers_path if (blocker_count > 0 and blockers_file.exists()) else None,
            "audit": audit_path,
        },
        "worktree_mode": IS_WORKTREE,
        "worktree_root": str(WORKTREE_ROOT) if IS_WORKTREE else None,
        "message": (
            f"[session-start] Active task: {task_id} | story: {story_id} "
            f"| phase: {phase} | agent: {agent} | blockers: {blocker_count} "
            f"| verdict: {verdict_summary}"
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

    # ── 阶段 1 改造:从 flow 子对象读取流程状态(替代 phase-based if-elif 路由) ──
    #
    # 旧版基于 phase + events.jsonl 的多路分发逻辑(waiting-consensus / consensus-approved /
    # planner:all-cases-ready 三段式自动路由)已彻底删除。所有路由由 flow 模板 + flow_advance.py
    # 决定,session-start hook 仅输出诊断信息,不再自动派发任何命令。
    flow_data = (state_data or {}).get("flow") if state_data else None
    if flow_data:
        steps = flow_data.get("steps") or []
        idx = flow_data.get("current_step_idx", 0)
        current = steps[idx] if 0 <= idx < len(steps) else None
        nxt = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None
        flow_id = flow_data.get("flow_id")

        if current:
            kind = current.get("kind")
            target = current.get("target")
            current_id = current.get("id")
            next_id = nxt.get("id") if nxt else "(终点)"

            if kind == "terminal":
                output["flow_status"] = "completed"
                output["flow_message"] = (
                    f"[session-start] flow 已完成 | flow={flow_id} | "
                    f"history={len(flow_data.get('history', []))} 步"
                )
            else:
                output["flow_status"] = "in_progress"
                output["flow_id"] = flow_id
                output["current_step"] = current
                output["next_step"] = nxt
                hint_lines = [
                    f"[session-start] flow 续接 | flow={flow_id}",
                    f"  当前 step: {current_id} (kind={kind}, target={target})",
                    f"  下一 step: {next_id}",
                ]
                if kind == "agent":
                    hint_lines.append(f"  → 路由至 {target} agent;完成后调 /flow-advance {current_id}")
                elif kind == "command":
                    hint_lines.append(f"  → 执行命令 {target};完成后调 /flow-advance {current_id}")
                elif kind == "skill":
                    hint_lines.append(f"  → 调用 {target} skill;完成后调 /flow-advance {current_id}")
                elif kind == "tool":
                    hint_lines.append(f"  → 用 {target} 工具直接处理;完成后调 /flow-advance {current_id}")
                elif kind == "gate":
                    gate_event = current.get("gate_event")
                    if gate_event and check_event(story_id, gate_event):
                        hint_lines.append(f"  → gate 事件 {gate_event} 已到达,可调 /flow-advance {current_id} 推进")
                    else:
                        hint_lines.append(f"  → gate 等待事件 {gate_event};未到达则保持等待")
                output["flow_message"] = "\n".join(hint_lines)
    else:
        # 无 flow 子对象:可能是阶段 0 旧 task 或未通过 /start-dev-flow 创建
        output["flow_status"] = "not-initialized"
        output["flow_message"] = (
            "[session-start] flow 未初始化 | "
            "建议从 /start-dev-flow 重新进入,或 python .claude/scripts/flow_advance.py init 实例化"
        )

    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
