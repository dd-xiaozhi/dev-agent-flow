---
name: tapd-subtask-emit
description: 部署完成后批量创建 TAPD subtask 并立即标 done + 回填工时。读本地 cases 估工时,与 GAN 链路解耦。
model: sonnet
---

# /tapd-subtask-emit

> 部署完成后批量创建 TAPD subtask 并立即标 done + 回填工时。
>
> **用法**：`/tapd-subtask-emit <ticket_id> [--dry-run] [--force] [--commit-range <range>]`

## 行为

### 第一步：前置校验
1. 读 `.chatlabs/tapd/tickets/<ticket_id>.json`,要求 `local_mapping.story_id` 已绑定且 `cases/CASE-*.md` 存在
2. `local_mapping.subtask_emitted == true` 且无 `--force` → 拒绝
3. 解析 cases frontmatter,`affected_files` 必填(缺失记 estimator 警告,工时跳过)

### 第二步：工时估算
- `case.estimate_hours` 已填 → 直接使用
- 未填 → 调 estimator agent 批量估算(单次调用,传入 `commit_range` 与待估 cases),解析 JSON 回填

### 第三步：批量回填
对每个 case 顺序创建 task → 标 done → 写工时,任意一步失败则该 case 跳过、其他继续。
任务名按 `case.type` 加角色前缀:`backend→【BE】` / `frontend→【FE】` / `infra→【INFRA】` / `doc→【DOC】`,未知不加;去除 title 已有项目标识。

### 第四步：本地落库
追加 `ticket.subtasks[]`,置 `local_mapping.subtask_emitted = true` + `total_estimated_hours`,父工单发评论 `[SUBTASK-EMITTED]`。父工单状态由 PM 手工管理,不动。

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id>` | 是 | TAPD 父工单 ID |
| `--dry-run` | 否 | 仅预览估算结果,不调 mcp |
| `--force` | 否 | 已 emitted 时仍执行(会产生重复 subtask) |
| `--commit-range <range>` | 否 | git diff 范围,默认 `origin/master..HEAD` |

## 产出

- TAPD 子任务 N 个,全部 done + 已填工时
- 更新 `ticket.json.subtasks` 与 `local_mapping.subtask_emitted` / `total_estimated_hours`
- 父工单评论 `[SUBTASK-EMITTED]`(子任务列表 + 工时汇总)

## 失败处理

| 场景 | 行为 |
|------|------|
| cases 目录不存在 | 拒绝,提示 GAN 链路未完成 |
| 已 emitted 且无 `--force` | 拒绝 |
| `affected_files` 缺失 | 该 case 工时跳过,创建+done 仍执行 |
| estimator 失败 / JSON 解析失败 | 写 Blocker(执行-子代理失败),整批退出 |
| 单条 mcp 调用失败 | 写 Blocker(该 case),其他继续 |
| 工作流 done 状态映射查不到 | 写 Blocker(信息-技术决策),停止全批 |

## 关联

- Skill: `.claude/skills/tapd-subtask/SKILL.md`
- Subagent: `.claude/agents/estimator.md`
- 上游: `/jenkins-deploy` 完成后自动触发
