#!/usr/bin/env python3
"""
flow-check.py — Flow 健康检查工具

在任意时刻评估 Flow 配置、命令/Skill 可用性、运行时状态、架构合规性、会话上下文的健康状况。

Usage:
    python3 .claude/scripts/flow-check.py [--check-type <full|config|runtime|session|health>] [--verbose]

Output:
    - Markdown 格式输出到 stdout
    - JSON 格式报告写入 .chatlabs/reports/flow-check/FC-YYYYMMDD-NNN.json
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# 导入集中路径常量
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import (
    PROJECT_DIR, CLAUDE_DIR, CHATLABS_DIR, STATE_DIR,
    STORIES_DIR, REPORTS_DIR, TAPD_DIR
)

# ── 报告输出目录 ──────────────────────────────────────────────────
FLOW_CHECK_REPORTS = REPORTS_DIR / "flow-check"
FLOW_CHECK_REPORTS.mkdir(parents=True, exist_ok=True)

# ── Phase 序列定义 ────────────────────────────────────────────────
PHASE_SEQUENCE = ["doc-librarian", "planner", "generator", "evaluator", "handoff"]


def ts() -> str:
    """返回 ISO 8601 格式时间戳"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_seq_num() -> int:
    """计算当日序列号（用于报告 ID）"""
    today = datetime.now().strftime("%Y%m%d")
    existing = list(FLOW_CHECK_REPORTS.glob(f"FC-{today}-*.json"))
    return len(existing) + 1


def status_from_score(score: int) -> str:
    """根据分数确定状态"""
    if score >= 90:
        return "pass"
    elif score >= 70:
        return "warn"
    else:
        return "fail"


def icon_for_status(status: str) -> str:
    """状态对应的图标"""
    return {"pass": "✓", "warn": "⚠", "fail": "✗"}.get(status, "?")


# ── 维度检查函数 ─────────────────────────────────────────────────

def check_config_health() -> dict:
    """检查配置健康度：settings.json、tapd-config.json、workflow-state.json"""
    issues = []
    score = 100

    # 检查 .claude/ 目录结构
    claude_required = [
        "settings.json",
        "commands",
        "skills",
        "hooks",
        "scripts",
        "agents",
        "templates",
    ]
    for name in claude_required:
        path = CLAUDE_DIR / name
        if not path.exists():
            issues.append(f".claude/{name} 不存在")
            score -= 10

    # 检查 settings.json
    settings = CLAUDE_DIR / "settings.json"
    if settings.exists():
        try:
            data = json.loads(settings.read_text())
            # 检查必需字段
            if "permissions" not in data:
                issues.append("settings.json 缺少 permissions 字段")
                score -= 5
            if "hooks" not in data:
                issues.append("settings.json 缺少 hooks 字段")
                score -= 5
        except json.JSONDecodeError:
            issues.append("settings.json 格式错误")
            score -= 15
    else:
        issues.append("settings.json 不存在")
        score -= 20

    # 检查 tapd-config.json
    tapd_config = CLAUDE_DIR / "tapd-config.json"
    if tapd_config.exists():
        try:
            data = json.loads(tapd_config.read_text())
            if "workspace_id" not in data:
                issues.append("tapd-config.json 缺少 workspace_id")
                score -= 5
        except json.JSONDecodeError:
            issues.append("tapd-config.json 格式错误")
            score -= 5
    # tapd-config.json 不存在不扣分（可选）

    # 检查 .chatlabs/ 目录结构
    chatlabs_required = ["state", "reports", "stories"]
    for name in chatlabs_required:
        path = CHATLABS_DIR / name
        if not path.exists():
            issues.append(f".chatlabs/{name} 不存在")
            score -= 10

    # 检查 workflow-state.json
    workflow_state = STATE_DIR / "workflow-state.json"
    if workflow_state.exists():
        try:
            data = json.loads(workflow_state.read_text())
            if not data.get("task_id"):
                issues.append("workflow-state.json 缺少 task_id")
                score -= 5
        except json.JSONDecodeError:
            issues.append("workflow-state.json 格式错误")
            score -= 5
    else:
        issues.append("workflow-state.json 不存在（正常，新项目）")
        score -= 5

    score = max(0, score)
    return {"score": score, "status": status_from_score(score), "issues": issues}


