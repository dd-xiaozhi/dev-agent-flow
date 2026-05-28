"""task_index.py — _index.jsonl 读写与解析辅助

被 task.py 的 cmd_finalize / cmd_search / cmd_list 复用,以及 gc skill 的 --archive 复用。
本文件不做 CLI,只暴露纯函数。

职责:
  - read_index / append_index / update_index_entry — _index.jsonl 增改读
  - search_entries — 内存级过滤(module / contract / keyword / verdict)
  - parse_contract_for_meta — 从 contract.md / patch.md frontmatter + 正文提取 title / contracts
  - git_log_for_task — 调 git log --grep 收集 commit hash
  - infer_complexity_from_flow_id — flow_id → complexity 反推
  - quarter_of — datetime → 'YYYY-QN'

不依赖:
  - LLM(所有摘要由主 Claude 预先填到 task.json.workflow.summary)
  - flow-engine(只读 task.json)

依赖:
  - Python 标准库（路径常量在本文件顶部硬编码）
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/task/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
TASK_INDEX = PROJECT_DIR / ".chatlabs" / "reports" / "tasks" / "_index.jsonl"
ARCHIVE_DIR = PROJECT_DIR / ".chatlabs" / "task" / "archive"
ARCHIVE_INDEX = ARCHIVE_DIR / "_index.jsonl"

# ─────────────────────── flow_id → complexity 映射 ───────────────────────

_FLOW_TO_COMPLEXITY: dict[str, str] = {
    "bugfix-vibe": "vibe",
    "bugfix-plan": "plan",
    "bugfix-spec": "spec",
    "local-vibe": "vibe",
    "local-plan": "plan",
    "local-spec": "spec",
    "tapd-full": "spec",
}


def infer_complexity_from_flow_id(flow_id: Optional[str]) -> Optional[str]:
    """flow_id → complexity 反推,未知返回 None。"""
    if not flow_id:
        return None
    return _FLOW_TO_COMPLEXITY.get(flow_id)


# ─────────────────────── _index.jsonl 读写 ───────────────────────

def read_index(path: Path = TASK_INDEX) -> list[dict]:
    """读 jsonl 索引,损坏行自动跳过(首次损坏时备份原文件)。

    path 缺省读主索引(TASK_INDEX),也可传归档索引路径。
    """
    if not path.exists():
        return []
    rows: list[dict] = []
    bad_lines = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad_lines += 1
    if bad_lines:
        backup = Path(str(path) + ".corrupt.bak")
        if not backup.exists():
            shutil.copy(path, backup)
    return rows


def append_index(entry: dict, path: Path = TASK_INDEX) -> None:
    """append 单条 entry 到 jsonl。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_index_entry(
    task_id: str,
    patch: dict,
    path: Path = TASK_INDEX,
) -> bool:
    """按 task_id 定位 entry 并合并 patch(浅 merge,patch 字段覆盖原值)。

    返回 True 表示找到并更新;False 表示 entry 不存在(调用方可决定是否 append)。
    """
    if not path.exists():
        return False
    rows = read_index(path)
    hit = False
    new_lines: list[str] = []
    for row in rows:
        if row.get("task_id") == task_id:
            row.update(patch)
            hit = True
        new_lines.append(json.dumps(row, ensure_ascii=False))
    if hit:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return hit


def upsert_index_entry(
    task_id: str,
    entry: dict,
    path: Path = TASK_INDEX,
) -> str:
    """update 或 append——entry 不存在时新增。返回 'updated' / 'appended'。"""
    if update_index_entry(task_id, entry, path):
        return "updated"
    append_index(entry, path)
    return "appended"


def remove_index_entries(
    task_ids: Iterable[str],
    path: Path = TASK_INDEX,
) -> int:
    """从 jsonl 移除指定 task_id 的 entry,返回实际移除数。"""
    target = set(task_ids)
    if not target or not path.exists():
        return 0
    rows = read_index(path)
    kept: list[str] = []
    removed = 0
    for row in rows:
        if row.get("task_id") in target:
            removed += 1
            continue
        kept.append(json.dumps(row, ensure_ascii=False))
    if removed:
        if kept:
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        else:
            path.unlink()  # 空索引文件直接删
    return removed


# ─────────────────────── 检索 ───────────────────────

def _entry_text_haystack(entry: dict) -> str:
    """把 entry 中所有可全文匹配的字符串拼成一个 haystack(小写)。"""
    parts: list[str] = []
    for key in ("title", "one_liner"):
        v = entry.get(key)
        if isinstance(v, str):
            parts.append(v)
    for key in ("tags", "keywords", "key_decisions", "modules", "contracts"):
        v = entry.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    return "\n".join(parts).lower()


