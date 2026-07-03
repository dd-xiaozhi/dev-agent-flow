"""git_config.py — 读 docs/env.yaml.git 并解析分支策略。

公开 API：
  load_branch_config(branch_type, cwd=Path.cwd()) -> dict
      返回某 branch_type 的解析后配置（prefix / source / merge_targets）。
      source 与 merge_targets 已经把特殊值（current / current-feature）解析为
      具体分支名。失败时 ok=False，带 error + candidates。

CLI：
  python git_config.py resolve --branch-type feature
  python git_config.py raw          # 输出原始 git section（不解析）

配置回退优先级（仅 source / merge_targets 字段，prefix 缺失即用默认）：
  1. env.yaml.git.branches.<type>.<field>
  2. 内置 DEFAULTS（与 .claude/skills/git/SKILL.md 一致）
  3. 仍缺失 → ok=False，candidates 提示

特殊取值：
  source == "current"          → git rev-parse --abbrev-ref HEAD
  source == "current-feature"  → 最近活跃的 feature/* 分支
  merge_targets 中含上述同样规则展开
"""
from __future__ import annotations

import argparse
import json
import yaml
import subprocess
import sys
from pathlib import Path
from typing import Optional

DEFAULTS: dict[str, dict] = {
    "feature": {"prefix": "feature/", "source": "master",  "merge_targets": ["dev", "uat"]},
    "bugfix":  {"prefix": "bugfix/",  "source": "current", "merge_targets": ["current-feature"]},
    "hotfix":  {"prefix": "hotfix/",  "source": "master",  "merge_targets": ["dev", "uat"]},
    "release": {"prefix": "release/", "source": "develop", "merge_targets": ["main", "develop"]},
}

VALID_TYPES = tuple(DEFAULTS.keys())

CANDIDATE_HINTS = ["master", "main", "dev", "uat", "develop", "current"]


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _is_git_repo(cwd: Path) -> bool:
    code, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    return code == 0


def _current_branch(cwd: Path) -> Optional[str]:
    code, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd)
    if code != 0 or not out:
        return None
    # detached HEAD 时输出 "HEAD"
    if out == "HEAD":
        return None
    return out


def _latest_feature_branch(cwd: Path) -> Optional[str]:
    code, out, _ = _run(
        ["git", "for-each-ref", "--sort=-committerdate", "--count=1",
         "--format=%(refname:short)", "refs/heads/feature/"],
        cwd,
    )
    if code != 0 or not out:
        return None
    return out


def _read_project_config(cwd: Path) -> dict:
    """读 env.yaml；不存在或损坏返回 {}。"""
    path = cwd / "docs" / "env.yaml"
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _resolve_special(value: str, cwd: Path) -> tuple[Optional[str], str]:
    """解析 source 字段中的特殊取值。返回 (resolved_branch, resolution_tag)。"""
    if value == "current":
        cur = _current_branch(cwd)
        if cur:
            return cur, "current"
        return None, "current-unresolved"
    if value == "current-feature":
        feat = _latest_feature_branch(cwd)
        if feat:
            return feat, "current-feature"
        return None, "current-feature-unresolved"
    return value, "literal"


def load_branch_config(branch_type: str, cwd: Optional[Path] = None) -> dict:
    cwd = cwd or Path.cwd()

    if branch_type not in DEFAULTS:
        return {
            "ok": False,
            "error": f"unknown branch_type '{branch_type}'",
            "valid_types": list(VALID_TYPES),
        }

    config = _read_project_config(cwd)
    branches = (config.get("git") or {}).get("branches") or {}
    user_cfg = branches.get(branch_type) or {}
    default_cfg = DEFAULTS[branch_type]

    # 资源来源记账
    fields_from_config: list[str] = []
    fields_from_default: list[str] = []

    def _pick(field: str):
        if field in user_cfg and user_cfg[field] is not None:
            fields_from_config.append(field)
            return user_cfg[field]
        fields_from_default.append(field)
        return default_cfg[field]

    prefix = _pick("prefix")
    source_raw = _pick("source")
    merge_targets_raw = _pick("merge_targets")

    # 解析 source
    source, source_resolution = _resolve_special(source_raw, cwd)
    if source is None:
        return {
            "ok": False,
            "branch_type": branch_type,
            "error": f"source unresolved: '{source_raw}' could not resolve "
                     f"(reason: {source_resolution})",
            "source_raw": source_raw,
            "candidates": CANDIDATE_HINTS,
        }

    # 解析 merge_targets
    merge_targets: list[str] = []
    target_warnings: list[dict] = []
    for raw in (merge_targets_raw or []):
        resolved, tag = _resolve_special(raw, cwd)
        if resolved is None:
            target_warnings.append({"raw": raw, "reason": tag})
            continue
        merge_targets.append(resolved)

    # 标记最终的 source_resolution
    if "source" in fields_from_config:
        if source_resolution == "literal":
            final_source_resolution = "config"
        else:
            final_source_resolution = source_resolution  # "current" / "current-feature"
    else:
        final_source_resolution = "default" if source_resolution == "literal" else source_resolution

    return {
        "ok": True,
        "branch_type": branch_type,
        "prefix": prefix,
        "source": source,
        "source_raw": source_raw,
        "source_resolution": final_source_resolution,
        "merge_targets": merge_targets,
        "merge_targets_raw": list(merge_targets_raw or []),
        "merge_targets_warnings": target_warnings,
        "fields_from_config": fields_from_config,
        "fields_from_default": fields_from_default,
    }


def load_git_section(cwd: Optional[Path] = None) -> dict:
    """返回 env.yaml 的完整 git section（未解析），不存在返回 {}。"""
    cwd = cwd or Path.cwd()
    config = _read_project_config(cwd)
    return config.get("git") or {}


# ─────────────────────────── CLI ────────────────────────────

def _cmd_resolve(args: argparse.Namespace) -> dict:
    cwd = Path.cwd()
    if not _is_git_repo(cwd):
        return {"ok": False, "error": "not a git repo", "cwd": str(cwd)}
    return load_branch_config(args.branch_type, cwd)


def _cmd_raw(_: argparse.Namespace) -> dict:
    return {"ok": True, "git": load_git_section()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve git branch config")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_resolve = sub.add_parser("resolve", help="解析 branch_type 的完整配置")
    p_resolve.add_argument("--branch-type", required=True, choices=list(VALID_TYPES))
    p_resolve.set_defaults(func=_cmd_resolve)

    p_raw = sub.add_parser("raw", help="输出原始 git section")
    p_raw.set_defaults(func=_cmd_raw)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