def check_command_skill_availability() -> dict:
    """检查命令/Skill 可用性"""
    issues = []
    score = 100

    # 扫描 commands/ 目录
    command_files = list(CLAUDE_DIR.glob("commands/**/*.md"))
    command_names = []
    for f in command_files:
        if f.name.endswith(".md") and f.name != "README.md":
            command_names.append(f.stem)

    # 检查关键命令是否存在
    critical_commands = [
        "story-start", "tapd-story-start", "task-resume",
        "tapd-subtask-emit", "tapd-consensus-push", "workflow-review",
        "start-dev-flow"
    ]
    for cmd in critical_commands:
        # 支持子目录查找
        found = any(cmd in str(f) for f in command_files)
        if not found:
            issues.append(f"关键命令 /{cmd} 不存在")
            score -= 5

    # 扫描 skills/ 目录
    skill_dirs = [d for d in (CLAUDE_DIR / "skills").iterdir() if d.is_dir()]
    skill_names = [d.name for d in skill_dirs]

    # 检查关键 skill 是否存在
    critical_skills = ["self-reflect", "fitness-run", "tapd-sync"]
    for skill in critical_skills:
        if skill not in skill_names:
            issues.append(f"关键 skill {skill} 不存在")
            score -= 5

    # 检查 skill 目录是否有 SKILL.md
    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            issues.append(f"skill {skill_dir.name} 缺少 SKILL.md")
            score -= 3

    # 检查 hooks 脚本是否存在
    hooks_dir = CLAUDE_DIR / "hooks"
    if hooks_dir.exists():
        hook_scripts = list(hooks_dir.glob("*.py"))
        hook_names = [h.stem for h in hook_scripts]
        critical_hooks = ["session-start", "session-end", "blocker-tracker"]
        for hook in critical_hooks:
            if hook not in hook_names:
                issues.append(f"关键 hook {hook}.py 不存在")
                score -= 5

    score = max(0, score)
    return {
        "score": score,
        "status": status_from_score(score),
        "issues": issues,
        "details": {
            "command_count": len(command_names),
            "skill_count": len(skill_names),
        }
    }


def check_runtime_state() -> dict:
    """检查运行时状态：phase、verdict、blocker、未处理事件"""
    issues = []
    score = 100

    # 读取 workflow-state.json
    workflow_state = STATE_DIR / "workflow-state.json"
    state_data = {}
    if workflow_state.exists():
        try:
            state_data = json.loads(workflow_state.read_text())
        except json.JSONDecodeError:
            issues.append("workflow-state.json 格式错误")
            score -= 10

    task_id = state_data.get("task_id")
    story_id = state_data.get("story_id")
    phase = state_data.get("phase")
    verdicts = state_data.get("verdicts", {})
    blocker_count = state_data.get("blocker_count", 0)

    # 检查未处理事件
    events_file = STATE_DIR / "events.jsonl"
    unprocessed_events = []
    if events_file.exists():
        with events_file.open("r") as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    if not event.get("processed", True):
                        unprocessed_events.append(event)
                except json.JSONDecodeError:
                    continue

    # 根据 phase 检查状态一致性
    if phase:
        # phase=planner 但没有 case 分配
        if phase == "planner" and not verdicts:
            issues.append("phase=planner 但尚未分配 CASE")
            score -= 10

        # phase=generator 但所有 case 都 PASS
        if phase == "generator":
            pass_cases = [k for k, v in verdicts.items() if v == "PASS"]
            fail_cases = [k for k, v in verdicts.items() if v == "FAIL"]
            if pass_cases and not fail_cases:
                issues.append("generator 阶段已完成但未进行 evaluator 验收")
                score -= 5

        # phase 顺序检查
        if phase not in PHASE_SEQUENCE:
            issues.append(f"phase={phase} 不在预期序列中")
            score -= 5

    # blocker 检查
    if blocker_count > 5:
        issues.append(f"blocker_count={blocker_count} 过高")
        score -= 10

    # 未处理事件检查
    if len(unprocessed_events) > 5:
        issues.append(f"有 {len(unprocessed_events)} 条未处理事件")
        score -= 10

    # 检查 TAPD 同步状态
    tapd = state_data.get("integrations", {}).get("tapd", {})
    if tapd.get("enabled"):
        last_synced = tapd.get("last_synced_at")
        if last_synced:
            try:
                last_dt = datetime.fromisoformat(last_synced.replace("Z", "+00:00"))
                hours_ago = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                if hours_ago > 24:
                    issues.append(f"TAPD 已 {hours_ago:.0f}h 未同步")
                    score -= 10
            except ValueError:
                pass

    score = max(0, score)
    return {
        "score": score,
        "status": status_from_score(score),
        "issues": issues,
        "details": {
            "task_id": task_id,
            "story_id": story_id,
            "phase": phase,
            "verdict_count": len(verdicts),
            "pass_count": sum(1 for v in verdicts.values() if v == "PASS"),
            "fail_count": sum(1 for v in verdicts.values() if v == "FAIL"),
            "blocker_count": blocker_count,
            "unprocessed_events": len(unprocessed_events),
        }
    }


