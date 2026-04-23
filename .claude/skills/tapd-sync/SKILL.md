---
name: tapd-sync
description: 事件驱动的 TAPD 同步适配器。监听 contract:frozen 事件推送契约到 TAPD，监听 TAPD 评论发布 consensus-approved 事件。触发关键词：tapd同步、TAPD事件、consensus事件驱动。
---

# TAPD Sync Skill（事件驱动版）

> TAPD 同步作为事件消费者，不依赖 doc-librarian 直接调用。
> 所有状态变更通过 `workflow-state.json`，事件通过 `events.jsonl` 传播。

## 核心设计

- **事件驱动**：监听 `contract:frozen` → push；监听 `[CONSENSUS-APPROVED]` → 发布 `tapd:consensus-approved`
- **状态隔离**：TAPD 相关状态全在 `workflow-state.json.integrations.tapd`
- **可选插件**：TAPD 未启用时完全静默，不阻断主流程

## 模式 A：Push（事件触发）

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `story_id` | string | 必填，从事件中获取 |
| `version` | int | 自动从 workflow-state.json.integrations.tapd.consensus_version + 1 |

### 流程

```
1. 检查 workflow-state.json.integrations.tapd.enabled == true
   → false：静默退出
2. 读取 contract.md，校验 frontmatter status == "frozen"
3. 提取摘要（第 1-5 节统计 + changelog）
4. 构造评论文本（4000 字符上限）
5. AskUserQuestion 确认推送
6. dry_run=true → 打印不推
7. dry_run=false → mcp__chopard-tapd__create_comments
8. 更新 workflow-state.json：
   - consensus_version += 1
   - last_synced_at = now()
9. 追加事件到 events.jsonl：
   { "type": "tapd:consensus-pushed", "story_id": "...", "actor": "tapd-sync" }
```

## 模式 B：Fetch（定期轮询或事件触发）

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `story_id` | string | 必填 |
| `since` | iso? | 默认 last_synced_at |

### 流程

```
1. 检查 TAPD enabled
2. mcp__chopard-tapd__get_comments(entry_id=ticket_id, ...)
3. 过滤 created > since
4. 对每条识别前缀标记（按 tapd-config.comment_markers）
5. 路由到对应 feedback 目录
6. 若有 [CONSENSUS-APPROVED]：
   - 追加事件：{ "type": "tapd:consensus-approved", "story_id": "...", "actor": "tapd-sync" }
7. 更新 workflow-state.json.last_synced_at
```

## 监听的事件

| 事件类型 | 触发动作 |
|---------|---------|
| `contract:frozen` | 检查 TAPD enabled → push → 发布 `tapd:consensus-pushed` |
| `tapd:consensus-approved` | 更新 workflow-state.json phase = "planner"，session-start hook 会自动路由到 planner |

## 关键约束

- **评论字符上限**：4000 字符
- **版本号单调递增**：consensus_version 只增不减
- **TAPD 可选**：enabled == false 时静默退出
- **事件幂等**：重复 push 不重复发评论（靠 consensus_version 防重）

## 依赖 MCP 工具

- `mcp__chopard-tapd__create_comments`
- `mcp__chopard-tapd__get_comments`

## 实现说明

本 SKILL.md 是规范文档。实际的事件监听通过 session-start.py 的事件分发器实现。

**session-start 中转模式**（已实现）：

| 事件类型 | session-start 消费动作 |
|---------|----------------------|
| `contract:frozen` | 若 TAPD enabled，提示执行 `/tapd-consensus-push` 推送契约到 TAPD |
| `tapd:consensus-approved` | 更新 phase = "planner"，session-start 会自动路由到 planner |
| `planner:all-cases-ready` | 自动派发 TAPD subtask + 路由到 generator |

**手动路径**（备用）：

- `/tapd-consensus-push` — 手动推送契约到 TAPD（绕过事件系统）
- `/tapd-consensus-fetch` — 手动拉取 TAPD 评论（用于主动检查评审结果）

两种路径并存：事件自动触发 + 手动命令触发。优先使用事件路径，手动路径作为备选。

## Feedback 路由

TAPD 评论识别后路由到以下目录：

| 前缀标记 | 路由目录 | 说明 |
|---------|---------|------|
| `[CONSENSUS-APPROVED]` | `.chatlabs/stories/<story_id>/feedback/approved/` | PM 评审通过 |
| `[CONSENSUS-REJECTED]` | `.chatlabs/stories/<story_id>/feedback/rejected/` | PM 打回 |
| `[QA-PASS]` | `.chatlabs/stories/<story_id>/feedback/qa/` | QA 通过 |
| `[QA-FAIL]` | `.chatlabs/stories/<story_id>/feedback/qa/` | QA 打回 |
| 其他 | `.chatlabs/stories/<story_id>/feedback/misc/` | 其他评论 |

每次路由生成文件：`feedback/<marker>-<timestamp>.md`，内容包含原始评论 + 元数据（story_id、created_at、marker）。

## 关联

- Commands: `tapd-consensus-push.md`、`tapd-consensus-fetch.md`
- State: `workflow-state.json`、`events.jsonl`
- Schema: `tapd-config.schema.json`
- 事件分发器: `.claude/hooks/session-start.py`（`_dispatch_pending_events` 函数）