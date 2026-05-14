"""
comments_cache.py — TAPD 评论缓存与 MD 文档生成

负责：
1. 调用 MCP get_comments 工具拉取评论
2. 基于 comment.id 去重
3. 增量更新 task.json.tapd.comments_cache
4. 生成人类可读的 MD 评论文档

Usage:
    # 拉取并保存评论
    python comments_cache.py fetch --story-id <story_id> --entry-id <ticket_id> --entry-type stories

    # 仅生成 MD（从已有缓存）
    python comments_cache.py generate-md --story-id <story_id>
"""
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import re
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from paths import BUG_FIX_DIR, STORE_DIR  # noqa: E402
from task_store import TaskJsonStore  # noqa: E402

COMMENTS_MD_FILENAME = "tapd-comment.md"

# 特殊标记正则（用于 MD 高亮）
MARKER_PATTERN = re.compile(
    r'\[(CONSENSUS-(APPROVED|REJECTED[^]]*?)'
    r'|QA-(PASSED|REJECTED[^]]*?)'
    r'|SUBTASK-(EMITTED|UPDATED))\]'
)


def get_task_dir(story_id: str, entity_type: str = "stories") -> Path:
    """根据 story_id 和实体类型返回任务目录路径。"""
    if entity_type == "bugs":
        return BUG_FIX_DIR / story_id
    return STORE_DIR / story_id


def get_comments_md_path(story_id: str, entity_type: str = "stories") -> Path:
    """返回评论 MD 文件路径。"""
    return get_task_dir(story_id, entity_type) / COMMENTS_MD_FILENAME


def dedupe_comments(existing: list[dict], new: list[dict]) -> tuple[list[dict], list[dict]]:
    """基于 comment.id 去重。

    Args:
        existing: 已存在的评论列表
        new: 新拉取的评论列表

    Returns:
        (合并后的全量评论列表, 新增的评论列表)
    """
    existing_ids = {c.get("id") for c in existing if c.get("id")}
    added = [c for c in new if c.get("id") and c["id"] not in existing_ids]
    merged = existing + added
    return merged, added


def highlight_markers(content: str) -> str:
    """将评论内容中的特殊标记加粗高亮。"""
    def _repl(match):
        return f"**{match.group(0)}**"
    return MARKER_PATTERN.sub(_repl, content)


def format_comment_md(comment: dict) -> str:
    """格式化单条评论为 Markdown。"""
    created = comment.get("created", "")
    author = comment.get("author", "unknown")
    content = comment.get("content", "") or ""
    content = highlight_markers(content.strip())
    return f"### {created} - {author}\n\n{content}\n"


def group_comments_by_date(comments: list[dict]) -> dict[str, list[dict]]:
    """按日期分组评论。"""
    grouped = defaultdict(list)
    for c in comments:
        created = c.get("created", "")
        if isinstance(created, str) and "T" in created:
            date_part = created.split("T")[0]
        elif isinstance(created, str) and " " in created:
            date_part = created.split(" ")[0]
        else:
            date_part = "unknown"
        grouped[date_part].append(c)
    return grouped


def generate_comments_md(
    comments: list[dict],
    ticket_id: str,
    entity_type: str = "stories",
    last_synced_at: Optional[str] = None
) -> str:
    """生成完整的评论 MD 文档内容。

    Args:
        comments: 评论列表
        ticket_id: 工单 ID
        entity_type: 实体类型（stories/tasks/bugs）
        last_synced_at: 上次同步时间
    """
    # 按创建时间排序（最新在前）
    comments_sorted = sorted(
        comments,
        key=lambda c: c.get("created", "") or "",
        reverse=True
    )

    # 按日期分组
    grouped = group_comments_by_date(comments_sorted)

    # 生成头部
    lines = [
        "# TAPD 工单评论记录",
        "",
        f"> 工单 ID: {ticket_id}",
        f"> 工单类型: {entity_type}",
        f"> 上次同步: {last_synced_at or datetime.now().isoformat()}",
        f"> 评论总数: {len(comments)}",
        "",
        "---",
        "",
    ]

    # 按日期倒序生成内容
    for date in sorted(grouped.keys(), reverse=True):
        lines.append(f"## {date}")
        lines.append("")
        # 同日评论按时间倒序
        day_comments = sorted(
            grouped[date],
            key=lambda c: c.get("created", "") or "",
            reverse=True
        )
        for i, comment in enumerate(day_comments):
            if i > 0:
                lines.append("---")
                lines.append("")
            lines.append(format_comment_md(comment))

    return "\n".join(lines)


def save_comments_md(
    story_id: str,
    comments: list[dict],
    ticket_id: str,
    entity_type: str = "stories",
    incremental: bool = False
) -> Path:
    """保存评论 MD 到文件。

    Args:
        story_id: 任务 ID
        comments: 评论列表
        ticket_id: 工单 ID
        entity_type: 实体类型
        incremental: 是否增量模式（仅追加新增评论，而非全量重写）

    Returns:
        MD 文件路径
    """
    task_dir = get_task_dir(story_id, entity_type)
    md_path = task_dir / COMMENTS_MD_FILENAME
    task_dir.mkdir(parents=True, exist_ok=True)

    last_synced_at = datetime.now().isoformat()

    if incremental and md_path.exists():
        # TODO: 增量模式下只追加新评论
        # 简单实现：全量重写（因为要按日期分组且需要排序）
        pass

    content = generate_comments_md(
            comments,
            ticket_id,
            entity_type,
            last_synced_at
        )

    md_path.write_text(content, encoding="utf-8")
    return md_path