def check_architecture_compliance() -> dict:
    """检查架构合规性：fitness 规则检查结果"""
    issues = []
    score = 100

    # 读取 fitness 报告
    fitness_report = REPORTS_DIR / "fitness" / "fitness-run.json"
    if fitness_report.exists():
        try:
            data = json.loads(fitness_report.read_text())
            results = data.get("results", [])

            # 检查失败的规则
            for result in results:
                rule_name = result.get("rule", "unknown")
                passed = result.get("passed", True)
                if not passed:
                    issues.append(f"fitness rule {rule_name} 失败")
                    score -= 10

            # 检查报告是否过期（> 1小时）
            report_time = data.get("timestamp")
            if report_time:
                try:
                    report_dt = datetime.fromisoformat(report_time.replace("Z", "+00:00"))
                    hours_ago = (datetime.now(timezone.utc) - report_dt).total_seconds() / 3600
                    if hours_ago > 1:
                        issues.append(f"fitness 报告已过期（{hours_ago:.0f}h 前）")
                except ValueError:
                    pass
        except json.JSONDecodeError:
            issues.append("fitness-run.json 格式错误")
            score -= 5
    else:
        issues.append("fitness 报告不存在（建议运行 /fitness-run）")
        score -= 15

    # 检查 fitness 目录是否存在规则脚本
    fitness_dir = PROJECT_DIR / "fitness"
    if fitness_dir.exists():
        rule_scripts = list(fitness_dir.glob("*.sh"))
        if not rule_scripts:
            issues.append("fitness 目录无规则脚本")
            score -= 5
    else:
        issues.append("fitness 目录不存在")
        score -= 10

    score = max(0, score)
    return {"score": score, "status": status_from_score(score), "issues": issues}


