# /workflow-review

> 手动触发工作流审查 Agent，聚合所有 Blocker，输出改进建议。
>
> **使用**：`/workflow-review [--since <date>] [--story <story-id>] [--min-count <N>]`
>
> - 无参数：分析所有任务的 Blocker
> - `--since 2026-04-01`：只分析指定日期后的 Blocker
> - `--story STORY-001`：只分析指定 Story 的 Blocker
> - `--min-count 2`：只输出出现 ≥2 次的 Blocker（默认 1）

## 行为

### 第一步：收集 Blocker 数据

1. 读取 `.chatlabs/reports/tasks/_index.jsonl`
2. 若指定 `--story`，过滤出该 story 的所有 task_id
3. 收集每个 task 的 `.chatlabs/reports/tasks/<task_id>/blockers.md`（跳过 blocker_count == 0 的）
4. 若指定 `--since`，过滤只保留指定日期之后的 Blocker

### 第二步：调用 workflow-reviewer Agent

Agent 输入：
- `blockers_files`: 所有收集到的 blockers.md 路径列表
- `index_file`: `.chatlabs/reports/tasks/_index.jsonl`
- `previous_summary`: `.chatlabs/reports/workflow/blockers-summary.md`（若存在，用于趋势对比）
- `min_count`: N（从 `--min-count` 参数读取）

### 第三步：workflow-reviewer Agent 输出

Agent 产出 `.chatlabs/reports/workflow/blockers-summary.md`，覆盖写。

格式要求（见 workflow-reviewer.md）：
1. 按类型聚合（环境 / 执行 / 信息 / 流程设计）
2. 按频次排序
3. 每条包含：问题 / 根因 / 影响 / 建议方案 / 优先级
4. 对比上次 summary 的趋势变化

### 第四步：Session 输出摘要

在当前 session 输出：

```
═══════════════════════════════════════
  📊 Workflow Blocker 审查报告

  分析范围：
    任务总数：     N
    有 Blocker：  M
    总 Blocker：  K

  🔴 P0（阻断）：
    1. [N 次] <问题描述>
       建议：<方案>
       影响：<影响范围>

  🟡 P1（严重影响）：
    1. [N 次] <问题描述>
       ...

  🟢 P2（优化）：
    1. [N 次] <问题描述>
       ...

  📈 趋势（对比上次）：
    ↑ 新增：<新增的 Blocker 类型>
    ↓ 减少：<减少的 Blocker 类型>
    ➡️ 持平：<持续的 Blocker 类型>

完整报告
═══════════════════════════════════════
```

### 第五步：输出报告位置

完整报告见 `.chatlabs/reports/workflow/blockers-summary.md`

## 错误处理

| 场景 | 处理 |
|------|------|
| `_index.jsonl` 为空 | 输出：`ℹ️ 暂无任务记录，无需审查` |
| 所有任务 blocker_count == 0 | 输出：`✅ 所有任务无阻塞，无需审查` |
| Blocker 数量 < 3 | 输出：`⚠️ Blocker 样本不足（< 3 条），趋势分析不可靠` |
