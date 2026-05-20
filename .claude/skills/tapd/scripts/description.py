"""
description.py — TAPD 工单详情落地脚本

职责（仅做一件事）：
1. 拉取 TAPD Story → 提取 description（HTML）→ 转 Markdown → 写入 source/description.md
2. 提取工单元信息（status / owner / iteration_id 等）→ 更新 task.json.tapd.raw

子命令：
- fetch  直接调 TAPD HTTP API（Bearer ${TAPD_TOKEN}）拉取工单后落地（推荐）
- save   接受 MCP `get_stories_or_tasks` 返回的 JSON（stdin/--input），落地（兼容旧链路）

强约束（不要扩展）：
- source/ 目录下**只**生成 description.md（没有 raw.html、metadata.json 等冗余物）
- 元信息**只**写入 task.json.tapd（SSOT，避免重复存储）
- HTML→Markdown 只做"无损还原结构"的最小变换，不做语义重写

Usage:
    # 端到端拉取（推荐，需要 env TAPD_TOKEN）
    python description.py fetch --story-id sf-account-merge --ticket-id 1152676229001047022

    # 从 stdin 读 MCP 返回（兼容旧链路）
    python description.py save --story-id 1046733 < mcp_output.json

    # 或从文件读
    python description.py save --story-id 1046733 --input /tmp/mcp_output.json
"""
import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 共享基础设施在 .claude/scripts/（本脚本位于 .claude/skills/tapd/scripts/，回退 2 级到 .claude/）
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from paths import PROJECT_CONFIG, STORE_DIR  # noqa: E402
from task_store import TaskJsonStore  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── HTML → Markdown 转换 ──────────────────────────────────────────────


def html_to_markdown(html: str) -> str:
    """把 TAPD 富文本 HTML 转 Markdown。

    TAPD HTML 特点：内容主要由 <p>...</p> 段落构成，<br /> 表示换行，
    标题用 <h1>~<h6>，强调用 <strong>/<em>。本函数处理常见标签，
    保留代码块、表格、mermaid 等 Markdown 原文格式。
    """
    text = html

    # <br /> → 换行
    text = re.sub(r'<br\s*/?>', '\n', text)

    # <hN>...</hN> → ## ... \n
    def _heading(m):
        level = int(m.group(1))
        inner = re.sub(r'</?span[^>]*>', '', m.group(2)).strip()
        return f'\n{"#" * level} {inner}\n'
    text = re.sub(
        r'<h([1-6])[^>]*>(.*?)</h\1>',
        _heading, text, flags=re.DOTALL,
    )

    # <p>...</p> → 内容 + 换行（空 <p> 视作空行）
    def _para(m):
        inner = re.sub(r'</?span[^>]*>', '', m.group(1)).strip()
        if not inner or inner == '\n':
            return '\n'
        return inner + '\n'
    text = re.sub(
        r'<p[^>]*>(.*?)</p>',
        _para, text, flags=re.DOTALL,
    )

    # <strong>/<b> → **...**
    text = re.sub(
        r'<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>',
        r'**\1**', text, flags=re.DOTALL,
    )
    # <em>/<i> → *...*
    text = re.sub(
        r'<(?:em|i)[^>]*>(.*?)</(?:em|i)>',
        r'*\1*', text, flags=re.DOTALL,
    )

    # 兜底：去掉剩余 span 标签
    text = re.sub(r'</?span[^>]*>', '', text)

    # HTML 实体解码（&nbsp; / &lt; / &gt; / &amp; ...）
    text = html_mod.unescape(text)
    # 不间断空格 → 普通空格
    text = text.replace('\xa0', ' ')

    # 多余空行压缩
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


# ── MCP 返回解析 ──────────────────────────────────────────────────────


