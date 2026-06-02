"""
task.py — 任务记录管理 CLI

子命令:
  new <story_id> --name <description>
        创建任务记录、分配 task_id、写 _index.jsonl + .current_task
        • task_id / story_id 命名由调用方按 docs/git-brance-spec.md 传入: <MM-dd>-<description>
          - branch 才用 <ticket-short>-<description>（不同维度;task.py 只校验字符集+长度,不强制具体格式）
          - 同名冲突时自动追加 UTC timestamp 后缀兜底
        • --name 强制必填,description 只允许 [a-z0-9-],长度 3-40
        • story_id 由调用方传入,是 .chatlabs/task/store/<story_id>/ 的目录名
          (语义独立于 task_id,允许多人多次在同一 story 下新建 task)
        • 任务元数据全部写入 .chatlabs/task/store/<story_id>/task.json (SSOT)
          (历史上的 reports/tasks/<task_id>/meta.json 已废除)

  resume <task_id>
        读 task.json + flow 状态、写 .current_task、输出注入材料
        task_id 即 cmd_new 生成的标识（同名冲突时含时间戳后缀）

  bind-branch <task_id> --branch <name> [--branch-type ...] [--source-branch ...] [--merge-targets ...]
        把 git 分支绑定到任务的 task.json.git section(经 TaskJsonStore.update_git)
        source-branch / merge-targets 未传时,若提供 --branch-type 则自动从
        .chatlabs/project-config.json.git.branches.<type> 读取(配置驱动)。
        显式参数始终最高优先级。

  list [--story-id <id>]
        列 _index.jsonl

输出: stdout 单一 JSON 对象(ok/error/data/todo_hint),exit code=0 表示 ok=true
依赖: 仅 Python 标准库 + 同目录 task_store.py / task_index.py(路径常量在本文件顶部硬编码)
"""
import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/task/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
STATE_DIR = PROJECT_DIR / ".chatlabs" / "state"
CURRENT_TASK = STATE_DIR / "current_task"
STORE_DIR = PROJECT_DIR / ".chatlabs" / "task" / "store"
BUG_FIX_DIR = PROJECT_DIR / ".chatlabs" / "task" / "bug-fix"
TASK_REPORTS = PROJECT_DIR / ".chatlabs" / "reports" / "tasks"
TASK_INDEX = TASK_REPORTS / "_index.jsonl"

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 同目录 task_store / task_index
from task_store import TaskJsonStore  # noqa: E402
import task_index  # noqa: E402

