"""Checklog 创建与管理模块。

支持需求变更检查记录的创建、查询、更新。

文件结构:
  .chatlabs/stories/<story_id>/checklogs/
  ├── _index.jsonl              # append-only 索引
  └── CHECK-001-20260422-100000.md
"""
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, asdict, field
from paths import STORIES_DIR, PROJECT_DIR


@dataclass
class ChecklogEntry:
    """Checklog 索引条目。"""
    check_id: str
    story_id: str
    trigger: str           # requirement_change | consensus_rejected | manual
    trigger_source: str
    created_at: str         # ISO8601
    file_path: str          # 相对于 PROJECT_DIR
    check_type: str = "incremental"  # incremental | full
    status: str = "pending"  # pending | applied | skipped
    contract_version_before: Optional[str] = None
    contract_version_after: Optional[str] = None


@dataclass
class ChecklogContent:
    """Checklog 文档内容（YAML frontmatter + Markdown 正文）。"""
    check_id: str
    story_id: str
    trigger: str
    trigger_source: str
    created_at: str
    contract_version_before: Optional[str] = None
    contract_version_after: Optional[str] = None
    check_type: str = "incremental"
    status: str = "pending"
    trigger_author: Optional[str] = None
    impact_analysis: list = field(default_factory=list)
    recommended_actions: list = field(default_factory=list)
    applied_at: Optional[str] = None
    applied_by: Optional[str] = None
    raw_description: str = ""  # TAPD 原始描述变更内容


def _ensure_checklogs_dir(story_id: str) -> Path:
    """确保 checklogs 目录存在，返回目录路径。"""
    dir_path = STORIES_DIR / story_id / "checklogs"
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def _checklogs_dir(story_id: str) -> Path:
    """返回 checklogs 目录路径。"""
    return STORIES_DIR / story_id / "checklogs"


def _index_file(story_id: str) -> Path:
    """返回 _index.jsonl 文件路径。"""
    return _checklogs_dir(story_id) / "_index.jsonl"


def _checklog_file(story_id: str, check_id: str, timestamp: str) -> Path:
    """返回 checklog markdown 文件路径。"""
    return _checklogs_dir(story_id) / f"{check_id}-{timestamp}.md"


