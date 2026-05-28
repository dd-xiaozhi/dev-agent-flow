"""deploy.py — Jenkins 部署辅助脚本

负责配置解析 + 通知文本生成 + 状态写回。
不直接调用 Jenkins / 企微 MCP（那是主 Claude 的事）。

CLI:
  python deploy.py resolve <story_id> [--mode full|task]
      解析 project-config.jenkins + task.json，输出待触发 targets JSON
      stdout: {"ok": bool, "targets": [...], "warnings": [...], "config": {...}}

  python deploy.py format-notify <story_id> --builds '<json>'
      根据 build 结果生成企微通知 markdown
      stdout: markdown 文本（供主 Claude 透传给 send_qiwei_message）

  python deploy.py save <story_id> --builds '<json>'
      把 build 聚合结果写回 task.json.git.builds
      stdout: {"ok": bool, "builds_path": "..."}

builds JSON schema:
  [
    {"env": "dev", "job": "...", "branch": "...", "build_number": 123,
     "status": "SUCCESS|FAILURE|ABORTED|TIMEOUT",
     "duration_seconds": 180, "console_summary": "...", "deployed_at": "ISO"}
  ]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
PROJECT_CONFIG = PROJECT_DIR / ".chatlabs" / "project-config.json"

sys.path.insert(0, str(PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
from task_store import TaskJsonStore  # noqa: E402


def _load_jenkins_config() -> dict:
    if not PROJECT_CONFIG.exists():
        return {}
    try:
        data = json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data.get("jenkins") or {}


def cmd_resolve(args) -> int:
    cfg = _load_jenkins_config()
    if not cfg:
        print(json.dumps({"ok": False, "error": "jenkins config missing — run /init-project first"}, ensure_ascii=False))
        return 1

    envs = cfg.get("envs") or []
    if not envs:
        print(json.dumps({"ok": False, "error": "jenkins.envs is empty"}, ensure_ascii=False))
        return 1

    warnings: list[str] = []
    if args.mode == "task":
        targets = [dict(envs[0])]
        store = TaskJsonStore.load_by_story(args.story_id)
        task_branch = (store.get_git() or {}).get("branch")
        if task_branch and task_branch != targets[0].get("branch"):
            warnings.append(
                f"task.json.git.branch={task_branch} != envs[0].branch={targets[0].get('branch')}"
                f" — 用 task branch 覆盖"
            )
            targets[0]["branch"] = task_branch
    else:
        targets = [dict(e) for e in envs]

    result = {
        "ok": True,
        "mode": args.mode,
        "targets": targets,
        "warnings": warnings,
        "config": {
            "poll_interval_seconds": cfg.get("poll_interval_seconds", 30),
            "timeout_minutes": cfg.get("timeout_minutes", 15),
            "notify_on_success": cfg.get("notify_on_success", True),
            "notify_on_failure": cfg.get("notify_on_failure", True),
        },
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_format_notify(args) -> int:
    try:
        builds = json.loads(args.builds)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid builds JSON: {e}"}, ensure_ascii=False))
        return 1

    if not isinstance(builds, list):
        print(json.dumps({"ok": False, "error": "builds must be a list"}, ensure_ascii=False))
        return 1

    success = [b for b in builds if b.get("status") == "SUCCESS"]
    failure = [b for b in builds if b.get("status") not in ("SUCCESS", None)]

    icon = "✅" if not failure else ("❌" if not success else "⚠️")
    lines = [f"## {icon} Jenkins 构建 — {args.story_id}"]
    lines.append(f"\n**汇总**：成功 {len(success)} / 失败 {len(failure)} / 总计 {len(builds)}")

    if builds:
        lines.append("\n| env | branch | build | status | 耗时 |")
        lines.append("|-----|--------|-------|--------|------|")
        for b in builds:
            duration = b.get("duration_seconds")
            dur_str = f"{duration}s" if duration is not None else "-"
            lines.append(
                f"| {b.get('env','-')} | `{b.get('branch','-')}` | "
                f"#{b.get('build_number','-')} | {b.get('status','-')} | {dur_str} |"
            )

    if failure:
        lines.append("\n**失败摘要**：")
        for b in failure:
            summary = (b.get("console_summary") or "").strip().splitlines()
            tail = "\n".join(summary[-5:]) if summary else "(no console summary)"
            lines.append(f"\n- `{b.get('env','-')}` #{b.get('build_number','-')}\n```\n{tail}\n```")

    print("\n".join(lines))
    return 0


def cmd_save(args) -> int:
    try:
        builds = json.loads(args.builds)
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid builds JSON: {e}"}, ensure_ascii=False))
        return 1

    store = TaskJsonStore.load_by_story(args.story_id)
    if not store.path.exists():
        print(json.dumps({"ok": False, "error": f"task.json not found for story_id={args.story_id}"}, ensure_ascii=False))
        return 1

    summary = {
        "total": len(builds),
        "success": sum(1 for b in builds if b.get("status") == "SUCCESS"),
        "failure": sum(1 for b in builds if b.get("status") not in ("SUCCESS", None)),
    }
    store.update_git({"builds": {"targets": builds, "summary": summary}})
    store.save()

    print(json.dumps({"ok": True, "builds_path": str(store.path.relative_to(Path.cwd()))}, ensure_ascii=False))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Jenkins deploy helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_r = sub.add_parser("resolve", help="resolve targets from config + task.json")
    p_r.add_argument("story_id")
    p_r.add_argument("--mode", choices=("full", "task"), default="full")
    p_r.set_defaults(func=cmd_resolve)

    p_n = sub.add_parser("format-notify", help="format qiwei notification markdown")
    p_n.add_argument("story_id")
    p_n.add_argument("--builds", required=True, help="JSON array of build results")
    p_n.set_defaults(func=cmd_format_notify)

    p_s = sub.add_parser("save", help="save build results back to task.json")
    p_s.add_argument("story_id")
    p_s.add_argument("--builds", required=True, help="JSON array of build results")
    p_s.set_defaults(func=cmd_save)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
