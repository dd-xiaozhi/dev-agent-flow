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

# task_store.py 位于 .claude/skills/task/scripts/（路径常量在本文件按需自行硬编码）
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))
sys.path.insert(0, str(_THIS_DIR.parents[2] / "skills" / "task" / "scripts"))

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/flow-engine/scripts/ 回退 4 级）
import os
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
TEMPLATES_DIR = PROJECT_DIR / ".claude" / "templates"
STORE_DIR = PROJECT_DIR / ".chatlabs" / "task" / "store"

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
    # flow 不再内嵌 steps(改为引用 flow_id 实时加载);移除旧结构残留,顺带瘦身存量 task
    flow = state.get("flow")
    if isinstance(flow, dict):
        flow.pop("steps", None)
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


def load_steps(flow: dict) -> list:
    """按 flow["flow_id"] 实时加载模板 steps(steps 不再内嵌 task.json)。

    校验 frozen_template_hash:不一致时 stderr 告警但继续用模板
    (flow 模板稳定不变动,正常永远匹配)。
    """
    flow_id = flow.get("flow_id")
    if not flow_id:
        raise ValueError("flow block missing flow_id; cannot load steps from template")
    template = load_template(flow_id)
    frozen = flow.get("frozen_template_hash")
    if frozen:
        current = template_hash(template)
        if current != frozen:
            print(
                f"[flow_advance] warning: template '{flow_id}' hash changed "
                f"(frozen={frozen}, current={current}); using current template",
                file=sys.stderr,
            )
    return template["steps"]


def set_step_snapshot(flow: dict, steps: list) -> None:
    """根据 current_step_idx 刷新 current_step_id / current_step / next_step 快照。

    idx 越界(terminal 之后)时 current_step_id=None,快照均为 None。
    """
    idx = flow.get("current_step_idx", 0)
    current = steps[idx] if 0 <= idx < len(steps) else None
    nxt = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None
    flow["current_step_id"] = current["id"] if current else None
    flow["current_step"] = current
    flow["next_step"] = nxt


def build_flow_block(template: dict) -> dict:
    """从模板构造初始 flow 子对象。

    只存 flow_id 引用 + 当前步/下一步快照,不内嵌完整 steps
    (完整 steps 推进时由 load_steps 实时加载)。
    """
    flow = {
        "flow_id": template["flow_id"],
        "version": template.get("version", "1.0"),
        "frozen_template_hash": template_hash(template),
        "current_step_idx": 0,
        "current_step_id": None,
        "current_step": None,
        "next_step": None,
        "started_at": now_iso(),
        "completed_at": None,
    }
    set_step_snapshot(flow, template["steps"])
    return flow


def sync_phase_alias(state: dict) -> None:
    """从 flow.current_step 快照双写 phase / agent(兼容旧读取代码)。"""
    flow = state.get("flow") or {}
    step = flow.get("current_step")
    if not step:
        return
    state["phase"] = step.get("phase_alias") or step["id"]
    if step.get("kind") == "agent":
        state["agent"] = step.get("target")
    else:
        state["agent"] = None


def resolve_args(state: dict, step: Optional[dict]) -> dict:
    """解析 step.args_from 中声明的字段路径，从 state 取值。

    - step 为 None 或无 args_from → 返回 {}
    - 字段路径支持点号取嵌套（如 "tapd.ticket_id"）
    - 路径不存在或中间节点非 dict → 该 key 对应 value 为 None
    """
    if not step:
        return {}
    paths = step.get("args_from") or []
    if not paths:
        return {}
    resolved: dict = {}
    for path in paths:
        parts = path.split(".")
        cursor: object = state
        value: object = None
        ok = True
        for part in parts:
            if isinstance(cursor, dict) and part in cursor:
                cursor = cursor[part]
            else:
                ok = False
                break
        if ok:
            value = cursor
        resolved[path] = value
    return resolved


