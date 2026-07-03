"""
init.py — TAPD 项目初始化（直接调 HTTP API，不依赖 MCP）

两个子命令：
  members  拉项目成员列表（JSON 输出，含角色自动猜测字段）
  setup    一键初始化 env.yaml.tapd（含成员 + 角色分类猜测 + 配置写入）

依赖：环境变量 ${TAPD_TOKEN}（Bearer Token）

Usage:
    # 仅查看成员列表（供主流程 Claude/AskUserQuestion 做二次分类）
    python init.py members --workspace-id 52676229

    # 一键初始化（仅当 team_roles 全空时写入）
    python init.py setup --workspace-id 52676229 --workspace-name "Chopard Project Refactoring"

    # 测试时指定临时配置文件（避免污染主配置）
    python init.py setup --workspace-id 52676229 --workspace-name "..." --config-path /tmp/test-env.yaml
"""
import argparse
import json
import yaml
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# 共享路径
# 项目根（CLAUDE_PROJECT_DIR 优先,否则按 .claude/skills/<x>/scripts/ 回退 4 级）
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).absolute().parents[4])
))
PROJECT_CONFIG = PROJECT_DIR / "docs" / "env.yaml"

TAPD_API_BASE = "https://api.tapd.cn"


# ── HTTP layer ────────────────────────────────────────────────────────────────


def _tapd_request(method: str, path: str, params: Optional[dict] = None) -> dict:
    """直接调 TAPD HTTP API，返回解析后的 JSON。复刻 push_wiki.py 的模板。"""
    token = os.environ.get("TAPD_TOKEN")
    if not token:
        raise RuntimeError("env TAPD_TOKEN not set; cannot call TAPD API directly")
    url = f"{TAPD_API_BASE}{path}"
    if params:
        filtered = {k: v for k, v in params.items() if v is not None}
        if filtered:
            url = f"{url}?{urllib.parse.urlencode(filtered)}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(url, headers=headers, method=method)
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


# ── Members fetch + classification ────────────────────────────────────────────


# 角色关键字（小写匹配）。优先级：qa > pm > fe > be > other
ROLE_KEYWORDS = {
    "qa": ["qa", "test", "tester", "测试"],
    "pm": ["pm", "po", "product", "产品", "项目经理"],
    "fe": ["fe", "frontend", "front-end", "前端", "ui"],
    "be": ["be", "backend", "back-end", "后端", "server"],
}


def _guess_role(member: dict) -> str:
    """根据 nick/user/email 关键字猜测角色。匹配不上返回 'other'。"""
    haystack_parts = [
        (member.get("nick") or "").lower(),
        (member.get("user") or "").lower(),
        (member.get("email") or "").lower(),
    ]
    haystack = " ".join(haystack_parts)
    # 优先级顺序：qa → pm → fe → be，避免 "fe" 被 "front-end" 之外的串误命中
    for role in ("qa", "pm", "fe", "be"):
        for kw in ROLE_KEYWORDS[role]:
            if kw in haystack:
                return role
    return "other"


def fetch_members(workspace_id: int) -> list[dict]:
    """拉项目成员列表。返回结构化的 list[dict]，含 user/nick/email/role_id_tapd/_classification_guess。

    TAPD GET /workspaces/users 端点不返回 id 字段（只有 user 中文名 + name 昵称）。
    本脚本将 `name`（TAPD 返回值）映射为 nick（拼音名），供分类与拼接成员串使用。
    """
    resp = _tapd_request(
        "GET",
        "/workspaces/users",
        params={
            "workspace_id": workspace_id,
            "fields": "user,name,nick,email,role_id",
        },
    )
    if resp.get("status") != 1:
        raise RuntimeError(f"fetch members failed: status={resp.get('status')} info={resp.get('info')}")
    rows = resp.get("data") or []
    members: list[dict] = []
    for row in rows:
        uw = row.get("UserWorkspace") or {}
        # TAPD 返回里 `name` 字段实际就是 nick；user 字段是中文姓名
        nick = uw.get("nick") or uw.get("name") or ""
        member = {
            "user": uw.get("user") or "",
            "nick": nick,
            "email": uw.get("email") or "",
            "role_id_tapd": uw.get("role_id") or [],
        }
        member["_classification_guess"] = _guess_role(member)
        members.append(member)
    return members


# ── Config persistence ────────────────────────────────────────────────────────