VALID_TRIGGERS = {"first-start", "requirement-change", "manual", "defect-fix",
                  "requirement-change-check"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fail(error: str, **extra) -> dict:
    out = {"ok": False, "error": error}
    out.update(extra)
    return out


# ─────────────────────────── _index.jsonl ────────────────────────────

def read_index() -> list[dict]:
    """读 _index.jsonl,损坏行自动跳过(并备份原文件一次)。"""
    if not TASK_INDEX.exists():
        return []
    rows: list[dict] = []
    bad_lines = 0
    for line in TASK_INDEX.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad_lines += 1
    if bad_lines and not Path(str(TASK_INDEX) + ".corrupt.bak").exists():
        shutil.copy(TASK_INDEX, str(TASK_INDEX) + ".corrupt.bak")
    return rows


def append_index(entry: dict) -> None:
    TASK_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with TASK_INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# description slug 校验：只允许 a-z 0-9 -，长度 3-40
_DESCRIPTION_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DESCRIPTION_MIN = 3
# 上限 50:兼容 TAPD 工单场景 ticket_short(7) + `-` + description(<=40) = 48 < 50
_DESCRIPTION_MAX = 50


def validate_description(name: str) -> tuple[bool, str]:
    """校验 --name 取值是否符合 description slug 规范。

    Returns:
        (ok, error_message)。ok=True 时 error_message 为空。
    """
    if not name:
        return False, "description is empty"
    if not _DESCRIPTION_RE.match(name):
        return False, (
            f"description '{name}' invalid: only lowercase letters/digits/hyphen allowed, "
            "no leading/trailing hyphen, no consecutive hyphens"
        )
    if len(name) < _DESCRIPTION_MIN or len(name) > _DESCRIPTION_MAX:
        return False, (
            f"description length must be between {_DESCRIPTION_MIN} and {_DESCRIPTION_MAX}, "
            f"got {len(name)}"
        )
    return True, ""


# ─────────────────────────── new ────────────────────────────

def cmd_new(args: argparse.Namespace) -> dict:
    story_id = args.story_id
    if not story_id:
        return fail(
            "story_id required",
            usage="python task.py new <story_id> --name <description> [--predecessor X] [--trigger Y]",
        )

    # --name 强制必填
    name = getattr(args, "name", None)
    if not name:
        return fail(
            "--name <description> is required",
            usage="python task.py new <story_id> --name <description>",
            example="python task.py new sf-account-merge --name sf-account-merge",
            description_rules="lowercase letters/digits/hyphen only, length 3-40, no leading/trailing/consecutive hyphens",
        )

    ok, err = validate_description(name)
    if not ok:
        return fail(
            err,
            description_rules="lowercase letters/digits/hyphen only, length 3-40, no leading/trailing/consecutive hyphens",
            given_name=name,
        )

    # 校验 trigger 取值
    trigger = args.trigger
    if trigger and trigger not in VALID_TRIGGERS:
        return fail(
            f"invalid trigger '{trigger}'",
            valid_triggers=sorted(VALID_TRIGGERS),
        )

    # 分配 task_id —— 直接用 --name 传入的 description
    # 格式: <description>(本地) 或 <ticket-short>-<description>(TAPD,调用方拼接好)
    # 不再生成 MM-dd 日期前缀
    task_id = name

    # 任务报告目录(仍保留,用来存放 blockers.md 等执行期产物)
    task_dir = TASK_REPORTS / task_id
    if task_dir.exists():
        # 目录已存在(并发或残留),追加 UTC timestamp 后缀避让
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        task_id = f"{task_id}-{ts}"
        task_dir = TASK_REPORTS / task_id
    task_dir.mkdir(parents=True, exist_ok=False)

    # Story 目录幂等创建（task.json 落在此处）
    story_dir = STORE_DIR / story_id
    story_dir.mkdir(parents=True, exist_ok=True)

    # 通过 TaskJsonStore 写 task.json（顶层元数据 SSOT）
    timestamp = now_iso()
    store = TaskJsonStore.load(story_dir)
    store.set_field("task_id", task_id)
    # task_type 默认 "store"（业务需求）；bug-fix 路径由 bug-fix command 后续 set
    if not store.data.get("task_type"):
        store.set_field("task_type", "store")
    store.set_field("story_id", story_id)
    if not store.data.get("created_at"):
        store.set_field("created_at", timestamp)
    store.set_field("updated_at", timestamp)
    if args.predecessor:
        store.set_field("predecessor_task_id", args.predecessor)
    if trigger:
        store.set_field("trigger", trigger)
    store.save()

    # blockers.md 不预创建,首次写入时 hook 自行 mkdir

    # 注册 _index.jsonl
    append_index({
        "task_id": task_id,
        "story_id": story_id,
        "phase": "created",
        "keywords": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "blocker_count": 0,
        "verdict": None,
        "tags": [],
    })

    # 写 .current_task
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_TASK.write_text(task_id, encoding="utf-8")

    # 输出
    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "task_dir": str(task_dir.relative_to(PROJECT_DIR)),
        "story_dir": str(story_dir.relative_to(PROJECT_DIR)),
        "task_json": str(store.path.relative_to(PROJECT_DIR)),
        "predecessor_task_id": args.predecessor,
        "trigger_reason": trigger,
        # 调用方据此创建平台原生 todo(可选)
        "todo_hint": {
            "subject": f"[{story_id}] 任务已创建,等待上游路由",
            "description": (
                f"任务记录已分配。Story: {story_id}。"
                f"后续由上游流程入口命令决定 phase 与 agent 路由。"
            ),
        },
    }


