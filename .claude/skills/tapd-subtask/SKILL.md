---
name: tapd-subtask
description: 子任务派发与状态机管理。emit 派发 cases 到 TAPD；close/reopen 双向同步状态。强制走"工作流前置三检查"。被 /tapd-subtask-emit、close、reopen 调用。触发关键词：子任务派发、subtask emit、QA 通过、QA 打回。
---

# TAPD Subtask Skill

> 子任务生命周期 + 状态机。**所有状态变更必须走"工作流前置三检查"**。

## 工作流前置三检查（强制，所有 mode 共用）

```
function check_transition(entity_type, current_status, target_local_key):
    config = read tapd-config.json
    target_status = config.status_map[entity_type][target_local_key]

    # 1. 二次确认目标态英文名仍存在
    map = mcp__chopard-tapd__get_workflows_status_map(system=entity_type, workitem_type_id=...)
    if target_status not in map:
        raise Blocker("信息-技术决策", "状态映射陈旧：{target_status} 在当前工作流不存在")

    # 2. 确认转换合法
    transitions = mcp__chopard-tapd__get_workflows_all_transitions(...)
    if (current_status, target_status) not in transitions:
        raise Blocker("信息-技术决策", "状态不可达：{current_status} → {target_status}")

    return target_status
```

---

## Mode A：Emit

### 输入
| 参数 | 类型 |
|------|------|
| `ticket_id` | string |
| `force` | bool |
| `dry_run` | bool |

### 流程
```
1. 校验：consensus_version > 0、subtask_emitted == false（除非 --force）
2. 读 cases/*.md 列表
3. 对每个 case，构造 task 对象
4. 人工确认列表
5. 批量 mcp__chopard-tapd__create_story_or_task(entity_type="tasks", story_id=ticket_id, ...)
6. 失败的 case 跳过 + Blocker
7. 写回 ticket.subtasks
8. 评论 [SUBTASK-EMITTED]
```

---

## Mode B：Close

### 输入
| 参数 | 类型 |
|------|------|
| `case_id` | string（本地 TASK-* ID） |

### 流程
```
1. 读 .chatlabs/reports/tasks/<case_id>/meta.json，校验 verdict == "PASS"
2. 反查 ticket_id（_index.jsonl + ticket.subtasks 匹配 local_case_id）
3. 走"工作流前置三检查"：current_status → to_test
4. mcp__chopard-tapd__update_story_or_task(entity_type="tasks", id=tapd_task_id, v_status=...)
5. 验证：mcp__chopard-tapd__get_stories_or_tasks(id=..., fields="id,status")
6. 评论 [QA-PASSED] 占位
7. 更新 ticket.subtasks[*].local_phase=done、tapd_status=...
```

---

## Mode C：Reopen

### 输入
| 参数 | 类型 |
|------|------|
| `case_id` | string |
| `reason` | string（≥5字符） |

### 流程
```
1. 校验 reason 非空、meta.phase == "done"
2. 反查 ticket + subtask
3. 工作流三检查：current_status → to_dev
4. 本地：meta.phase = in_progress、verdict = WIP
5. blockers.md 追加 [QA 打回] 条目
6. mcp__chopard-tapd__update_story_or_task(... v_status=to_dev_chinese)
7. mcp__chopard-tapd__create_comments [QA-REJECTED:reason]
8. 更新 ticket.subtasks[*].local_phase=in_progress
```

---

## 关键约束

- **强制工作流三检查**：跳过会导致状态机崩坏
- **优先用 v_status（中文别名）而非 status（英文）**：跨 workspace 更稳定
- **本地状态先更，TAPD 后更**：失败可自然回滚（最差是 TAPD 比本地新，下次 fetch 修正）
- **dry_run 必须真不调 MCP**：测试态保护

## 失败处理

| 场景 | 行为 |
|------|------|
| verdict != PASS | 拒绝 close |
| 状态不可达 | Blocker（信息-技术决策） |
| TAPD 更新成功，本地写失败 | 严重告警（state 撕裂），输出修复指引 |
| reason 太短或缺失 | 拒绝 reopen |

## 依赖 MCP 工具清单

- `mcp__chopard-tapd__create_story_or_task`
- `mcp__chopard-tapd__update_story_or_task`
- `mcp__chopard-tapd__get_stories_or_tasks`
- `mcp__chopard-tapd__get_workflows_status_map`
- `mcp__chopard-tapd__get_workflows_all_transitions`
- `mcp__chopard-tapd__create_comments`

## 关联

- Commands: `tapd-subtask-emit.md`、`tapd-subtask-close.md`、`tapd-subtask-reopen.md`
- Schema: `ticket.schema.json`（subtasks 段）+ `tapd-config.schema.json`（status_map 段）