def check_session_context() -> dict:
    """检查会话上下文：phase 偏差和 flow-log 评分趋势"""
    issues = []
    score = 100

    # 读取 workflow-state.json
    workflow_state = STATE_DIR / "workflow-state.json"
    state_data = {}
    if workflow_state.exists():
        try:
            state_data = json.loads(workflow_state.read_text())
        except json.JSONDecodeError:
            pass

    phase = state_data.get("phase")
    verdicts = state_data.get("verdicts", {})

    # 计算 phase 偏差
    if phase and phase in PHASE_SEQUENCE:
        phase_idx = PHASE_SEQUENCE.index(phase)

        # 检查是否有异常的 phase 跳跃
        if phase == "planner" and verdicts:
            issues.append("phase=planner 但已有 verdict（phase 可能跳跃）")
            score -= 15

        if phase == "generator" and not verdicts:
            issues.append("phase=generator 但尚未开始执行 CASE")
            score -= 10

        if phase == "evaluator" and not verdicts:
            issues.append("phase=evaluator 但无 verdict（无 CASE 可验收）")
            score -= 15

        # 检查 contract 状态与 phase 的匹配
        contract_path = state_data.get("artifacts", {}).get("contract", {}).get("path")
        if phase in ("planner", "generator") and not contract_path:
            issues.append(f"phase={phase} 但 contract 尚未生成")
            score -= 10
    elif phase:
        issues.append(f"phase={phase} 不在标准序列中")
        score -= 10
    else:
        issues.append("workflow-state.json 无 phase（正常，新会话）")
        score -= 5

    # 检查 flow-logs 趋势
    flow_logs_dir = CHATLABS_DIR / "flow-logs"
    if flow_logs_dir.exists():
        flow_logs = list(flow_logs_dir.glob("**/*.json"))
        if flow_logs:
            # 读取最近的 flow-log
            recent_logs = sorted(flow_logs, key=lambda p: p.stat().st_mtime, reverse=True)[:5]
            declining_scores = []
            for log_file in recent_logs:
                try:
                    data = json.loads(log_file.read_text())
                    dimensions = data.get("dimensions", {})
                    avg_score = sum(
                        d.get("score", 0) for d in dimensions.values()
                    ) / max(len(dimensions), 1)
                    declining_scores.append(avg_score)
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            # 检查评分趋势
            if len(declining_scores) >= 2:
                if declining_scores[0] < declining_scores[-1] - 2:
                    issues.append(f"flow-log 评分呈下降趋势（{declining_scores[-1]:.1f} → {declining_scores[0]:.1f}）")
                    score -= 10
        else:
            issues.append("无 flow-log 数据（尚未运行自审）")
            score -= 5
    else:
        issues.append("flow-logs 目录不存在（正常，初次运行）")
        score -= 5

    score = max(0, score)
    return {
        "score": score,
        "status": status_from_score(score),
        "issues": issues,
        "details": {
            "current_phase": phase,
            "phase_sequence": PHASE_SEQUENCE,
        }
    }


def compute_overall_score(scores: dict) -> dict:
    """计算综合评分"""
    dimension_scores = []
    weights = {
        "config": 1.0,
        "commands": 1.0,
        "runtime": 1.5,
        "architecture": 1.0,
        "session": 1.0,
    }

    total_weight = 0
    weighted_sum = 0

    for dim, data in scores.items():
        weight = weights.get(dim, 1.0)
        dimension_scores.append({"dimension": dim, "score": data["score"], "weight": weight})
        weighted_sum += data["score"] * weight
        total_weight += weight

    overall = round(weighted_sum / total_weight) if total_weight > 0 else 0

    return {
        "overall_score": overall,
        "overall_status": status_from_score(overall),
        "dimensions": dimension_scores,
    }


def generate_recommendations(scores: dict) -> list[dict]:
    """生成优先级建议"""
    recommendations = []

    # 从各维度收集问题
    priority_map = {"fail": "P0", "warn": "P1", "pass": "P2"}

    for dim, data in scores.items():
        status = data["status"]
        priority = priority_map.get(status, "P2")

        for issue in data.get("issues", []):
            # 跳过 "正常" 的提示
            if "正常" in issue or "建议运行" in issue:
                continue

            recommendations.append({
                "priority": priority,
                "dimension": dim,
                "issue": issue,
            })

    # 按优先级排序
    priority_order = {"P0": 0, "P1": 1, "P2": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 2))

    return recommendations[:10]  # 最多返回 10 条