# ─────────────────────────── resume ────────────────────────────

def _load_flow_state(story_id: str) -> dict:
    """读 per-story task.json 的 workflow section（任务级 SSOT）。

    task.json 顶层的 task_id/story_id 也会平铺到返回 dict,保持扁平结构,
    便于下游 _flow_check 直接消费。task.json 缺失或解析失败时返回 {}。
    """
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


def _flow_check(state: dict) -> dict:
    """从 state 提取 flow.current_step / next_step / is_terminal(读 task.json 快照)。"""
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow initialized"}
    current = flow.get("current_step")
    next_step = flow.get("next_step")
    return {
        "ok": True,
        "flow_id": flow.get("flow_id"),
        "current_step_idx": flow.get("current_step_idx", 0),
        "current_step": current,
        "next_step": next_step,
        "is_terminal": bool(current and current.get("kind") == "terminal"),
    }


def _related_completed_tasks(story_id: str, current_task_id: str) -> list[dict]:
    related = []
    for row in read_index():
        if row.get("story_id") != story_id:
            continue
        if row.get("task_id") == current_task_id:
            continue
        if row.get("verdict") == "PASS":
            related.append({
                "task_id": row.get("task_id"),
                "verdict": row.get("verdict"),
                "updated_at": row.get("updated_at"),
            })
    return related


# task_id 命名格式(2026-05-29 起):
#   - 本地任务: <description>             例:ec-user-exists-api
#   - TAPD 工单: <ticket-short>-<description>  例:000123-add-payment
#   - 同名冲突兜底: 上述 + -<YYYYMMDD-HHMMSS>
# 正则与 _DESCRIPTION_RE 一致(均接受 lowercase + 数字 + 中间 hyphen),向后兼容历史 MM-dd 前缀
_TASK_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def cmd_resume(args: argparse.Namespace) -> dict:
    task_id = args.task_id
    # 接受新旧两种格式:
    #   新: <description> 或 <ticket-short>-<description>
    #   旧(已废弃但向后兼容): {MM}-{dd}-{description}(05-29 之前的历史 task)
    # 同名冲突时 task.py new 会追加 -{YYYYMMDD-HHMMSS} 时间戳兜底,正则仍可匹配。
    if not task_id or not _TASK_ID_RE.match(task_id):
        return fail(
            "invalid task_id",
            usage="python task.py resume <task_id>",
            expected_format="<description> 或 <ticket-short>-<description>",
            examples=["ec-user-exists-api", "000123-add-payment"],
        )

    # 通过 _index.jsonl 反查 story_id（task_id 不一定等于 story_id：同日重名时会加时间戳后缀）
    story_id: Optional[str] = None
    for row in read_index():
        if row.get("task_id") == task_id:
            story_id = row.get("story_id")
            break
    if not story_id:
        # 兜底：尝试 task_id 本身作为 story_id（新约定下两者一致的常见场景）
        store_probe = TaskJsonStore.load_by_story(task_id)
        if store_probe.data.get("task_id") == task_id:
            story_id = task_id

    if not story_id:
        return fail("task not found", task_id=task_id)

    store = TaskJsonStore.load_by_story(story_id)
    if not store.data.get("task_id"):
        return fail(
            "task.json not found",
            task_id=task_id,
            story_id=story_id,
            task_json=str((STORE_DIR / story_id / "task.json").relative_to(PROJECT_DIR)),
        )

    td = store.data
    wf = td.get("workflow") or {}

    # task_dir 仍保留作 blockers.md 等执行期产物存放位置
    task_dir = TASK_REPORTS / task_id

    # 读 flow 状态
    state = _load_flow_state(story_id)
    flow_check = _flow_check(state)

    # blockers
    blockers_path = task_dir / "blockers.md"
    blocker_count = wf.get("blocker_count", 0)
    blockers_content = None
    if blockers_path.exists() and blocker_count > 0:
        blockers_content = blockers_path.read_text(encoding="utf-8")

    # 同 story 已完成 task
    related = _related_completed_tasks(story_id, task_id)

    # 更新 .current_task
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_TASK.write_text(task_id, encoding="utf-8")
    current_task_updated = True

    tapd_section = td.get("tapd") or {}

    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "meta": {
            "phase": wf.get("phase"),
            "agent": wf.get("agent"),
            "verdict": wf.get("verdict"),
            "blocker_count": blocker_count,
            "tapd_ticket_id": tapd_section.get("ticket_id"),
            "predecessor_task_id": td.get("predecessor_task_id"),
            "trigger_reason": td.get("trigger"),
            "summary": wf.get("summary", {}),
        },
        "flow": flow_check,
        "blockers": blockers_content,
        "related_completed_tasks": related,
        "current_task_updated": current_task_updated,
        "paths": {
            "task_dir": str(task_dir.relative_to(PROJECT_DIR)),
            "task_json": str(store.path.relative_to(PROJECT_DIR)),
            "blockers": (
                str(blockers_path.relative_to(PROJECT_DIR))
                if blockers_path.exists() else None
            ),
        },
        # 调用方据此更新平台原生 todo 状态(可选)
        "todo_hint": {
            "task_id": task_id,
            "status": "in_progress",
        },
    }


