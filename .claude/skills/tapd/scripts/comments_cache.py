"""
comments_cache.py — TAPD 评论缓存与 MD 文档生成

负责：
1. 拉取 TAPD 工单评论（fetch 子命令直调 HTTP API；process 子命令处理 MCP 输出）
2. 基于 comment.id 去重
3. 增量更新 task.json.tapd.comments_cache
4. 生成人类可读的 MD 评论文档 tapd-comment.md
5. 高亮 [CONSENSUS-APPROVED] / [CONSENSUS-REJECTED:*] / [QA-PASSED] 等关键标记

Usage:
    # 端到端：直接调 TAPD HTTP API 拉评论 + 落地 (需要 env TAPD_TOKEN)
    python comments_cache.py fetch --story-id <id> [--entry-type stories]

    # 老接口：Claude 调 MCP 后传 JSON 给本脚本处理
    python comments_cache.py process --story-id <id> --ticket-id <tid> --comments-json '<json>'

    # 仅从已有缓存生成 MD
    python comments_cache.py generate-md --story-id <story_id>
"""
import json
import os
import sys
import urllib.parse
import urllib.request
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
    """基于 comment.id 去重；同 id 但 content/modified 变化时替换。

    Args:
        existing: 已存在的评论列表
        new: 新拉取的评论列表

    Returns:
        (合并后的全量评论列表, 新增/更新的评论列表)
    """
    by_id: dict = {c["id"]: c for c in existing if c.get("id")}
    changed: list[dict] = []
    for n in new:
        nid = n.get("id")
        if not nid:
            continue
        old = by_id.get(nid)
        if old is None:
            by_id[nid] = n
            changed.append(n)
            continue
        # 同 id：比较 content 与 modified（PM 编辑评论、首次拉取字段缺失修复等）
        if (old.get("content") != n.get("content")
                or old.get("title") != n.get("title")):
            by_id[nid] = n
            changed.append(n)
    merged = list(by_id.values())
    return merged, changed


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


def _fetch_comments_http(
    workspace_id: str,
    entry_id: str,
    entry_type: str = "stories",
    limit: int = 200,
) -> list[dict]:
    """直接调 TAPD HTTP API 拉评论（Bearer ${TAPD_TOKEN}）。

    避免依赖 Claude 主流程"调 MCP → 喂 JSON"的链路,实现端到端的脚本可执行性。
    返回标准化后的评论列表。
    """
    token = os.environ.get("TAPD_TOKEN")
    if not token:
        raise RuntimeError("env TAPD_TOKEN not set; cannot fetch directly")

    params = urllib.parse.urlencode({
        "workspace_id": workspace_id,
        "entry_id": entry_id,
        "entry_type": entry_type,
        "order": "created desc",
        "limit": str(limit),
    })
    url = f"https://api.tapd.cn/comments?{params}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(
            f"TAPD API GET /comments → HTTP {e.code}: "
            f"{e.read().decode('utf-8', errors='ignore')[:500]}"
        ) from e

    if payload.get("status") != 1:
        raise RuntimeError(f"TAPD API failure: {payload.get('info')}")

    data = payload.get("data") or []
    out: list[dict] = []
    for item in data:
        # TAPD 返回结构: [{"Comment": {...}}, ...]
        raw = item.get("Comment") if isinstance(item, dict) else None
        if not raw:
            continue
        out.append(_normalize_comment(raw, entry_type, entry_id))
    return out


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


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """简单去掉 HTML 标签 + 解码常见实体（评论一般是富文本短文本，无需完整 HTML 解析）。"""
    if not text:
        return ""
    s = _HTML_TAG_RE.sub("", text)
    # 常见 HTML 实体
    s = (s.replace("&nbsp;", " ")
           .replace("&lt;", "<")
           .replace("&gt;", ">")
           .replace("&amp;", "&")
           .replace("&quot;", '"')
           .replace("\xa0", " "))
    return s.strip()


def _normalize_comment(raw_comment: dict, entry_type: str, entry_id: str) -> dict:
    """标准化 TAPD 评论字段到统一格式。

    TAPD /comments API 的评论正文字段是 `description`（富文本 HTML），
    `title` 是流转动作描述（如"在状态 [规划中] 添加"）。
    """
    raw_content = (
        raw_comment.get("description")  # ← TAPD API 主字段(富文本 HTML)
        or raw_comment.get("content")
        or raw_comment.get("comment")
        or ""
    )
    content = _strip_html(str(raw_content))
    return {
        "id": str(raw_comment.get("id") or ""),
        "author": str(raw_comment.get("author") or raw_comment.get("creator") or "unknown"),
        "created": str(raw_comment.get("created") or raw_comment.get("created_at") or ""),
        "content": content,
        "title": str(raw_comment.get("title") or ""),
        "entity_type": entry_type,
        "entity_id": str(entry_id),
    }


