"""
registry_query.py — 跨任务注册表 scoped 查询

问题：arbiter 判定跨 story 冲突此前**全量读** docs/registry/{api,schema,decisions}.jsonl。
story 累积后全量读 = context rot（token 越多召回越差）+ 漏读风险。本脚本提供
按维度（entity / path 前缀 / method+path / 关键字）的 scoped 查询，arbiter 先从
本任务 spec 提取涉及的资源名，再只拉命中条目，遵守"最小有效上下文"。

放置位置说明：registry（docs/registry/）是跨任务编排全局状态，与 task.json / events
同类；flow-engine 是编排引擎 skill，故本查询工具与 events.py 同置于其 scripts/。

冲突维度对照 arbiter 4 类：
- C2 API 路径重复  → `api --path-prefix` / `api --method --path`
- C3 字段类型矛盾  → `schema --entity [--field]`
- C4 重复造轮子    → `decisions --keyword`

Usage:
    python registry_query.py stats
    python registry_query.py api --path-prefix /api/v1/auth --exclude-story 05-27-x
    python registry_query.py api --method POST --path /api/v1/auth/login
    python registry_query.py schema --entity User [--field userId] [--exclude-story <id>]
    python registry_query.py decisions --keyword wechat [--exclude-task <id>]

默认只返回 status=active 行（api.jsonl）；--all 含所有 status。
输出 JSON：{ok, file, matched:[...], total_scanned, note}。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 项目根：CLAUDE_PROJECT_DIR 优先，否则按 .claude/skills/flow-engine/scripts/ 回退 4 级
# 用 .absolute() 而非 .resolve()——.claude 常是 symlink，resolve() 会穿透到错误项目
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[4])
))
REGISTRY_DIR = PROJECT_DIR / "docs" / "registry"

# 全量读仍划算的阈值：条目数 ≤ 此值时 stats 建议直接全读（scoped 查询开销无收益）
FULL_READ_THRESHOLD = 50


def _load_jsonl(name: str) -> list[dict]:
    """读 registry/<name>.jsonl，逐行解析，跳过空行与坏行（坏行不阻断查询）。"""
    path = REGISTRY_DIR / name
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 坏行跳过，不阻断
    return rows


def _emit(file: str, matched: list[dict], total: int, note: str | None = None) -> int:
    out = {"ok": True, "file": file, "matched": matched,
           "matched_count": len(matched), "total_scanned": total}
    if note:
        out["note"] = note
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(_args: argparse.Namespace) -> int:
    """各 registry 文件条目数 + 是否建议全量读（小表 scoped 查询无收益）。"""
    counts = {name: len(_load_jsonl(f"{name}.jsonl"))
              for name in ("api", "schema", "decisions")}
    total = sum(counts.values())
    print(json.dumps({
        "ok": True,
        "counts": counts,
        "total": total,
        "full_read_ok": total <= FULL_READ_THRESHOLD,
        "note": (f"总条目 {total} ≤ {FULL_READ_THRESHOLD}，全量读仍划算"
                 if total <= FULL_READ_THRESHOLD
                 else f"总条目 {total} > {FULL_READ_THRESHOLD}，建议 scoped 查询"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_api(args: argparse.Namespace) -> int:
    rows = _load_jsonl("api.jsonl")
    total = len(rows)
    out = rows
    if not args.all:
        out = [r for r in out if r.get("status", "active") == "active"]
    if args.exclude_story:
        out = [r for r in out if r.get("story_id") != args.exclude_story
               and r.get("owner_task") != args.exclude_story]
    if args.path_prefix:
        out = [r for r in out if str(r.get("path", "")).startswith(args.path_prefix)]
    if args.method:
        out = [r for r in out if str(r.get("method", "")).upper() == args.method.upper()]
    if args.path:
        out = [r for r in out if r.get("path") == args.path]
    return _emit("api.jsonl", out, total)


def cmd_schema(args: argparse.Namespace) -> int:
    rows = _load_jsonl("schema.jsonl")
    total = len(rows)
    out = rows
    if args.exclude_story:
        out = [r for r in out if r.get("story_id") != args.exclude_story
               and r.get("source_task") != args.exclude_story]
    if args.entity:
        out = [r for r in out if str(r.get("entity", "")).lower() == args.entity.lower()]
    if args.field:
        out = [r for r in out if str(r.get("field", "")).lower() == args.field.lower()]
    return _emit("schema.jsonl", out, total)


def cmd_decisions(args: argparse.Namespace) -> int:
    rows = _load_jsonl("decisions.jsonl")
    total = len(rows)
    out = rows
    if args.exclude_task:
        out = [r for r in out if r.get("task_id") != args.exclude_task]
    if args.keyword:
        kw = args.keyword.lower()
        out = [r for r in out
               if kw in json.dumps(r, ensure_ascii=False).lower()]
    return _emit("decisions.jsonl", out, total)


def main() -> int:
    parser = argparse.ArgumentParser(description="Registry scoped 查询（arbiter 冲突检测用）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="各文件条目数 + 是否建议全量读").set_defaults(func=cmd_stats)

    p_api = sub.add_parser("api", help="查 api.jsonl（C2 路径冲突）")
    p_api.add_argument("--path-prefix", default=None)
    p_api.add_argument("--method", default=None)
    p_api.add_argument("--path", default=None)
    p_api.add_argument("--exclude-story", default=None, help="排除自身 story，只看他人")
    p_api.add_argument("--all", action="store_true", help="含所有 status（默认只 active）")
    p_api.set_defaults(func=cmd_api)

    p_schema = sub.add_parser("schema", help="查 schema.jsonl（C3 字段类型矛盾）")
    p_schema.add_argument("--entity", default=None)
    p_schema.add_argument("--field", default=None)
    p_schema.add_argument("--exclude-story", default=None)
    p_schema.set_defaults(func=cmd_schema)

    p_dec = sub.add_parser("decisions", help="查 decisions.jsonl（C4 重复造轮子）")
    p_dec.add_argument("--keyword", default=None, help="关键字全字段匹配（语义初筛）")
    p_dec.add_argument("--exclude-task", default=None)
    p_dec.set_defaults(func=cmd_decisions)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
