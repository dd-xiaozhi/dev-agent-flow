---
name: gc
description: 工作流熵管理：清理 stale TAPD cache、孤立 _index 条目、过期 task report、过量 source 快照。每日定时（3:00）或手动触发。触发关键词：gc、垃圾回收、清理、cleanup、定时清理。
model: haiku
---

# GC — 工作流熵管理

## 职责

定期清理主流程积累的元数据熵，保持工作流状态可维护。

## 扫描项（与主流程一一对应）

| 扫描类型 | 来源 | 阈值 | 动作 |
|---------|------|------|------|
| stale_ticket_cache | `.chatlabs/tapd/tickets/*.json` | 30 天未更新 | archive_to_reports_gc |
| orphaned_index_entry | `_index.jsonl` 中 task_id 目录不存在 | 7 天持续孤儿 | remove_from_index |
| stale_task_report | `reports/tasks/TASK-*/meta.json` | 60 天未更新 + terminal phase | archive_to_reports_gc |
| stale_source_snapshots | `tasks/stories/*/source/*.md` | 单 story 超 10 个快照 | review_snapshots（不自动删除） |
| stale_flow_logs | `.chatlabs/flow-logs/YYYY-MM/*.json` | insights 已提炼后超过 60 天 | archive_flow_logs（只删除已提炼洞察的日志） |
| orphaned_insights | `insights/_index.jsonl` 中有 proposal_id 但对应提案不存在 | 持续孤儿 | remove_from_insights_index |

**原则：**
- 永远不删除 source 快照（审计链不可破坏）
- 永远不自动删除（dry_run 优先）
- `_index.jsonl orphan` 是唯一可安全自动清理的项
- flow-log 只 archive 已提炼洞察且超过 60 天的原始日志
- 洞察索引条目只清理孤立的 proposal_id 引用

## 模式

```bash
# dry_run（默认）— 只产出报告
python .claude/scripts/gc.py

# apply（需确认）— 执行清理
python .claude/scripts/gc.py --apply
```

## 报告

- 位置：`.chatlabs/reports/gc/YYYY-MM-DD.json`
- 内容：每项发现 + action + reason + 影响范围

## 触发方式

| 方式 | 说明 |
|------|------|
| 每日定时（session-start） | 每天首次 session 自动触发 dry_run |
| 手动 | `python .claude/scripts/gc.py` 或 `/gc` |

## 关联

- 脚本：`.claude/scripts/gc.py`
- 报告目录：`.chatlabs/reports/gc/`