def parse_mcp_payload(payload) -> dict:
    """从 MCP get_stories_or_tasks 的返回里提取 Story 字段。

    兼容三种输入形态：
    - 顶层 dict 含 "result" (JSON string)
    - 顶层 dict 直接是解析后结构（含 "data" / "url_template"）
    - 顶层 dict 就是 Story 字段本身（含 id/name/description）
    """
    obj = payload
    # 形态 1: {"result": "<json string>"}
    if isinstance(obj, dict) and isinstance(obj.get("result"), str):
        obj = json.loads(obj["result"])
    # 形态 2: {"data": [{"Story": {...}}], "url_template": "..."}
    if isinstance(obj, dict) and "data" in obj:
        data = obj["data"]
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                # 兼容 Story / Task / Bug 三种 wrapper
                for k in ("Story", "Task", "Bug"):
                    if k in first:
                        return first[k]
                return first
    # 形态 3: 直接是 Story dict
    if isinstance(obj, dict) and "description" in obj:
        return obj
    raise ValueError("无法从 MCP 返回中定位 Story 字段；请检查输入结构")


# ── 主要落地函数 ──────────────────────────────────────────────────────


_TAPD_META_FIELDS = (
    "id", "name", "status", "priority_label", "owner", "creator",
    "iteration_id", "iteration_name", "workitem_type_id", "category_id",
    "category_name", "developer", "cc", "begin", "due", "size",
    "created", "modified", "module", "version", "release_id", "parent_id",
)


def save_description(
    story_id: str,
    payload: dict,
    workspace_id: Optional[str] = None,
) -> dict:
    """把 MCP 返回的工单详情落地到 source/description.md + task.json.tapd.raw。

    Returns:
        dict：含 description_path / task_json_path / extracted_meta_keys
    """
    story = parse_mcp_payload(payload)

    description_html = story.get("description") or ""
    if not description_html.strip():
        raise ValueError(f"Story {story.get('id')} description 为空")

    description_md = html_to_markdown(description_html)

    # 写 source/description.md（含轻量 frontmatter，仅记录可追溯字段）
    task_dir = STORE_DIR / story_id
    source_dir = task_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    description_path = source_dir / "description.md"

    fm_lines = [
        "---",
        f"source: TAPD Story",
        f'ticket_id: "{story.get("id", "")}"',
        f'pulled_at: "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"',
        "---",
        "",
        f"# {story.get('name', '(untitled)')}",
        "",
    ]
    description_path.write_text(
        "\n".join(fm_lines) + description_md, encoding="utf-8",
    )

    # 元信息进 task.json.tapd.raw（SSOT）
    store = TaskJsonStore.load(task_dir)
    if not store.data.get("task_id"):
        # task.json 缺失则自动创建（fetch 入口允许直接拉取新工单）
        store = TaskJsonStore.create(
            task_dir,
            task_type="store",
            story_id=story_id,
            trigger="tapd-fetch",
        )

    raw_meta = {k: story.get(k) for k in _TAPD_META_FIELDS if k in story}
    tapd_patch: dict = {
        "ticket_id": str(story.get("id", "")),
        "entity_type": "stories",
        "raw": raw_meta,
        "raw_pulled_at": now_iso(),
    }
    if workspace_id:
        tapd_patch["workspace_id"] = str(workspace_id)
    # local_mapping 保留累积（不覆盖已有的）
    existing_mapping = (store.get_tapd() or {}).get("local_mapping") or {}
    existing_mapping.setdefault("story_id", story_id)
    tapd_patch["local_mapping"] = existing_mapping

    store.update_tapd(tapd_patch)
    store.save()

    return {
        "ok": True,
        "description_path": str(description_path),
        "task_json_path": str(store.path),
        "extracted_meta_keys": sorted(raw_meta.keys()),
        "description_chars": len(description_md),
    }


# ── TAPD HTTP API ─────────────────────────────────────────────────────


_STORY_FIELDS = (
    "id,name,description,status,priority_label,owner,creator,"
    "iteration_id,iteration_name,workitem_type_id,category_id,category_name,"
    "developer,cc,begin,due,size,created,modified,module,version,"
    "release_id,parent_id"
)


def _resolve_workspace_id(explicit: Optional[str]) -> Optional[str]:
    """workspace_id 解析：参数 > project-config.tapd.workspace_id。"""
    if explicit:
        return str(explicit)
    if PROJECT_CONFIG.exists():
        try:
            cfg = json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        wid = (cfg.get("tapd") or {}).get("workspace_id")
        if wid:
            return str(wid)
    return None