def _now_iso() -> str:
    """返回当前 UTC 时间 ISO8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


def _generate_check_id(story_id: str, index_path: Path) -> str:
    """生成新的 check_id（CHECK-001, CHECK-002...）。"""
    next_num = 1
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    check_id = entry.get("check_id", "")
                    # 提取数字部分
                    match = re.search(r"CHECK-(\d+)", check_id)
                    if match:
                        num = int(match.group(1))
                        next_num = max(next_num, num + 1)
                except json.JSONDecodeError:
                    continue
    return f"CHECK-{next_num:03d}"


def _timestamp_now() -> str:
    """生成文件名用的时间戳 YYYYMMDD-HHMMSS。"""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _parse_impact_analysis(content: str) -> list[dict]:
    """解析 checklog 内容中的影响分析表格。"""
    # 简单解析：找到表格行，提取章节和影响程度
    impacts = []
    lines = content.split("\n")
    in_table = False
    for line in lines:
        if "§" in line or "页面结构" in line or "接口契约" in line:
            in_table = True
        if in_table and "|" in line:
            # 解析表格行
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3 and parts[1]:
                impacts.append({
                    "section": parts[1],
                    "impact": parts[2] if len(parts) > 2 else "未知",
                    "note": parts[3] if len(parts) > 3 else "",
                })
    return impacts


def create_checklog(
    story_id: str,
    trigger: str,
    trigger_source: str,
    contract_version_before: Optional[str] = None,
    check_type: str = "incremental",
    trigger_author: Optional[str] = None,
    raw_description: str = "",
    impact_analysis: list = None,
    recommended_actions: list = None,
) -> ChecklogEntry:
    """创建新的 checklog 条目。

    Args:
        story_id: 故事 ID
        trigger: 触发类型 (requirement_change | consensus_rejected | manual)
        trigger_source: 触发来源 (tapd_description_updated | consensus_rejected | manual_trigger)
        contract_version_before: 变更前的契约版本
        check_type: 检查类型 (incremental | full)
        trigger_author: 触发人（如 PM 名字）
        raw_description: 原始描述变更内容
        impact_analysis: 影响分析列表
        recommended_actions: 建议动作列表

    Returns:
        ChecklogEntry 对象
    """
    if impact_analysis is None:
        impact_analysis = []
    if recommended_actions is None:
        recommended_actions = []

    checklogs_dir = _ensure_checklogs_dir(story_id)
    index_path = _index_file(story_id)

    check_id = _generate_check_id(story_id, index_path)
    timestamp = _timestamp_now()
    created_at = _now_iso()

    # 构建 checklog 文件内容
    content = _build_checklog_content(
        check_id=check_id,
        story_id=story_id,
        trigger=trigger,
        trigger_source=trigger_source,
        created_at=created_at,
        contract_version_before=contract_version_before,
        check_type=check_type,
        trigger_author=trigger_author,
        raw_description=raw_description,
        impact_analysis=impact_analysis,
        recommended_actions=recommended_actions,
    )

    # 写入 markdown 文件
    file_path = _checklog_file(story_id, check_id, timestamp)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 更新索引文件（append-only）
    entry = ChecklogEntry(
        check_id=check_id,
        story_id=story_id,
        trigger=trigger,
        trigger_source=trigger_source,
        created_at=created_at,
        file_path=str(file_path.relative_to(PROJECT_DIR)),
        check_type=check_type,
        status="pending",
        contract_version_before=contract_version_before,
    )
    with open(index_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")

    return entry


def _build_checklog_content(
    check_id: str,
    story_id: str,
    trigger: str,
    trigger_source: str,
    created_at: str,
    contract_version_before: Optional[str],
    check_type: str,
    trigger_author: Optional[str],
    raw_description: str,
    impact_analysis: list,
    recommended_actions: list,
) -> str:
    """构建 checklog markdown 文件内容。"""
    # frontmatter
    frontmatter = f"""---
check_id: {check_id}
story_id: {story_id}
trigger: {trigger}
trigger_source: {trigger_source}
created_at: {created_at}
contract_version_before: {contract_version_before or 'null'}
contract_version_after: null
check_type: {check_type}
status: pending
---

# 需求变更检查报告

> **check_id**: {check_id} | **story_id**: {story_id} | **created**: {created_at}

## 变更来源

| 属性 | 值 |
|------|-----|
| 触发类型 | {trigger} |
| 触发来源 | {trigger_source} |
| 触发人 | {trigger_author or '系统'} |
| 检查类型 | {check_type} |

"""
    # 影响分析表格
    impact_table = "## 影响分析\n\n| 章节 | 影响程度 | 说明 |\n|------|---------|------|\n"
    if impact_analysis:
        for item in impact_analysis:
            section = item.get("section", "未知")
            impact = item.get("impact", "未知")
            note = item.get("note", "")
            impact_table += f"| {section} | {impact} | {note} |\n"
    else:
        impact_table += "| — | — | 暂未评估 |\n"

    # 建议动作
    actions = "## 建议动作\n\n"
    if recommended_actions:
        for i, action in enumerate(recommended_actions, 1):
            actions += f"{i}. {action}\n"
    else:
        actions += "- 暂无建议动作\n"

    # 原始描述变更
    raw_section = ""
    if raw_description:
        raw_section = f"""

## 原始变更内容

<details>
<summary>点击展开 TAPD 描述变更</summary>

{raw_description}

</details>

"""

    # 应用记录
    applied_section = """

## 应用记录

- **applied_at**: null
- **applied_by**: null