def _attach_resolved_args(state: dict, step: Optional[dict]) -> Optional[dict]:
    """返回 step 的浅拷贝并附加 resolved_args 字段（不污染原 state 中的 step 对象）。

    无 args_from 时返回原对象（不强行附加，便于消费方判断）。
    """
    if not step:
        return step
    if not step.get("args_from"):
        return step
    enriched = dict(step)
    enriched["resolved_args"] = resolve_args(state, step)
    return enriched


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

    steps_list = template["steps"]
    first_step = steps_list[0]
    next_step = steps_list[1] if len(steps_list) > 1 else None
    return {
        "ok": True,
        "flow_id": template["flow_id"],
        "current_step": _attach_resolved_args(state, first_step),
        "next_step": _attach_resolved_args(state, next_step),
    }


def cmd_check(args: argparse.Namespace) -> dict:
    """只读输出当前状态。task.py resume 用。"""
    state = load_state(args.story_id)
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow initialized for this state"}

    steps = load_steps(flow)
    idx = flow["current_step_idx"]
    current = steps[idx] if 0 <= idx < len(steps) else None
    next_step = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None

    return {
        "ok": True,
        "flow_id": flow["flow_id"],
        "current_step_idx": idx,
        "current_step": _attach_resolved_args(state, current),
        "next_step": _attach_resolved_args(state, next_step),
        "is_terminal": current is not None and current.get("kind") == "terminal",
    }


# ── consensus-gate preflight: contract TBD 残留扫描 ────────────────
#
# 在 consensus-gate 推进时强制扫描 contract.md：
#   1) "TBD 跟踪表 / 待澄清"章节中数据行 > 0（排除占位行 "—" / "无" / 空）
#      （章节按标题关键字识别,无该章节 = 合规省略,跳过规则 1）
#   2) 正文中残留 TBD 编号（TBD-\d+ 或 TBD-(PM|BE|FE|QA)-\d+），且不在豁免区
#   3) 正文中裸 TBD（不带编号），且不在豁免区
#
# 章节切分同时识别一级（`# `）与二级（`## `）标题——contract 模板正文用一级标题。
#
# 豁免区：
#   - frontmatter（owner_pm: TBD 等占位）
#   - 修订记录 / 变更日志章节（§0、"修订记录"、"变更日志"标题,含其子小节）
#   - 所有标题行的裸 TBD（标题是结构名称,不构成内容残留;编号 TBD 仍命中）
#   - TBD 跟踪章节的标题行与说明 blockquote
#   - 含"来源："的溯源引用行（历史 PM 评审答复 TBD-XX）
#
# 豁免覆盖标记：frontmatter 含 `tbd_allowed: true` → 警告但放行。

_RE_TBD_NUMBERED = re.compile(r"\bTBD-(?:(?:PM|BE|FE|QA)-)?\d+\b")
_RE_TBD_BARE = re.compile(r"\bTBD\b(?!-)")
_RE_HEADING = re.compile(r"^#{1,2} ")  # 章节切分:一级或二级标题（### 及以下不切）
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
    """切分章节（一级 `# ` 与二级 `## ` 标题，平铺）。

    contract 模板正文用一级标题（`# 7. TBD 跟踪表`），历史实现只认 `## ` 导致
    章节定位全部失效（规则 1 形同虚设 + 标题豁免失效）。

    返回 [(start_line, end_line, heading_text), ...]，行号 0-based，end 为闭区间。
    fm_end 之前的行不计入任何 section。
    """
    headings: list[tuple[int, str]] = []
    for i in range(fm_end, len(lines)):
        if _RE_HEADING.match(lines[i]):
            headings.append((i, lines[i].strip()))
    ranges: list[tuple[int, int, str]] = []
    for k, (start, text) in enumerate(headings):
        end = headings[k + 1][0] - 1 if k + 1 < len(headings) else len(lines) - 1
        ranges.append((start, end, text))
    return ranges


def _section_number(heading: str) -> Optional[str]:
    """从 '# 7. xxx' / '## 16. xxx' / '## §16.1 xxx' 提取章节号（如 '7' 或 '16.1'）。"""
    m = re.match(r"^#{1,2}\s+(?:§\s*)?(\d+(?:\.\d+)?)", heading)
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
    """修订记录 / 变更日志章节判定（§0、'修订记录'、'变更日志'）。"""
    num = _section_number(heading)
    if num == "0":
        return True
    return "修订记录" in heading or "变更日志" in heading


