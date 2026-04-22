#!/usr/bin/env python3
"""
member-activity-skill.py — 成员活动查询 Skill

提供查询成员活动历史、生成贡献报告等功能。
"""
import json
import sys
from pathlib import Path

# Import centralized path constants
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from member_log_utils import (  # noqa: E402
    load_member_activity, get_member_context, search_activities,
    get_current_member
)


def format_activity(entry: dict) -> str:
    """格式化单个活动条目为可读字符串"""
    ts = entry.get("ts", "?")
    event_type = entry.get("type", "?")
    summary = entry.get("summary", "")

    # 根据事件类型生成更详细的描述
    if event_type == "session-start":
        task_id = entry.get("task_id", "")
        return f"[{ts}] 会话开始 {'(任务: ' + task_id + ')' if task_id else ''}"
    elif event_type == "session-end":
        duration = entry.get("session_duration", 0)
        files = entry.get("files_changed", 0)
        return f"[{ts}] 会话结束 (时长: {duration}s, 文件: {files})"
    elif event_type == "file-changed":
        files = entry.get("files", [])
        return f"[{ts}] 修改文件: {', '.join(files[:3])}{'...' if len(files) > 3 else ''}"
    elif event_type == "task-done":
        task_id = entry.get("task_id", "?")
        cases = entry.get("cases_completed", 0)
        return f"[{ts}] 任务完成: {task_id} (完成 {cases} 个 case)"
    elif event_type == "story-done":
        story_id = entry.get("story_id", "?")
        cases = entry.get("cases", 0)
        return f"[{ts}] Story 完成: {story_id} (共 {cases} 个 case)"
    else:
        return f"[{ts}] {summary or event_type}"


def format_activities(activities: list[dict]) -> str:
    """格式化活动列表"""
    if not activities:
        return "无活动记录"

    lines = []
    for entry in activities:
        lines.append(format_activity(entry))
    return "\n".join(lines)


def get_member_report(member_id: str) -> str:
    """生成成员贡献报告"""
    context = get_member_context(member_id, limit=50)
    stats = context.get("stats", {})

    report_lines = [
        f"# 成员贡献报告: {member_id}",
        "",
        f"## 统计数据",
        f"- 活跃会话数: {stats.get('active_sessions', 0)}",
        f"- 完成任务数: {stats.get('tasks_completed', 0)}",
        f"- 完成 Story 数: {stats.get('stories_completed', 0)}",
        "",
        f"## 最近活动 (最近 20 条)",
        format_activities(context.get("recent_activities", [])),
    ]

    return "\n".join(report_lines)


def main():
    """命令行入口，用于测试和调试"""
    import argparse

    parser = argparse.ArgumentParser(description="成员活动查询工具")
    parser.add_argument("--member", "-m", help="指定成员 ID（默认当前成员）")
    parser.add_argument("--limit", "-l", type=int, default=20, help="返回最近 N 条活动")
    parser.add_argument("--report", "-r", action="store_true", help="生成成员贡献报告")
    parser.add_argument("--task-id", "-t", help="搜索特定任务的活动")
    parser.add_argument("--story-id", "-s", help="搜索特定 Story 的活动")
    parser.add_argument("--type", "-T", help="过滤事件类型")

    args = parser.parse_args()

    # 确定成员 ID
    member_id = args.member or get_current_member()

    if args.report:
        print(get_member_report(member_id))
    elif args.task_id or args.story_id or args.type:
        results = search_activities(
            member=member_id if args.member else None,
            task_id=args.task_id,
            story_id=args.story_id,
            event_type=args.type,
            limit=args.limit
        )
        print(f"# {member_id} 的搜索结果 (共 {len(results)} 条)")
        print(format_activities(results))
    else:
        activities = load_member_activity(member_id, limit=args.limit)
        print(f"# {member_id} 的最近活动")
        print(format_activities(activities))


if __name__ == "__main__":
    main()