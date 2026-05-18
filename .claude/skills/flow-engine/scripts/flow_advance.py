"""
flow_advance.py — 流程编排推进器

读 workflow-state.json.flow + 模板 JSON,推进 current_step_idx,
双写 phase/agent,追加 history,输出下一步。

阶段 1:由主 Claude 在每个 step 完成后显式调用（command/skill 类型）。
阶段 2:接 PostToolUse hook 自动化（agent 类型完成后自动推进）。

注意：原设计的 SubagentStop hook 不存在，实际用 post-tool-flow-advance.py
通过 PostToolUse 事件检测 Agent 工具完成后自动推进。

Usage:
    # 初始化(task 创建时,/start-dev-flow 调用)
    python flow_advance.py init --flow-id tapd-full --story-id 1140xxxx --task-id TASK-xxx

    # 推进(agent 完成后,主 Claude 调用)
    python flow_advance.py complete doc-librarian

    # 只读检查(task.py resume 调用)
    python flow_advance.py check

    # 重置(debug 用)
    python flow_advance.py reset
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 共享基础设施位于 .claude/scripts/，本脚本位于 .claude/skills/flow-engine/scripts/
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parents[2] / "scripts"))

from paths import TEMPLATES_DIR, STORE_DIR, STATE_DIR  # noqa: E402
from task_store import TaskJsonStore  # noqa: E402
from events import check_event, get_recent_events  # noqa: E402

FLOW_TEMPLATES_DIR = TEMPLATES_DIR / "flows"

# task.json 顶层固定字段（其余字段在 workflow section）
_TASK_JSON_TOP_FIELDS = {
    "task_id", "task_type", "story_id", "created_at",
    "updated_at", "trigger", "dev_mode",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_template(flow_id: str) -> dict:
    """加载流程模板 JSON。"""
    template_path = FLOW_TEMPLATES_DIR / f"{flow_id}.json"
    if not template_path.exists():
        raise FileNotFoundError(f"flow template not found: {template_path}")
    return json.loads(template_path.read_text(encoding="utf-8"))


def template_hash(template: dict) -> str:
    """模板内容 SHA256 前 16 位,创建时锁定版本。"""
    canonical = json.dumps(template, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def state_file_for(story_id: Optional[str]) -> Path:
    """返回该 story 的 task.json 路径(无 story_id 则用全局 workflow-state.json)。

    新格式：状态聚合在 `<task_dir>/task.json` 的 workflow section；
    旧的 per-story workflow-state.json 已弃用，仅保留全局 fallback。"""
    if story_id:
        return STORE_DIR / story_id / "task.json"
    return STATE_DIR / "workflow-state.json"


def load_state(story_id: Optional[str]) -> dict:
    """读取 state dict（保持旧 dict 形态：task_id/story_id 顶层 + 其余平铺）。

    per-story 走 task.json 时，会把 task.json 顶层 meta 与 workflow section 合并成平铺 dict。
    """
    if story_id:
        store = TaskJsonStore.load_by_story(story_id)
        wf = store.get_workflow() or {}
        merged: dict = {
            k: v for k, v in store.data.items()
            if k in _TASK_JSON_TOP_FIELDS and v is not None
        }
        merged.update(wf)
        return merged
    # 全局 workflow-state.json fallback
    path = state_file_for(None)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict, story_id: Optional[str]) -> None:
    """保存 state dict。

    per-story 走 task.json：把 dict 拆成顶层 meta 与 workflow section 分别写。
    """
    state["updated_at"] = now_iso()
    if story_id:
        store = TaskJsonStore.load_by_story(story_id)
        store.task_dir.mkdir(parents=True, exist_ok=True)
        # 顶层固定字段直接 set
        for key in _TASK_JSON_TOP_FIELDS:
            if key in state and state[key] is not None:
                store.set_field(key, state[key])
        # 其余字段全部进 workflow section
        workflow_patch = {
            k: v for k, v in state.items()
            if k not in _TASK_JSON_TOP_FIELDS
        }
        store.update_workflow(workflow_patch)
        store.save()
        return
    # 全局 fallback
    path = state_file_for(None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def build_flow_block(template: dict) -> dict:
    """从模板构造初始 flow 子对象。"""
    steps = template["steps"]
    first = steps[0]
    return {
        "flow_id": template["flow_id"],
        "version": template.get("version", "1.0"),
        "frozen_template_hash": template_hash(template),
        "steps": steps,  # 内嵌 steps 副本(锁定版本,模板后续升级不影响 task)
        "current_step_idx": 0,
        "current_step_id": first["id"],
        "history": [],
        "started_at": now_iso(),
        "completed_at": None,
    }


def sync_phase_alias(state: dict) -> None:
    """从 flow.current_step 双写 phase / agent(兼容旧读取代码)。"""
    flow = state.get("flow") or {}
    steps = flow.get("steps") or []
    idx = flow.get("current_step_idx", 0)
    if idx >= len(steps):
        return
    step = steps[idx]
    state["phase"] = step.get("phase_alias") or step["id"]
    if step.get("kind") == "agent":
        state["agent"] = step.get("target")
    else:
        state["agent"] = None


def cmd_init(args: argparse.Namespace) -> dict:
    """初始化 flow 子对象。task 创建时由 /start-dev-flow 调用。"""
    template = load_template(args.flow_id)
    state = load_state(args.story_id)

    # 已存在 flow 时拒绝(避免覆盖),除非 --force
    if state.get("flow") and not args.force:
        return {
            "ok": False,
            "error": "flow already initialized",
            "existing_flow_id": state["flow"].get("flow_id"),
            "hint": "use --force to overwrite",
        }

    if args.task_id:
        state["task_id"] = args.task_id
    if args.story_id:
        state["story_id"] = args.story_id

    state["flow"] = build_flow_block(template)
    sync_phase_alias(state)
    save_state(state, args.story_id)

    first_step = state["flow"]["steps"][0]
    return {
        "ok": True,
        "flow_id": template["flow_id"],
        "current_step": first_step,
        "next_step": state["flow"]["steps"][1] if len(state["flow"]["steps"]) > 1 else None,
    }


def cmd_check(args: argparse.Namespace) -> dict:
    """只读输出当前状态。task.py resume 用。"""
    state = load_state(args.story_id)
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow initialized for this state"}

    steps = flow["steps"]
    idx = flow["current_step_idx"]
    current = steps[idx] if idx < len(steps) else None
    next_step = steps[idx + 1] if idx + 1 < len(steps) else None

    return {
        "ok": True,
        "flow_id": flow["flow_id"],
        "current_step_idx": idx,
        "current_step": current,
        "next_step": next_step,
        "is_terminal": current is not None and current.get("kind") == "terminal",
        "history_count": len(flow.get("history", [])),
    }


def _latest_gate_state(
    story_id: str,
    approve_event: Optional[str],
    reject_event: Optional[str],
) -> tuple[bool, bool]:
    """返回 (approved, rejected),取 approve_event / reject_event 中**最近**那一条的状态。

    - 都没出现 → (False, False)
    - 只出现 approve → (True, False)
    - 只出现 reject → (False, True)
    - 都出现 → 比较 ts,新的胜出;无 ts 字段时按 events 数组顺序末尾胜出
    """
    if not approve_event and not reject_event:
        return False, False
    types = [t for t in (approve_event, reject_event) if t]
    # 拿到所有相关事件,按时间排序找最新
    relevant: list[tuple[str, dict]] = []
    for t in types:
        for ev in get_recent_events(story_id, t, limit=0):
            relevant.append((ev.get("type", t), ev))
    if not relevant:
        return False, False
    # 时间戳字段名通常是 ts / timestamp / created_at,做兜底
    def _ts(ev: dict) -> str:
        return ev.get("ts") or ev.get("timestamp") or ev.get("created_at") or ""
    # 稳定按 (ts, 原始顺序) 排序,取末位
    indexed = [(i, evt) for i, evt in enumerate(relevant)]
    indexed.sort(key=lambda x: (_ts(x[1][1]), x[0]))
    _, (latest_type, _) = indexed[-1]
    return (latest_type == approve_event), (latest_type == reject_event)


def cmd_complete(args: argparse.Namespace) -> dict:
    """推进 flow:声明 step_id 已完成,advance 到下一步。

    Gate 特殊语义(kind=gate):
      - 必须携带评审证据(--evidence-type + --evidence-id)
      - evidence-type 支持: wiki-comment-id(Wiki评论ID,会验证是否包含[CONSENSUS-APPROVED])
      - on_complete_event 到达 → 正常 advance
      - reject_event 到达 → 跳回 reject_jump_to 指定 step(契约重做循环)
      - 两个事件都没有 → 拒绝推进
    """
    state = load_state(args.story_id)
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow initialized"}

    steps = flow["steps"]
    idx = flow["current_step_idx"]
    if idx >= len(steps):
        return {"ok": False, "error": "flow already terminated"}

    current = steps[idx]
    if current["id"] != args.step_id:
        # 幂等检查:声明的 step 已经在 history 里 -> 静默 ok(防重复调用)
        already_done = any(h["step_id"] == args.step_id for h in flow.get("history", []))
        if already_done:
            return {
                "ok": True,
                "noop": True,
                "reason": f"step '{args.step_id}' already advanced past",
                "current_step": current,
            }
        return {
            "ok": False,
            "error": f"step mismatch: current is '{current['id']}', got '{args.step_id}'",
            "hint": "did you skip a step?",
        }

    # ── Gate 事件依赖判断 ──
    advance_action = "advance"  # "advance" | "jump_back"
    jump_to_idx: Optional[int] = None
    if current.get("kind") == "gate":
        if not args.story_id:
            return {
                "ok": False,
                "error": "gate step requires --story-id to check events",
            }

        # Gate 必须携带评审证据
        if not args.evidence_type or not args.evidence_id:
            return {
                "ok": False,
                "error": (
                    f"gate step '{current['id']}' requires evidence. "
                    f"Must provide --evidence-type and --evidence-id. "
                    f"Example: --evidence-type wiki-comment-id --evidence-id 1152676229001xxxx"
                ),
                "hint": (
                    "Evidence types: wiki-comment-id (TAPD Wiki comment ID containing [CONSENSUS-APPROVED])"
                ),
            }

        # 验证评审证据（由 AI 在调用前已完成，脚本只做存在性校验）
        # AI 有责任先调用 /tapd-consensus-fetch 确认评论内容包含 [CONSENSUS-APPROVED]
        if args.evidence_type == "wiki-comment-id":
            if not args.evidence_id or args.evidence_id == "fake-evidence":
                return {
                    "ok": False,
                    "error": (
                        f"gate step '{current['id']}' requires valid evidence. "
                        f"Must provide --evidence-id with the actual TAPD comment ID. "
                        f"Example: --evidence-type wiki-comment-id --evidence-id 1152676229001006xxx"
                    ),
                    "hint": (
                        "Before calling this, use /tapd-consensus-fetch to retrieve "
                        "and verify the PM's approval comment containing [CONSENSUS-APPROVED]. "
                        "Then pass the verified comment ID as --evidence-id."
                    ),
                }

        approve_event = current.get("on_complete_event")
        reject_event = current.get("reject_event")

        # 检查是否有真实的 approve 事件（基于验证后的证据）
        approved, rejected = _latest_gate_state(
            args.story_id, approve_event, reject_event,
        )

        # 如果证据验证通过但还没有事件记录，创建事件
        if args.evidence_type == "wiki-comment-id" and args.evidence_id:
            # 证据已验证通过，创建 approve 事件
            from events import emit_event
            emit_event(approve_event, {
                "story_id": args.story_id,
                "evidence_type": args.evidence_type,
                "evidence_id": args.evidence_id,
                "actor": "pm-consensus"
            })
            approved = True
            rejected = False

        if not approved and not rejected:
            return {
                "ok": False,
                "error": (
                    f"gate '{current['id']}' blocked: "
                    f"neither '{approve_event}' nor '{reject_event}' event found"
                ),
            }
        elif rejected and not approved:
            jump_target = current.get("reject_jump_to")
            if not jump_target:
                return {
                    "ok": False,
                    "error": (
                        f"gate '{current['id']}' rejected but no reject_jump_to "
                        f"defined in template"
                    ),
                }
            for i, s in enumerate(steps):
                if s["id"] == jump_target:
                    jump_to_idx = i
                    advance_action = "jump_back"
                    break
            if jump_to_idx is None:
                return {
                    "ok": False,
                    "error": (
                        f"reject_jump_to target '{jump_target}' not found in steps"
                    ),
                }

    # 写 history
    history_entry = {
        "step_id": current["id"],
        "kind": current.get("kind"),
        "target": current.get("target"),
        "completed_at": now_iso(),
        "result": args.result or (
            "rejected" if advance_action == "jump_back" else "ok"
        ),
    }
    if args.evidence_type and args.evidence_id:
        history_entry["evidence"] = {
            "type": args.evidence_type,
            "id": args.evidence_id,
        }
    if advance_action == "jump_back":
        history_entry["jumped_to"] = steps[jump_to_idx]["id"]
    flow.setdefault("history", []).append(history_entry)

    # advance or jump back
    if advance_action == "jump_back":
        flow["current_step_idx"] = jump_to_idx
        flow["current_step_id"] = steps[jump_to_idx]["id"]
    else:
        flow["current_step_idx"] = idx + 1
        if flow["current_step_idx"] < len(steps):
            flow["current_step_id"] = steps[flow["current_step_idx"]]["id"]
        else:
            flow["current_step_id"] = None
            flow["completed_at"] = now_iso()

    sync_phase_alias(state)
    save_state(state, args.story_id)

    new_idx = flow["current_step_idx"]
    new_current = steps[new_idx] if new_idx < len(steps) else None
    new_next = steps[new_idx + 1] if new_idx + 1 < len(steps) else None

    return {
        "ok": True,
        "advanced_from": current["id"],
        "advanced_to": new_current["id"] if new_current else None,
        "action": advance_action,
        "forced": False,
        "current_step": new_current,
        "next_step": new_next,
        "is_terminal": new_current is not None and new_current.get("kind") == "terminal",
    }


def cmd_reset(args: argparse.Namespace) -> dict:
    """重置 flow 到 idx=0。debug 用。"""
    state = load_state(args.story_id)
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow to reset"}
    flow["current_step_idx"] = 0
    flow["current_step_id"] = flow["steps"][0]["id"]
    flow["history"] = []
    flow["completed_at"] = None
    sync_phase_alias(state)
    save_state(state, args.story_id)
    return {"ok": True, "reset_to": flow["current_step_id"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Flow advance — 流程编排推进器")
    parser.add_argument("--story-id", default=None, help="story id(默认读全局 state)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="初始化 flow 子对象")
    p_init.add_argument("--flow-id", required=True,
                        choices=["tapd-full", "local-spec", "local-plan", "local-vibe",
                                 "bugfix-spec", "bugfix-plan", "bugfix-vibe"])
    p_init.add_argument("--task-id", default=None)
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", help="只读输出当前状态")
    p_check.set_defaults(func=cmd_check)

    p_complete = sub.add_parser("complete", help="声明 step 完成,推进到下一步")
    p_complete.add_argument("step_id")
    p_complete.add_argument("--result", default=None)
    p_complete.add_argument("--evidence-type", default=None,
                           help="Gate 步骤必须提供的证据类型(如 wiki-comment-id)")
    p_complete.add_argument("--evidence-id", default=None,
                           help="Gate 步骤必须提供的证据ID")
    p_complete.set_defaults(func=cmd_complete)

    p_reset = sub.add_parser("reset", help="重置到第一步(debug)")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
