"""init_config.py — 设置项目本地 git 配置以符合 docs/git-brance-spec.md。

只修改当前仓库的 `.git/config`（本地），不动 user / global 配置。
同时将 merge 相关配置写入 `env.yaml` 的 `git.merge` section。

行为：
- 本地 .git/config：
  - merge.ff             = false     # 禁 fast-forward
  - merge.noff           = true      # 默认 --no-ff
  - pull.rebase          = true      # pull 自动 rebase
  - branch.autosetuprebase = always
  - push.default         = current   # push 只推当前分支
- env.yaml git.merge section：
  - no_ff                = true
  - pull_before_merge    = true
  - allow_force_push     = false
  - return_to_branch     = "source"

输出 JSON：{"ok": true, "action": "init-config", "applied": {...}, "skipped": [...], "project_config": {...}}
"""
from __future__ import annotations

import json
import yaml
import subprocess
import sys
from pathlib import Path

# 期望的本地仓库配置
EXPECTED: dict[str, str] = {
    "merge.ff": "false",
    "merge.noff": "true",
    "pull.rebase": "true",
    "branch.autosetuprebase": "always",
    "push.default": "current",
}

# env.yaml git.merge section 期望配置
PROJECT_CONFIG_MERGE: dict = {
    "no_ff": True,
    "pull_before_merge": True,
    "allow_force_push": False,
    "return_to_branch": "source",
}


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def _is_git_repo(cwd: Path) -> bool:
    code, _, _ = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd)
    return code == 0


def _update_project_config(cwd: Path) -> dict:
    """将 git.merge 配置写入 env.yaml"""
    config_path = cwd / "docs" / "env.yaml"
    if not config_path.exists():
        return {"ok": False, "error": "env.yaml not found", "path": str(config_path)}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"JSON decode error: {e}"}

    # 确保 git section 存在
    if "git" not in config:
        config["git"] = {}
    if "merge" not in config["git"]:
        config["git"]["merge"] = {}

    # 记录变更
    applied: dict = {}
    skipped: list = []
    existing_merge = config["git"].get("merge", {})

    for key, value in PROJECT_CONFIG_MERGE.items():
        if existing_merge.get(key) == value:
            skipped.append(key)
            continue
        old_value = existing_merge.get(key)
        config["git"]["merge"][key] = value
        applied[key] = {"old": old_value, "new": value}

    if not applied and not skipped:
        return {"ok": True, "applied": {}, "skipped": list(PROJECT_CONFIG_MERGE.keys()), "note": "no changes needed"}

    # 写回文件
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
    except IOError as e:
        return {"ok": False, "error": f"Failed to write env.yaml: {e}"}

    return {"ok": True, "applied": applied, "skipped": skipped}


def init_config(cwd: Path) -> dict:
    if not _is_git_repo(cwd):
        return {"ok": False, "action": "init-config", "error": "not a git repo", "cwd": str(cwd)}

    applied: dict[str, dict] = {}
    skipped: list[str] = []
    errors: list[dict] = []

    for key, value in EXPECTED.items():
        code_old, old, _ = _run(["git", "config", "--local", "--get", key], cwd)
        old = old if code_old == 0 else None
        if old == value:
            skipped.append(key)
            continue
        code, _, err = _run(["git", "config", "--local", key, value], cwd)
        if code != 0:
            errors.append({"key": key, "error": err})
            continue
        applied[key] = {"old": old, "new": value}

    # 更新 env.yaml
    project_config_result = _update_project_config(cwd)

    ok = not errors and project_config_result.get("ok", False)
    return {
        "ok": ok,
        "action": "init-config",
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
        "project_config": project_config_result,
        "cwd": str(cwd),
    }


def main() -> int:
    cwd = Path.cwd()
    result = init_config(cwd)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