def format_markdown_report(
    check_type: str,
    flow_version: str,
    scores: dict,
    overall: dict,
    recommendations: list,
    report_id: str,
) -> str:
    """生成 Markdown 格式报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "═══════════════════════════════════════",
        "  Flow 健康检查报告",
        f"  时间: {now} | 范围: {check_type} | 版本: {flow_version}",
        "═══════════════════════════════════════",
        "",
    ]

    dim_labels = {
        "config": "配置健康度",
        "commands": "命令/Skill 可用性",
        "runtime": "运行时状态",
        "architecture": "架构合规性",
        "session": "会话上下文",
    }

    # 维度详情
    for dim, data in scores.items():
        label = dim_labels.get(dim, dim)
        icon = icon_for_status(data["status"])
        score = data["score"]
        status_label = {"pass": "通过", "warn": "警告", "fail": "失败"}.get(data["status"], "")

        lines.append(f"## {icon} {label}  [{status_label}] {score}/100")

        # 显示问题
        if data.get("issues"):
            for issue in data["issues"][:3]:  # 最多显示 3 个
                lines.append(f"  - {issue}")
        else:
            lines.append("  ✓ 无问题")

        # 显示额外详情
        if data.get("details"):
            for key, value in data["details"].items():
                lines.append(f"  - {key}: {value}")

        lines.append("")

    # 综合评分
    overall_icon = icon_for_status(overall["overall_status"])
    status_text = {"pass": "优秀", "warn": "良好，有改进空间", "fail": "需要修复"}.get(
        overall["overall_status"], ""
    )
    lines.extend([
        "───────────────────────────────────────",
        f"  综合健康分: {overall['overall_score']}/100  {overall_icon} {status_text}",
        "",
        "  📋 优先建议:",
    ])

    if recommendations:
        for i, rec in enumerate(recommendations[:5], 1):
            lines.append(f"  {i}. [{rec['priority']}] {rec['issue']}")
    else:
        lines.append("  ✓ 无需建议")

    lines.extend([
        "",
        f"  📁 详细报告: {FLOW_CHECK_REPORTS}/FC-{report_id}.json",
        "═══════════════════════════════════════",
    ])

    return "\n".join(lines)


def generate_json_report(
    check_type: str,
    flow_version: str,
    scores: dict,
    overall: dict,
    recommendations: list,
    report_id: str,
) -> dict:
    """生成 JSON 格式报告"""
    return {
        "id": f"FC-{report_id}",
        "timestamp": ts(),
        "check_type": check_type,
        "flow_version": flow_version,
        "scores": scores,
        "overall_score": overall["overall_score"],
        "overall_status": overall["overall_status"],
        "recommendations": recommendations,
        "metadata": {
            "report_path": str(FLOW_CHECK_REPORTS / f"FC-{report_id}.json"),
        }
    }


def run_check(check_type: str = "full", verbose: bool = False) -> dict:
    """执行健康检查"""
    # 确定要执行的检查维度
    check_map = {
        "full": ["config", "commands", "runtime", "architecture", "session"],
        "config": ["config", "commands"],
        "runtime": ["runtime", "architecture"],
        "session": ["session"],
        "health": ["config", "commands", "runtime", "architecture", "session"],
    }

    dimensions = check_map.get(check_type, check_map["full"])

    # 执行检查
    scores = {}
    check_functions = {
        "config": check_config_health,
        "commands": check_command_skill_availability,
        "runtime": check_runtime_state,
        "architecture": check_architecture_compliance,
        "session": check_session_context,
    }

    for dim in dimensions:
        if dim in check_functions:
            scores[dim] = check_functions[dim]()

    # 计算综合评分
    overall = compute_overall_score(scores)

    # 生成建议
    recommendations = generate_recommendations(scores)

    # 读取 flow 版本
    manifest = CLAUDE_DIR / "MANIFEST.md"
    flow_version = "unknown"
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            if line.startswith("`flow_version:"):
                flow_version = line.split(":")[-1].strip().strip("`")
                break

    # 生成报告 ID
    today = datetime.now().strftime("%Y%m%d")
    seq_num = compute_seq_num()
    report_id = f"{today}-{seq_num:03d}"

    # 生成报告
    markdown = format_markdown_report(
        check_type, flow_version, scores, overall, recommendations, report_id
    )
    json_report = generate_json_report(
        check_type, flow_version, scores, overall, recommendations, report_id
    )

    # 保存 JSON 报告
    report_file = FLOW_CHECK_REPORTS / f"FC-{report_id}.json"
    report_file.write_text(json.dumps(json_report, ensure_ascii=False, indent=2))

    return {
        "markdown": markdown,
        "json": json_report,
        "scores": scores,
        "overall": overall,
        "recommendations": recommendations,
    }


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="Flow 健康检查工具")
    parser.add_argument(
        "--check-type", "-t",
        choices=["full", "config", "runtime", "session", "health"],
        default="full",
        help="检查范围（默认 full）"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")

    args = parser.parse_args()

    result = run_check(check_type=args.check_type, verbose=args.verbose)

    print(result["markdown"])

    if args.verbose:
        print("\n--- JSON 报告 ---")
        print(json.dumps(result["json"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
