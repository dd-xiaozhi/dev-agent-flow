---
name: tapd-pull
description: 拉取 TAPD 工单到本地缓存（.chatlabs/tapd/tickets/*.json）+ 维护 _index.jsonl。被 /tapd-ticket-sync 和 /tapd-story-start 调用。触发关键词：tapd 拉取、ticket sync、同步工单、拉工单。
---

# TAPD Pull Skill

> 工单拉取与本地缓存维护。增量同步策略，不重复请求未变化的字段。

## 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `workspace_id` | int | 必填，从 tapd-config 读 |
| `entity_type` | string | stories / tasks / bug，默认 stories |
| `owner` | string? | 默认 owner_nick |
| `iteration_id` | string? | 限定迭代 |
| `since` | iso? | 增量起点，默认 last_sync_at |
| `force_full` | bool | 强制全量拉，忽略 since |

## 输出

| 路径 | 内容 |
|------|------|
| `.chatlabs/tapd/tickets/<id>.json` | 单条工单缓存（schema：ticket.schema.json） |
| `.claude/tapd/_index.jsonl` | 全量索引（覆盖写） |
| `project-config.json.tapd.last_sync_at` | 更新 |

## 流程

```
1. 拉摘要列表：
   - 默认 entity_type=stories：mcp__chopard-tapd__get_todo
   - 否则：mcp__chopard-tapd__get_stories_or_tasks(owner=..., iteration_id=...)
2. 对每条 ID，拉详情：
   - mcp__chopard-tapd__get_stories_or_tasks(id=<id>, fields="id,name,status,description,iteration_id,iteration_name,workitem_type_name,owner,...")
3. 对每条详情：
   - 读现有 ticket.json（如有），保留 local_mapping、subtasks、comments_cache 字段
   - 用新返回字段覆盖 fields_cache、status_at_pull、pulled_at
   - 校验 schema → 写文件
4. 重建 _index.jsonl（按 ticket_id 排序，便于 grep）
5. 更新 project-config.json.tapd.last_sync_at
```

## 关键约束

- **保留本地状态**：`local_mapping`、`subtasks`、`comments_cache` 是本地累积的，不能被远端拉取覆盖
- 拉详情时 `fields` 参数显式列出，避免拉一堆无用字段
- 全量重建 _index.jsonl，避免 jsonl 增量写时的并发损坏

## 失败处理

| 场景 | 行为 |
|------|------|
| 单条拉取失败 | 跳过，记录到 stderr + Blocker（信息-外部依赖） |
| 全部失败 | 不动 _index.jsonl，写 Blocker 退出 |
| 字段缺失 | 用 null 占位，schema 校验时若必填则报错 |

## 依赖 MCP 工具清单

- `mcp__chopard-tapd__get_todo`
- `mcp__chopard-tapd__get_stories_or_tasks`
- `mcp__chopard-tapd__get_iterations`（可选，校验 iteration_id 有效性）

## 关联

- Commands: `.claude/commands/tapd/tapd-ticket-sync.md`、`.claude/commands/tapd/tapd-story-start.md`
- 配置：`.chatlabs/project-config.json`
