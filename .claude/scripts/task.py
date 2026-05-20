"""
task.py — 任务记录管理 CLI

子命令:
  new <story_id> --name <description>
        创建任务记录、分配 task_id、写 _index.jsonl + .current_task
        • task_id 格式固定: {MM}-{dd}-{description}
        • --name 强制必填,description 只允许 [a-z0-9-],长度 3-40
        • story_id 由调用方传入,是 .chatlabs/task/store/<story_id>/ 的目录名
          (语义独立于 task_id,允许多人多次在同一 story 下新建 task)

  resume <task_id>
        读 meta + flow 状态、写 .current_task、输出注入材料
        兼容历史 TASK- 前缀格式与新 {MM}-{dd}-... 格式

  bind-branch <task_id> --branch <name> [--branch-type ...] [--source-branch ...] [--merge-targets ...]
        把 git 分支绑定到任务的 task.json.git section(经 TaskJsonStore.update_git)

  list [--story-id <id>]
        列 _index.jsonl

输出: stdout 单一 JSON 对象(ok/error/data/todo_hint),exit code=0 表示 ok=true
依赖: 仅 Python 标准库 + paths.py + task_store.py
"""
import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import (  # noqa: E402
    CURRENT_TASK,
    PROJECT_DIR,
    STATE_DIR,
    STORE_DIR,
    TASK_INDEX,
    TASK_REPORT_TEMPLATE,
    TASK_REPORTS,
)

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
_DESCRIPTION_MAX = 40


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

    # 校验模板存在
    meta_template = TASK_REPORT_TEMPLATE / "meta.json"
    if not meta_template.exists():
        return fail(
            "task template missing (need meta.json)",
            template_dir=str(TASK_REPORT_TEMPLATE),
        )

    # 校验 trigger 取值
    trigger = args.trigger
    if trigger and trigger not in VALID_TRIGGERS:
        return fail(
            f"invalid trigger '{trigger}'",
            valid_triggers=sorted(VALID_TRIGGERS),
        )

    # 分配 task_id —— 格式固定 {MM}-{dd}-{description}（无 TASK- 前缀，无序号）
    today = datetime.now().strftime("%m-%d")  # 本地日期
    task_id = f"{today}-{name}"

    # 任务目录
    task_dir = TASK_REPORTS / task_id
    if task_dir.exists():
        # 目录已存在(并发或残留),追加时间戳后缀避让
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        task_id = f"{task_id}-{ts}"
        task_dir = TASK_REPORTS / task_id
    task_dir.mkdir(parents=True, exist_ok=False)

    # 填充 meta.json
    template_text = meta_template.read_text(encoding="utf-8")
    timestamp = now_iso()
    meta_text = (
        template_text
        .replace("{task_id}", task_id)
        .replace("{story_id}", story_id)
        .replace("{created_at}", timestamp)
        .replace("{updated_at}", timestamp)
    )
    meta = json.loads(meta_text)
    if args.predecessor:
        meta["predecessor_task_id"] = args.predecessor
    if trigger:
        meta["trigger_reason"] = trigger
    (task_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # blockers.md 不预创建,首次写入时 hook 自行 mkdir

    # Story 目录幂等创建
    story_dir = STORE_DIR / story_id
    story_dir.mkdir(parents=True, exist_ok=True)

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
    task_path = STORE_DIR / story_id / "task.json"
    if not task_path.exists():
        return {}
    try:
        td = json.loads(task_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    wf = td.get("workflow") or {}
    merged: dict = {
        k: td.get(k) for k in
        ("task_id", "task_type", "story_id", "trigger", "dev_mode")
        if td.get(k) is not None
    }
    merged.update(wf)
    return merged


def _flow_check(state: dict) -> dict:
    """从 state 提取 flow.current_step / next_step / is_terminal。"""
    flow = state.get("flow")
    if not flow:
        return {"ok": False, "error": "no flow initialized"}
    steps = flow.get("steps", [])
    idx = flow.get("current_step_idx", 0)
    current = steps[idx] if 0 <= idx < len(steps) else None
    next_step = steps[idx + 1] if 0 <= idx + 1 < len(steps) else None
    return {
        "ok": True,
        "flow_id": flow.get("flow_id"),
        "current_step_idx": idx,
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


_TASK_ID_RE = re.compile(r"^\d{2}-\d{2}-[a-z0-9-]+$")


def cmd_resume(args: argparse.Namespace) -> dict:
    task_id = args.task_id
    # 接受两种格式：
    #   新： {MM}-{dd}-{description}（如 05-20-sf-account-merge）
    #   旧： TASK-{MM}-{dd}-{description}（历史任务兼容，去掉末尾序号）
    if not task_id or not _TASK_ID_RE.match(task_id):
        return fail(
            "invalid task_id",
            usage="python task.py resume <task_id>",
            expected_format="{MM}-{dd}-{description}",
            examples=["05-20-sf-account-merge", "04-30-wechat-login"],
        )

    task_dir = TASK_REPORTS / task_id
    meta_path = task_dir / "meta.json"
    if not meta_path.exists():
        return fail("task not found", task_dir=str(task_dir.relative_to(PROJECT_DIR)))

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as e:
        return fail(f"failed to read meta.json: {e}")

    story_id = meta.get("story_id")
    if not story_id:
        return fail("meta.json missing story_id", task_id=task_id)

    # 读 flow 状态
    state = _load_flow_state(story_id)
    flow_check = _flow_check(state)

    # blockers
    blockers_path = task_dir / "blockers.md"
    blockers_content = None
    blocker_count = meta.get("blocker_count", 0)
    if blockers_path.exists() and blocker_count > 0:
        blockers_content = blockers_path.read_text(encoding="utf-8")

    # 同 story 已完成 task
    related = _related_completed_tasks(story_id, task_id)

    # 更新 .current_task
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_TASK.write_text(task_id, encoding="utf-8")
    current_task_updated = True

    return {
        "ok": True,
        "task_id": task_id,
        "story_id": story_id,
        "meta": {
            "phase": meta.get("phase"),
            "agent": meta.get("agent"),
            "verdict": meta.get("verdict"),
            "blocker_count": blocker_count,
            "tapd_ticket_id": meta.get("tapd_ticket_id"),
            "predecessor_task_id": meta.get("predecessor_task_id"),
            "trigger_reason": meta.get("trigger_reason"),
            "summary": meta.get("summary", {}),
        },
        "flow": flow_check,
        "blockers": blockers_content,
        "related_completed_tasks": related,
        "current_task_updated": current_task_updated,
        "paths": {
            "task_dir": str(task_dir.relative_to(PROJECT_DIR)),
            "meta": str(meta_path.relative_to(PROJECT_DIR)),
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
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from task_store import TaskJsonStore  # 延迟导入避免循环
    from paths import STORE_DIR, BUG_FIX_DIR

    task_id = args.task_id
    if not task_id:
        return fail("task_id required",
                    usage="task.py bind-branch <task_id> --branch <name> [--branch-type ...] [--source-branch ...]")

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
        "source_branch": args.source_branch,
        "merge_targets": (
            [t.strip() for t in args.merge_targets.split(",") if t.strip()]
            if args.merge_targets else None
        ),
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


# ─────────────────────────── main ────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Task record CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="创建任务记录")
    p_new.add_argument("story_id")
    p_new.add_argument("--name", default=None, required=False,
                       help="(强制必填) 任务描述 slug,只允许 a-z 0-9 -,长度 3-40;"
                            "task_id 格式为 {MM}-{dd}-{slug}")
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

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
