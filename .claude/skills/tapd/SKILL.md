---
name: tapd
description: TAPD 统一入口 skill。工单拉取、共识管理、子任务回填、事件驱动同步。触发关键词：tapd、初始化、ticket sync、共识、Wiki 评审、子任务、工时回填、QA 通过、QA 打回、TAPD 事件、契约推送、同步工单、拉工单。
model: sonnet
---

# TAPD Skill

> TAPD 统一入口 skill。合并原 tapd-init、tapd-pull、tapd-consensus、tapd-subtask、tapd-sync 五个 skill 的能力。

## 触发场景

| 场景 | 触发词 |
|------|--------|
| 初始化 | tapd 初始化、tapd init、配置 tapd、绑定项目 |
| 工单拉取 | tapd 拉取、ticket sync、同步工单、拉工单、tapd pull |
| 共识管理 | TAPD 共识、Wiki 评审、contract 推送、consensus、契约评审 |
| 子任务 | 工时回填、subtask emit、QA 通过、QA 打回、tapd subtask |
| 事件同步 | tapd同步、TAPD事件、契约推送 |

---

## 模块化能力

### init 模块

> 引导式初始化 TAPD 配置。

**职责**：
- 发现项目（调用 `get_user_participant_projects`）
- 探测工作流状态（调用 `get_workflows_status_map`）
- 智能匹配语义键（to_dev/to_review/to_test/done）
- 获取项目成员（调用 `get_workspace_members`）并按角色分类（PM/BE/QA/FE）
- 生成配置写入 `.chatlabs/project-config.json`

**触发词**：tapd 初始化、tapd init、配置 tapd、绑定项目

---

### pull 模块

> 工单拉取与本地缓存维护。

**职责**：
- 拉取 TAPD 工单到本地缓存
- 增量同步策略（不重复请求未变化的字段）
- 维护 `_index.jsonl`

**输入**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `workspace_id` | int | 必填，从 tapd-config 读 |
| `entity_type` | string | stories / tasks / bugs，默认 stories |
| `owner` | string? | 默认 owner_nick |
| `iteration_id` | string? | 限定迭代 |
| `since` | iso? | 增量起点，默认 last_sync_at |
| `force_full` | bool | 强制全量拉，忽略 since |
| `generate_md` | bool | 是否生成评论 MD 文档，默认 true |

**输出**：
| 路径 | 内容 |
|------|------|
| `.chatlabs/task/store/<story_id>/task.json` | 工单详情写入 `tapd` section（`ticket_id`、`entity_type`、`local_mapping`、`subtasks`、`comments_cache`、`raw`） |
| `.chatlabs/task/store/<story_id>/tapd-comment.md` | 人类可读的评论汇总（generate_md=true 时） |
| `.chatlabs/task/_index.jsonl` | 任务索引（task_id ↔ story_id ↔ ticket_id 关联） |
| `project-config.json.tapd.last_sync_at` | 更新 |

**流程**：
```
1. 拉摘要列表：get_todo 或 get_stories_or_tasks
2. 对每条 ID，拉详情：get_stories_or_tasks(id=<id>, fields="...")
3. 通过 TaskJsonStore.find_by_tapd_id(ticket_id) 定位对应 task 目录；
   首次拉取时新建 task（按 entity_type=bug 走 BUG_FIX_DIR，否则 STORE_DIR）
4. 保留 task.json.tapd 中的 local_mapping/subtasks/comments_cache（累积字段），新字段合入 raw
5. 走 TaskJsonStore.update_tapd(patch) → save()
6. 若 generate_md=true，拉取工单评论并生成 tapd-comment.md：
   - 调用 get_comments(entry_type, ticket_id)
   - 经 scripts/comments_cache.py 去重（基于 comment.id）
   - 生成格式美观的 MD 文档，按日期分组、特殊标记加粗
7. 重建 .chatlabs/task/_index.jsonl
8. 更新 last_sync_at
```

**关键约束**：
- `local_mapping`、`subtasks`、`comments_cache` 是本地累积的，禁止整段覆盖；只对发生变化的字段做 partial update
- 全量重建 `.chatlabs/task/_index.jsonl`，避免增量写时的并发损坏
- 所有 tapd 字段写入必须经 TaskJsonStore.update_tapd，禁止直接写 task.json
- MD 文档字段映射：评论时间（`created`）、评论人（`author`）、评论内容（`content`）

**触发词**：tapd 拉取、ticket sync、同步工单、拉工单、tapd pull

---

### consensus 模块

> 共识文档版本管理 + Wiki 驱动的双向同步。

**核心变更**：共识文档推送到 TAPD Wiki 进行评审，而不是工单评论。

**目录结构**：
```
共识文档/
├── {ticket_id}-{slug}/
│   ├── {ticket_id}-{slug} 契约文档 v1.0.0.md
│   └── ...
```

#### Push（本地 → TAPD Wiki）

**输入**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `story_id` | string | 必填 |
| `store_name` | string | 可选 |
| `dry_run` | bool | 默认 false |

**流程**：
```
1. 校验 task.json.tapd.local_mapping.story_id 非空
2. 读 contract.md，校验 status == "frozen"
3. 确定 store_name（参数 > task.json.tapd.local_mapping > 实时派生）
4. 确定父 Wiki（查找/创建根目录 "共识文档" + store 子目录）
5. 确定版本号（已有数量 + 1）
6. 构造 Wiki 内容（完整 contract.md + 元信息）
7. dry_run=true → 打印预览
8. dry_run=false → 创建 Wiki
9. TaskJsonStore.update_tapd({wiki_id, wiki_url, consensus_version: prev+1}) → save()
```

#### Fetch（TAPD → 本地）

