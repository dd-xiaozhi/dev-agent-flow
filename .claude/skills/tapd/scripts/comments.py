"""
comments.py — TAPD 工单评论本地化同步

职责：
1. 直接调 TAPD HTTP API（GET /comments，Bearer ${TAPD_TOKEN}）拉取工单评论
2. 复用 comments_cache.py 的去重逻辑，累积写入 task.json.tapd.comments_cache
3. 生成人类可读的 tapd-comment.md（按日期升序分组，关键评论 blockquote 突出）

子命令：
    fetch    端到端：拉取 → 去重 → 累积 → 重写 MD（推荐）

Usage:
    python comments.py fetch --story-id sf-account-merge
    python comments.py fetch --story-id sf-account-merge --ticket-id 1152676229001047022 --limit 100
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# 共享基础设施
# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
PROJECT_CONFIG = PROJECT_DIR / ".chatlabs" / "project-config.json"
STORE_DIR = PROJECT_DIR / ".chatlabs" / "task" / "store"

sys.path.insert(0, str(PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
from task_store import TaskJsonStore  # noqa: E402

# 复用 comments_cache.py 的去重 + 标准化逻辑（避免双份实现）
SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from comments_cache import (  # noqa: E402
    MARKER_PATTERN,
    build_marker_pattern,
    dedupe_comments,
    _normalize_comment,
)


def _load_marker_pattern() -> "re.Pattern":
    """读取 project-config.json.tapd.comment_markers 构造容错正则。

    配置缺失 / JSON 错误 / 字段空 → 回退模块级 MARKER_PATTERN(默认 5 个 marker)。
    """
    if not PROJECT_CONFIG.exists():
        return MARKER_PATTERN
    try:
        cfg = json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return MARKER_PATTERN
    markers_cfg = (cfg.get("tapd") or {}).get("comment_markers")
    if not markers_cfg:
        return MARKER_PATTERN
    return build_marker_pattern(markers_cfg)

COMMENTS_MD_FILENAME = "tapd-comment.md"


# ── HTML → Markdown（轻量版，专为评论场景） ────────────────────────────


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_md(html: str) -> str:
    """评论 HTML → Markdown。

    评论通常是短文本富文本（含 <p>、<br>、<strong>），转换规则与
    description.html_to_markdown 保持一致，但更轻量（不处理标题、表格等）。
    """
    if not html:
        return ""
    text = html
    # <br> → 换行
    text = re.sub(r"<br\s*/?>", "\n", text)
    # <p>...</p> → 段落 + 换行（空 <p> 视作空行）
    def _para(m):
        inner = m.group(1).strip()
        return (inner + "\n") if inner else "\n"
    text = re.sub(r"<p[^>]*>(.*?)</p>", _para, text, flags=re.DOTALL)
    # <strong>/<b> → **...**
    text = re.sub(
        r"<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>",
        r"**\1**", text, flags=re.DOTALL,
    )
    # <em>/<i> → *...*
    text = re.sub(
        r"<(?:em|i)[^>]*>(.*?)</(?:em|i)>",
        r"*\1*", text, flags=re.DOTALL,
    )
    # 兜底剔除剩余标签
    text = _HTML_TAG_RE.sub("", text)
    # 实体解码
    text = html_mod.unescape(text)
    text = text.replace("\xa0", " ")
    # 多余空行压缩
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── TAPD HTTP API ─────────────────────────────────────────────────────


def _resolve_workspace_id(explicit: Optional[str], tapd_cache: dict) -> Optional[str]:
    """workspace_id 解析：参数 > task.json.tapd.workspace_id > project-config.tapd.workspace_id。"""
    if explicit:
        return str(explicit)
    wid = tapd_cache.get("workspace_id")
    if wid:
        return str(wid)
    if PROJECT_CONFIG.exists():
        try:
            cfg = json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        wid = (cfg.get("tapd") or {}).get("workspace_id")
        if wid:
            return str(wid)
    return None


def _fetch_comments_http(
    workspace_id: str,
    ticket_id: str,
    limit: int = 100,
) -> list[dict]:
    """GET /comments?workspace_id=&entry_type=stories&entry_id=&limit=&order=created desc

    返回标准化后的评论列表（_normalize_comment 处理，content 已去 HTML 标签）。
    """
    token = os.environ.get("TAPD_TOKEN")
    if not token:
        raise RuntimeError("env TAPD_TOKEN not set; cannot fetch directly")
    params = urllib.parse.urlencode({
        "workspace_id": str(workspace_id),
        "entry_type": "stories",
        "entry_id": str(ticket_id),
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
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"TAPD API GET /comments → HTTP {e.code}: {err_body[:500]}"
        ) from e
    if payload.get("status") != 1:
        raise RuntimeError(f"TAPD API failure: {payload.get('info')}")

    out: list[dict] = []
    for item in payload.get("data") or []:
        raw = item.get("Comment") if isinstance(item, dict) else None
        if not raw:
            continue
        # _normalize_comment 会读 description 富文本并 _strip_html
        normalized = _normalize_comment(raw, "stories", ticket_id)
        # 多保留一份原始 HTML 给 MD 渲染（_normalize_comment 已扁平化为 content）
        normalized["description_html"] = str(
            raw.get("description")
            or raw.get("content")
            or raw.get("comment")
            or ""
        )
        out.append(normalized)
    return out


# ── MD 文档渲染 ────────────────────────────────────────────────────────


def _date_part(created: str) -> str:
    """从 ISO/普通时间串提取 YYYY-MM-DD。"""
    if not created:
        return "unknown"
    if "T" in created:
        return created.split("T")[0]
    if " " in created:
        return created.split(" ")[0]
    return created


def _is_key_comment(content: str) -> bool:
    """是否含关键评审标记，用于 MD blockquote 突出。"""
    return bool(MARKER_PATTERN.search(content or ""))


def _resolve_render_content(comment: dict) -> str:
    """优先渲染原始 HTML→Markdown；缺失时退回已去标签的 content。"""
    html = comment.get("description_html")
    if html:
        md = _html_to_md(html)
        if md:
            return md
    return (comment.get("content") or "").strip()


def render_comments_md(
    comments: list[dict],
    ticket_id: str,
    last_synced_at: str,
) -> str:
    """生成完整 tapd-comment.md 内容。

    格式：
        ---
        ticket_id: "..."
        last_synced_at: "..."
        count: N
        ---

        ## YYYY-MM-DD

        ### YYYY-MM-DD HH:MM:SS — author

        {content...}

        > comment_id: ...

        关键评论用 `> ⚠️ 关键评论` blockquote 突出。
    """
    # 升序排序（最早 → 最新）
    sorted_comments = sorted(
        comments,
        key=lambda c: c.get("created", "") or "",
    )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for c in sorted_comments:
        grouped[_date_part(c.get("created") or "")].append(c)

    lines: list[str] = [
        "---",
        f'ticket_id: "{ticket_id}"',
        f'last_synced_at: "{last_synced_at}"',
        f"count: {len(sorted_comments)}",
        "---",
        "",
        "# TAPD 工单评论",
        "",
    ]

    for date in sorted(grouped.keys()):
        lines.append(f"## {date}")
        lines.append("")
        for comment in grouped[date]:
            created = comment.get("created") or ""
            author = comment.get("author") or "unknown"
            content = _resolve_render_content(comment)
            comment_id = comment.get("id") or ""

            lines.append(f"### {created} — {author}")
            lines.append("")
            if _is_key_comment(content):
                lines.append("> ⚠️ 关键评论")
                lines.append(">")
                for ln in content.splitlines() or [""]:
                    lines.append(f"> {ln}" if ln else ">")
            else:
                lines.append(content if content else "_(空)_")
            lines.append("")
            lines.append(f"> comment_id: {comment_id}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ── 需求变更检测 ─────────────────────────────────────────────────────
#
# 标签格式(新规范):
#   [REQUIREMENT-CHANGE]
#
#   <变更内容,可多行,直到下一个 [XXX] 标签或评论结束>
#
# 正则提取标签后的全部内容(允许 HTML 标签如 <p> / <br/> 残留,后续 strip)。

_REQ_CHANGE_RE = re.compile(
    r"\[\s*REQUIREMENT[-\s]+CHANGE\s*\]"      # 标签独立
    r"\s*(?:<br\s*/?>|<p[^>]*>|</p>|\s)*"     # 跨标签 / 空白
    r"(.+?)"                                  # 变更内容(贪婪到下一标签)
    r"(?=\[\s*[A-Z][A-Z0-9-]+\s*[:\]]|\Z)",   # 直到下一个 [XXX] 标签或评论结束
    re.IGNORECASE | re.DOTALL,
)

_HTML_INLINE_RE = re.compile(r"<[^>]+>")
_LEADING_TAG_RE = re.compile(r"^\s*\[[A-Z][A-Z0-9-]+\s*[:\]]")


def _clean_change_desc(raw: str) -> str:
    """清理 TAPD HTML 评论中的标签 / 多余空白,提取纯文本内容。

    若清理后剩余内容以另一个 [XXX] 标签开头(说明 [REQUIREMENT-CHANGE] 与下一标签紧邻,
    中间无实际变更内容),视为空 desc。
    """
    text = _HTML_INLINE_RE.sub("", raw or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if _LEADING_TAG_RE.match(text):
        return ""
    return text


def _extract_requirement_changes(
    comments: list[dict],
    existing_changes: list[dict],
) -> Optional[list[dict]]:
    """从评论列表里提取 [REQUIREMENT-CHANGE] 标签 + 下方变更内容。

    新格式(2026-05-29):
        [REQUIREMENT-CHANGE]

        响应增加 traceId 字段
        前端表格新增 status 列

    去重:已在 existing_changes 中(by comment_id)的不重复添加。
    无新增 → 返回 None (调用方据此跳过 update,避免无谓写入)。
    有新增 → 返回 existing_changes + 新条目,新条目 processed=false 待主流程响应。
    """
    existing_ids = {
        str(x.get("comment_id")) for x in existing_changes if x.get("comment_id")
    }
    new_entries: list[dict] = []
    for c in comments:
        content = c.get("content") or ""
        m = _REQ_CHANGE_RE.search(content)
        if not m:
            continue
        cid = str(c.get("id") or "")
        if not cid or cid in existing_ids:
            continue
        desc = _clean_change_desc(m.group(1))
        if not desc:
            # 标签命中但内容空 → 跳过(防止误判)
            continue
        new_entries.append({
            "comment_id": cid,
            "description": desc,
            "author": c.get("author"),
            "ts": c.get("created") or c.get("modified") or "",
            "processed": False,
        })
    if not new_entries:
        return None
    return list(existing_changes) + new_entries


# ── 主流程 ────────────────────────────────────────────────────────────


def cmd_fetch(args: argparse.Namespace) -> int:
    # 加载项目级 marker 配置,刷新模块级 MARKER_PATTERN。
    # CLI 进程级隔离,刷新只影响本次调用;_is_key_comment / finditer 都消费此全局变量。
    global MARKER_PATTERN
    import comments_cache as _cc
    _pattern = _load_marker_pattern()
    MARKER_PATTERN = _pattern
    _cc.MARKER_PATTERN = _pattern  # 同步 comments_cache 模块(highlight_markers 默认参数依赖)

    task_dir = STORE_DIR / args.story_id
    store = TaskJsonStore.load(task_dir)
    if not store.data.get("task_id"):
        print(json.dumps(
            {"ok": False,
             "error": f"task.json not found in {task_dir}; "
                      f"请先运行 description.py fetch 拉取工单"},
            ensure_ascii=False,
        ))
        return 1

    tapd = store.get_tapd() or {}
    ticket_id = args.ticket_id or tapd.get("ticket_id") or (tapd.get("raw") or {}).get("id")
    if not ticket_id:
        print(json.dumps(
            {"ok": False,
             "error": "ticket_id 未指定，且 task.json.tapd.ticket_id 缺失"},
            ensure_ascii=False,
        ))
        return 1

    workspace_id = _resolve_workspace_id(args.workspace_id, tapd)
    if not workspace_id:
        print(json.dumps(
            {"ok": False,
             "error": "workspace_id 未指定，且 task.json/project-config 均无 workspace_id"},
            ensure_ascii=False,
        ))
        return 1

    try:
        fetched = _fetch_comments_http(
            workspace_id=workspace_id,
            ticket_id=str(ticket_id),
            limit=args.limit,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    existing = list(tapd.get("comments_cache") or [])
    merged, changed = dedupe_comments(existing, fetched)

    # 需求变更检测: 提取 [REQUIREMENT-CHANGE] 标签 + 下方内容, 追加到 requirement_changes
    # (去重 by comment_id, 新条目 processed=false 待主流程处理)
    requirement_changes = _extract_requirement_changes(
        merged,
        existing_changes=list(tapd.get("requirement_changes") or []),
    )

    last_synced_at = datetime.now().isoformat()
    patch = {
        "comments_cache": merged,
        "last_synced_at": last_synced_at,
    }
    if requirement_changes is not None:
        patch["requirement_changes"] = requirement_changes
    store.update_tapd(patch)
    store.save()

    md_path = task_dir / COMMENTS_MD_FILENAME
    md_content = render_comments_md(merged, str(ticket_id), last_synced_at)
    task_dir.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_content, encoding="utf-8")

    # 关键标记摘要（方便流程门校验）
    # 防御(2026-05-29):同一评论命中 ≥2 种不同 marker = 评审「请求/指引」评论
    #   （列了 [CONSENSUS-APPROVED]/[CONSENSUS-REJECTED]/[REQUIREMENT-CHANGE] 多个示例供团队回复），
    #   并非真实评审结论,整条跳过——否则 consensus-push 发的指引评论会被误判为评审通过/打回,
    #   导致 flow 在无人真实评审时误推进。真实评审一条评论只含单一结论 marker。
    markers: list[dict] = []
    for c in merged:
        hits = [m.group(0) for m in MARKER_PATTERN.finditer(c.get("content") or "")]
        if len(set(hits)) >= 2:
            continue  # 指引/请求评论(含多种 marker 示例),跳过,不计入流程门判定
        for marker_text in hits:
            markers.append({
                "marker": marker_text,
                "comment_id": c.get("id"),
                "author": c.get("author"),
                "created": c.get("created"),
            })

    result = {
        "ok": True,
        "ticket_id": str(ticket_id),
        "workspace_id": workspace_id,
        "existing_count": len(existing),
        "fetched_count": len(fetched),
        "added_or_updated": len(changed),
        "total_count": len(merged),
        "md_path": str(md_path),
        "markers": markers,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TAPD 工单评论本地化同步（HTTP API → task.json.comments_cache + tapd-comment.md）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser(
        "fetch",
        help="直接调 TAPD HTTP API 拉评论并落地（需要 env TAPD_TOKEN）",
    )
    p_fetch.add_argument("--story-id", required=True, help="本地 story_id")
    p_fetch.add_argument("--ticket-id", default=None,
                         help="TAPD 工单 id；省略则从 task.json.tapd.ticket_id 取")
    p_fetch.add_argument("--workspace-id", default=None,
                         help="TAPD workspace_id；省略则从 task.json/project-config 取")
    p_fetch.add_argument("--limit", type=int, default=100,
                         help="拉取上限（TAPD 默认上限 200）")
    p_fetch.set_defaults(func=cmd_fetch)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
