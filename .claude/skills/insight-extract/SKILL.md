---
name: insight-extract
description: 从 flow-logs 提炼跨事件的洞察模式。读取近期 flow-log，识别重复出现的问题标签、评分趋势，产出 insight 条目写入 .chatlabs/flow-logs/insights/_index.jsonl。被 workflow-review 自动调用，或手动触发。触发关键词：insight-extract、提炼洞察、模式识别、洞察分析。
---

# Insight Extract — 洞察提炼

## 职责

读取 `.chatlabs/flow-logs/` 下的近期日志（默认近 30 天），识别跨事件的重复模式，提炼出高价值的洞察条目，写入 `insights/_index.jsonl`。

## 洞察条目的质量标准

| 标准 | 说明 |
|------|------|
| **跨事件** | 必须在 2+ 条 flow-log 中出现同一标签/模式，单条日志不构成洞察 |
| **可操作** | 必须能转化为 spec 变更或行为改进，不是空洞总结 |
| **未重复** | 与已有 insights 不重复（ID 不同） |

## 行为

### 第一步：读取近期 flow-log

1. 确定时间窗口（默认 30 天，可通过参数覆盖）：
   - 读取 `.chatlabs/flow-logs/YYYY-MM/*.json`（当月）
   - 递归向上月找补满窗口
   - 若无日志文件 → 输出 `ℹ️ 暂无 flow-log 数据`，退出

2. 收集所有日志，提取字段：
   - `trigger`、`dimensions` 评分、`insight_tags`、`root_cause`

### 第二步：识别模式

**标签频率分析**：
```
统计所有 insight_tags 的出现频率。
标签出现 ≥2 次 → 候选洞察
标签出现 ≥3 次 → 强候选洞察
```

**评分趋势分析**：
```
各维度平均分 vs 上期（若存在 insights/_index.jsonl）：
- 某维度持续走低 → 潜在系统性问题
- 某维度突然下降 → 新出现的问题
```

**根因聚类**：
```
将 root_cause 按关键词聚类：
- "理解偏差" 类 → 指向 understanding 维度 spec
- "规范缺失" 类 → 指向 compliance 维度 spec
- "流程跳过" 类 → 指向 workflow 维度 spec
```

### 第三步：生成洞察条目

对每个强候选洞察（出现 ≥2 次），生成一条 insight 条目：

```json
{
  "id": "INS-{YYYY}{MM}{NN}",
  "pattern": "<模式描述，如：'在 3 次 story-start 中，对边界条件理解均出现偏差'>",
  "evidence": ["FL-YYYY-MM-DD-NNN", "FL-YYYY-MM-DD-MMM"],
  "affected_dimension": "<understanding|implementation|compliance|workflow>",
  "proposed_fix": "<具体的 spec 改进建议，如：'spec: 在 story-start.md 增加 边界条件澄清清单'>",
  "confidence": "<high|medium>（≥3次=high，2次=medium）",
  "proposal_id": null
}
```

**ID 格式**：`INS-{年4位}{月2位}{序号2位}`，如 `INS-20260401`。

### 第四步：去重检查

读取 `insights/_index.jsonl`，检查是否已有完全相同的 pattern：
- 若重复 → 跳过，不写入
- 若存在相似但表述不同 → 合并 evidence，更新已有条目

### 第五步：写入 insights

1. 创建 `insights/` 目录（若不存在）
2. 写入 `insights/_index.jsonl`（追加模式）
3. 每条洞察同时生成详细文件（可选）：`insights/INS-YYYYMMNN.json`

### 第六步：输出

```
═══════════════════════════════════════
  🔍 洞察提炼完成

  分析范围：{N} 条 flow-log（近 30 天）
  新增洞察：{M} 条
  重复跳过：{K} 条

  📊 维度评分趋势（vs 上期）：
    理解   {avg}/10 {trend}
    实现   {avg}/10 {trend}
    遵守   {avg}/10 {trend}
    流程   {avg}/10 {trend}

  💡 新增洞察：
    [{id}] [{dimension}] {pattern}
             → {proposed_fix}

  {若无新增洞察：}  ℹ️ 近期无明显重复模式，保持观察。
═══════════════════════════════════════
```

## 输入参数

| 参数 | 说明 |
|------|------|
| `--days <N>` | 分析窗口天数（默认 30） |
| `--min-occurrences <N>` | 标签最小出现次数（默认 2） |
| `--since <date>` | 仅分析指定日期后的日志（覆盖 --days） |

## 关联

- 自审日志：`.claude/skills/self-reflect/SKILL.md`
- 进化提案：`.claude/skills/evolution-propose/SKILL.md`
- 日志目录：`.chatlabs/flow-logs/`
- 洞察存储：`.chatlabs/flow-logs/insights/`