"""

    return frontmatter + impact_table + actions + raw_section + applied_section


def load_checklogs(story_id: str, status: Optional[str] = None) -> list[ChecklogEntry]:
    """加载 checklog 索引条目。

    Args:
        story_id: 故事 ID
        status: 可选，只返回指定状态的条目

    Returns:
        ChecklogEntry 列表
    """
    index_path = _index_file(story_id)
    if not index_path.exists():
        return []

    entries = []
    with open(index_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                checklog = ChecklogEntry(**entry)
                if status is None or checklog.status == status:
                    entries.append(checklog)
            except json.JSONDecodeError:
                continue

    return entries


def load_checklog_content(story_id: str, check_id: str) -> Optional[ChecklogContent]:
    """加载 checklog markdown 文件内容。"""
    checklogs_dir = _checklogs_dir(story_id)
    # 查找对应的 md 文件
    pattern = f"{check_id}-*.md"
    matches = list(checklogs_dir.glob(pattern))
    if not matches:
        return None

    file_path = matches[0]
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 解析 frontmatter
    frontmatter = {}
    body_lines = []
    in_frontmatter = False
    for line in content.split("\n"):
        if line.strip() == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter:
            if ":" in line:
                key, _, value = line.partition(":")
                frontmatter[key.strip()] = value.strip()
        else:
            body_lines.append(line)

    return ChecklogContent(
        check_id=frontmatter.get("check_id", ""),
        story_id=frontmatter.get("story_id", ""),
        trigger=frontmatter.get("trigger", ""),
        trigger_source=frontmatter.get("trigger_source", ""),
        created_at=frontmatter.get("created_at", ""),
        contract_version_before=frontmatter.get("contract_version_before"),
        contract_version_after=frontmatter.get("contract_version_after"),
        check_type=frontmatter.get("check_type", "incremental"),
        status=frontmatter.get("status", "pending"),
        raw_description=raw_description_from_body(body_lines),
    )


def raw_description_from_body(body_lines: list[str]) -> str:
    """从 checklog 正文提取原始变更内容。"""
    in_raw_section = False
    lines = []
    for line in body_lines:
        if "原始变更内容" in line:
            in_raw_section = True
            continue
        if in_raw_section:
            if line.startswith("## ") and "原始变更内容" not in line:
                break
            lines.append(line)
    return "\n".join(lines).strip()


def update_checklog_status(
    story_id: str,
    check_id: str,
    new_status: str,
    contract_version_after: Optional[str] = None,
    applied_by: Optional[str] = None,
) -> bool:
    """更新 checklog 状态。

    Args:
        story_id: 故事 ID
        check_id: check ID
        new_status: 新状态 (applied | skipped)
        contract_version_after: 变更后的契约版本
        applied_by: 应用人

    Returns:
        是否成功
    """
    checklogs_dir = _checklogs_dir(story_id)
    pattern = f"{check_id}-*.md"
    matches = list(checklogs_dir.glob(pattern))
    if not matches:
        return False

    file_path = matches[0]
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 更新 frontmatter 中的 status
    import re
    content = re.sub(
        r"^status: .+$",
        f"status: {new_status}",
        content,
        flags=re.MULTILINE,
    )

    if contract_version_after:
        content = re.sub(
            r"^contract_version_after: .+$",
            f"contract_version_after: {contract_version_after}",
            content,
            flags=re.MULTILINE,
        )

    if new_status == "applied" and applied_by:
        content = re.sub(
            r"\*\*applied_by\*\*: .+$",
            f"**applied_by**: {applied_by}",
            content,
            flags=re.MULTILINE,
        )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # 更新索引文件中的状态
    index_path = _index_file(story_id)
    if index_path.exists():
        lines = []
        with open(index_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("check_id") == check_id:
                        entry["status"] = new_status
                        if contract_version_after:
                            entry["contract_version_after"] = contract_version_after
                    lines.append(json.dumps(entry, ensure_ascii=False))
                except json.JSONDecodeError:
                    lines.append(line.strip())
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    return True


def get_pending_checklogs(story_id: str) -> list[ChecklogEntry]:
    """获取待处理的 checklog 列表。"""
    return load_checklogs(story_id, status="pending")