def search_entries(
    entries: list[dict],
    module: Optional[str] = None,
    contract: Optional[str] = None,
    keyword: Optional[str] = None,
    verdict: Optional[str] = None,
    task_type: Optional[str] = None,
    complexity: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[dict]:
    """内存级过滤。多个条件之间 AND;list 字段 contains 匹配;keyword 全文模糊。"""
    out: list[dict] = []
    kw_lower = keyword.lower() if keyword else None

    for entry in entries:
        if task_type and entry.get("task_type") != task_type:
            continue
        if complexity and entry.get("complexity") != complexity:
            continue
        if verdict and entry.get("verdict") != verdict:
            continue
        if module:
            mods = entry.get("modules") or []
            if module not in mods:
                continue
        if contract:
            contracts = entry.get("contracts") or []
            c_lower = contract.lower()
            if not any(c_lower in str(c).lower() for c in contracts):
                continue
        if kw_lower:
            haystack = _entry_text_haystack(entry)
            if kw_lower not in haystack:
                continue
        out.append(entry)

    # 优先 completed_at 倒序,缺失靠后
    out.sort(
        key=lambda e: e.get("completed_at") or e.get("updated_at") or "",
        reverse=True,
    )
    if limit and limit > 0:
        out = out[:limit]
    return out


# ─────────────────────── 解析辅助 ───────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
_HTTP_VERB_RE = re.compile(
    r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-/{}.:?=&%]+)",
    re.IGNORECASE,
)


def parse_frontmatter_title(text: str) -> Optional[str]:
    """从 markdown frontmatter 取 title 字段。"""
    m = _FRONTMATTER_RE.search(text)
    if not m:
        return None
    body = m.group(1)
    tm = _TITLE_RE.search(body)
    if not tm:
        return None
    title = tm.group(1).strip().strip('"').strip("'")
    return title or None


def extract_http_endpoints(text: str, limit: int = 20) -> list[str]:
    """粗匹配 'METHOD /path' 形式的端点,返回去重列表。"""
    seen: set[str] = set()
    out: list[str] = []
    for m in _HTTP_VERB_RE.finditer(text):
        verb = m.group(1).upper()
        path = m.group(2)
        endpoint = f"{verb} {path}"
        if endpoint not in seen:
            seen.add(endpoint)
            out.append(endpoint)
            if len(out) >= limit:
                break
    return out


def parse_contract_for_meta(task_dir: Path) -> dict:
    """从 task 目录的 contract.md / spec.md / patch.md 提取 title + contracts。

    扫描优先级:contract.md > patch.md(取 title) / spec.md > contract.md(取 contracts)。
    缺失文件不报错,返回字段为空。
    """
    title: Optional[str] = None
    contracts: list[str] = []

    for fname in ("contract.md", "patch.md"):
        fpath = task_dir / fname
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8", errors="replace")
            title = title or parse_frontmatter_title(text)
            if fname == "contract.md":
                contracts = extract_http_endpoints(text)
            break

    spec_path = task_dir / "spec.md"
    if spec_path.exists():
        spec_text = spec_path.read_text(encoding="utf-8", errors="replace")
        spec_endpoints = extract_http_endpoints(spec_text)
        # spec 端点更准确,优先取 spec 的
        if spec_endpoints:
            contracts = spec_endpoints

    return {"title": title, "contracts": contracts}


# ─────────────────────── git log ───────────────────────

def git_log_for_task(task_id: str, max_count: int = 50) -> list[str]:
    """git log --grep=<task_id> 收集 commit short hash。

    不抛异常——非 git 仓库 / git 命令失败时返回空 list。
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                f"--grep={task_id}",
                f"--max-count={max_count}",
                "--format=%h",
            ],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ─────────────────────── 季度归档辅助 ───────────────────────

def quarter_of(dt: datetime) -> str:
    """datetime → 'YYYY-QN'(Q1=1-3 月, Q2=4-6, Q3=7-9, Q4=10-12)。"""
    q = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{q}"


def archive_quarter_index(quarter: str) -> Path:
    """归档季度索引路径,如 archive/2026-Q2/_index.jsonl。"""
    return ARCHIVE_DIR / quarter / "_index.jsonl"


def rebuild_archive_master_index() -> int:
    """重建 archive/_index.jsonl 总索引,cat 各季度索引。返回总 entry 数。"""
    if not ARCHIVE_DIR.exists():
        return 0
    all_entries: list[str] = []
    for quarter_dir in sorted(ARCHIVE_DIR.iterdir()):
        if not quarter_dir.is_dir():
            continue
        qidx = quarter_dir / "_index.jsonl"
        if qidx.exists():
            all_entries.extend(
                line for line in qidx.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
    ARCHIVE_INDEX.parent.mkdir(parents=True, exist_ok=True)
    if all_entries:
        ARCHIVE_INDEX.write_text("\n".join(all_entries) + "\n", encoding="utf-8")
    elif ARCHIVE_INDEX.exists():
        ARCHIVE_INDEX.unlink()
    return len(all_entries)