def _team_roles_is_empty(team_roles: Optional[dict]) -> bool:
    """所有角色数组都为空时返回 True；任一非空返回 False。"""
    if not team_roles:
        return True
    for role in ("pm", "be", "fe", "qa", "other"):
        if team_roles.get(role):
            return False
    return True


def _format_member(user: str, nick: str) -> str:
    """把 (中文姓名, 拼音名) 拼成 team_roles 成员字符串。

    格式 "中文名(拼音名)"；无拼音名时仅 "中文名"。与 push_wiki.parse_member 互逆。
    """
    user = (user or "").strip()
    nick = (nick or "").strip()
    if not user:
        return ""
    return f"{user}({nick})" if nick else user


def _classify_members(members: list[dict]) -> dict:
    """把成员列表按 _classification_guess 分桶为 team_roles 结构。

    每个成员条目是字符串 "中文名(拼音名)"（无拼音名时仅 "中文名"）。
    other 桶承载未能自动归类的成员，由主流程 AskUserQuestion 复核改桶。
    """
    buckets: dict = {"pm": [], "be": [], "fe": [], "qa": [], "other": []}
    for m in members:
        role = m.get("_classification_guess") or "other"
        if role not in buckets:
            role = "other"
        entry = _format_member(m.get("user", ""), m.get("nick", ""))
        if entry:
            buckets[role].append(entry)
    return buckets


def _load_config(config_path: Path) -> dict:
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text(encoding="utf-8"))


def _save_config(config_path: Path, cfg: dict) -> None:
    config_path.write_text(
        yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


# ── CLI commands ──────────────────────────────────────────────────────────────


def cmd_members(args: argparse.Namespace) -> dict:
    members = fetch_members(int(args.workspace_id))
    # 顺带给出分桶预览，方便主流程直接复用
    return {
        "ok": True,
        "workspace_id": str(args.workspace_id),
        "total": len(members),
        "members": members,
        "classification_preview": _classify_members(members),
    }


def cmd_setup(args: argparse.Namespace) -> dict:
    config_path = Path(args.config_path) if args.config_path else PROJECT_CONFIG
    cfg = _load_config(config_path)
    tapd_cfg = cfg.get("tapd") or {}
    existing_roles = tapd_cfg.get("team_roles") or {}

    # 保护已有 team_roles：任一角色非空 → 跳过
    if not _team_roles_is_empty(existing_roles):
        return {
            "ok": True,
            "skipped": True,
            "reason": "team_roles already populated",
            "config_path": str(config_path),
            "existing_counts": {
                role: len(existing_roles.get(role) or [])
                for role in ("pm", "be", "fe", "qa", "other")
            },
        }

    # 拉成员
    members = fetch_members(int(args.workspace_id))
    team_roles = _classify_members(members)

    # 增量写入 tapd section（保留其他字段）
    tapd_cfg["enabled"] = True
    tapd_cfg["workspace_id"] = str(args.workspace_id)
    if args.workspace_name:
        tapd_cfg["workspace_name"] = args.workspace_name
    tapd_cfg["team_roles"] = team_roles

    cfg["tapd"] = tapd_cfg
    _save_config(config_path, cfg)

    return {
        "ok": True,
        "skipped": False,
        "config_path": str(config_path),
        "workspace_id": str(args.workspace_id),
        "workspace_name": tapd_cfg.get("workspace_name"),
        "members_total": len(members),
        "team_roles_counts": {
            role: len(team_roles.get(role, [])) for role in ("pm", "be", "fe", "qa", "other")
        },
        "note": "角色基于 nick/user/email 关键字猜测，建议主流程用 AskUserQuestion 让用户复核 other 桶。",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TAPD 项目初始化（直接调 HTTP API）",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_members = sub.add_parser("members", help="拉项目成员列表（JSON 输出）")
    p_members.add_argument("--workspace-id", required=True)
    p_members.set_defaults(func=cmd_members)

    p_setup = sub.add_parser("setup", help="一键初始化 env.yaml.tapd（仅当 team_roles 全空时写入）")
    p_setup.add_argument("--workspace-id", required=True)
    p_setup.add_argument("--workspace-name", default=None)
    p_setup.add_argument(
        "--config-path",
        default=None,
        help="目标配置文件路径，默认 docs/env.yaml（测试时可指向临时副本）",
    )
    p_setup.set_defaults(func=cmd_setup)

    args = parser.parse_args()
    try:
        result = args.func(args)
    except Exception as e:
        result = {"ok": False, "error": str(e)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
