"""worktree.py — 按 env.yaml.git.worktree 决定并创建 task 的独立 worktree。

把原先散落在 4 个入口命令里的硬编码（vibe 豁免写死、路径写死、无 auto_create 开关）
收敛到一处，统一读 config：

  worktree.root              worktree 根目录          默认 docs/worktrees
  worktree.auto_create       task 启动是否自动开      默认 true
  worktree.skip_for_complexity  哪些复杂度档跳过      默认 ["vibe"]

config 缺字段时回退到 WORKTREE_DEFAULTS（与 .claude/skills/git/SKILL.md 一致）。

职责边界：本脚本只管 worktree，不调 task.py bind-branch —— 分支绑定由入口命令负责
（vibe 档也要 bind，只是不带 worktree_path），路径从本脚本输出接住。

CLI：
  python worktree.py resolve <task_id> --complexity <vibe|plan|spec>
      只读决策，不执行 git。输出 will_create / worktree_path / reason + 回显配置。
  python worktree.py create  <task_id> --branch <b> --complexity <vibe|plan|spec>
      先内部 resolve；该建才建（git worktree add），否则 noop skip。

输出 JSON（create）：
  {
    "ok": true,
    "action": "worktree-create",
    "created": true|false,
    "skipped": true|false,
    "worktree_path": "<root>/<task_id>" | null,
    "branch": "<branch>",
    "reason": "..."
  }
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from git_config import load_git_section  # noqa: E402

# 与 .claude/skills/git/SKILL.md 配置表保持一致
WORKTREE_DEFAULTS: dict = {
    "root": "docs/worktrees",
    "auto_create": True,
    "skip_for_complexity": ["vibe"],
}

VALID_COMPLEXITY = ("vibe", "plan", "spec")


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _is_git_repo(cwd: Path) -> bool:
    code, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    return code == 0


def _load_worktree_config(cwd: Path) -> dict:
    """读 git.worktree，逐字段回退到 WORKTREE_DEFAULTS。"""
    wt = (load_git_section(cwd) or {}).get("worktree") or {}
    return {
        "root": wt.get("root", WORKTREE_DEFAULTS["root"]),
        "auto_create": wt.get("auto_create", WORKTREE_DEFAULTS["auto_create"]),
        "skip_for_complexity": wt.get(
            "skip_for_complexity", WORKTREE_DEFAULTS["skip_for_complexity"]
        ),
    }


def resolve_worktree(task_id: str, complexity: str, cwd: Optional[Path] = None) -> dict:
    """决定是否为 task 创建 worktree，不执行任何 git 操作。"""
    cwd = cwd or Path.cwd()
    cfg = _load_worktree_config(cwd)

    base = {
        "ok": True,
        "action": "worktree-resolve",
        "task_id": task_id,
        "complexity": complexity,
        "root": cfg["root"],
        "auto_create": cfg["auto_create"],
        "skip_for_complexity": cfg["skip_for_complexity"],
    }

    if not cfg["auto_create"]:
        return {**base, "will_create": False, "worktree_path": None,
                "reason": "auto_create is false in config"}

    if complexity in cfg["skip_for_complexity"]:
        return {**base, "will_create": False, "worktree_path": None,
                "reason": f"complexity '{complexity}' is in skip_for_complexity "
                          f"{cfg['skip_for_complexity']}"}

    worktree_path = f"{cfg['root'].rstrip('/')}/{task_id}"
    return {**base, "will_create": True, "worktree_path": worktree_path,
            "reason": f"complexity '{complexity}' not skipped; auto_create enabled"}


def create_worktree(
    task_id: str, branch: str, complexity: str, cwd: Optional[Path] = None
) -> dict:
    """据 resolve 决策创建 worktree（git worktree add）。"""
    cwd = cwd or Path.cwd()

    if not _is_git_repo(cwd):
        return {"ok": False, "action": "worktree-create",
                "error": "not a git repo", "cwd": str(cwd)}

    decision = resolve_worktree(task_id, complexity, cwd)

    if not decision["will_create"]:
        return {
            "ok": True,
            "action": "worktree-create",
            "created": False,
            "skipped": True,
            "worktree_path": None,
            "branch": branch,
            "reason": decision["reason"],
        }

    worktree_path = decision["worktree_path"]

    if (cwd / worktree_path).exists():
        return {
            "ok": False,
            "action": "worktree-create",
            "error": f"worktree path already exists: {worktree_path}",
            "worktree_path": worktree_path,
            "branch": branch,
        }

    code, _, err = _run(["git", "worktree", "add", worktree_path, branch], cwd)
    if code != 0:
        return {
            "ok": False,
            "action": "worktree-create",
            "error": f"git worktree add failed: {err}",
            "worktree_path": worktree_path,
            "branch": branch,
        }

    return {
        "ok": True,
        "action": "worktree-create",
        "created": True,
        "skipped": False,
        "worktree_path": worktree_path,
        "branch": branch,
        "reason": decision["reason"],
    }


# ─────────────────────────── CLI ────────────────────────────

def _cmd_resolve(args: argparse.Namespace) -> dict:
    return resolve_worktree(args.task_id, args.complexity, Path.cwd())


def _cmd_create(args: argparse.Namespace) -> dict:
    return create_worktree(args.task_id, args.branch, args.complexity, Path.cwd())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 config 决定并创建 task 的独立 worktree"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_resolve = sub.add_parser("resolve", help="只读决策：是否创建 worktree + 路径")
    p_resolve.add_argument("task_id", help="task / story id（worktree 目录名）")
    p_resolve.add_argument("--complexity", required=True, choices=list(VALID_COMPLEXITY),
                           help="复杂度档，决定是否命中 skip_for_complexity")
    p_resolve.set_defaults(func=_cmd_resolve)

    p_create = sub.add_parser("create", help="据决策执行 git worktree add")
    p_create.add_argument("task_id", help="task / story id（worktree 目录名）")
    p_create.add_argument("--branch", required=True, help="worktree checkout 的分支全名")
    p_create.add_argument("--complexity", required=True, choices=list(VALID_COMPLEXITY),
                          help="复杂度档，决定是否命中 skip_for_complexity")
    p_create.set_defaults(func=_cmd_create)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