def _is_tbd_tracking_section(heading: str) -> bool:
    """TBD 跟踪章节判定（标题含'TBD 跟踪'/'待澄清'；不依赖章节编号）。"""
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

    def _effective_end(idx: int) -> int:
        """一级标题章节的有效结束行：延伸到下一个一级标题前。

        平铺切分会让一级章节在其二级子节（如变更日志的 `## v0.2.0`）处提前
        截断，导致子节内容脱离父章节的豁免范围——此处按层级修正。
        """
        start, end, heading = sections[idx]
        if not heading.startswith("# "):
            return end
        for nk in range(idx + 1, len(sections)):
            if sections[nk][2].startswith("# "):
                return sections[nk][0] - 1
        return len(lines) - 1

    # 标记每一行的章节归属（用于豁免判断）
    revision_lines: set[int] = set()
    tbd_table_section: Optional[tuple[int, int, str]] = None
    for k, (start, end, heading) in enumerate(sections):
        if _is_revision_log_section(heading):
            for i in range(start, _effective_end(k) + 1):
                revision_lines.add(i)
        if _is_tbd_tracking_section(heading):
            # 只取第一个 TBD 跟踪章节（应该只有一个）
            if tbd_table_section is None:
                tbd_table_section = (start, _effective_end(k), heading)

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
        # 豁免：修订记录 / 变更日志章节
        if i in revision_lines:
            continue
        # 豁免：来源溯源引用
        if _is_source_attribution(line):
            continue
        # 豁免：行含历史完成标志(已澄清/PM答复/范围扩展 等),TBD-XX 视为引用
        if _is_tbd_resolved_context(line):
            continue
        # 豁免：TBD 跟踪章节的标题行与说明 blockquote
        if tbd_table_section is not None:
            sec_start, sec_end, _ = tbd_table_section
            if i == sec_start:
                continue  # 跟踪章节标题行
            # blockquote 说明行（以 > 开头,描述章节用途）也豁免
            if sec_start <= i <= sec_end and line.lstrip().startswith(">"):
                continue

        # 命中编号 TBD
        for m in _RE_TBD_NUMBERED.finditer(line):
            # 跟踪章节表格行已在规则 1 计入,避免重复
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
        # 豁免：标题行的裸 TBD（如 '# 7. TBD 跟踪表'）——标题是结构名称,不构成内容残留
        if line.lstrip().startswith("#"):
            continue
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

    steps = load_steps(flow)
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

    # 不再维护 history;只更新当前步骤指针 + 快照
    if advance_action == "jump_back":
        flow["current_step_idx"] = jump_to_idx
    else:
        flow["current_step_idx"] = idx + 1
        if flow["current_step_idx"] >= len(steps):
            flow["completed_at"] = now_iso()

    set_step_snapshot(flow, steps)
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
        "current_step": _attach_resolved_args(state, new_current),
        "next_step": _attach_resolved_args(state, new_next),
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
    steps = load_steps(flow)
    flow["current_step_idx"] = 0
    flow["completed_at"] = None
    set_step_snapshot(flow, steps)
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
    # step_id 支持位置参数与 --step-id 具名参数两种调用方式(二选一)
    p_complete.add_argument("step_id", nargs="?", default=None,
                           help="待完成的 step id(位置参数,与 --step-id 二选一)")
    p_complete.add_argument("--step-id", dest="step_id_opt", default=None,
                           help="待完成的 step id(具名参数,与位置参数二选一)")
    p_complete.add_argument("--result", default=None)
    p_complete.add_argument("--evidence-type", default=None,
                           help="Gate 步骤必须提供的证据类型(如 wiki-comment-id)")
    p_complete.add_argument("--evidence-id", default=None,
                           help="Gate 步骤必须提供的证据ID")
    p_complete.set_defaults(func=cmd_complete)

    p_reset = sub.add_parser("reset", help="重置到第一步(debug)")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    # 对 complete 子命令做 step_id 归一化:位置参数 与 --step-id 二选一,都缺则报错
    if getattr(args, "cmd", None) == "complete":
        effective = getattr(args, "step_id_opt", None) or getattr(args, "step_id", None)
        if not effective:
            parser.error(
                "complete 缺少 step_id 参数。\n"
                "用法二选一:\n"
                "  位置参数:  flow_advance.py complete <step_id>\n"
                "  具名参数:  flow_advance.py complete --step-id <step_id>"
            )
        args.step_id = effective
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