def _call_mcp_get_comments(
    entry_id: str,
    entry_type: str = "stories",
    order: str = "created desc",
    limit: int = 100
) -> list[dict]:
    """调用 MCP get_comments 工具拉取评论。

    注意：此函数在 Python 脚本中不能直接调用 MCP API。
    实际的 MCP 调用由 Claude Agent 在运行时根据命令文档和技能文档中的指令执行。
    此函数仅作为参考实现逻辑的占位符。

    真实的调用格式（由 Agent 执行）：
        mcp__chopard_tapd__get_comments(
            workspace_id=<ws_id>,
            entry_id=<ticket_id>,
            entry_type="stories",
            order="created desc",
            limit=50
        )
    """
    raise NotImplementedError(
        "MCP 调用必须由 Claude Agent 在运行时执行，不能直接从 Python 脚本调用。"
        "\n请参考 .claude/commands/tapd.md 中的 fetch 子命令。"
    )


def update_task_comments_cache(
    story_id: str,
    new_comments: list[dict],
    entity_type: str = "stories"
) -> tuple[int, int]:
    """更新 task.json.tapd.comments_cache。

    Args:
        story_id: 任务 ID
        new_comments: 新拉取的评论列表
        entity_type: 实体类型

    Returns:
        (现有评论数, 新增评论数)
    """
    task_dir = get_task_dir(story_id, entity_type)
    store = TaskJsonStore.load(task_dir)
    tapd = store.get_tapd() or {}
    existing = tapd.get("comments_cache") or []

    merged, added = dedupe_comments(existing, new_comments)

    if added:
        last_synced_at = datetime.now().isoformat()
        store.update_tapd({
            "comments_cache": merged,
            "last_synced_at": last_synced_at
        })
        store.save()

    return len(existing), len(added)


def _normalize_comment(raw_comment: dict, entry_type: str, entry_id: str) -> dict:
    """标准化 TAPD 评论字段到统一格式。"""
    return {
        "id": str(raw_comment.get("id") or ""),
        "author": str(raw_comment.get("author") or raw_comment.get("creator") or "unknown"),
        "created": str(raw_comment.get("created") or raw_comment.get("created_at") or ""),
        "content": str(raw_comment.get("content") or raw_comment.get("comment") or ""),
        "entity_type": entry_type,
        "entity_id": str(entry_id),
    }


# ── CLI ─────────────────────────────────────────────────────────────


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="TAPD 评论缓存与 MD 生成")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # fetch 子命令（注意：MCP 调用必须由 Agent 执行，此命令仅用于处理评论数据）
    p_fetch = sub.add_parser("process", help="处理评论数据并更新缓存和 MD")
    p_fetch.add_argument("--story-id", required=True, help="任务 ID")
    p_fetch.add_argument("--ticket-id", required=True, help="TAPD 工单 ID")
    p_fetch.add_argument("--entry-type", default="stories", choices=["stories", "tasks", "bugs"])
    p_fetch.add_argument("--comments-json", help="评论 JSON 字符串（由 Agent 调用 MCP 后传入）")

    # generate-md 子命令（从已有缓存生成 MD）
    p_gen = sub.add_parser("generate-md", help="从已有缓存生成 MD")
    p_gen.add_argument("--story-id", required=True, help="任务 ID")
    p_gen.add_argument("--entry-type", default="stories", choices=["stories", "tasks", "bugs"])

    args = parser.parse_args()

    if args.cmd == "process":
        import json
        try:
            raw_comments = json.loads(args.comments_json)
        except (json.JSONDecodeError, TypeError):
            print("错误：comments_json 格式无效", file=sys.stderr)
            return 1

        comments = [_normalize_comment(c, args.entry_type, args.ticket_id) for c in raw_comments]
        existing_count, added_count = update_task_comments_cache(
            args.story_id, comments, args.entry_type
        )

        # 重新读取合并后的评论生成 MD
        task_dir = get_task_dir(args.story_id, args.entry_type)
        store = TaskJsonStore.load(task_dir)
        tapd = store.get_tapd() or {}
        all_comments = tapd.get("comments_cache") or []

        md_path = save_comments_md(
            args.story_id, all_comments, args.ticket_id, args.entry_type
        )

        result = {
            "ok": True,
            "existing_count": existing_count,
            "added_count": added_count,
            "total_count": len(all_comments),
            "md_path": str(md_path.relative_to(Path.cwd()))
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "generate-md":
        task_dir = get_task_dir(args.story_id, args.entry_type)
        store = TaskJsonStore.load(task_dir)
        tapd = store.get_tapd() or {}
        comments = tapd.get("comments_cache") or []
        ticket_id = tapd.get("ticket_id") or args.story_id

        if not comments:
            print(f"警告：story_id={args.story_id} 没有评论缓存", file=sys.stderr)

        md_path = save_comments_md(
            args.story_id, comments, str(ticket_id), args.entry_type
        )

        result = {
            "ok": True,
            "comment_count": len(comments),
            "md_path": str(md_path.relative_to(Path.cwd()))
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(_main())
