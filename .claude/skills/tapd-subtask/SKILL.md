---
name: tapd-subtask
description: TAPD 子任务回填器。Emit 模式在部署后批量创建 subtask 并设为 done + 估算工时；Close/Reopen 模式调整 subtask 状态。被 /tapd-subtask-emit、close、reopen 调用。触发关键词：工时回填、subtask emit、QA 通过、QA 打回。
model: sonnet
---

# TAPD Subtask

## 职责

把本地 cases 回填为 TAPD 父工单下的 subtask + 工时台账。三种模式：Emit 部署后批量创建并标 done、Close 把单个 subtask 推到待测试、Reopen 把 subtask 拉回开发态。父工单状态不动，由 PM 手工管理。

## Blocker 等级

| 等级 | 行为 |
|------|------|
| FATAL | 立即终止，抛 Blocker |
| WARN | 写入 `warnings[]`，批次结束一次性展示 |
| INFO | 仅记日志 |

## 模式契约

### Emit

| 输入 | 类型 | 说明 |
|------|------|------|
| `ticket_id` | string | TAPD 父工单 ID |
| `force` | bool | 已 emitted 仍允许重派 |
| `dry_run` | bool | 仅预览，不调 mcp |
| `commit_range` | string | git diff 范围，默认 `origin/master..HEAD` |

输出：每个 case → 一个 TAPD subtask（status=done，含工时记录）；ticket 缓存写回 `subtasks[]`（每条带 `estimated_hours / estimate_source / emitted_at`）、`subtask_emitted=true`、`subtask_emitted_at`、`total_estimated_hours`。

副作用：父工单评论 `[SUBTASK-EMITTED]` 列出 subtask 与工时汇总；不修改父工单状态。

工时来源：`case.estimate_hours` 非空走人工值（`estimate_source=manual`）；为空时调用 estimator agent 批量估算（详见其 agent 契约）。`name` 前缀按 `case.type` 取 `【BE】/【FE】/【INFRA】/【DOC】`，未知不加；去掉 title 已有的项目标识前缀。

### Close

| 输入 | 类型 |
|------|------|
| `case_id` | string |

输出：本地 `meta.phase=done`、TAPD subtask 推到 `to_test` 状态。前置 `verdict==PASS`，否则 FATAL。

副作用：subtask 评论 `[QA-PASSED]`；ticket 缓存 `subtasks[*].local_phase=done`。

### Reopen

| 输入 | 类型 | 说明 |
|------|------|------|
| `case_id` | string | |
| `reason` | string | ≥5 字符 |

输出：本地 `meta.phase=in_progress / verdict=WIP`、TAPD subtask 回退到 `to_dev` 状态。前置 `phase==done`。

副作用：`blockers.md` 追加 `[QA 打回]`、subtask 评论 `[QA-REJECTED:{reason}]`。

## 工作流前置三检查（Close / Reopen）

每次状态流转前依次校验，结果决定 Blocker 等级：

| 检查 | 数据源 | 不通过 |
|------|--------|--------|
| 目标状态在 `project-config.status_enum` 内 | 本地配置 | WARN（status_map 陈旧） |
| 目标状态在 TAPD workflow status_map 内 | `get_workflows_status_map` | WARN |
| `current → target` 在 `get_workflows_all_transitions` 列表内 | TAPD | FATAL（transition 不合法） |

实现见 `.claude/scripts/check_transition.py`。

## 关键约束

- 父工单状态由 PM 手工管理，本 skill 永不调用 `update_story_or_task` 推进父工单
- Emit 创建即 done，不留 open subtask；单 case 失败记录 Blocker 后继续，不阻塞批次
- estimator 失败或 affected_files 缺失 → 该 case 工时为 null，仍创建 subtask + 设 done，仅跳过 add_timesheets
- 非阻塞问题汇总到 `warnings[]`，一次性展示，不逐个询问

## MCP 工具

- `create_story_or_task` / `update_story_or_task` / `get_stories_or_tasks`
- `add_timesheets`
- `get_workflows_last_steps` / `get_workflows_status_map` / `get_workflows_all_transitions`
- `create_comments`

## 失败处理

| 场景 | 行为 |
|------|------|
| cases 不存在、subtask 已 emitted（无 --force）、done 状态查不到、配置缺失 | FATAL，终止 |
| transition 不合法（Close/Reopen） | FATAL，提示检查 transitions 配置 |
| Close 时 `verdict != PASS`、Reopen 时 `phase != done` 或 `reason < 5` | FATAL，提示先跑 evaluator 或补充打回理由 |
| 单 case MCP 调用失败 | 记录 Blocker，跳过该 case，批次继续 |
| status_map 陈旧 / status 不在 workflow / 单 case affected_files 缺失 | WARN，汇总展示 |

## 关联

- Commands：`.claude/commands/tapd/tapd-subtask-emit.md` / `tapd-subtask-close.md` / `tapd-subtask-reopen.md`
- Subagent：`.claude/agents/estimator.md`
- Schema：`ticket.schema.json`（subtasks 段）、`tapd-config.schema.json`（status_enum / transitions 段）
- 上游：`/jenkins-deploy` 完成后由 flow 触发 Emit
