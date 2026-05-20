"""
flow_advance.py — 流程编排推进器

读 task.json.workflow.flow + 模板 JSON,推进 current_step_idx,
双写 phase/agent,输出下一步。**只保留当前步骤,不维护 history**。

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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 共享基础设施位于 .claude/scripts/，本脚本位于 .claude/skills/flow-engine/scripts/
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parents[2] / "scripts"))

from paths import TEMPLATES_DIR, STORE_DIR  # noqa: E402
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


def load_state(story_id: Optional[str]) -> dict:
    """读取 state dict（保持旧 dict 形态：task_id/story_id 顶层 + 其余平铺）。

    state 单一来源：`<task_dir>/task.json`。story_id 缺失时返回空 dict（不再有全局 fallback）。
    """
    if not story_id:
        return {}
    store = TaskJsonStore.load_by_story(story_id)
    wf = store.get_workflow() or {}
    merged: dict = {
        k: v for k, v in store.data.items()
        if k in _TASK_JSON_TOP_FIELDS and v is not None
    }
    merged.update(wf)
    return merged


def save_state(state: dict, story_id: Optional[str]) -> None:
    """保存 state dict 到 task.json（顶层 meta 与 workflow section 分别写）。

    story_id 必填；缺失则直接报错（不再有全局 fallback）。
    """
    if not story_id:
        raise ValueError("save_state requires story_id; global workflow-state.json fallback removed")
    state["updated_at"] = now_iso()
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


def build_flow_block(template: dict) -> dict:
    """从模板构造初始 flow 子对象。只保留当前步骤,不维护历史。"""
    steps = template["steps"]
    first = steps[0]
    return {
        "flow_id": template["flow_id"],
        "version": template.get("version", "1.0"),
        "frozen_template_hash": template_hash(template),
        "steps": steps,  # 内嵌 steps 副本(锁定版本,模板后续升级不影响 task)
        "current_step_idx": 0,
        "current_step_id": first["id"],
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
    }


# ── consensus-gate preflight: contract TBD 残留扫描 ────────────────
#
# 在 consensus-gate 推进时强制扫描 contract.md：
#   1) §16 / §16.x "TBD 跟踪表"中数据行 > 0（排除占位行 "—" / "无" / 空）
#   2) 正文中残留 TBD 编号（TBD-\d+ 或 TBD-(PM|BE|FE|QA)-\d+），且不在豁免区
#   3) 正文中裸 TBD（不带编号），不在豁免区
#
# 豁免区：
#   - frontmatter（owner_pm: TBD 等占位）
#   - §0 修订记录章节（含其子小节，到下一个二级标题为止）
#   - §16 / §16.x 标题行本身
#   - 含"来源："的溯源引用行（历史 PM 评审答复 TBD-XX）
#
# 豁免覆盖标记：frontmatter 含 `tbd_allowed: true` → 警告但放行。

_RE_TBD_NUMBERED = re.compile(r"\bTBD-(?:(?:PM|BE|FE|QA)-)?\d+\b")
_RE_TBD_BARE = re.compile(r"\bTBD\b(?!-)")
_RE_H2 = re.compile(r"^##\s+(?:§\s*)?(\d+)(?:\.\d+)?[\.\s)]")
_RE_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
_RE_PLACEHOLDER_CELL = re.compile(r"^[\s\-—–]*$|^无$")


def _parse_frontmatter(lines: list[str]) -> tuple[dict, int]:
    """解析 markdown frontmatter（首个 --- ... --- 块）。

    返回 (frontmatter_dict, end_line_idx)。end_line_idx 是 frontmatter 结束的下一行
    （从 0 开始计）。无 frontmatter 时返回 ({}, 0)。
    """
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fm: dict = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return fm, i + 1
        m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+?)\s*$", lines[i])
        if m:
            key = m.group(1)
            val = m.group(2).strip().strip('"').strip("'")
            fm[key] = val
    return fm, 0  # 没找到闭合 ---,视为无 frontmatter


def _section_ranges(lines: list[str], fm_end: int) -> list[tuple[int, int, str]]:
    """切分二级标题章节。

    返回 [(start_line, end_line, heading_text), ...]，行号 0-based，end 为闭区间。
    fm_end 之前的行不计入任何 section。
    """
    headings: list[tuple[int, str]] = []
    for i in range(fm_end, len(lines)):
        if lines[i].startswith("## "):
            headings.append((i, lines[i].strip()))
    ranges: list[tuple[int, int, str]] = []
    for k, (start, text) in enumerate(headings):
        end = headings[k + 1][0] - 1 if k + 1 < len(headings) else len(lines) - 1
        ranges.append((start, end, text))
    return ranges


def _section_number(heading: str) -> Optional[str]:
    """从 '## 16. xxx' 或 '## §16.1 xxx' 提取章节号（如 '16' 或 '16.1'）。"""
    m = re.match(r"^##\s+(?:§\s*)?(\d+(?:\.\d+)?)", heading)
    if not m:
        return None
    return m.group(1)


def _is_table_data_row(line: str) -> bool:
    """判断是否是 markdown 表格的"数据行"（非表头分隔符、非空、非占位）。"""
    s = line.strip()
    if not s.startswith("|"):
        return False
    if _RE_TABLE_SEP.match(s):
        return False
    cells = [c.strip() for c in s.strip("|").split("|")]
    if not cells:
        return False
    # 全部单元为占位（—/-/空/无）→ 占位行
    if all(_RE_PLACEHOLDER_CELL.match(c) for c in cells):
        return False
    return True


def _is_revision_log_section(heading: str) -> bool:
    """§0 修订记录章节判定。"""
    num = _section_number(heading)
    if num == "0":
        return True
    return "修订记录" in heading


def _is_tbd_tracking_section(heading: str) -> bool:
    """§16 / §16.x TBD 跟踪章节判定（编号 16 或标题含'TBD 跟踪'/'待澄清'）。"""
    num = _section_number(heading)
    if num and num.startswith("16"):
        return True
    if "TBD" in heading and ("跟踪" in heading or "tracking" in heading.lower()):
        return True
    if "待澄清" in heading:
        return True
    return False


def _is_source_attribution(line: str) -> bool:
    """是否是溯源引用行（'（来源：…）' 或 '(来源：…)' 等）。"""
    return "来源：" in line or "来源:" in line


# 表示 TBD 已被消化的历史完成标志词。若 TBD-XX 出现的行含任一标志,视为历史溯源引用,豁免。
_TBD_RESOLVED_MARKERS = (
    "已澄清", "已就绪", "已落地", "已答复", "已合并",
    "PM 答复", "PM答复", "答复 TBD", "答复登记",
    "范围扩展", "落入", "落地章节",
)


def _is_tbd_resolved_context(line: str) -> bool:
    """行中含历史完成标志 → TBD-XX 是已澄清项的引用,豁免。"""
    return any(marker in line for marker in _TBD_RESOLVED_MARKERS)


def _check_contract_tbd(story_id: str) -> dict:
    """扫描 .chatlabs/task/store/<story_id>/contract.md 检查 TBD 残留。

    返回:
        {
            "ok": bool,                       # True=放行 False=阻塞
            "tbd_count": int,
            "tbd_locations": [{"line": int, "content": str}, ...],
            "warning": str | None,            # tbd_allowed override 时设置
            "skipped": bool,                  # contract.md 不存在 → 跳过且放行
            "skipped_reason": str | None,
        }
    """
    contract_path = STORE_DIR / story_id / "contract.md"
    result: dict = {
        "ok": True,
        "tbd_count": 0,
        "tbd_locations": [],
        "warning": None,
        "skipped": False,
        "skipped_reason": None,
    }
    if not contract_path.exists():
        result["skipped"] = True
        result["skipped_reason"] = f"contract.md not found at {contract_path}"
        return result

    text = contract_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fm, fm_end = _parse_frontmatter(lines)

    # 豁免标记
    tbd_allowed = str(fm.get("tbd_allowed", "")).strip().lower() in {"true", "yes", "1"}

    sections = _section_ranges(lines, fm_end)

    # 标记每一行的章节归属（用于豁免判断）
    revision_lines: set[int] = set()
    tbd_table_section: Optional[tuple[int, int, str]] = None
    for start, end, heading in sections:
        if _is_revision_log_section(heading):
            for i in range(start, end + 1):
                revision_lines.add(i)
        if _is_tbd_tracking_section(heading):
            # 只取第一个 TBD 跟踪章节（应该只有一个）
            if tbd_table_section is None:
                tbd_table_section = (start, end, heading)

    locations: list[dict] = []

    # 规则 1: §16 TBD 跟踪表数据行
    if tbd_table_section is not None:
        sec_start, sec_end, _ = tbd_table_section
        # 跳过章节标题行（含 ## 16. xxx）和首个表头行
        # 简化：扫描章节内所有 `|` 开头的行，过滤数据行
        in_table = False
        header_seen = False
        for i in range(sec_start + 1, sec_end + 1):
            line = lines[i]
            stripped = line.strip()
            if stripped.startswith("|"):
                if not in_table:
                    in_table = True
                    header_seen = False
                if _RE_TABLE_SEP.match(stripped):
                    header_seen = True
                    continue
                if not header_seen:
                    # 表头行,跳过
                    continue
                if _is_table_data_row(stripped):
                    content = stripped[:80]
                    locations.append({
                        "line": i + 1,
                        "content": content,
                        "rule": "section-16-table-row",
                    })
            else:
                # 表结束（遇到非 | 行且非空）
                if stripped == "":
                    continue
                in_table = False
                header_seen = False

    # 规则 2 & 3: 全文 TBD 扫描（带编号 + 裸 TBD）
    for i in range(fm_end, len(lines)):
        line = lines[i]
        # 豁免：§0 修订记录
        if i in revision_lines:
            continue
        # 豁免：来源溯源引用
        if _is_source_attribution(line):
            continue
        # 豁免：行含历史完成标志(已澄清/PM答复/范围扩展 等),TBD-XX 视为引用
        if _is_tbd_resolved_context(line):
            continue
        # 豁免：§16 跟踪章节的标题行与说明 blockquote（标题已通过编号识别）
        if tbd_table_section is not None:
            sec_start, sec_end, _ = tbd_table_section
            if i == sec_start:
                continue  # §16 标题行
            # blockquote 说明行（以 > 开头,描述章节用途）也豁免
            if sec_start <= i <= sec_end and line.lstrip().startswith(">"):
                continue

        # 命中编号 TBD
        for m in _RE_TBD_NUMBERED.finditer(line):
            # §16 表格行已在规则 1 计入,避免重复
            if tbd_table_section is not None:
                sec_start, sec_end, _ = tbd_table_section
                if sec_start <= i <= sec_end and line.strip().startswith("|"):
                    continue
            content = line.strip()[:80]
            locations.append({
                "line": i + 1,
                "content": content,
                "rule": "tbd-numbered",
                "match": m.group(0),
            })
            break  # 同一行只记一次

        # 裸 TBD（不带 -）
        # 注意：编号 TBD 的正则 \bTBD\b(?!-) 已经排除掉 TBD- 形式
        bare = _RE_TBD_BARE.search(line)
        if bare:
            # 若同一行已经被编号规则命中,跳过避免重复
            already = any(
                loc.get("line") == i + 1 and loc.get("rule") == "tbd-numbered"
                for loc in locations
            )
            if already:
                continue
            content = line.strip()[:80]
            locations.append({
                "line": i + 1,
                "content": content,
                "rule": "tbd-bare",
                "match": bare.group(0),
            })

    # 去重（同 line + rule 只保留一条）
    seen: set[tuple[int, str]] = set()
    dedup: list[dict] = []
    for loc in locations:
        key = (loc["line"], loc.get("rule", ""))
        if key in seen:
            continue
        seen.add(key)
        dedup.append(loc)

    result["tbd_locations"] = dedup
    result["tbd_count"] = len(dedup)

    if result["tbd_count"] == 0:
        result["ok"] = True
    else:
        if tbd_allowed:
            result["ok"] = True
            result["warning"] = "TBD allowed by frontmatter override (tbd_allowed: true)"
        else:
            result["ok"] = False

    return result


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
        # 幂等检查:声明的 step idx < 当前 idx -> 已经 advance past,静默 ok(防重复调用)
        target_idx = next(
            (i for i, s in enumerate(steps) if s["id"] == args.step_id),
            None,
        )
        if target_idx is None:
            return {
                "ok": False,
                "error": f"step '{args.step_id}' not found in flow steps",
            }
        if target_idx < idx:
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
    preflight_warning: Optional[str] = None
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
            # Preflight：consensus-gate 推进前强制扫描 contract.md TBD 残留
            # 仅当模板声明 preflight_check == "contract_tbd_empty" 时启用
            if current.get("preflight_check") == "contract_tbd_empty":
                tbd_result = _check_contract_tbd(args.story_id)
                if not tbd_result["ok"]:
                    return {
                        "ok": False,
                        "error": "consensus-gate 阻塞：contract.md 仍有残留 TBD 未处理",
                        "tbd_locations": tbd_result["tbd_locations"],
                        "tbd_count": tbd_result["tbd_count"],
                        "hint": (
                            "请让 doc-librarian 处理所有 TBD 后再推进；"
                            "或在 contract frontmatter 中明确标注 tbd_allowed: true"
                        ),
                    }
                # 记录可能的 warn（tbd_allowed 豁免）
                preflight_warning = tbd_result.get("warning")
            else:
                preflight_warning = None

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

    # 不再维护 history;只更新当前步骤
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

    result = {
        "ok": True,
        "advanced_from": current["id"],
        "advanced_to": new_current["id"] if new_current else None,
        "action": advance_action,
        "forced": False,
        "current_step": new_current,
        "next_step": new_next,
        "is_terminal": new_current is not None and new_current.get("kind") == "terminal",
    }
    if preflight_warning:
        result["warning"] = preflight_warning
    return result


def cmd_reset(args: argparse.Namespace) -> dict:
    """重置 flow 到 idx=0。debug 用。"""
    state = load_state(args.story_id)
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow to reset"}
    flow["current_step_idx"] = 0
    flow["current_step_id"] = flow["steps"][0]["id"]
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
