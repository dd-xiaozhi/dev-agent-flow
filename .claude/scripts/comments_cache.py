"""评论缓存读写模块。

支持全量 TAPD 评论本地持久化，按时间排序，增量同步。

文件结构:
  .chatlabs/tapd/tickets/<ticket_id>/
  ├── <ticket_id>.json      # 现有工单缓存（快速索引）
  ├── comments.json          # 全量评论缓存
  └── _metadata.json         # 增量同步元数据
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict
from paths import TAPD_TICKETS_DIR, PROJECT_DIR


@dataclass
class Comment:
    """单条评论结构。"""
    id: str
    author: str
    created: str          # ISO8601
    updated: str           # ISO8601
    marker: Optional[str]  # 如 [CONSENSUS-APPROVED]
    description: str       # 评论正文
    description_hash: str  # sha256
    is_automation: bool    # 是否自动化标记评论
    is_read: bool          # 是否已处理


@dataclass
class CommentsCache:
    """评论缓存容器。"""
    ticket_id: str
    schema_version: str = "1.1"
    last_synced_at: str = ""
    comments: list = None

    def __post_init__(self):
        if self.comments is None:
            self.comments = []


@dataclass
class SyncMetadata:
    """增量同步元数据。"""
    ticket_id: str
    last_sync_at: str = ""
    last_etag: Optional[str] = None
    comment_count: int = 0
    hash_of_last_description: Optional[str] = None


def _ensure_ticket_dir(ticket_id: str) -> Path:
    """确保工单目录存在，返回目录路径。"""
    dir_path = TAPD_TICKETS_DIR / ticket_id
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _comments_file(ticket_id: str) -> Path:
    """评论缓存文件路径。"""
    return _ensure_ticket_dir(ticket_id) / "comments.json"


def _metadata_file(ticket_id: str) -> Path:
    """同步元数据文件路径。"""
    return _ensure_ticket_dir(ticket_id) / "_metadata.json"


def _compute_hash(text: str) -> str:
    """计算内容 SHA256 哈希。"""
    return f"sha256:{hashlib.sha256(text.encode()).hexdigest()[:16]}"


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _parse_comment(raw: dict) -> Comment:
    """将 API 返回的原始评论转换为 Comment 结构。"""
    description = raw.get("description", "")
    return Comment(
        id=str(raw.get("id", "")),
        author=raw.get("author", {}).get("name", raw.get("author", "unknown")),
        created=raw.get("created", ""),
        updated=raw.get("updated", raw.get("created", "")),
        marker=_extract_marker(description),
        description=description,
        description_hash=_compute_hash(description),
        is_automation=bool(_extract_marker(description)),
        is_read=False,
    )


def _extract_marker(description: str) -> Optional[str]:
    """从评论描述中提取标记（如 [CONSENSUS-APPROVED]）。"""
    import re
    # 匹配方括号包裹的标记
    patterns = [
        r"\[CONSENSUS-V\d+\]",
        r"\[CONSENSUS-APPROVED\]",
        r"\[CONSENSUS-REJECTED:[^\]]+\]",
        r"\[QA-PASSED\]",
        r"\[QA-REJECTED:[^\]]+\]",
        r"\[BLOCKER:[^\]]+\]",
    ]
    for pattern in patterns:
        match = re.search(pattern, description)
        if match:
            return match.group(0)
    return None


def load_cache(ticket_id: str) -> Optional[CommentsCache]:
    """加载已有评论缓存，不存在返回 None。"""
    cache_file = _comments_file(ticket_id)
    if not cache_file.exists():
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return CommentsCache(
            ticket_id=data.get("ticket_id", ticket_id),
            schema_version=data.get("schema_version", "1.1"),
            last_synced_at=data.get("last_synced_at", ""),
            comments=[Comment(**c) for c in data.get("comments", [])],
        )
    except (json.JSONDecodeError, TypeError) as e:
        # 损坏的缓存文件，返回 None 让调用方重新拉取
        return None


def save_cache(cache: CommentsCache) -> None:
    """保存评论缓存到文件。"""
    cache.last_synced_at = _now_iso()
    cache_file = _comments_file(cache.ticket_id)
    data = {
        "ticket_id": cache.ticket_id,
        "schema_version": cache.schema_version,
        "last_synced_at": cache.last_synced_at,
        "comments": [asdict(c) for c in cache.comments],
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def sync_comments(ticket_id: str, raw_comments: list) -> CommentsCache:
    """同步新评论到缓存，增量追加，按 created ASC 排序。

    Args:
        ticket_id: 工单 ID
        raw_comments: 从 TAPD API 拉取的原始评论列表

    Returns:
        更新后的 CommentsCache
    """
    cache = load_cache(ticket_id)
    if cache is None:
        cache = CommentsCache(ticket_id=ticket_id)

    existing_ids = {c.id for c in cache.comments}
    existing_hashes = {c.description_hash for c in cache.comments}

    for raw in raw_comments:
        comment = _parse_comment(raw)
        # 增量：跳过已存在的（按 ID 或 hash 判断）
        if comment.id in existing_ids:
            continue
        if comment.description_hash in existing_hashes:
            continue
        cache.comments.append(comment)

    # 按 created ASC 升序排序
    cache.comments.sort(key=lambda c: c.created)

    save_cache(cache)
    _update_metadata(ticket_id, len(cache.comments))

    return cache


def _update_metadata(ticket_id: str, comment_count: int) -> None:
    """更新同步元数据。"""
    meta_file = _metadata_file(ticket_id)
    meta = SyncMetadata(
        ticket_id=ticket_id,
        last_sync_at=_now_iso(),
        comment_count=comment_count,
    )
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(asdict(meta), f, ensure_ascii=False, indent=2)


def load_metadata(ticket_id: str) -> Optional[SyncMetadata]:
    """加载同步元数据。"""
    meta_file = _metadata_file(ticket_id)
    if not meta_file.exists():
        return None
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return SyncMetadata(**data)
    except (json.JSONDecodeError, TypeError):
        return None


def get_comments(
    ticket_id: str,
    since: Optional[str] = None,
    marker_filter: Optional[str] = None,
) -> list[Comment]:
    """获取评论列表，支持按时间和标记过滤。

    Args:
        ticket_id: 工单 ID
        since: 可选，ISO8601 时间字符串，只返回此时间之后的评论
        marker_filter: 可选，只返回包含此标记的评论

    Returns:
        符合条件的 Comment 列表
    """
    cache = load_cache(ticket_id)
    if cache is None:
        return []

    result = cache.comments
    if since:
        result = [c for c in result if c.created > since]
    if marker_filter:
        result = [c for c in result if marker_filter in (c.marker or "")]

    return result


def mark_as_read(ticket_id: str, comment_ids: list[str]) -> None:
    """将指定评论标记为已读。"""
    cache = load_cache(ticket_id)
    if cache is None:
        return

    id_set = set(comment_ids)
    for comment in cache.comments:
        if comment.id in id_set:
            comment.is_read = True

    save_cache(cache)