# ─────────────────────────── bind-branch ────────────────────────────

def cmd_bind_branch(args: argparse.Namespace) -> dict:
    """绑定 git 分支到任务的 task.json.git section。

    git skill 创建/切换分支后调用此命令把结果回写。
    支持 store 与 bug-fix 两种 task_type，按 task_id 解析对应任务目录。

    source_branch / merge_targets 解析优先级：
      1. 显式传入的 --source-branch / --merge-targets
      2. --branch-type 走 .chatlabs/project-config.json.git.branches.<type>
      3. 仍缺失 → 报错（保持显式调用方有意识）
    """
    task_id = args.task_id
    if not task_id:
        return fail("task_id required",
                    usage="task.py bind-branch <task_id> --branch <name> [--branch-type ...]")

    # 通过 _index.jsonl 找到 story_id
    story_id = None
    for row in read_index():
        if row.get("task_id") == task_id:
            story_id = row.get("story_id")
            break
    if not story_id:
        return fail("task_id not found in _index.jsonl", task_id=task_id)

    # 优先 store；不存在则尝试 bug-fix
    task_dir = STORE_DIR / story_id
    task_type = "store"
    if not (task_dir / "task.json").exists():
        alt = BUG_FIX_DIR / story_id
        if (alt / "task.json").exists():
            task_dir = alt
            task_type = "bug-fix"

    # source / targets 解析：显式 > config > 报错
    source_branch = args.source_branch
    merge_targets: Optional[list[str]] = (
        [t.strip() for t in args.merge_targets.split(",") if t.strip()]
        if args.merge_targets else None
    )
    config_resolution: Optional[str] = None
    if args.branch_type and (source_branch is None or merge_targets is None):
        # 延迟导入 git_config，避免无 --branch-type 时也强制依赖
        git_scripts_dir = Path(__file__).resolve().parents[2] / "git" / "scripts"
        sys.path.insert(0, str(git_scripts_dir))
        try:
            from git_config import load_branch_config  # type: ignore
        except ImportError as exc:
            return fail(f"git_config import failed: {exc}")

        cfg = load_branch_config(args.branch_type)
        if not cfg.get("ok"):
            return fail(
                cfg.get("error", "git config unresolved"),
                branch_type=args.branch_type,
                candidates=cfg.get("candidates"),
            )
        if source_branch is None:
            source_branch = cfg["source"]
            config_resolution = cfg["source_resolution"]
        if merge_targets is None:
            merge_targets = list(cfg.get("merge_targets") or [])

    store = TaskJsonStore.load(task_dir)
    if not store.data.get("task_id"):
        # 兜底：task.json 缺失时基于参数初始化骨架
        store._data.update({
            "task_id": task_id,
            "task_type": task_type,
            "story_id": story_id,
        })

    git_patch = {
        "branch": args.branch,
        "branch_type": args.branch_type,
        "worktree_path": args.worktree_path,
        "source_branch": source_branch,
        "merge_targets": merge_targets,
        "source_resolution": config_resolution,
    }
    # 删 None 值，避免覆盖
    git_patch = {k: v for k, v in git_patch.items() if v is not None}
    store.update_git(git_patch)
    store.save()

    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "task_type": task_type,
        "git": store.get_git(),
        "task_json": str(store.path.relative_to(PROJECT_DIR)),
    }


