"""gen_handoff.py — Context Reset handoff 工件生成

两阶段流程：
  1. gen — 采集文件系统层面状态，生成 draft（task.json snapshot + 活跃文件清单 + 模板骨架）
  2. 主 Claude 读 draft，补"任务声明 / 已完成 / 下一步 / 关键约束"等需要 transcript 总结的字段
  3. finalize — 校验完整性 + 追加 handoffs.jsonl 指标

CLI:
  python gen_handoff.py gen [--story-id <id>] --reason <text>
      生成 handoff draft
      stdout: {"ok": bool, "draft_path": "..."}

  python gen_handoff.py finalize <path>
      校验 + 追加指标
      stdout: {"ok": bool, "missing_fields": [...], "metrics_path": "..."}
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from paths import (  # noqa: E402
    HANDOFFS_DIR,
    HANDOFF_METRICS,
    PROJECT_DIR,
    TEMPLATES_DIR,
)
from task_store import TaskJsonStore  # noqa: E402


REQUIRED_SECTIONS = [
    "任务声明",
    "已完成",
    "下一步",
    "关键约束",
    "活跃工件",
    "未决问题",
    "禁止事项",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_status() -> list[str]:
    """采集当前工作区状态（未提交文件清单）"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "status", "--short"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode != 0:
            return []
        return [line.rstrip("\n\r") for line in proc.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _git_recent_commits(limit: int = 5) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(PROJECT_DIR), "log", f"-{limit}", "--oneline"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode != 0:
            return []
        return [line.rstrip("\n\r") for line in proc.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _task_snapshot(story_id: str | None) -> dict:
    """读 task.json 快照（如指定 story_id）"""
    if not story_id:
        # 无 story_id：列出所有活跃任务
        return {"active_tasks": TaskJsonStore.list_active()}

    store = TaskJsonStore.find_by_story_id(story_id)
    if not store:
        return {"story_id": story_id, "error": "task not found"}

    data = store.to_dict()
    return {
        "story_id": story_id,
        "task_id": data.get("task_id"),
        "phase": (data.get("workflow") or {}).get("phase"),
        "current_step": (data.get("workflow") or {}).get("current_step_id"),
        "branch": (data.get("git") or {}).get("branch"),
        "blocker_count": (data.get("workflow") or {}).get("blocker_count", 0),
        "task_dir": str(store.task_dir.relative_to(PROJECT_DIR)),
    }


def _build_draft(story_id: str | None, reason: str) -> str:
    """生成 handoff draft markdown"""
    ts = _utc_now_iso()
    snap = _task_snapshot(story_id)
    git_st = _git_status()
    commits = _git_recent_commits()

    lines = [
        f"# Handoff — {ts}",
        "",
        f"**触发原因**: {reason}",
        f"**story_id**: {story_id or '(无,全局)'}",
        "",
        "---",
        "",
        "## 📦 自动采集（脚本生成,主 Claude 不必改）",
        "",
        "### task.json snapshot",
        "```json",
        json.dumps(snap, ensure_ascii=False, indent=2),
        "```",
        "",
        "### git status (未提交变更)",
        "```",
        "\n".join(git_st) if git_st else "(clean)",
        "```",
        "",
        "### 最近 5 次提交",
        "```",
        "\n".join(commits) if commits else "(none)",
        "```",
        "",
        "---",
        "",
        "## ✍️ 待主 Claude 补全（基于 transcript 总结）",
        "",
        "### 任务声明",
        "_TBD — 一句话描述当前任务目标_",
        "",
        "### 已完成",
        "_TBD — 列举本 session 已交付的关键步骤,引用文件路径_",
        "",
        "### 下一步",
        "_TBD — 新 session 接手后应先做什么,具体到命令或文件_",
        "",
        "### 关键约束",
        "_TBD — 业务规则 / 技术决策 / 必须遵守的禁止项,引用 contract.md 或 ADR_",
        "",
        "### 活跃工件",
        "_TBD — 列出当前 session 在改的核心文件路径 + 它们的状态_",
        "",
        "### 未决问题",
        "_TBD — 等待 PM / 用户回复的 Blocker,引用 blockers.md 条目_",
        "",
        "### 禁止事项",
        "_TBD — 新 session 不该碰的文件 / 不该走的路径,降低误操作风险_",
        "",
    ]
    return "\n".join(lines)


def cmd_gen(args) -> int:
    HANDOFFS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d-%H%M")
    draft_path = HANDOFFS_DIR / f"{ts}.md"
    draft_path.write_text(_build_draft(args.story_id, args.reason), encoding="utf-8")

    print(json.dumps({
        "ok": True,
        "draft_path": str(draft_path.relative_to(PROJECT_DIR)),
        "next_step": "主 Claude 读 draft → 补全 TBD 字段 → 调 finalize",
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_finalize(args) -> int:
    path = Path(args.path)
    if not path.is_absolute():
        path = PROJECT_DIR / path
    if not path.exists():
        print(json.dumps({"ok": False, "error": f"handoff file not found: {path}"}, ensure_ascii=False))
        return 1

    content = path.read_text(encoding="utf-8")
    missing: list[str] = []
    for section in REQUIRED_SECTIONS:
        # 检查该 section 下是否仍有 TBD（未补全）
        marker = f"### {section}"
        idx = content.find(marker)
        if idx < 0:
            missing.append(f"{section}（章节缺失）")
            continue
        # 截到下一个 ## 或 ### 或文件末尾
        rest = content[idx + len(marker):]
        next_h = min(
            (rest.find("\n## "), rest.find("\n### "), len(rest)),
            key=lambda x: x if x >= 0 else len(rest),
        )
        body = rest[:next_h]
        if "_TBD" in body or "TBD —" in body:
            missing.append(f"{section}（仍为 TBD）")

    if missing:
        print(json.dumps({"ok": False, "missing_fields": missing}, ensure_ascii=False, indent=2))
        return 1

    # 追加指标到 handoffs.jsonl
    HANDOFF_METRICS.parent.mkdir(parents=True, exist_ok=True)
    metric = {
        "ts": _utc_now_iso(),
        "source": "context-reset",
        "handoff_file": str(path.relative_to(PROJECT_DIR)) if path.is_relative_to(PROJECT_DIR) else str(path),
        "ctx_usage_pct": os.environ.get("CLAUDE_CTX_USAGE_PCT"),
    }
    with HANDOFF_METRICS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(metric, ensure_ascii=False) + "\n")

    print(json.dumps({
        "ok": True,
        "metrics_path": str(HANDOFF_METRICS.relative_to(PROJECT_DIR)),
        "handoff_file": metric["handoff_file"],
    }, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Context-reset handoff helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_g = sub.add_parser("gen", help="generate handoff draft")
    p_g.add_argument("--story-id", help="task story_id (optional, omit for global handoff)")
    p_g.add_argument("--reason", required=True, help="why this reset (e.g. 'ctx-guard阻断' / 'sprint 收尾')")
    p_g.set_defaults(func=cmd_gen)

    p_f = sub.add_parser("finalize", help="validate + append metrics")
    p_f.add_argument("path", help="handoff file path")
    p_f.set_defaults(func=cmd_finalize)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
