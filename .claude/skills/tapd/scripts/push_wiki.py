"""
push_wiki.py — TAPD Wiki 推送（prepare 拼装 + push 直发 + record 回写）

三个子命令：
  prepare  读 contract.md 与 project-config，输出完整 wiki body JSON 到 stdout（不调外部）
  push     直接调 TAPD HTTP API（Bearer ${TAPD_TOKEN}）推送 wiki，避开手抄；推送后自动 record
  record   推送成功后回写 task.json.tapd.{wiki_id, wiki_url, consensus_version, ...}

Usage:
    # 端到端推送（推荐：自动拼装 + 调 API + 回写）
    python push_wiki.py push --story-id 1046733

    # 只拼装(不推送),输出 stdout
    python push_wiki.py prepare --story-id 1046733

    # 推送被打回后重做,版本号+1
    python push_wiki.py push --story-id 1046733 --bump-version
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# 共享基础设施
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from paths import STORE_DIR, PROJECT_DIR  # noqa: E402
from task_store import TaskJsonStore  # noqa: E402

PROJECT_CONFIG = PROJECT_DIR / ".chatlabs" / "project-config.json"
CONSENSUS_ROOT_WIKI_NAME = "共识文档"


def fail(msg: str, **extra) -> dict:
    out = {"ok": False, "error": msg}
    out.update(extra)
    return out


def load_project_config() -> dict:
    if not PROJECT_CONFIG.exists():
        return {}
    return json.loads(PROJECT_CONFIG.read_text(encoding="utf-8"))


def format_pm_mention(pm_list: list[dict]) -> str:
    """生成 @PM 提及串，如 @郭沅宜(TinaGuo)。多 PM 用顿号连接。"""
    parts = []
    for pm in pm_list or []:
        user = pm.get("user")
        nick = pm.get("nick")
        if user and nick:
            parts.append(f"@{user}({nick})")
        elif nick:
            parts.append(f"@{nick}")
        elif user:
            parts.append(f"@{user}")
    return "、".join(parts) if parts else "@PM"


def build_footer(
    pm_mention: str,
    consensus_version_next: int,
    contract_path: Path,
    story_url: Optional[str] = None,
) -> str:
    """拼接评审 footer。

    注意：TAPD Wiki 没有获取评论的 API,因此评审评论统一在**对应工单(Story)**下进行。
    `/tapd-consensus-fetch` 通过 `get_comments(entry_type=stories, entry_id=<ticket_id>)`
    拉评论，检测 `[CONSENSUS-APPROVED]` / `[CONSENSUS-REJECTED:<原因>]` 标记。
    """
    story_link = (
        f"\n>\n> **工单链接**：{story_url}（点击进入对应 Story 评论区）"
        if story_url else ""
    )
    return f"""

---

## 评审说明（请 PM 审核）