# ─────────────────────────── list ────────────────────────────

def cmd_list(args: argparse.Namespace) -> dict:
    rows = read_index()
    if args.story_id:
        rows = [r for r in rows if r.get("story_id") == args.story_id]
    return {
        "ok": True,
        "count": len(rows),
        "tasks": rows,
    }


# ─────────────────────────── finalize ────────────────────────────

def _resolve_task_dirs(task_id: str, story_id: str) -> tuple[Path, str]:
    """按 task_type 优先级定位任务目录,返回 (task_dir, task_type)。"""
    store_dir = STORE_DIR / story_id
    if (store_dir / "task.json").exists():
        return store_dir, "store"
    bug_dir = BUG_FIX_DIR / story_id
    if (bug_dir / "task.json").exists():
        return bug_dir, "bug-fix"
    # 都不存在,默认 store(便于 finalize 后续兜底)
    return store_dir, "store"


def _build_finalize_entry(task_id: str, story_id: str) -> dict:
    """从 task.json + patch/contract/spec + git log 装配 entry。"""
    timestamp = now_iso()
    task_dir, task_type_inferred = _resolve_task_dirs(task_id, story_id)

    store = TaskJsonStore.load(task_dir)
    td = store.data
    wf = td.get("workflow") or {}
    summary = wf.get("summary") or {}
    flow = wf.get("flow") or {}

    flow_id = flow.get("flow_id")
    complexity = task_index.infer_complexity_from_flow_id(flow_id)

    acceptance = summary.get("acceptance") or ""
    one_liner = acceptance.split("\n", 1)[0].split("。", 1)[0].strip() or None

    parsed = task_index.parse_contract_for_meta(task_dir)
    commit_hashes = task_index.git_log_for_task(task_id)

    entry = {
        "task_id": task_id,
        "story_id": story_id,
        "task_type": td.get("task_type") or task_type_inferred,
        "phase": wf.get("phase") or "done",
        "complexity": complexity,
        "flow_id": flow_id,
        "title": parsed.get("title"),
        "one_liner": one_liner,
        "modules": summary.get("touched_modules") or [],
        "contracts": parsed.get("contracts") or [],
        "tags": td.get("tags") or [],
        "keywords": td.get("keywords") or [],
        "key_decisions": summary.get("key_decisions") or [],
        "commit_hashes": commit_hashes,
        "blocker_count": wf.get("blocker_count", 0),
        "verdict": wf.get("verdict"),
        "created_at": td.get("created_at") or timestamp,
        "updated_at": timestamp,
        "completed_at": summary.get("completed_at") or timestamp,
    }
    return entry


def cmd_finalize(args: argparse.Namespace) -> dict:
    """任务完成时回填 _index.jsonl 对应 entry,字段聚合自 task.json + 周边文件。"""
    task_id = args.task_id
    if not task_id or not _TASK_ID_RE.match(task_id):
        return fail(
            "invalid task_id",
            usage="python task.py finalize <task_id>",
            expected_format="<description> 或 <ticket-short>-<description>",
        )

    # _index.jsonl 反查 story_id
    story_id: Optional[str] = None
    for row in read_index():
        if row.get("task_id") == task_id:
            story_id = row.get("story_id")
            break
    if not story_id:
        # 兜底:假设 task_id == story_id(常见场景)
        story_id = task_id

    entry = _build_finalize_entry(task_id, story_id)
    action = task_index.upsert_index_entry(task_id, entry, path=TASK_INDEX)

    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "action": action,  # "updated" | "appended"
        "entry": entry,
    }


