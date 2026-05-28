#!/usr/bin/env python3
"""
session-start — 新 Session 启动时加载当前任务上下文

事件: SessionStart
Matcher: ""（空，全匹配）

触发条件:
  - .chatlabs/state/current_task 存在（有 active task_id）

行为:
  1. 反查 task_id → story_id 并加载 task.json
  2. 读 task.json.workflow.flow，确定当前 step 与下一步建议
  3. 当天首次 session → 触发 gc dry_run（静默）
  4. 输出任务摘要给 Claude

降级 / 阻断:
  - 阻断条件: 无
  - 失败兜底: 无 active task → 静默退出；gc 失败不阻断主流程

产物:
  - 输出任务摘要（stdout JSON）给 Claude
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

# ── 集中路径常量 ──────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parents[2]
_CHATLABS_DIR = _PROJECT_DIR / ".chatlabs"
_STATE_DIR = _CHATLABS_DIR / "state"
_CURRENT_TASK_FILE = _STATE_DIR / "current_task"
_STORE_DIR = _CHATLABS_DIR / "task" / "store"
_REPORTS_DIR = _CHATLABS_DIR / "reports" / "tasks"
_TASK_INDEX = _REPORTS_DIR / "_index.jsonl"
_GC_LAST_RUN = _STATE_DIR / "gc_last_run"

# 加载 TaskJsonStore（task.json 单写者门面）+ 事件总线
sys.path.insert(0, str(_PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
sys.path.insert(0, str(_PROJECT_DIR / ".claude" / "skills" / "flow-engine" / "scripts"))
from task_store import TaskJsonStore  # noqa: E402
from events import check_event  # noqa: E402


# ── 类型定义 ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class TaskContext:
    """任务上下文完整数据。"""
    task_id: str
    story_id: str
    phase: str
    agent: str
    blocker_count: int
    verdict_summary: str
    tapd_ticket_id: Optional[str]
    flow_id: Optional[str]
    flow_status: str  # "completed" | "in_progress" | "not-initialized"
    paths: dict


@dataclass(frozen=True)
class FlowStep:
    """Flow 步骤信息。"""
    kind: str
    id: str
    target: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "FlowStep":
        return cls(
            kind=d.get("kind", "unknown"),
            id=d.get("id", ""),
            target=d.get("target"),
        )


@dataclass
class SessionStartOutput:
    """session-start hook 的 JSON 输出结构。"""
    task_id: str
    story_id: str
    phase: str
    agent: str
    blocker_count: int
    verdict: str
    tapd_ticket_id: Optional[str]
    records: dict
    flow_status: str
    flow_id: Optional[str] = None
    current_step: Optional[dict] = None
    next_step: Optional[dict] = None
    flow_message: Optional[str] = None
    message: Optional[str] = None
    auto_action: Optional[str] = None
    auto_action_message: Optional[str] = None
    review_suggestion: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


# ── 辅助函数 ──────────────────────────────────────────────────────

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def read_per_story_state(story_id: str) -> dict:
    """读取 per-story task.json（优先），平铺 workflow section 与顶层 meta。"""
    store = TaskJsonStore.load_by_story(story_id)
    if not store.data.get("task_id"):
        return {}
    td = store.data
    wf = td.get("workflow") or {}
    merged: dict = {
        k: td.get(k) for k in
        ("task_id", "task_type", "story_id", "trigger", "dev_mode")
        if td.get(k) is not None
    }
    merged.update(wf)
    return merged


def get_current_task_id() -> Optional[str]:
    """获取当前活跃的 task_id。"""
    try:
        return _CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def lookup_story_id(task_id: str) -> Optional[str]:
    """通过 _index.jsonl 反查 task_id → story_id。

    若索引缺失或未命中，则兜底用 task_id 直接作为 story_id 探测 task.json
    （新约定下两者通常一致：task_id == story_id == {MM-dd}-{slug}）。
    """
    if _TASK_INDEX.exists():
        try:
            for line in _TASK_INDEX.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("task_id") == task_id:
                    sid = entry.get("story_id")
                    if sid:
                        return sid
        except Exception:
            pass
    # 兜底：task_id 直接作 story_id 探测
    probe = TaskJsonStore.load_by_story(task_id)
    if probe.data.get("task_id") == task_id:
        return task_id
    return None


def load_task_data(task_id: str) -> dict:
    """通过 task_id 加载 task.json 完整数据（dict）。无法定位时返回 {}。"""
    story_id = lookup_story_id(task_id)
    if not story_id:
        return {}
    store = TaskJsonStore.load_by_story(story_id)
    return store.data if store.data.get("task_id") else {}


def extract_task_context(state_data: Optional[dict], task_id: Optional[str]) -> TaskContext:
    """从 state_data 或 task.json 提取任务上下文。"""
    if state_data and state_data.get("flow"):
        return TaskContext(
            task_id=state_data.get("task_id", task_id or "?"),
            story_id=state_data.get("story_id", "?"),
            phase=state_data.get("phase", "?"),
            agent=state_data.get("agent", "?"),
            blocker_count=state_data.get("blocker_count", 0),
            verdict_summary=_format_verdict(state_data.get("verdicts", {})),
            tapd_ticket_id=_extract_tapd_ticket(state_data),
            flow_id=state_data["flow"].get("flow_id"),
            flow_status="in_progress",
            paths={},
        )

    # 回退：从 task.json 顶层 + workflow section 读取
    if task_id:
        td = load_task_data(task_id)
        wf = td.get("workflow") or {}
        tapd = td.get("tapd") or {}
        verdicts = wf.get("verdicts", {})
        return TaskContext(
            task_id=td.get("task_id", task_id),
            story_id=td.get("story_id", "?"),
            phase=wf.get("phase", "?"),
            agent=wf.get("agent", "?"),
            blocker_count=wf.get("blocker_count", 0),
            verdict_summary=_format_verdict(verdicts) if verdicts else wf.get("verdict", "WIP"),
            tapd_ticket_id=tapd.get("ticket_id"),
            flow_id=(wf.get("flow") or {}).get("flow_id"),
            flow_status="not-initialized",
            paths={},
        )

    # 无任务
    return TaskContext(
        task_id="?", story_id="?", phase="?", agent="?", blocker_count=0,
        verdict_summary="N/A", tapd_ticket_id=None, flow_id=None,
        flow_status="not-initialized", paths={},
    )


def _format_verdict(verdicts: dict) -> str:
    if not verdicts:
        return "WIP"
    passed = sum(1 for v in verdicts.values() if v == "PASS")
    return f"PASS({passed}/{len(verdicts)})"


def _extract_tapd_ticket(state_data: dict) -> Optional[str]:
    tapd_state = state_data.get("integrations", {}).get("tapd", {})
    if tapd_state.get("enabled"):
        return tapd_state.get("ticket_id")
    return None


def build_flow_message(flow_data: dict, story_id: str) -> tuple[str, str]:
    """构建 flow 状态消息。返回 (status, message)。"""
    steps = flow_data.get("steps") or []
    idx = flow_data.get("current_step_idx", 0)
    current = steps[idx] if 0 <= idx < len(steps) else None
    nxt = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None

    if not current:
        return "not-initialized", "[session-start] flow 未初始化"

    kind = current.get("kind", "")
    current_id = current.get("id", "")
    target = current.get("target", "")
    next_id = nxt.get("id") if nxt else "(终点)"

    if kind == "terminal":
        return "completed", (
            f"[session-start] flow 已完成 | flow={flow_data.get('flow_id')}"
        )

    # in_progress
    lines = [
        f"[session-start] flow 续接 | flow={flow_data.get('flow_id')}",
        f"  当前 step: {current_id} (kind={kind}, target={target})",
        f"  下一 step: {next_id}",
    ]

    route_hint = {
        "agent": f"路由至 {target} agent;完成后通过 flow-engine skill 推进流程",
        "command": f"执行命令 {target};完成后通过 flow-engine skill 推进流程",
        "skill": f"调用 {target} skill;完成后通过 flow-engine skill 推进流程",
        "tool": f"用 {target} 工具直接处理;完成后通过 flow-engine skill 推进流程",
        "gate": _build_gate_hint(current, story_id),
    }

    if kind in route_hint:
        lines.append(f"  → {route_hint[kind]}")

    return "in_progress", "\n".join(lines)


def _build_gate_hint(current: dict, story_id: str) -> str:
    gate_event = current.get("gate_event")
    if gate_event:
        if check_event(story_id, gate_event):
            return f"gate 事件 {gate_event} 已到达,可通过 flow-engine skill 推进流程"
        return f"gate 等待事件 {gate_event};未到达则保持等待"
    return "gate 未知"


# ── GC 触发 ──────────────────────────────────────────────────────

def run_gc_if_needed() -> None:
    """每天首次 session 自动 dry_run gc，不阻断主流程。"""
    today = utc_now().strftime("%Y-%m-%d")
    try:
        last = _GC_LAST_RUN.read_text().strip()
        if last == today:
            return
    except FileNotFoundError:
        pass

    gc_script = _PROJECT_DIR / ".claude" / "skills" / "gc" / "scripts" / "gc.py"
    if not gc_script.exists():
        return

    try:
        result = subprocess.run(
            [sys.executable, str(gc_script)],
            capture_output=True, text=True, timeout=60,
            cwd=str(_PROJECT_DIR),
        )
        _GC_LAST_RUN.write_text(today)
        if result.returncode != 0 or result.stderr:
            print(f"[session-start] gc: {result.stderr or result.stdout}", file=sys.stderr)
    except Exception as e:
        print(f"[session-start] gc skip: {e}", file=sys.stderr)


# ── workflow-review 触发检查 ──────────────────────────────────────

def check_workflow_review_trigger() -> Optional[str]:
    """检查是否满足 workflow-review 触发条件。"""
    reasons: list[str] = []

    # 条件 2: task 数超过 20
    task_count = 0
    if _TASK_INDEX.exists():
        try:
            with _TASK_INDEX.open("r", encoding="utf-8") as f:
                task_count = sum(1 for line in f if line.strip())
        except Exception:
            pass
    if task_count > 20:
        reasons.append(f"task 数已达 {task_count} 条")

    # 条件 3: blocker 堆积超过 10 条
    if _TASK_INDEX.exists():
        blocker_total = 0
        try:
            with _TASK_INDEX.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
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
    summary_file = _CHATLABS_DIR / "reports" / "workflow" / "blockers-summary.md"
    if summary_file.exists():
        mtime = datetime.fromtimestamp(summary_file.stat().st_mtime, tz=timezone.utc)
        days_since = (utc_now() - mtime).days
        if days_since > 7:
            reasons.append(f"距上次 workflow-review {days_since} 天")
    else:
        reasons.append("尚未执行过 workflow-review")

    if not reasons:
        return None

    return (
        f"\n{'='*60}\n"
        f"[session-start] 建议触发 workflow-review\n"
        f"  原因：{' + '.join(reasons)}\n"
        f"  → 执行 /workflow-review\n"
        f"{'='*60}\n"
    )


# ── 主逻辑 ──────────────────────────────────────────────────────

def main() -> None:
    # 每日首次 session 触发 gc
    run_gc_if_needed()

    # 获取当前 task_id
    task_id = get_current_task_id()

    # 加载 state（task.json.workflow 是单一 SSOT；通过 task_id → story_id 定位）
    state_data: dict = {}
    if task_id:
        story_id = lookup_story_id(task_id)
        if story_id:
            state_data = read_per_story_state(story_id)

    # session 级事件已废弃（events 仅承载任务级事件，写入 task.json.events）；
    # check_event 仍由 _build_gate_hint 用于 gate step 判定。

    # 构建任务上下文
    ctx = extract_task_context(state_data if state_data else None, task_id)

    # 构建 paths
    reports_base = str(_REPORTS_DIR.relative_to(_PROJECT_DIR))
    blockers_path = f"{reports_base}/{ctx.task_id}/blockers.md" if ctx.blocker_count > 0 else None
    blockers_file = _REPORTS_DIR / ctx.task_id / "blockers.md"

    # 构建输出
    output = SessionStartOutput(
        task_id=ctx.task_id,
        story_id=ctx.story_id,
        phase=ctx.phase,
        agent=ctx.agent,
        blocker_count=ctx.blocker_count,
        verdict=ctx.verdict_summary,
        tapd_ticket_id=ctx.tapd_ticket_id,
        records={
            "blockers": blockers_path if blockers_file.exists() else None,
        },
        flow_status=ctx.flow_status,
        flow_id=ctx.flow_id,
        message=f"[session-start] Active task: {ctx.task_id} | story: {ctx.story_id} "
                f"| phase: {ctx.phase} | agent: {ctx.agent} | blockers: {ctx.blocker_count} "
                f"| verdict: {ctx.verdict_summary}",
    )

    # 检查 workflow-review 触发条件
    review_suggestion = check_workflow_review_trigger()
    if review_suggestion:
        output.review_suggestion = review_suggestion

    # Flow 状态
    flow_data = state_data.get("flow") if state_data else None
    if flow_data:
        status, message = build_flow_message(flow_data, ctx.story_id)
        output.flow_status = status
        output.flow_message = message
        if status == "in_progress":
            steps = flow_data.get("steps") or []
            idx = flow_data.get("current_step_idx", 0)
            output.current_step = steps[idx] if 0 <= idx < len(steps) else None
            output.next_step = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None
    else:
        output.flow_message = (
            "[session-start] flow 未初始化 | "
            "建议从 /start-dev-flow 重新进入"
        )

    print(json.dumps(output.to_dict(), ensure_ascii=False))


if __name__ == "__main__":
    main()