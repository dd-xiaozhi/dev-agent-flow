# /tapd-subtask-emit

> **[Internal]** 由 start-dev-flow 或 session-start hook 内部调用，用户不直接使用。

> 把本地 cases 派发到 TAPD 作为子任务（task entity）。
>
> **用法**：`/tapd-subtask-emit <ticket_id> [--dry-run]`

## 行为

### 第一步：前置校验
1. 读 `.chatlabs/tapd/tickets/<ticket_id>.json`
2. 校验：
   - `local_mapping.story_id != null`
   - `local_mapping.consensus_version > 0`（必须先推过共识）
   - `subtask_emitted == false`（防重，覆盖需 `--force`）
3. 读 `.chatlabs/stories/<story_id>/cases/`，列出所有 case md

### 第二步：状态机前置检查
1. 读 `project-config.json.tapd.status_map.task.to_dev`
2. `mcp__chopard-tapd__get_workflows_status_map(system="task", workitem_type_id=...)` 二次确认
3. 不一致 → 写 Blocker，退出（防止配置陈旧）

### 第三步：构造子任务列表
对每个 case md：
1. 解析 frontmatter：case_id、title、acceptance_criteria
2. 构造 task 对象：
   - `name`: 角色前缀 + case 标题（截断到 60 字符）
     - 前缀规则：按 case type 确定实现者角色前缀
     - `type=backend → 【BE】`（后端实现）
     - `type=frontend → 【FE】`（前端实现）
     - `type=infra → 【INFRA】`（基础设施）
     - `type=doc → 【DOC】`（文档）
     - type 未知或为空 → 不加前缀
     - 去掉 title 中已有的项目标识前缀（如 `[bde-simple-report]`、`[xxx]`、`【xxx】`）
   - `entity_type`: "tasks"
   - `story_id`: ticket_id（父 story）
   - `description`: 引用 case md 的 repo URL + AC 摘要
   - `owner`: project-config.json.tapd.owner_nick
   - `iteration_id`: ticket.iteration_id（如非空）

### 第四步：批量派发
对每个 task 对象：
1. `mcp__chopard-tapd__create_story_or_task(workspace_id=..., name=..., options={entity_type="tasks", story_id=ticket_id, ...})`
2. 拿到 tapd_task_id 和 url
3. 追加到 `ticket.subtasks`：
   ```json
   {
     "tapd_task_id": "...",
     "tapd_task_url": "...",
     "local_case_id": "TASK-STORYNNN-XX",
     "local_phase": "pending",
     "tapd_status": "open"
   }
   ```
4. 失败 → 写 Blocker，跳过该条

### 第五步：写评论标记 + 更新缓存
1. 在父 ticket 上发评论 `[SUBTASK-EMITTED]`，列出新建子任务 ID 列表
2. 更新 `ticket.local_mapping.subtask_emitted = true`、`subtask_emitted_at = now()`

### 第六步：输出
```
✓ 已派发 N 个子任务到 TAPD
  · TASK-STORY001-01 → tapd:1145141919810002 ({url})
  · TASK-STORY001-02 → tapd:1145141919810003 ({url})
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id>` | 是 | TAPD 父工单 ID |
| `--dry-run` | 否 | 仅预览 |
| `--force` | 否 | 重派（已派过的会重复创建，慎用） |

## 产出

- TAPD 子任务 N 个
- 更新 `ticket.json.subtasks` + `local_mapping.subtask_emitted`
- TAPD 评论 [SUBTASK-EMITTED]

## 失败处理

| 场景 | 行为 |
|------|------|
| 共识未推过 | 拒绝，提示先 `/tapd-consensus-push` |
| subtask_emitted == true 且无 --force | 拒绝 |
| 部分 case 派发失败 | 已派发的保留，失败的写 Blocker |
| 工作流状态映射不一致 | 立即停止全批，写 Blocker（信息-技术决策） |

## 关联

- Skill: `.claude/skills/tapd-subtask/SKILL.md`
- 上游：planner 完成 cases 拆分
- 下游：`/tapd-subtask-close`、`/tapd-subtask-reopen`
