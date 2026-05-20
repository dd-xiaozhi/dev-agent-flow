"""ensure_branch.py — 幂等地确保 <branch_name> 存在并切过去。

行为：
1. 若工作区有未提交变更 → 报错（不自动 stash）
2. 若 <branch_name> 是当前分支 → 直接成功（noop）
3. 若 <branch_name> 已存在 → checkout 过去
4. 否则 → 从 <source_branch> 创建并切过去
   - 远端有 origin/<source_branch> → 优先用 origin/<source_branch>
   - 否则 → 用本地 <source_branch>
   - 都不存在 → 报错

输出 JSON：
  {
    "ok": true,
    "action": "ensure-branch",
    "branch": "<branch_name>",
    "source_branch": "<source>",
    "created": true|false,
    "switched": true|false,
    "previous_branch": "<old>"
  }
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _is_git_repo(cwd: Path) -> bool:
    code, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    return code == 0


def _current_branch(cwd: Path) -> str:
    code, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    return out if code == 0 else ""


def _branch_exists_local(cwd: Path, branch: str) -> bool:
    code, _, _ = _run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd)
    return code == 0


def _branch_exists_remote(cwd: Path, branch: str, remote: str = "origin") -> bool:
    code, out, _ = _run(["git", "ls-remote", "--heads", remote, branch], cwd)
    return code == 0 and bool(out)


def _is_dirty(cwd: Path) -> bool:
    code, out, _ = _run(["git", "status", "--porcelain"], cwd)
    return code == 0 and bool(out.strip())


def ensure_branch(
    cwd: Path,
    branch_name: str,
    source_branch: str,
    allow_dirty: bool = False,
) -> dict:
    if not _is_git_repo(cwd):
        return {"ok": False, "action": "ensure-branch", "error": "not a git repo", "cwd": str(cwd)}

    if not branch_name:
        return {"ok": False, "action": "ensure-branch", "error": "branch_name required"}

    if not source_branch:
        return {"ok": False, "action": "ensure-branch", "error": "source_branch required"}

    current = _current_branch(cwd)

    # 已经在目标分支
    if current == branch_name:
        return {
            "ok": True,
            "action": "ensure-branch",
            "branch": branch_name,
            "source_branch": source_branch,
            "created": False,
            "switched": False,
            "previous_branch": current,
            "note": "already on target branch",
        }

    if not allow_dirty and _is_dirty(cwd):
        return {
            "ok": False,
            "action": "ensure-branch",
            "error": "working tree dirty, commit or stash first",
            "current_branch": current,
        }

    # 本地已有分支 → 直接切
    if _branch_exists_local(cwd, branch_name):
        code, _, err = _run(["git", "checkout", branch_name], cwd)
        if code != 0:
            return {"ok": False, "action": "ensure-branch", "error": f"checkout failed: {err}"}
        return {
            "ok": True,
            "action": "ensure-branch",
            "branch": branch_name,
            "source_branch": source_branch,
            "created": False,
            "switched": True,
            "previous_branch": current,
        }

    # 需要从 source 创建：优先 origin/<source>
    fetch_code, _, fetch_err = _run(["git", "fetch", "origin", source_branch], cwd)
    used_remote = False
    if fetch_code == 0 and _branch_exists_remote(cwd, source_branch):
        start_point = f"origin/{source_branch}"
        used_remote = True
    elif _branch_exists_local(cwd, source_branch):
        start_point = source_branch
    else:
        return {
            "ok": False,
            "action": "ensure-branch",
            "error": f"source branch '{source_branch}' not found locally or on origin",
            "fetch_error": fetch_err or None,
        }

    code, _, err = _run(["git", "checkout", "-b", branch_name, start_point], cwd)
    if code != 0:
        return {"ok": False, "action": "ensure-branch", "error": f"create failed: {err}"}

    return {
        "ok": True,
        "action": "ensure-branch",
        "branch": branch_name,
        "source_branch": source_branch,
        "start_point": start_point,
        "from_remote": used_remote,
        "created": True,
        "switched": True,
        "previous_branch": current,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure a git branch exists and switch to it")
    parser.add_argument("branch_name", help="目标分支全名（如 feature/05-20-sf-account-merge）")
    parser.add_argument("--from", dest="source_branch", required=True,
                        help="若分支不存在时从该分支创建（如 dev / master）")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="允许工作区脏（默认拒绝）")
    args = parser.parse_args()

    result = ensure_branch(Path.cwd(), args.branch_name, args.source_branch, args.allow_dirty)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
