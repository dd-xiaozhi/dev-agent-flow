# /tapd-subtask-reopen

> **[Internal]** 由 start-dev-flow 或 session-start hook 内部调用，用户不直接使用。

> QA 打回时使用：本地 case phase 回退到 in_progress + TAPD 子任务回退到开发态。
>
> **用法**：`/tapd-subtask-reopen <case_id> --reason "<打回原因>"`

## 行为

### 第一步：前置校验
1. `--reason` 必填，且长度 ≥ 5 字符（防止空打回）
2. 读本地 `.chatlabs/reports/tasks/<case_id>/meta.json`
3. 校验 `meta.phase == "done"`（只有 done 才能 reopen）
4. 在 `.claude/tapd/_index.jsonl` 反查 ticket_id，读 ticket.json 找到对应 subtask

### 第二步：状态机三步前置检查
1. 读 `tapd-config.json.status_map.task.to_dev`（目标态，通常是 progressing）
2. `mcp__chopard-tapd__get_workflows_status_map(system="task", ...)` 二次确认
3. `mcp__chopard-tapd__get_workflows_all_transitions(...)` 确认从当前 tapd_status 可达 to_dev
4. 不可达 → Blocker，退出

### 第三步：本地状态回退
1. 更新 `.chatlabs/reports/tasks/<case_id>/meta.json`:
   - `phase = "in_progress"`
   - `verdict = "WIP"`
2. 在 `.chatlabs/reports/tasks/<case_id>/blockers.md` 追加：
   ```
   ## {timestamp} [QA 打回]
   - **类型**: 业务-验收失败
   - **来源**: TAPD QA 反馈
   - **原因**: {--reason 内容}
   - **解决状态**: 待解决
   - **解决方案**: 修复后重新 /tapd-subtask-close
   ```
3. 在 summary.md 追加打回记录

### 第四步：更新 TAPD
1. `mcp__chopard-tapd__update_story_or_task(options={entity_type="tasks", id=tapd_task_id, v_status=to_dev_chinese})`
2. `mcp__chopard-tapd__create_comments(entry_id=tapd_task_id, entry_type="tasks", description="[QA-REJECTED:{reason}] 本地 case 已重置为 in_progress，将重新开发。本地 case: <case_id>")`

### 第五步：更新缓存
1. `ticket.subtasks[*]`:
   - `local_phase = "in_progress"`
   - `tapd_status = <to_dev 英文>`
   - `last_synced_at = now()`

### 第六步：输出
```
⚠️ 子任务已重新打开
  · 本地 case: TASK-STORY001-03 (phase: done → in_progress)
  · TAPD task: {url} (status: 待测试 → 进行中)
  · 打回原因: {reason}
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<case_id>` | 是 | 本地 case ID |
| `--reason "<text>"` | 是 | 打回原因，≥5 字符 |

## 产出

- 本地 meta.json + blockers.md + summary.md 更新
- TAPD 子任务状态变更
- TAPD 评论 [QA-REJECTED:reason]
- 更新 `ticket.json.subtasks[*]`

## 失败处理

| 场景 | 行为 |
|------|------|
| --reason 缺失或太短 | 拒绝 |
| meta.phase != done | 拒绝（"未完成无需 reopen"） |
| 状态不可达 | Blocker |
| TAPD 更新成功但本地写失败 | 严重（state 撕裂），输出大写告警 + 手工修复指引 |

## 关联

- Skill: `.claude/skills/tapd-subtask/SKILL.md`
- 配对：`/tapd-subtask-close`
- 触发：`/tapd-consensus-fetch` 检测到 [QA-REJECTED]