# ─────────────────────────── search ────────────────────────────

def cmd_search(args: argparse.Namespace) -> dict:
    """检索 _index.jsonl(可含归档)。多条件 AND,无条件即返回最近 N 条。"""
    rows = read_index()
    if args.include_archive:
        rows.extend(task_index.read_index(task_index.ARCHIVE_INDEX))

    matched = task_index.search_entries(
        rows,
        module=args.module,
        contract=args.contract,
        keyword=args.keyword,
        verdict=args.verdict,
        task_type=args.task_type,
        complexity=args.complexity,
        limit=args.limit,
    )
    return {
        "ok": True,
        "count": len(matched),
        "total_scanned": len(rows),
        "include_archive": bool(args.include_archive),
        "tasks": matched,
    }


# ─────────────────────────── main ────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Task record CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="创建任务记录")
    p_new.add_argument("story_id")
    p_new.add_argument("--name", default=None, required=False,
                       help="(强制必填) 任务描述 slug 或 <ticket-short>-<slug>,"
                            "只允许 a-z 0-9 -,长度 3-50;task_id 直接取此值")
    p_new.add_argument("--predecessor", default=None,
                       help="前驱 task_id(用于追溯链)")
    p_new.add_argument("--trigger", default=None,
                       help=f"触发原因({'/'.join(sorted(VALID_TRIGGERS))})")
    p_new.set_defaults(func=cmd_new)

    p_resume = sub.add_parser("resume", help="续接已存在的任务")
    p_resume.add_argument("task_id")
    p_resume.set_defaults(func=cmd_resume)

    p_bind = sub.add_parser("bind-branch", help="把 git 分支绑定到 task.json.git")
    p_bind.add_argument("task_id")
    p_bind.add_argument("--branch", required=True, help="分支全名（含前缀，如 feature/12345-x）")
    p_bind.add_argument("--branch-type", default=None,
                        choices=["feature", "bugfix", "hotfix", "release", None],
                        help="分支前缀类型，从 branch 推断时可省")
    p_bind.add_argument("--source-branch", default=None,
                        help="分支创建时的 source（master/develop/feature 等）")
    p_bind.add_argument("--worktree-path", default=None,
                        help="若用 git worktree 隔离，填写 worktree 路径")
    p_bind.add_argument("--merge-targets", default=None,
                        help="逗号分隔的合并目标，如 'dev,uat'")
    p_bind.set_defaults(func=cmd_bind_branch)

    p_list = sub.add_parser("list", help="列任务索引")
    p_list.add_argument("--story-id", default=None)
    p_list.set_defaults(func=cmd_list)

    p_finalize = sub.add_parser(
        "finalize",
        help="任务完成时回填 _index.jsonl(由 flow finalize step 触发)"
    )
    p_finalize.add_argument("task_id")
    p_finalize.set_defaults(func=cmd_finalize)

    p_search = sub.add_parser(
        "search",
        help="检索任务索引(module/contract/keyword/verdict 多条件 AND)"
    )
    p_search.add_argument("--module", default=None,
                          help="模块名精确匹配(modules 数组 contains)")
    p_search.add_argument("--contract", default=None,
                          help="接口端点子串匹配(contracts 数组 contains substring)")
    p_search.add_argument("--keyword", default=None,
                          help="全文模糊匹配(title/one_liner/tags/keywords/key_decisions/modules/contracts)")
    p_search.add_argument("--verdict", default=None,
                          choices=["PASS", "FAIL", "ERROR", None],
                          help="按验收结论过滤")
    p_search.add_argument("--task-type", default=None,
                          choices=["store", "bug-fix", None],
                          help="按 task_type 过滤")
    p_search.add_argument("--complexity", default=None,
                          choices=["vibe", "plan", "spec", None],
                          help="按复杂度档位过滤")
    p_search.add_argument("--include-archive", action="store_true",
                          help="同时检索归档索引")
    p_search.add_argument("--limit", type=int, default=10,
                          help="返回数量上限(默认 10,0=不限)")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
