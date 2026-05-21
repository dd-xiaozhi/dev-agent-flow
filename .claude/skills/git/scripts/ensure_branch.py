"""ensure_branch.py — 幂等地确保 <branch_name> 存在并切过去。

行为：
1. 若工作区有未提交变更 → 报错（不自动 stash）
2. 若 <branch_name> 是当前分支 → 直接成功（noop）
3. 若 <branch_name> 已存在 → checkout 过去
4. 否则 → 从 <source_branch> 创建并切过去
   - 远端有 origin/<source_branch> → 优先用 origin/<source_branch>
   - 否则 → 用本地 <source_branch>
   - 都不存在 → 报错

source_branch 解析优先级：
  1. 显式 --from         → resolution=explicit
  2. --branch-type 走 project-config.json.git.branches.<type>.source
                        → resolution=config | current | current-feature | default
  3. 都没传              → 报错附 candidates

输出 JSON：
  {
    "ok": true,
    "action": "ensure-branch",
    "branch": "<branch_name>",
    "source_branch": "<resolved source>",
    "source_resolution": "explicit|config|default|current|current-feature",
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
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from git_config import (  # noqa: E402
    CANDIDATE_HINTS,
    VALID_TYPES,
    load_branch_config,
)


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


def _resolve_source(
    cwd: Path,
    explicit_from: Optional[str],
    branch_type: Optional[str],
) -> dict:
    """返回 {ok, source_branch, source_resolution} 或 {ok:False, error, candidates}."""
    if explicit_from:
        return {
            "ok": True,
            "source_branch": explicit_from,
            "source_resolution": "explicit",
        }
    if branch_type:
        cfg = load_branch_config(branch_type, cwd)
        if not cfg.get("ok"):
            return {
                "ok": False,
                "error": cfg.get("error", "branch config unresolved"),
                "candidates": cfg.get("candidates", CANDIDATE_HINTS),
                "branch_type": branch_type,
            }
        return {
            "ok": True,
            "source_branch": cfg["source"],
            "source_resolution": cfg["source_resolution"],
            "source_raw": cfg.get("source_raw"),
        }
    return {
        "ok": False,
        "error": "must pass --from or --branch-type",
        "candidates": CANDIDATE_HINTS,
    }


def ensure_branch(
    cwd: Path,
    branch_name: str,
    explicit_from: Optional[str] = None,
    branch_type: Optional[str] = None,
    allow_dirty: bool = False,
) -> dict:
    if not _is_git_repo(cwd):
        return {"ok": False, "action": "ensure-branch", "error": "not a git repo", "cwd": str(cwd)}

    if not branch_name:
        return {"ok": False, "action": "ensure-branch", "error": "branch_name required"}

    resolved = _resolve_source(cwd, explicit_from, branch_type)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "action": "ensure-branch",
            **{k: v for k, v in resolved.items() if k != "ok"},
        }

    source_branch = resolved["source_branch"]
    source_resolution = resolved["source_resolution"]

    current = _current_branch(cwd)

    # 已经在目标分支
    if current == branch_name:
        return {
            "ok": True,
            "action": "ensure-branch",
            "branch": branch_name,
            "source_branch": source_branch,
            "source_resolution": source_resolution,
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
            "source_resolution": source_resolution,
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
            "source_resolution": source_resolution,
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
        "source_resolution": source_resolution,
        "start_point": start_point,
        "from_remote": used_remote,
        "created": True,
        "switched": True,
        "previous_branch": current,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Ensure a git branch exists and switch to it")
    parser.add_argument("branch_name", help="目标分支全名（如 feature/05-20-sf-account-merge）")
    parser.add_argument("--from", dest="source_branch", default=None,
                        help="显式 source 分支；与 --branch-type 二选一（显式优先）")
    parser.add_argument("--branch-type", dest="branch_type", default=None,
                        choices=list(VALID_TYPES),
                        help="走 project-config.json.git.branches.<type>.source 解析；与 --from 二选一")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="允许工作区脏（默认拒绝）")
    args = parser.parse_args()

    result = ensure_branch(
        Path.cwd(),
        args.branch_name,
        explicit_from=args.source_branch,
        branch_type=args.branch_type,
        allow_dirty=args.allow_dirty,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
