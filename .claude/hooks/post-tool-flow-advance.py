#!/usr/bin/env python3
"""
post-tool-flow-advance.py — Agent 完成后自动推进 flow

事件：PostToolUse
触发条件：
  1. tool 是 Agent 类型 (tool_name == "Agent")
  2. agent 成功完成 (isError == false)
  3. 当前 flow step 是 agent 类型，且 target 匹配

行为：
  1. 读 task.json.workflow 获取当前 step
  2. 若当前 step.kind == "agent" 且 step.target == agent_type
  3. 自动调用 flow_advance.py complete <step_id>
  4. 输出下一步建议给主 Claude

注意：
  - Gate 类型不会自动推进（需要等待外部事件注入）
  - Command / Skill 类型由各自的处理逻辑推进（或手动）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ── 路径常量 ──────────────────────────────────────────────────────
_PROJECT_DIR = Path(__file__).resolve().parents[1]  # .claude/
_CLAUDE_DIR = _PROJECT_DIR
_CHATLABS_DIR = _PROJECT_DIR.parent / ".chatlabs"
_STATE_DIR = _CHATLABS_DIR / "state"
_CURRENT_TASK_FILE = _STATE_DIR / "current_task"

# flow-engine 脚本
_FLOW_ADVANCE = _CLAUDE_DIR / "skills" / "flow-engine" / "scripts" / "flow_advance.py"

# 共享路径与工具
sys.path.insert(0, str(_PROJECT_DIR / "scripts"))
from paths import STORE_DIR  # noqa: E402

sys.path.insert(0, str(_PROJECT_DIR / "skills" / "flow-engine" / "scripts"))
from task_store import TaskJsonStore  # noqa: E402


# ── 辅助函数 ──────────────────────────────────────────────────────

def get_current_task_id() -> Optional[str]:
    """获取当前活跃的 task_id。"""
    try:
        return _CURRENT_TASK_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def get_story_id_from_task_id(task_id: str) -> Optional[str]:
    """从 task_id 反查 story_id（通过 task.json）。"""
    # task_id 格式: TASK-05-17-sf-token-retry-01
    # story_id 在 task.json.story_id 字段
    for task_dir in STORE_DIR.iterdir():
        if not task_dir.is_dir():
            continue
        task_json = task_dir / "task.json"
        if not task_json.exists():
            continue
        try:
            data = json.loads(task_json.read_text())
            if data.get("task_id") == task_id:
                return data.get("story_id")
        except Exception:
            pass
    return None


def get_agent_target_from_tool_input(tool_input: dict) -> Optional[str]:
    """从 Agent tool 的输入中解析 target agent 类型。"""
    # Agent tool 的输入通常有 subagent_type 字段
    # 或者从 tool_name 后缀推断（如 "Agent:generator"）
    if tool_input is None:
        return None
    return tool_input.get("subagent_type")


def advance_flow(
    story_id: str,
    step_id: str,
    result: str = "ok",
) -> tuple[bool, dict]:
    """调用 flow_advance.py complete 推进 flow。"""
    cmd = [
        sys.executable,
        str(_FLOW_ADVANCE),
        "--story-id", story_id,
        "complete", step_id,
        "--result", result,
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if proc.returncode != 0:
            return False, {"error": proc.stderr or proc.stdout}
        out = json.loads(proc.stdout)
        return out.get("ok", False), out
    except Exception as e:
        return False, {"error": str(e)}


# ── 主逻辑 ────────────────────────────────────────────────────────

def main():
    # 读取 hook 输入（stdin JSON）
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        # 不是合法 JSON，静默退出
        return 0

    # 1. 检查是否是 Agent 工具调用
    tool_name = hook_input.get("tool_name", "")
    if not tool_name.startswith("Agent"):
        return 0

    # 2. 检查是否成功
    if hook_input.get("isError"):
        return 0

    # 3. 获取当前 task
    task_id = get_current_task_id()
    if not task_id:
        return 0

    story_id = get_story_id_from_task_id(task_id)
    if not story_id:
        return 0

    # 4. 加载 task.json 获取当前 flow step
    try:
        store = TaskJsonStore.load_by_story(story_id)
        wf = store.get_workflow() or {}
        flow = wf.get("flow") or {}
        steps = flow.get("steps") or []
        idx = flow.get("current_step_idx", 0)
        if idx >= len(steps):
            return 0
        current_step = steps[idx]
    except Exception:
        return 0

    # 5. 检查当前 step 类型是否为 agent
    if current_step.get("kind") != "agent":
        return 0

    # 6. 检查 agent target 是否匹配
    step_target = current_step.get("target")
    agent_target = get_agent_target_from_tool_input(hook_input.get("tool_input"))

    # 放宽匹配：如果 tool_input 没有 subagent_type，或者匹配都算
    # (因为有些 Agent 调用可能不通过 subagent_type 参数指定)
    should_advance = False
    if agent_target and step_target == agent_target:
        should_advance = True
    elif not agent_target:
        # 没有明确的 agent target，假设是当前 step 的 agent
        # (避免误判，只在 tool_name 明确包含时匹配)
        # 例如: "Agent:generator" -> generator
        if ":" in tool_name:
            actual_agent = tool_name.split(":")[1]
            if actual_agent == step_target:
                should_advance = True

    if not should_advance:
        return 0

    # 7. 自动推进 flow
    step_id = current_step.get("id")
    ok, result = advance_flow(story_id, step_id, "ok")

    # 输出结果给 Claude 看
    output = {
        "auto_advanced": ok,
        "from_step": step_id,
        "result": result,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