> {pm_mention} 本契约 v{consensus_version_next}.0.0 由 doc-librarian 基于 TAPD Story description 生成，**完整版**（{contract_path.stat().st_size // 1024}K）。{story_link}
>
> **审核流程（评论位置：对应 TAPD 工单的评论区，不在本 Wiki 下）**：
> - ✅ **通过**：在**工单评论区**留言 `[CONSENSUS-APPROVED]` → 主流程通过 `/tapd-consensus-fetch` 拉取工单评论后自动推进到 planner 阶段
> - ❌ **打回**：在**工单评论区**留言 `[CONSENSUS-REJECTED: <具体原因>]` → 主流程自动回退到 doc-librarian 重新生成契约（版本 +1，本 Wiki 同步更新）
>
> **为何不在 Wiki 下评论**：TAPD Wiki 暂无单独获取评论的 API，无法被流程自动检测；所有评审/QA/工时事件统一通过**工单评论**承载，并同步到本地 `tapd-comment.md` 留痕。
>
> **重点审核项**：
> 1. 业务规则（BR-XX）是否完整覆盖业务语义
> 2. 验收标准（AC-XXX）是否每条都可独立测试
> 3. TBD 项是否需要在本期解决
> 4. 对外契约不变项（异常类型 / HTTP 端点 / 调用方代码 / 错误码）的强承诺
"""


def derive_version_wiki_name(consensus_version: int) -> str:
    """生成版本节点 Wiki 名称，固定格式 v{seq}（v1 / v2 / ...）。

    Wiki 层级：共识文档 / {story_id} / v{seq}
    版本号即叶子节点 wiki 名称，store_id 由父节点承载（无需再出现在标题）。
    """
    return f"v{consensus_version}"


def cmd_prepare(args: argparse.Namespace) -> dict:
    task_dir = STORE_DIR / args.story_id
    if not task_dir.exists():
        return fail(f"task dir not found: {task_dir}")

    source_path = task_dir / args.source
    if not source_path.exists():
        return fail(f"source not found: {source_path}")

    body = source_path.read_text(encoding="utf-8")
    if not body.strip():
        return fail(f"source is empty: {source_path}")

    store = TaskJsonStore.load(task_dir)
    tapd = store.get_tapd() or {}
    cfg = load_project_config()
    tapd_cfg = cfg.get("tapd") or {}
    pm_list = (tapd_cfg.get("team_roles") or {}).get("pm") or []
    workspace_id = args.workspace_id or tapd_cfg.get("workspace_id")
    creator = args.creator or (pm_list[0].get("nick") if pm_list else None) or "system"

    prev_version = int(tapd.get("consensus_version") or 0)
    consensus_version_next = prev_version + 1 if args.bump_version else max(prev_version, 1)

    # 决定父 wiki：默认查现有 consensus root
    parent_wiki_id = args.parent_wiki_id or tapd.get("consensus_parent_wiki_id")

    # 拼装 footer（带工单 URL，引导 PM 在工单评论区评审）
    pm_mention = format_pm_mention(pm_list)
    ticket_id = tapd.get("ticket_id") or (tapd.get("raw") or {}).get("id")
    story_url = (
        f"https://www.tapd.cn/{workspace_id}/prong/stories/view/{ticket_id}"
        if (workspace_id and ticket_id) else None
    )
    footer = build_footer(pm_mention, consensus_version_next, source_path, story_url)
    full_body = body.rstrip() + footer

    # wiki_id 仅在"同版本覆盖更新"时有效；版本号 bump 后必须创建新 v{seq} 节点
    existing_version_wiki_id = tapd.get("wiki_id")
    same_version = (
        existing_version_wiki_id
        and not args.bump_version
        and prev_version == consensus_version_next
    )
    action = "update" if same_version else "create"
    version_wiki_id = existing_version_wiki_id if same_version else None

    name = derive_version_wiki_name(consensus_version_next)

    return {
        "ok": True,
        "action": action,
        "story_id": args.story_id,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "wiki_id": version_wiki_id,
        "consensus_root_name": CONSENSUS_ROOT_WIKI_NAME,
        # 推送时由 cmd_push 用 _ensure_wiki 派生：root_wiki_id → store_wiki_id → 版本节点
        "store_wiki_name": args.story_id,
        "store_root_id_cached": tapd.get("consensus_root_wiki_id") or (cfg.get("tapd") or {}).get("consensus_root_wiki_id"),
        "store_wiki_id_cached": tapd.get("consensus_store_wiki_id"),
        "name": name,
        "creator": creator,
        "consensus_version_prev": prev_version,
        "consensus_version_next": consensus_version_next,
        "source_path": str(source_path.relative_to(PROJECT_DIR)),
        "body_chars": len(full_body),
        "markdown_description": full_body,
    }


def _tapd_request(
    method: str,
    path: str,
    body: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict:
    """直接调 TAPD HTTP API（Bearer ${TAPD_TOKEN}）。返回解析后的响应 JSON。

    Args:
        method: HTTP 方法（GET/POST）
        path: API path，如 /tapd_wikis
        body: POST 请求体，会被 json.dumps
        params: GET 查询参数，会被 urlencode 拼到 path 后
    """
    token = os.environ.get("TAPD_TOKEN")
    if not token:
        raise RuntimeError("env TAPD_TOKEN not set; cannot push directly")
    url = f"https://api.tapd.cn{path}"
    if params:
        # 过滤掉 None 值，避免 ?key=None
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url = f"{url}?{urllib.parse.urlencode(filtered)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"TAPD API {method} {path} → HTTP {e.code}: {err_body[:500]}"
        ) from e
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        raise RuntimeError(f"TAPD API returned non-JSON: {payload[:500]}")


def _find_wiki(
    workspace_id: int,
    name: Optional[str] = None,
    parent_wiki_id: Optional[str] = None,
    wiki_id: Optional[str] = None,
) -> Optional[dict]:
    """按 (name, parent_wiki_id) 查找 wiki，返回第一条匹配项的 dict（含 id/name/parent_wiki_id），找不到返回 None。

    注意：TAPD GET /tapd_wikis 是模糊匹配，需要在客户端再做精确过滤
    （特别是 name 完全相等 + parent_wiki_id 完全相等）。
    """
    params: dict = {"workspace_id": workspace_id, "limit": 50,
                    "fields": "id,name,parent_wiki_id"}
    if name:
        params["name"] = name
    if parent_wiki_id is not None:
        params["parent_wiki_id"] = parent_wiki_id
    if wiki_id:
        params["id"] = wiki_id
    resp = _tapd_request("GET", "/tapd_wikis", params=params)
    if resp.get("status") != 1:
        return None
    rows = resp.get("data") or []
    for row in rows:
        wiki = row.get("Wiki") or {}
        # 精确匹配 name（防止 TAPD 模糊匹配返回 superset）
        if name and wiki.get("name") != name:
            continue
        # 精确匹配 parent
        if parent_wiki_id is not None and str(wiki.get("parent_wiki_id") or "0") != str(parent_wiki_id):
            continue
        return wiki
    return None


def _ensure_wiki(
    workspace_id: int,
    name: str,
    parent_wiki_id: Optional[str],
    creator: str,
    description: str = "",
) -> dict:
    """查找 (name, parent_wiki_id) 对应的 wiki；找不到则创建一个空 wiki。返回 wiki dict（含 id/name）。

    用于"目录层" wiki（共识文档 root / store 节点），不承载契约正文。
    """
    found = _find_wiki(workspace_id, name=name, parent_wiki_id=parent_wiki_id)
    if found and found.get("id"):
        return {"id": str(found["id"]), "name": found.get("name"), "action": "found"}
    # 创建
    payload: dict = {
        "workspace_id": int(workspace_id),
        "name": name,
        "creator": creator,
        "markdown_description": description or f"# {name}\n\n（自动创建的目录节点）",
    }
    if parent_wiki_id and str(parent_wiki_id) != "0":
        payload["parent_wiki_id"] = str(parent_wiki_id)
    resp = _tapd_request("POST", "/tapd_wikis", body=payload)
    if resp.get("status") != 1:
        raise RuntimeError(f"ensure_wiki failed for name={name}: {resp.get('info')}")
    wiki = (resp.get("data") or {}).get("Wiki") or {}
    wiki_id = wiki.get("id")
    if not wiki_id:
        raise RuntimeError(f"ensure_wiki returned no id for name={name}: {resp}")
    return {"id": str(wiki_id), "name": wiki.get("name") or name, "action": "created"}


def cmd_push(args: argparse.Namespace) -> dict:
    """端到端推送：prepare → ensure root → ensure store → 推 v{seq} → record。

    Wiki 层级（严格三层）：
        共识文档（root，全局唯一）
        └── {story_id}（store 节点，每个 story 一个，仅承载目录语义）
            └── v{seq}（版本叶子，承载契约正文 + footer）

    避开 MCP 工具调用的手抄风险——脚本输出的 body 直接进入 HTTP 请求。
    """
    prep = cmd_prepare(args)
    if not prep.get("ok"):
        return prep

    workspace_id_str = prep["workspace_id"]
    if not workspace_id_str:
        return fail("workspace_id not configured in project-config.tapd")
    workspace_id = int(workspace_id_str)
    creator = prep["creator"]
    story_id = prep["story_id"]

    # ── 第 1 层：共识文档 root ─────────────────────────────────────────
    root_id_cached = prep.get("store_root_id_cached")
    if root_id_cached:
        # 仍校验缓存是否真实存在
        found = _find_wiki(workspace_id, wiki_id=root_id_cached)
        root_info = {"id": str(root_id_cached), "action": "cached"} if found else None
    else:
        root_info = None
    if not root_info:
        root_info = _ensure_wiki(
            workspace_id=workspace_id,
            name=CONSENSUS_ROOT_WIKI_NAME,
            parent_wiki_id=None,  # root 挂在顶层
            creator=creator,
            description=f"# {CONSENSUS_ROOT_WIKI_NAME}\n\n按 story 维度组织各项目契约文档；每个 story 下按版本 v{{seq}} 归档。",
        )
    root_wiki_id = root_info["id"]

    # ── 第 2 层：{story_id} store 节点 ────────────────────────────────
    store_id_cached = prep.get("store_wiki_id_cached")
    store_info = None
    if store_id_cached:
        found = _find_wiki(workspace_id, wiki_id=store_id_cached)
        if found and str(found.get("parent_wiki_id") or "0") == str(root_wiki_id):
            store_info = {"id": str(store_id_cached), "action": "cached"}
    if not store_info:
        store_info = _ensure_wiki(
            workspace_id=workspace_id,
            name=prep["store_wiki_name"],
            parent_wiki_id=root_wiki_id,
            creator=creator,
            description=f"# {prep['store_wiki_name']}\n\n本 story 的契约文档归档；按版本 v1/v2/... 排列。",
        )
    store_wiki_id = store_info["id"]

    # ── 第 3 层：v{seq} 版本节点（承载 contract 正文）──────────────────
    payload: dict = {
        "workspace_id": workspace_id,
        "name": prep["name"],  # v{seq}
        "markdown_description": prep["markdown_description"],
        "creator": creator,
        "parent_wiki_id": store_wiki_id,
    }
    if prep["action"] == "update" and prep.get("wiki_id"):
        payload["id"] = prep["wiki_id"]

    resp = _tapd_request("POST", "/tapd_wikis", body=payload)
    if resp.get("status") != 1:
        return fail(f"TAPD API returned status={resp.get('status')}: {resp.get('info')}",
                    response=resp,
                    root_wiki_id=root_wiki_id,
                    store_wiki_id=store_wiki_id)

    wiki = (resp.get("data") or {}).get("Wiki") or {}
    new_wiki_id = str(wiki.get("id") or prep.get("wiki_id") or "")
    wiki_url = (
        f"https://www.tapd.cn/{workspace_id}/markdown_wikis/show/#{new_wiki_id}"
    )

    # 自动 record（含三层 id 缓存，下次推送无需重复 ensure）
    store = TaskJsonStore.load_by_story(args.story_id)
    store.update_tapd({
        "wiki_id": new_wiki_id,
        "wiki_url": wiki_url,
        "consensus_root_wiki_id": root_wiki_id,
        "consensus_store_wiki_id": store_wiki_id,
        "consensus_parent_wiki_id": store_wiki_id,  # 兼容旧字段，指向直接父
        "consensus_version": prep["consensus_version_next"],
        "last_wiki_pushed_at": datetime.now().isoformat(),
    })
    store.save()

    return {
        "ok": True,
        "action": prep["action"],
        "root_wiki_id": root_wiki_id,
        "root_wiki_action": root_info["action"],
        "store_wiki_id": store_wiki_id,
        "store_wiki_action": store_info["action"],
        "wiki_id": new_wiki_id,
        "wiki_url": wiki_url,
        "name": prep["name"],
        "store_name": prep["store_wiki_name"],
        "consensus_version": prep["consensus_version_next"],
        "body_chars": prep["body_chars"],
        "modified_at": wiki.get("modified"),
    }


def cmd_record(args: argparse.Namespace) -> dict:
    """Claude 调 MCP 推送成功后，回写 task.json.tapd 的 wiki_id 等字段。"""
    task_dir = STORE_DIR / args.story_id
    if not task_dir.exists():
        return fail(f"task dir not found: {task_dir}")
    store = TaskJsonStore.load(task_dir)
    if not store.data.get("task_id"):
        return fail(f"task.json not found in {task_dir}")
    patch: dict = {}
    if args.wiki_id:
        patch["wiki_id"] = args.wiki_id
    if args.wiki_url:
        patch["wiki_url"] = args.wiki_url
    if args.parent_wiki_id:
        patch["consensus_parent_wiki_id"] = args.parent_wiki_id
    if args.consensus_version is not None:
        patch["consensus_version"] = args.consensus_version
    patch["last_wiki_pushed_at"] = datetime.now().isoformat()
    store.update_tapd(patch)
    store.save()
    return {"ok": True, "task_json_path": str(store.path.relative_to(PROJECT_DIR)),
            "patched": patch}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TAPD Wiki 推送 body 准备（不调 MCP）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common_args(p):
        p.add_argument("--story-id", required=True)
        p.add_argument("--source", default="contract.md",
                       help="task_dir 内的源文件名（默认 contract.md）")
        p.add_argument("--workspace-id", default=None)
        p.add_argument("--creator", default=None,
                       help="Wiki 创建人 nick；默认从 project-config.tapd.team_roles.pm[0].nick 取")
        p.add_argument("--parent-wiki-id", default=None,
                       help="父 Wiki ID；默认从 task.json.tapd.consensus_parent_wiki_id 取")
        p.add_argument("--bump-version", action="store_true",
                       help="本次推送是新版本（PM 拒绝重做后用）")

    p_prep = sub.add_parser("prepare", help="读 contract.md 拼接 footer 输出 wiki body")
    add_common_args(p_prep)
    p_prep.set_defaults(func=cmd_prepare)

    p_push = sub.add_parser("push", help="端到端推送：拼装 → 调 TAPD API → 回写 task.json")
    add_common_args(p_push)
    p_push.set_defaults(func=cmd_push)

    p_rec = sub.add_parser("record", help="MCP 推送成功后回写 task.json.tapd（兼容老接口）")
    p_rec.add_argument("--story-id", required=True)
    p_rec.add_argument("--wiki-id", required=True)
    p_rec.add_argument("--wiki-url", default=None)
    p_rec.add_argument("--parent-wiki-id", default=None)
    p_rec.add_argument("--consensus-version", type=int, default=None)
    p_rec.set_defaults(func=cmd_record)

    args = parser.parse_args()
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
