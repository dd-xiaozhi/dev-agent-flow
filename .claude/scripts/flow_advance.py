"""
flow_advance.py — 流程编排推进器

读 workflow-state.json.flow + 模板 JSON,推进 current_step_idx,
双写 phase/agent,追加 history,输出下一步。

阶段 1:由主 Claude 在每个 step 完成后显式调用。
阶段 2:接 SubagentStop hook 自动化。

Usage:
    # 初始化(task 创建时,/start-dev-flow 调用)
    python flow_advance.py init --flow-id tapd-full --story-id 1140xxxx --task-id TASK-xxx

    # 推进(agent 完成后,主 Claude 调用)
    python flow_advance.py complete doc-librarian

    # 只读检查(/task-resume 调用)
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import TEMPLATES_DIR, STORIES_DIR, STATE_DIR

FLOW_TEMPLATES_DIR = TEMPLATES_DIR / "flows"


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
    """返回该 story 的 workflow-state.json 路径(无 story_id 则用全局)。"""
    if story_id:
        return STORIES_DIR / story_id / "workflow-state.json"
    return STATE_DIR / "workflow-state.json"


def load_state(story_id: Optional[str]) -> dict:
    path = state_file_for(story_id)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict, story_id: Optional[str]) -> None:
    path = state_file_for(story_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now_iso()
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
    """只读输出当前状态。/task-resume 用。"""
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


def cmd_complete(args: argparse.Namespace) -> dict:
    """推进 flow:声明 step_id 已完成,advance 到下一步。"""
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
            "hint": "did you skip a step? use --force to override",
        }

    # 写 history
    flow.setdefault("history", []).append({
        "step_id": current["id"],
        "kind": current.get("kind"),
        "target": current.get("target"),
        "completed_at": now_iso(),
        "result": args.result or "ok",
    })

    # advance
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
                        choices=["tapd-full", "local-spec", "local-plan", "local-vibe"])
    p_init.add_argument("--task-id", default=None)
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", help="只读输出当前状态")
    p_check.set_defaults(func=cmd_check)

    p_complete = sub.add_parser("complete", help="声明 step 完成,推进到下一步")
    p_complete.add_argument("step_id")
    p_complete.add_argument("--result", default=None)
    p_complete.add_argument("--force", action="store_true")
    p_complete.set_defaults(func=cmd_complete)

    p_reset = sub.add_parser("reset", help="重置到第一步(debug)")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
