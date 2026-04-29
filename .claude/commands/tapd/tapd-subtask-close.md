---
name: tapd-subtask-close
description: '[Internal] 标记本地 case 完成 + 把 TAPD 子任务推到"待测试"状态。由 start-dev-flow 或 session-start hook 内部调用。'
model: haiku
---

# /tapd-subtask-close

> **[Internal]** 由 start-dev-flow 或 session-start hook 内部调用，用户不直接使用。

> 标记本地 case 完成 + 把 TAPD 子任务推到"待测试"状态。
>
> **用法**：`/tapd-subtask-close <case_id>`

## 行为

### 第一步：前置校验
1. 读本地 `.chatlabs/reports/tasks/<case_id>/meta.json`
2. 校验 `meta.verdict == "PASS"`，否则拒绝
3. 在 `.claude/tapd/_index.jsonl` 反查 `case_id` 所属的 ticket_id
4. 读 ticket.json，找到 `subtasks[*]` 中 `local_case_id == case_id` 的记录

### 第二步：状态机三步前置检查（强制）
1. 读 `project-config.json.tapd.status_map.task.to_test`（目标态）
2. `mcp__chopard-tapd__get_workflows_status_map(system="task", workitem_type_id=...)` 二次确认目标态英文名仍存在
3. `mcp__chopard-tapd__get_workflows_all_transitions(system="task", workitem_type_id=...)` 确认从 `subtask.tapd_status` 可达 `to_test`
4. 不可达 → 写 Blocker（信息-技术决策），输出"当前 TAPD 状态 X 无法直接转到待测试，请人工处理"，退出

### 第三步：更新 TAPD 状态
1. `mcp__chopard-tapd__update_story_or_task(workspace_id=..., options={entity_type="tasks", id=tapd_task_id, v_status=to_test_chinese_name})`
   - 用 `v_status`（中文别名）更稳，避免 status 英文名跨 workspace 差异
2. 验证：`mcp__chopard-tapd__get_stories_or_tasks(id=tapd_task_id, fields="id,status")` 确认生效

### 第四步：发评论
1. `mcp__chopard-tapd__create_comments(entry_id=tapd_task_id, entry_type="tasks", description="[QA-PASSED] 本地 case 完成验收 (verdict=PASS)，等待 QA 测试。本地 case: <case_id>")`

### 第五步：更新本地 ticket.json
1. 更新对应 subtask：
   - `local_phase = "done"`
   - `tapd_status = <to_test 英文名>`
   - `last_synced_at = now()`
2. 更新 `ticket.last_synced_at`

### 第六步：输出
```
✓ TAPD 子任务已推送到"待测试"
  · 本地 case: TASK-STORY001-03 (verdict=PASS)
  · TAPD task: {url}
  · TAPD 状态: progressing → 待测试
等待 QA 反馈：
  · 通过 → TAPD 评论 [QA-PASSED]，本地无需操作
  · 打回 → TAPD 评论 [QA-REJECTED:reason]，运行 /tapd-subtask-reopen <case_id>
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<case_id>` | 是 | 本地 TASK-STORYNNN-XX |

## 产出

- TAPD 子任务状态变更
- TAPD 评论 [QA-PASSED]
- 更新 `ticket.json.subtasks[*]`

## 失败处理

| 场景 | 行为 |
|------|------|
| meta.verdict != PASS | 拒绝 |
| ticket 未在本地索引 | 提示先 `/tapd-ticket-sync` |
| 状态不可达 | Blocker（信息-技术决策） |
| 更新成功但验证失败 | 写日志 + 提示用户去 TAPD 检查 |

## 关联

- Skill: `.claude/skills/tapd-subtask/SKILL.md`
- 上游：evaluator 给出 PASS verdict
- 配对：`/tapd-subtask-reopen`