**流程**：
```
1. 读取 task.json.tapd.wiki_id
2. 调用 get_wiki 获取 Wiki 详情
3. 调用 get_comments 拉取工单评论
4. 经 scripts/comments_cache.py 去重并更新 task.json.tapd.comments_cache
5. 生成/更新 tapd-comment.md（按日期分组，特殊标记加粗高亮）
6. 检查评审状态标记（[CONSENSUS-APPROVED] / [CONSENSUS-REJECTED]）
7. TaskJsonStore.update_tapd / update_workflow 写回状态
```

**触发词**：TAPD 共识、Wiki 评审、contract 推送、consensus、契约评审

---

### subtask 模块

> TAPD 子任务回填。Emit 批量创建、Close 推到待测、Reopen 回退开发态。

#### Emit

**输入**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `ticket_id` | string | TAPD 父工单 ID |
| `force` | bool | 已 emitted 仍允许重派 |
| `dry_run` | bool | 仅预览 |
| `commit_range` | string | git diff 范围 |

**输出**：每个 case → 一个 TAPD subtask（status=done，含工时记录）

**工时来源**：
- `case.estimate_hours` 非空走人工值（`estimate_source=manual`）
- 为空时调用 estimator agent 批量估算

**副作用**：父工单评论 `[SUBTASK-EMITTED]` 列出 subtask 与工时汇总；不修改父工单状态。

#### Close

**前置**：`meta.verdict == "PASS"`

**输出**：本地 `meta.phase=done`、TAPD subtask 推到 `to_test` 状态

**副作用**：subtask 评论 `[QA-PASSED]`

#### Reopen

**前置**：`meta.phase == "done"`、`reason.length >= 5`

**输出**：本地 `meta.phase=in_progress / verdict=WIP`、TAPD subtask 回退到 `to_dev`

**副作用**：`blockers.md` 追加 `[QA 打回]`、subtask 评论 `[QA-REJECTED:{reason}]`

#### 工作流前置三检查（Close / Reopen）

| 检查 | 数据源 | 不通过 |
|------|--------|--------|
| 目标状态在 status_enum 内 | 本地配置 | WARN |
| 目标状态在 TAPD workflow status_map 内 | API | WARN |
| current → target 在 transitions 内 | TAPD | FATAL |

**触发词**：工时回填、subtask emit、QA 通过、QA 打回、tapd subtask

---

### sync 模块

> 事件驱动的 TAPD 同步适配器。

**职责**：
- 监听 `contract:frozen` → 推送契约到 TAPD Wiki
- 监听 TAPD 评论 → 识别 `[CONSENSUS-APPROVED]`

**事件监听**：
| 事件 | 触发动作 |
|------|---------|
| `contract:frozen` | 若 TAPD enabled，推送契约到 Wiki |
| `tapd:consensus-approved` | 更新 phase = "planner"，自动路由 |

**状态隔离**：
- TAPD 相关状态全在 `task.json.tapd` section（替代旧 `workflow-state.json.integrations.tapd`）
- TAPD 未启用时完全静默，不阻断主流程

**触发词**：tapd同步、TAPD事件、契约推送

---

## MCP 工具清单

**初始化类**：
- `get_user_participant_projects`
- `get_workspace_info`
- `get_workspace_members`（获取项目所有成员列表，含 user/id/nick/email）
- `get_workitem_types`
- `get_workflows_status_map`
- `get_workflows_all_transitions`
- `get_entity_custom_fields`

**工单操作类**：
- `get_todo`
- `get_stories_or_tasks`
- `create_story_or_task`
- `update_story_or_task`
- `add_timesheets`

**Wiki 操作类**：
- `create_wiki`
- `get_wiki`
- `update_wiki`

**评论/通知类**：
- `get_comments`
- `create_comments`
- `send_qiwei_message`

---

## 关键约束

1. **父工单状态不动**：由 PM 手工管理，本 skill 永不调用 `update_story_or_task` 推进父工单
2. **TAPD 可选**：enabled == false 时静默退出
3. **版本号单调递增**：consensus_version 只增不减
4. **本地状态保留**：`local_mapping`、`subtasks`、`comments_cache` 是本地累积的

---

## 配置结构说明

### `tapd.team_roles（项目角色映射）

初始化时通过 `get_workspace_members` 拉取项目成员列表，用户交互标记角色后持久化。

**数据结构**：
```json
{
  "pm": [
    {"user": "张三", "nick": "zhangsan", "id": "123456"}
  ],
  "be": [
    {"user": "李四", "nick": "lisi", "id": "123457"},
    {"user": "王五", "nick": "wangwu", "id": "123458"}
  ],
  "fe": [...],
  "qa": [...],
  "other": [...]
}
```

**角色定义**：
| 角色 | 说明 | TAPD @ 用法 |
|------|------|-------------|
| pm | 产品经理 | `@<nick>` 用于需求评审、契约确认 |
| be | 后端开发 | `@<nick>` 用于技术方案、后端实现 |
| fe | 前端开发 | `@<nick>` 用于前端实现、联调通知 |
| qa | 测试人员 | `@<nick>` 用于提测、验收确认 |
| other | 其他角色 | 不自动 @ |

**使用场景**：
- `consensus push 推送 Wiki 时自动 @ pm 列表
- subtask emit 时按 case.type 自动 @ 对应角色
- QA 通过/打回时自动 @ qa 列表

---

## 关联

- Command: `.claude/commands/tapd.md`
- 配置: `.chatlabs/project-config.json`
- 状态：`.chatlabs/task/store/<story_id>/task.json` 的 `tapd` section（per-task SSOT）
  全局 fallback：`.chatlabs/state/workflow-state.json`
- 索引：`.chatlabs/task/_index.jsonl`
- Schema: `ticket.schema.json`、`tapd-config.schema.json`