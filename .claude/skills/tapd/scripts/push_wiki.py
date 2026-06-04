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

    # 强制创建新版本(契约业务规则发生变化时使用)
    python push_wiki.py push --story-id 1046733 --bump-version

版本号语义（默认：同版本覆盖）
  - 默认不带 --bump-version → 同版本覆盖当前 Wiki 节点（action=update）；首次推送则版本号=1。
  - 传 --bump-version       → 版本号 +1，创建新 v{N+1} 节点（action=create）。

何时用 --bump-version：
  ✅ 契约业务规则变更（新增/移除 AC、范围扩展、Non-Goals 调整）
  ✅ 上一版被 [CONSENSUS-REJECTED]，且本次修订引入了新业务规则
  ❌ 仅合并 TBD 答复（用同版本覆盖）
  ❌ 笔误/格式修正
  ❌ §0 修订记录追加
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# 共享基础设施
# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[4])
))
STORE_DIR = PROJECT_DIR / ".chatlabs" / "task" / "store"

sys.path.insert(0, str(PROJECT_DIR / ".claude" / "skills" / "task" / "scripts"))
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


def parse_member(member: str) -> tuple[str, str]:
    """解析 team_roles 成员字符串 "中文名(拼音名)" → (user, nick)。

    user = 中文姓名（TAPD @ 识别依据 data-userid）；nick = 拼音名（展示用）。
    无括号时 nick 为空。兼容半角 () 与全角 （）。与 init._format_member 互逆。
    """
    s = (member or "").strip()
    if not s:
        return "", ""
    m = re.match(r"^(.+?)\s*[(（](.+?)[)）]\s*$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return s, ""


def format_user_mention(member: str) -> str:
    """生成单个 TAPD at-who HTML 标签(页面展示 + 留痕用)。

    格式:
        <b class="at-who" contenteditable="false" data-userid="<user>" data-type="user">@<user>(<nick>)</b>

    🚨 通知可达性(2026-06-04 debeers 一手实测,推翻 5-29 "格式正确即通知"结论):
    开放 API(create_comments)发的评论,at-who 即使与界面原生格式逐字节一致
    (data-userid 中文名/数字 user_id 变体均实测)也**不触发通知**——TAPD 通知管线
    只在网页端发评论时由前端触发,API 仅落库(官方 API 文档亦无 mention 参数)。
    流程上"必须通知到人"的节点,必须同时走 notify skill(企微 webhook)主动通知。

    ★ 载体限制(2026-05-29 一手验证): 此标签仅在「评论 description」(富文本)里有 @ 语义;
    放进 wiki 正文 markdown_description 不被 TAPD 识别。
    data-userid 取**中文名**(与界面原生格式一致,2026-06-04 界面手动评论对照确认)。

    入参 member 由 team_roles 提供，格式 "中文名(拼音名)"，经 parse_member 拆出 user / nick。
    """
    user, nick = parse_member(member)
    if not user:
        return ""
    inner = f"@{user}({nick})" if nick else f"@{user}"
    return (
        f'<b class="at-who" contenteditable="false" '
        f'data-userid="{user}" data-type="user">{inner}</b>'
    )


def format_user_list_mention(user_list: list[str]) -> str:
    """多用户 → 多个 at-who 标签拼接（空格分隔，确保每个 mention 独立可识别）。"""
    parts = [format_user_mention(u) for u in (user_list or [])]
    parts = [p for p in parts if p]
    return " ".join(parts)


def format_pm_mention(pm_list: list[str]) -> str:
    """[向后兼容入口] 等价于 format_user_list_mention，空时回退到字面"@PM"提示。"""
    mention = format_user_list_mention(pm_list)
    return mention if mention else "@PM"


def build_footer(
    mentions: dict,
    consensus_version_next: int,
    source_path: Path,
    doc_type: str = "contract",
    story_url: Optional[str] = None,
    is_revision: bool = False,
) -> str:
    """拼接评审 footer(按 doc_type 区分措辞 + @ 范围)。

    Args:
        mentions: build_role_mentions 输出,含 pm/be/fe/qa/all 各角色 at-who 标签
        consensus_version_next: 本次推送的版本号
        source_path: 源文件(contract.md / spec.md)
        doc_type: contract → 评审给 PM(共识层);spec → 评审给 BE(技术层)
        story_url: 关联工单 URL(评论区入口)
        is_revision: 同版本覆盖 / True 时显示"修订覆盖"

    注意:TAPD Wiki 没有获取评论的 API,所有评审 / 变更评论统一在**对应工单(Story)**下。
    """
    story_link = (
        f"\n>\n> **工单链接**:{story_url}(点击进入对应 Story 评论区)"
        if story_url else ""
    )
    version_label = (
        f"v{consensus_version_next}.0.0(修订覆盖)"
        if is_revision else f"v{consensus_version_next}.0.0"
    )

    if doc_type == "spec":
        # spec 文档 — 技术评审, 主审 BE
        title = "技术评审说明(请 BE 复审)"
        reviewer_mention = mentions.get("be") or "@BE"
        gen_by = "由 planner 基于已冻结的 contract.md 生成"
        review_focus = (
            "> **重点审核项**:\n"
            "> 1. API 端点 / 数据模型 / 状态机 是否对齐 contract §AC\n"
            "> 2. 错误码契约 + 异常处理是否覆盖 contract 中的全部场景\n"
            "> 3. 测试入口 / 集成测试矩阵 是否充分(参考 spec.md §7)\n"
            "> 4. 第三方集成 / 配置 / 依赖 是否标注清晰"
        )
    else:
        # contract 文档 — 业务共识, 主审 PM
        title = "评审说明(请 PM 审核)"
        reviewer_mention = mentions.get("pm") or "@PM"
        gen_by = "由 doc-librarian 基于 TAPD Story description 生成"
        review_focus = (
            "> **重点审核项**:\n"
            "> 1. 业务规则(BR-XX)是否完整覆盖业务语义\n"
            "> 2. 验收标准(AC-XXX)是否每条都可独立测试\n"
            "> 3. TBD 项是否需要在本期解决\n"
            "> 4. 对外契约不变项(异常类型 / HTTP 端点 / 调用方代码 / 错误码)的强承诺"
        )

    # 协办通知 — 所有 roles_required 角色(去除 reviewer 本身重复 @)
    coordination_mention = mentions.get("all") or ""

    return f"""

---

## {title}

> {reviewer_mention} 本文档 {version_label} {gen_by},**完整版**({source_path.stat().st_size // 1024}K)。{story_link}
>
> **审核流程**(评论位置:对应 TAPD 工单评论区):
> - ✅ **通过**:留言 `[CONSENSUS-APPROVED]` → 主流程自动推进到下一阶段
> - ❌ **打回**:留言 `[CONSENSUS-REJECTED: <原因>]` → 主流程自动回退重做
> - 🔄 **需求变更**:留言 `[REQUIREMENT-CHANGE]` 独立一行 + 下方写变更内容(可多行)→ 主流程自动追加版本历史
>
> {review_focus}
>
> **协办通知（仅标识，不触发通知）**:{coordination_mention}
>
> ⚠️ 本 Wiki 正文内的 @ 不触发通知;评审 @ 已通过「对应工单评论区」发出(见上方工单链接)。
"""


# 文档类型 → leaf 节点名映射
_LEAF_WIKI_NAMES = {
    "contract": "共识文档",
    "spec": "spec文档",
}

_DEFAULT_SOURCE_BY_DOC_TYPE = {
    "contract": "contract.md",
    "spec": "spec.md",
}


def derive_leaf_wiki_name(doc_type: str) -> str:
    """生成 leaf 节点 Wiki 名称。

    新版结构(2026-05-29):
        共识文档(root) / {ticket_id}-{slug}(store) / {共识文档|spec文档}(leaf, 固定名)

    版本号不再作为 wiki 节点名,改为正文末尾"变更历史"段维护。
    """
    name = _LEAF_WIKI_NAMES.get(doc_type)
    if not name:
        raise ValueError(f"unsupported doc_type: {doc_type!r}, expect contract|spec")
    return name


def build_role_mentions(team_roles: dict, roles_required: list[str]) -> dict[str, str]:
    """根据 roles_required 拼装各角色的 at-who 标签字符串。

    Args:
        team_roles: project-config.json.tapd.team_roles
        roles_required: 任务要求的角色列表(如 ["pm","be","qa"] 或 ["pm","be","fe","qa"])

    Returns:
        {"pm": "<at-who tag>", "be": "...", "fe": "...", "qa": "...", "all": "<拼合>"}
        缺角色 / 空 list → 该 key 对应 ""(写日志,不报错)。"all" 是按 pm→be→fe→qa 顺序拼合。
    """
    role_order = ("pm", "be", "fe", "qa")
    mentions: dict[str, str] = {role: "" for role in role_order}
    required = set(roles_required or [])
    for role in role_order:
        if role not in required:
            continue
        members = team_roles.get(role) or []
        if not members:
            # 配置中该角色为空,跳过(不报错)
            continue
        mentions[role] = format_user_list_mention(members)
    # 按角色顺序拼合
    parts = [mentions[r] for r in role_order if mentions[r]]
    mentions["all"] = " ".join(parts)
    return mentions


def build_change_history_section(change_log: list[dict]) -> str:
    """根据 change_log 拼装正文末尾"## 变更历史"段。

    change_log 格式: [{"version": int, "ts": iso8601, "description": str}, ...]
    按 version 倒序展示(最新在前)。空 log → 返回空字符串。
    """
    if not change_log:
        return ""
    rows = sorted(change_log, key=lambda x: x.get("version", 0), reverse=True)
    lines = [
        "",
        "---",
        "",
        "## 变更历史",
        "",
        "| 版本 | 时间 | 变更内容 |",
        "|------|------|---------|",
    ]
    for row in rows:
        version = row.get("version", "?")
        ts = (row.get("ts") or "").replace("T", " ").split(".")[0]  # 简化展示
        desc = (row.get("description") or "").replace("\n", " ").replace("|", "\\|")
        lines.append(f"| v{version} | {ts} | {desc} |")
    return "\n".join(lines) + "\n"


def cmd_prepare(args: argparse.Namespace) -> dict:
    """拼装待推送的 wiki body。

    新结构(2026-05-29):
        共识文档(root) / {ticket_id}-{slug}(store) / {共识文档|spec文档}(leaf 固定名)
    版本号在正文末尾"变更历史"段维护,不再作为 leaf 节点名。
    """
    doc_type = getattr(args, "doc_type", None) or "contract"
    if doc_type not in _LEAF_WIKI_NAMES:
        return fail(f"unsupported doc-type: {doc_type!r}, expect contract|spec")

    task_dir = STORE_DIR / args.story_id
    if not task_dir.exists():
        return fail(f"task dir not found: {task_dir}")

    # source 默认值随 doc_type 切换(contract→contract.md / spec→spec.md)
    source_name = args.source
    if not source_name or source_name == "contract.md":
        source_name = _DEFAULT_SOURCE_BY_DOC_TYPE[doc_type]
    source_path = task_dir / source_name
    if not source_path.exists():
        return fail(f"source not found: {source_path}")

    body = source_path.read_text(encoding="utf-8")
    if not body.strip():
        return fail(f"source is empty: {source_path}")

    store = TaskJsonStore.load(task_dir)
    tapd = store.get_tapd() or {}
    cfg = load_project_config()
    tapd_cfg = cfg.get("tapd") or {}
    team_roles = tapd_cfg.get("team_roles") or {}
    pm_list = team_roles.get("pm") or []
    workspace_id = args.workspace_id or tapd_cfg.get("workspace_id")
    creator = args.creator or (parse_member(pm_list[0])[1] if pm_list else None) or "system"

    # 角色 / @ 范围: --roles CLI > task.json.tapd.roles_required > 默认 ["pm","be","qa"]
    if getattr(args, "roles", None):
        roles_required = [r.strip().lower() for r in args.roles.split(",") if r.strip()]
    elif tapd.get("roles_required"):
        roles_required = list(tapd["roles_required"])
    else:
        roles_required = ["pm", "be", "qa"]
    mentions = build_role_mentions(team_roles, roles_required)

    # 按 doc_type 选字段
    if doc_type == "spec":
        log_field = "spec_change_log"
        version_field = "spec_version"
        wiki_id_field = "spec_wiki_id"
    else:
        log_field = "consensus_change_log"
        version_field = "consensus_version"
        wiki_id_field = "consensus_wiki_id"

    prev_version = int(tapd.get(version_field) or tapd.get("consensus_version") or 0)
    existing_leaf_wiki_id = tapd.get(wiki_id_field) or (
        tapd.get("wiki_id") if doc_type == "contract" else None
    )
    change_log: list[dict] = list(tapd.get(log_field) or [])

    # 版本流转:
    #   --bump-version 或 首次推送 → version+1, 追加 change_log 一行
    #   否则同版本覆盖, 不动 change_log
    change_desc = getattr(args, "change_desc", None) or ""
    if args.bump_version or prev_version == 0:
        version_next = max(prev_version, 0) + 1
        is_revision = False
        if prev_version == 0 and not args.bump_version:
            log_desc = change_desc or "初版"
        else:
            log_desc = change_desc or "(无变更描述)"
        change_log.append({
            "version": version_next,
            "ts": datetime.now().isoformat(),
            "description": log_desc,
        })
    else:
        version_next = prev_version
        is_revision = True

    if existing_leaf_wiki_id:
        action = "update"
        leaf_wiki_id = existing_leaf_wiki_id
    else:
        action = "create"
        leaf_wiki_id = None

    # store 节点名: {ticket_id}-{slug}(TAPD) 或 {slug}(本地)
    local_mapping = tapd.get("local_mapping") or {}
    ticket_id_full = (
        local_mapping.get("tapd_ticket_id")
        or tapd.get("ticket_id")
        or (tapd.get("raw") or {}).get("id")
    )
    if ticket_id_full:
        store_wiki_name = f"{ticket_id_full}-{args.story_id}"
    else:
        store_wiki_name = args.story_id

    # footer
    story_url = (
        f"https://www.tapd.cn/{workspace_id}/prong/stories/view/{ticket_id_full}"
        if (workspace_id and ticket_id_full) else None
    )
    footer = build_footer(
        mentions=mentions,
        consensus_version_next=version_next,
        source_path=source_path,
        doc_type=doc_type,
        story_url=story_url,
        is_revision=is_revision,
    )
    history_section = build_change_history_section(change_log)
    full_body = body.rstrip() + history_section + footer

    leaf_name = derive_leaf_wiki_name(doc_type)

    return {
        "ok": True,
        "action": action,
        "doc_type": doc_type,
        "story_id": args.story_id,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "wiki_id": leaf_wiki_id,
        "consensus_root_name": CONSENSUS_ROOT_WIKI_NAME,
        "store_wiki_name": store_wiki_name,
        "store_root_id_cached": tapd.get("consensus_root_wiki_id") or (cfg.get("tapd") or {}).get("consensus_root_wiki_id"),
        "store_wiki_id_cached": tapd.get("consensus_store_wiki_id"),
        "name": leaf_name,
        "creator": creator,
        "consensus_version_prev": prev_version,
        "consensus_version_next": version_next,
        "version_field": version_field,
        "wiki_id_field": wiki_id_field,
        "log_field": log_field,
        "change_log_next": change_log,
        "source_path": str(source_path.relative_to(PROJECT_DIR)),
        "body_chars": len(full_body),
        "markdown_description": full_body,
        "mentions": mentions,
        "roles_required": roles_required,
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
    # parent_wiki_id == "0" 表示顶层 root：不作为模糊查询参数下发（TAPD 可能误解），仅靠下方客户端精确过滤
    if parent_wiki_id is not None and str(parent_wiki_id) != "0":
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
            parent_wiki_id="0",  # root 挂在顶层（parent==0 精确匹配，避免按名命中同名 leaf）
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

    # 自动 record:按 doc_type 写 consensus_* / spec_* 不同字段
    doc_type = prep.get("doc_type", "contract")
    wiki_id_field = prep["wiki_id_field"]
    version_field = prep["version_field"]
    log_field = prep["log_field"]
    url_field = "spec_wiki_url" if doc_type == "spec" else "consensus_wiki_url"

    patch: dict = {
        wiki_id_field: new_wiki_id,
        url_field: wiki_url,
        version_field: prep["consensus_version_next"],
        log_field: prep["change_log_next"],
        "consensus_root_wiki_id": root_wiki_id,
        "consensus_store_wiki_id": store_wiki_id,
        "last_wiki_pushed_at": datetime.now().isoformat(),
    }
    # 兼容旧字段(只 contract 时维护,避免 spec 推送覆盖)
    if doc_type == "contract":
        patch["wiki_id"] = new_wiki_id
        patch["wiki_url"] = wiki_url
        patch["consensus_parent_wiki_id"] = store_wiki_id
        patch["consensus_version"] = prep["consensus_version_next"]

    store = TaskJsonStore.load_by_story(args.story_id)
    store.update_tapd(patch)
    store.save()

    return {
        "ok": True,
        "action": prep["action"],
        "doc_type": doc_type,
        "root_wiki_id": root_wiki_id,
        "root_wiki_action": root_info["action"],
        "store_wiki_id": store_wiki_id,
        "store_wiki_action": store_info["action"],
        "wiki_id": new_wiki_id,
        "wiki_url": wiki_url,
        "name": prep["name"],
        "store_name": prep["store_wiki_name"],
        "version": prep["consensus_version_next"],
        "version_field": version_field,
        "wiki_id_field": wiki_id_field,
        "body_chars": prep["body_chars"],
        "modified_at": wiki.get("modified"),
    }


def cmd_record(args: argparse.Namespace) -> dict:
    """Claude 调 MCP 推送成功后,回写 task.json.tapd 的 wiki_id 等字段。

    按 --doc-type 写不同字段(contract → consensus_*;spec → spec_*),兼容老调用方。
    """
    task_dir = STORE_DIR / args.story_id
    if not task_dir.exists():
        return fail(f"task dir not found: {task_dir}")
    store = TaskJsonStore.load(task_dir)
    if not store.data.get("task_id"):
        return fail(f"task.json not found in {task_dir}")
    doc_type = getattr(args, "doc_type", None) or "contract"
    if doc_type == "spec":
        wiki_id_field, url_field, version_field = "spec_wiki_id", "spec_wiki_url", "spec_version"
    else:
        wiki_id_field, url_field, version_field = "consensus_wiki_id", "consensus_wiki_url", "consensus_version"

    patch: dict = {}
    if args.wiki_id:
        patch[wiki_id_field] = args.wiki_id
        # 兼容老字段(仅 contract 写)
        if doc_type == "contract":
            patch["wiki_id"] = args.wiki_id
    if args.wiki_url:
        patch[url_field] = args.wiki_url
        if doc_type == "contract":
            patch["wiki_url"] = args.wiki_url
    if args.parent_wiki_id:
        patch["consensus_parent_wiki_id"] = args.parent_wiki_id
    if args.consensus_version is not None:
        patch[version_field] = args.consensus_version
        if doc_type == "contract":
            patch["consensus_version"] = args.consensus_version
    patch["last_wiki_pushed_at"] = datetime.now().isoformat()
    store.update_tapd(patch)
    store.save()
    return {"ok": True, "task_json_path": str(store.path.relative_to(PROJECT_DIR)),
            "doc_type": doc_type, "patched": patch}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TAPD Wiki 推送 body 准备（不调 MCP）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_common_args(p):
        p.add_argument("--story-id", required=True)
        p.add_argument("--doc-type", default="contract", choices=["contract", "spec"],
                       help="文档类型 (contract→共识文档/spec→spec文档),决定 leaf 节点名 + source 默认值 + footer 措辞")
        p.add_argument("--source", default="contract.md",
                       help="task_dir 内的源文件名 (默认按 doc-type:contract→contract.md / spec→spec.md)")
        p.add_argument("--workspace-id", default=None)
        p.add_argument("--creator", default=None,
                       help="Wiki 创建人(拼音名);默认从 project-config.tapd.team_roles.pm[0] 取")
        p.add_argument("--parent-wiki-id", default=None,
                       help="父 Wiki ID;默认从 task.json.tapd.consensus_parent_wiki_id 取")
        p.add_argument("--bump-version", action="store_true",
                       help="本次推送是新版本(版本号+1+追加变更历史段一行)")
        p.add_argument("--change-desc", default=None,
                       help="--bump-version 时的变更描述,写入正文末尾变更历史段")
        p.add_argument("--roles", default=None,
                       help="覆盖 task.json.tapd.roles_required,逗号分隔,如 pm,be,fe,qa")

    p_prep = sub.add_parser("prepare", help="读 contract.md 拼接 footer 输出 wiki body")
    add_common_args(p_prep)
    p_prep.set_defaults(func=cmd_prepare)

    p_push = sub.add_parser("push", help="端到端推送：拼装 → 调 TAPD API → 回写 task.json")
    add_common_args(p_push)
    p_push.set_defaults(func=cmd_push)

    p_rec = sub.add_parser("record", help="MCP 推送成功后回写 task.json.tapd (兼容老接口)")
    p_rec.add_argument("--story-id", required=True)
    p_rec.add_argument("--doc-type", default="contract", choices=["contract", "spec"])
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
