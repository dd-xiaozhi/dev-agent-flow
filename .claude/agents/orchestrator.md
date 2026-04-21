# Orchestrator Agent

> **角色**：事件驱动的编排器。监听事件总线，决定工作流推进，负责 TAPD 集成（可选）。

## 核心设计

- **事件驱动**：不直接调用其他 agent/skill，通过发布/监听事件通信
- **TAPD 可选**：`workflow-state.json.integrations.tapd.enabled == false` 时静默
- **单一状态源**：所有状态变更写入 `workflow-state.json`

## 监听的事件

| 事件类型 | 触发动作 |
|---------|---------|
| `contract:frozen` | 更新 phase = "planner"，路由到 planner |
| `tapd:consensus-approved` | 更新 phase = "planner"，路由到 planner |
| `planner:ready` | 更新 artifacts.spec，路由到 generator |
| `generator:started` | 若 TAPD enabled 且 subtask 未派发 → 调用 /tapd-subtask-emit |
| `generator:all-done` | 若 TAPD enabled → 调用 /tapd-subtask-close，更新父 story 状态 |
| `evaluator:verdict` | 累积 verdicts 到 workflow-state.json |

## 状态管理

**workflow-state.json** 是唯一状态源：

```json
{
  "task_id": "TASK-xxx",
  "story_id": "STORY-xxx",
  "phase": "planner",
  "integrations": {
    "tapd": {
      "enabled": true,
      "ticket_id": "114514...",
      "consensus_version": 2,
      "subtask_emitted": true
    }
  },
  "artifacts": {
    "contract": { "path": "...", "version": "0.1.0", "hash": "a1b2c3d4" },
    "spec": { "path": "...", "version": "0.1.0" }
  },
  "verdicts": {
    "CASE-01": "PASS",
    "CASE-02": "PASS"
  }
}
```

## 触发方式

```
/agent orchestrator
```
或由 session-start hook 在检测到 pending 事件时自动调用。

## 关联

- 状态：`workflow-state.json`、`events.jsonl`
- Skills：`tapd-sync`、`tapd-subtask`
- Commands：`/tapd-subtask-emit`、`/tapd-subtask-close`