# ── CLI ─────────────────────────────────────────────────────────────


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="TAPD 评论缓存与 MD 生成")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # process 子命令：Claude 调 MCP 后,把评论 JSON 传给本脚本（兼容老接口）
    p_proc = sub.add_parser("process", help="处理评论数据（由 Agent 调 MCP 后传入 JSON）")
    p_proc.add_argument("--story-id", required=True, help="任务 ID")
    p_proc.add_argument("--ticket-id", required=True, help="TAPD 工单 ID")
    p_proc.add_argument("--entry-type", default="stories", choices=["stories", "tasks", "bugs"])
    p_proc.add_argument("--comments-json", help="评论 JSON 字符串")

    # fetch 子命令：直接调 TAPD HTTP API 拉评论 + 落地（推荐）
    p_fetch = sub.add_parser("fetch", help="直接调 TAPD HTTP API 拉评论并同步到本地（需要 TAPD_TOKEN）")
    p_fetch.add_argument("--story-id", required=True, help="本地 story_id")
    p_fetch.add_argument("--entry-type", default="stories", choices=["stories", "tasks", "bugs"])
    p_fetch.add_argument("--limit", type=int, default=200)

    # generate-md 子命令（从已有缓存生成 MD）
    p_gen = sub.add_parser("generate-md", help="从已有缓存生成 MD")
    p_gen.add_argument("--story-id", required=True, help="任务 ID")
    p_gen.add_argument("--entry-type", default="stories", choices=["stories", "tasks", "bugs"])

    args = parser.parse_args()

    if args.cmd == "process":
        try:
            raw_comments = json.loads(args.comments_json)
        except (json.JSONDecodeError, TypeError):
            print("错误：comments_json 格式无效", file=sys.stderr)
            return 1

        # 兼容两种数据格式：
        # 1. TAPD API 直接返回列表: [{...}, {...}]
        # 2. MCP get_comments 返回包装格式: {"status": 1, "data": [{"Comment": {...}}, ...]}
        if isinstance(raw_comments, dict):
            if "data" in raw_comments:
                raw_comments = raw_comments["data"]
            else:
                # 兜底：把整个 dict 当作单条评论处理（理论上不应该走到这里）
                raw_comments = [raw_comments]
        elif not isinstance(raw_comments, list):
            raw_comments = []

        # 从 data 数组中提取 Comment 对象
        comments = []
        for item in raw_comments:
            if isinstance(item, dict) and "Comment" in item:
                comments.append(_normalize_comment(item["Comment"], args.entry_type, args.ticket_id))
            elif isinstance(item, dict):
                # 直接是评论对象（其他调用方传入的格式）
                comments.append(_normalize_comment(item, args.entry_type, args.ticket_id))
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

    if args.cmd == "fetch":
        task_dir = get_task_dir(args.story_id, args.entry_type)
        store = TaskJsonStore.load(task_dir)
        tapd = store.get_tapd() or {}
        ticket_id = tapd.get("ticket_id") or (tapd.get("raw") or {}).get("id")
        workspace_id = tapd.get("workspace_id")
        if not workspace_id:
            # 兜底从 project-config.json 取
            cfg_path = Path(__file__).resolve().parents[3].parent / ".chatlabs" / "project-config.json"
            if cfg_path.exists():
                workspace_id = (json.loads(cfg_path.read_text(encoding="utf-8"))
                                 .get("tapd") or {}).get("workspace_id")
        if not (ticket_id and workspace_id):
            print(json.dumps({"ok": False,
                              "error": "需要 ticket_id 和 workspace_id；先跑 description.py save"},
                             ensure_ascii=False))
            return 1
        try:
            comments = _fetch_comments_http(
                workspace_id=str(workspace_id),
                entry_id=str(ticket_id),
                entry_type=args.entry_type,
                limit=args.limit,
            )
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
            return 1

        existing_count, added_count = update_task_comments_cache(
            args.story_id, comments, args.entry_type,
        )
        # 重新读取合并后的全量评论生成 MD
        store = TaskJsonStore.load(task_dir)
        tapd = store.get_tapd() or {}
        all_comments = tapd.get("comments_cache") or []
        md_path = save_comments_md(
            args.story_id, all_comments, str(ticket_id), args.entry_type,
        )

        # 关键标记摘要（[CONSENSUS-APPROVED]/[CONSENSUS-REJECTED:*]/[QA-PASSED]/...）
        markers_found = []
        for c in all_comments:
            for m in MARKER_PATTERN.finditer(c.get("content") or ""):
                markers_found.append({
                    "marker": m.group(0),
                    "comment_id": c.get("id"),
                    "author": c.get("author"),
                    "created": c.get("created"),
                })

        result = {
            "ok": True,
            "ticket_id": str(ticket_id),
            "existing_count": existing_count,
            "added_count": added_count,
            "total_count": len(all_comments),
            "md_path": str(md_path.relative_to(Path.cwd())) if md_path.is_absolute() else str(md_path),
            "markers": markers_found,
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
