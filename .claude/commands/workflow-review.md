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

### 第零步 A：验证已应用的进化（自动）

读取 `evolution-proposals/_applied.jsonl` 中 `verification_due <= today` 的条目：

```
检查 .chatlabs/flow-logs/evolution-proposals/_applied.jsonl
过滤 verification_due <= 今天日期
```

对每条已超期的提案：
1. 读取对应 insight 的 `insight_tags`
2. 扫描近期（14 天）flow-log 中这些标签的出现频率
3. 对比提案应用前的 baseline blocker_count
4. 输出验证报告：

```
═══════════════════════════════════════
  🔬 进化验证报告

  [EP-YYYYMMDDNN] {target_file} 变更验证
    预期改善：{insight_tags}
    基线 blocker：{baseline_blocker_count}
    当前 blocker：{current}
    趋势：📈 改善 / 📉 退化 / ➡️ 无变化
═══════════════════════════════════════
```

若连续 3 次验证"无变化"，在报告中输出警告，提示可能是无效提案。

### 第零步 B：前置检查

1. 检查 `insights/_pending.jsonl` 是否有待确认提案：
   ```bash
   if [ -f ".chatlabs/flow-logs/evolution-proposals/_pending.jsonl" ] && \
      [ -s ".chatlabs/flow-logs/evolution-proposals/_pending.jsonl" ]; then
     echo "⚠️  有 {N} 条待确认进化提案，建议先处理："
     echo "    /evolution-apply --all      # 应用全部"
     echo "    /evolution-apply --discard # 丢弃全部"
   fi
   ```
2. 无论是否有待确认提案，workflow-review 均正常执行后续步骤。

### 第一步：收集 Blocker 数据

1. 读取 `.chatlabs/reports/tasks/_index.jsonl`
2. 若指定 `--story`，过滤出该 story 的所有 task_id
3. 收集每个 task 的 `.chatlabs/reports/tasks/<task_id>/blockers.md`（跳过 blocker_count == 0 的；文件不存在亦 skip——blockers.md 现按需创建）
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

### 第六步：AI 自审（workflow 级别）

在 Blocker 审查完成后，调用 `self-reflect` skill：

```
Skill: self-reflect
trigger: workflow-review
context_ref: workflow
分析范围: --since <date>（取本次 workflow-review 的 --since 参数值）
```

**重点自审**：
- workflow 维度：流程关卡是否被有效执行
- compliance 维度：spec 规范是否被遵守
- 是否存在重复出现的模式（结合 blocker's-summary 的发现）

### 第七步：洞察提炼

调用 `insight-extract` skill：

```
Skill: insight-extract
参数: --days 30 --since <date>
```

读取近 30 天 flow-log，提炼跨事件洞察模式，写入 `insights/_index.jsonl`。

### 第八步：生成进化提案

调用 `evolution-propose` skill：

```
Skill: evolution-propose
```

将 pending insights 转化为 spec 变更提案，写入 `evolution-proposals/_pending.jsonl`。

## 错误处理

| 场景 | 处理 |
|------|------|
| `_index.jsonl` 为空 | 输出：`ℹ️ 暂无任务记录，无需审查` |
| 所有任务 blocker_count == 0 | 输出：`✅ 所有任务无阻塞，无需审查` |
| Blocker 数量 < 3 | 输出：`⚠️ Blocker 样本不足（< 3 条），趋势分析不可靠` |