def _tapd_get_story(workspace_id: str, ticket_id: str) -> dict:
    """GET /stories?workspace_id=&id=&fields=...，返回 Story dict。

    参考 push_wiki.py 的 _tapd_request 实现方式，直读 ${TAPD_TOKEN}。
    """
    token = os.environ.get("TAPD_TOKEN")
    if not token:
        raise RuntimeError("env TAPD_TOKEN not set; cannot fetch directly")
    params = urllib.parse.urlencode({
        "workspace_id": str(workspace_id),
        "id": str(ticket_id),
        "fields": _STORY_FIELDS,
    })
    url = f"https://api.tapd.cn/stories?{params}"
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
            f"TAPD API GET /stories → HTTP {e.code}: {err_body[:500]}"
        ) from e
    if payload.get("status") != 1:
        raise RuntimeError(f"TAPD API failure: {payload.get('info')}")
    data = payload.get("data") or []
    if not data:
        raise RuntimeError(
            f"TAPD GET /stories returned empty data for ticket_id={ticket_id}"
        )
    first = data[0]
    if isinstance(first, dict) and "Story" in first:
        return first["Story"]
    if isinstance(first, dict):
        return first
    raise RuntimeError(f"unexpected TAPD payload shape: {type(first)}")


# ── CLI ───────────────────────────────────────────────────────────────


def cmd_fetch(args: argparse.Namespace) -> int:
    workspace_id = _resolve_workspace_id(args.workspace_id)
    if not workspace_id:
        print(json.dumps(
            {"ok": False,
             "error": "workspace_id 未指定，且 project-config.tapd.workspace_id 缺失"},
            ensure_ascii=False,
        ))
        return 1
    try:
        story = _tapd_get_story(workspace_id, args.ticket_id)
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    try:
        result = save_description(
            story_id=args.story_id,
            payload=story,  # 直接传 Story dict，parse_mcp_payload 会兼容
            workspace_id=workspace_id,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    result["source"] = "http"
    result["ticket_id"] = str(args.ticket_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_save(args: argparse.Namespace) -> int:
    if args.input:
        raw_text = Path(args.input).read_text(encoding="utf-8")
    else:
        raw_text = sys.stdin.read()
    if not raw_text.strip():
        print(json.dumps(
            {"ok": False, "error": "no input (stdin/--input 都为空)"},
            ensure_ascii=False,
        ))
        return 1
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(json.dumps(
            {"ok": False, "error": f"输入不是合法 JSON: {e}"},
            ensure_ascii=False,
        ))
        return 1

    try:
        result = save_description(
            story_id=args.story_id,
            payload=payload,
            workspace_id=args.workspace_id,
        )
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TAPD 工单详情落地脚本（description.md + task.json.tapd.raw）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    # fetch：直接调 TAPD HTTP API（推荐）
    p_fetch = sub.add_parser(
        "fetch",
        help="直接调 TAPD HTTP API 拉取工单并落地（需要 env TAPD_TOKEN）",
    )
    p_fetch.add_argument("--story-id", required=True, help="本地 story_id（短 id）")
    p_fetch.add_argument("--ticket-id", required=True, help="TAPD 工单 id（数字 id）")
    p_fetch.add_argument(
        "--workspace-id", default=None,
        help="TAPD workspace_id；省略则读 project-config.tapd.workspace_id",
    )
    p_fetch.set_defaults(func=cmd_fetch)

    # save：兼容旧链路（MCP JSON 输入）
    p_save = sub.add_parser(
        "save",
        help="[deprecated] 接受 MCP get_stories_or_tasks JSON 输入落地（兼容旧链路）",
    )
    p_save.add_argument("--story-id", required=True, help="本地 story_id（短 id）")
    p_save.add_argument("--workspace-id", default=None,
                        help="TAPD workspace_id（可选，写入 task.json.tapd.workspace_id）")
    p_save.add_argument("--input", default=None,
                        help="MCP get_stories_or_tasks 返回的 JSON 文件路径；省略则读 stdin")
    p_save.set_defaults(func=cmd_save)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
