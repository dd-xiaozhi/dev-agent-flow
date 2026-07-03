"""
consensus_poll.py — consensus-gate 评审结论轮询（去人工搬运）

问题：consensus-gate 放行此前是 3 步人工搬运——① 跑 comments.py fetch
② 人肉读 markers 找 [CONSENSUS-APPROVED]/[CONSENSUS-REJECTED] ③ 手抄 comment_id
构造 flow_advance complete。本脚本把前两步合成一条命令，直接输出可喂给
flow_advance 的 evidence_id + decision。

人保留的动作只剩「在 TAPD 写评审评论」这个真实决策，不再做 fetch + 读 marker
的机械搬运（对齐"掌舵不微管理"）。

职责边界：
- 只读检测 + 输出结论，**不 emit 事件、不推进 flow**（放行仍由主 Claude 调
  flow_advance complete，evidence_id 用本脚本输出的 comment_id）。单点决策不分散。
- 复用 comments.py 的 marker 检测（含"同评论 ≥2 marker = 指引评论，跳过"防误判）。

decision 取值：
- approved  — 命中唯一 [CONSENSUS-APPROVED]，输出 evidence_id=该 comment_id
- rejected  — 命中 [CONSENSUS-REJECTED]，输出 evidence_id + reject 语义
- pending   — 未命中任何评审结论 marker（还没人评审）
- ambiguous — 同时命中 approve 和 reject（取最新一条为准，但显式标 ambiguous 供人核）

Usage:
    python consensus_poll.py --story-id <id>
    python consensus_poll.py --story-id <id> --ticket-id <tid> --workspace-id <wid>

退出码：0 = approved / 1 = 非 approved（pending/rejected/ambiguous/error），便于脚本判断。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_COMMENTS_SCRIPT = _THIS_DIR / "comments.py"

_APPROVE_MARKER = "[CONSENSUS-APPROVED]"
_REJECT_MARKER = "[CONSENSUS-REJECTED]"


def _run_comments_fetch(
    story_id: str,
    ticket_id: str | None,
    workspace_id: str | None,
) -> dict:
    """subprocess 跑 comments.py fetch，返回其 JSON（含 markers[]）。

    复用既有 fetch + marker 检测逻辑，不重复实现。失败时抛异常由调用方兜底。
    """
    cmd = [sys.executable, str(_COMMENTS_SCRIPT), "fetch", "--story-id", story_id]
    if ticket_id:
        cmd += ["--ticket-id", str(ticket_id)]
    if workspace_id:
        cmd += ["--workspace-id", str(workspace_id)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        # comments.py 失败（多为 TAPD_TOKEN 缺失 / 网络 / ticket 缺失）
        try:
            payload = json.loads(proc.stdout or "{}")
            err = payload.get("error") or proc.stderr or "comments.py fetch failed"
        except json.JSONDecodeError:
            err = proc.stderr or proc.stdout or "comments.py fetch failed"
        raise RuntimeError(err)
    return json.loads(proc.stdout)


def _decide(markers: list[dict]) -> dict:
    """从 markers[] 判定 consensus 结论。

    markers 已由 comments.py 过滤掉"同评论 ≥2 marker 的指引评论"，此处只需按
    marker 文本归类。同时命中 approve + reject → 取 created 最新一条，标 ambiguous。
    """
    approves = [m for m in markers if m.get("marker") == _APPROVE_MARKER]
    rejects = [m for m in markers if m.get("marker") == _REJECT_MARKER]

    def _latest(items: list[dict]) -> dict:
        return sorted(items, key=lambda m: m.get("created") or "")[-1]

    if approves and rejects:
        latest_a = _latest(approves)
        latest_r = _latest(rejects)
        winner = latest_a if (latest_a.get("created") or "") >= (latest_r.get("created") or "") else latest_r
        decision = "approved" if winner is latest_a else "rejected"
        return {
            "decision": decision,
            "evidence_id": winner.get("comment_id"),
            "ambiguous": True,
            "note": "同时存在 approve 与 reject 评论，取最新一条；建议人工确认",
        }
    if approves:
        w = _latest(approves)
        return {"decision": "approved", "evidence_id": w.get("comment_id"), "ambiguous": False}
    if rejects:
        w = _latest(rejects)
        return {"decision": "rejected", "evidence_id": w.get("comment_id"), "ambiguous": False}
    return {"decision": "pending", "evidence_id": None, "ambiguous": False}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="consensus-gate 评审结论轮询（fetch + marker 检测一步到位）",
    )
    parser.add_argument("--story-id", required=True, help="本地 story_id")
    parser.add_argument("--ticket-id", default=None,
                        help="TAPD 工单 id；省略则由 comments.py 从 task.json 取")
    parser.add_argument("--workspace-id", default=None,
                        help="TAPD workspace_id；省略则由 comments.py 从 task.json/env.yaml 取")
    args = parser.parse_args()

    try:
        fetch_result = _run_comments_fetch(args.story_id, args.ticket_id, args.workspace_id)
    except Exception as e:
        print(json.dumps(
            {"ok": False, "decision": "error", "error": str(e),
             "hint": "确认 TAPD_TOKEN 已设置且 task.json.tapd.ticket_id 存在"},
            ensure_ascii=False, indent=2,
        ))
        return 1

    markers = fetch_result.get("markers") or []
    result = _decide(markers)
    result["ok"] = True
    result["story_id"] = args.story_id
    result["markers_total"] = len(markers)
    if result["decision"] == "approved":
        result["next"] = (
            f"python .claude/skills/flow-engine/scripts/flow_advance.py "
            f"--story-id {args.story_id} complete consensus-gate "
            f"--evidence-type wiki-comment-id --evidence-id {result['evidence_id']}"
        )
    elif result["decision"] == "rejected":
        result["next"] = (
            "评审打回：doc-librarian 重做 contract（版本号+1），flow 会跳回 doc-librarian"
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "approved" else 1


if __name__ == "__main__":
    sys.exit(main())
