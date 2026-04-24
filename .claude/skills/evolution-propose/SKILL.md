---
name: evolution-propose
description: 从洞察生成 spec 进化提案。读取 insights/_index.jsonl，将洞察转化为具体的 spec 变更提议，产出 evolution-proposal 条目（待用户确认）。被 workflow-review 自动调用。触发关键词：evolution-propose、进化提案、提案生成、spec 变更、propose-evolution。
---

# Evolution Propose — 进化提案生成

## 职责

读取 `insights/_index.jsonl` 中所有 `proposal_id=null` 的洞察，为每个洞察生成一个 spec 变更提案，写入 `evolution-proposals/_pending.jsonl`，等待用户确认后生效。

## 提案格式

```json
{
  "id": "EP-{YYYYMMDD}{NN}",
  "insight_id": "INS-YYYYMMNN",
  "created_at": "<ISO8601>",
  "status": "pending",
  "change": {
    "target_file": "<.chatlabs/knowledge/xxx.md 或 docs/xxx.md>",
    "action": "<add|modify|delete>",
    "location": "<文件内位置或插入点建议>",
    "content_before": "<原文（仅 modify/delete 填写）>",
    "content_after": "<新增/修改后的内容（仅 add/modify 填写）>",
    "rationale": "<为什么需要这个变更，来自哪条洞察>"
  },
  "risk": "<low|medium|high — 变更可能带来的风险>",
  "revertible": "<yes|no — 是否可回滚>",
  "confidence": "<high|medium|low>"
}
```

## Spec 目标文件映射规则

根据洞察的 `affected_dimension` 和 `proposed_fix`，决定写入哪个文件：

| affected_dimension | 目标文件 | 原因 |
|-------------------|---------|------|
| `understanding` | `docs/team-workflow.md` 或相关 command | 理解流程相关 |
| `implementation` | `.chatlabs/knowledge/tech/backend/` 或 `asset/contract/` | 实现规范相关 |
| `compliance` | `docs/team-workflow.md` 或 `knowledge/README.md` | 规范遵守相关 |
| `workflow` | `docs/team-workflow.md` 或 skill 文件 | 流程设计相关 |

`proposed_fix` 中的 `spec:` 前缀 → 直接使用指定文件。

## 行为

### 第一步：读取待处理洞察

1. 读取 `insights/_index.jsonl`
2. 过滤 `proposal_id == null` 的条目
3. 若为空 → 输出 `ℹ️ 暂无待处理洞察`，退出

### 第二步：生成提案

对每个洞察：

1. **分析 proposed_fix**：
   - 提取 `spec:` 后缀指定的目标文件
   - 分析需要的变更类型（add/modify/delete）
   - 若无指定，使用目标文件映射规则

2. **生成 content_after**：
   - `add`：直接写要插入的内容（带适当层级结构）
   - `modify`：描述原文 + 新文
   - 必须包含具体文字，不能只有方向

3. **评估风险**：
   - `low`：不改变现有流程，仅补充说明或示例
   - `medium`：影响局部流程，但有回滚路径
   - `high`：改变核心流程或删除现有内容

4. **判断可回滚性**：
   - `yes`：变更可逆（有明确回滚步骤）
   - `no`：会删除内容或改变已固化的流程

### 第三步：写入提案

1. 创建 `evolution-proposals/` 目录（若不存在）
2. 写入 `evolution-proposals/_pending.jsonl`（追加，每条提案一行）
3. 更新洞察条目的 `proposal_id` 字段

### 第四步：输出

```
═══════════════════════════════════════
  📝 进化提案生成完成

  待确认提案：{N} 条

  提案摘要：
  [{id}] {target_file}
    洞察: {insight_id}
    变更: {action} · 风险: {risk}
    理由: {rationale(前30字)}...

  ⚠️ 提案待确认，运行以下命令应用：
    /evolution-apply [{id1},{id2},...]   # 应用指定提案
    /evolution-apply --all              # 应用全部
    /evolution-apply --discard           # 丢弃全部
═══════════════════════════════════════
```

## 输入参数

| 参数 | 说明 |
|------|------|
| `--insight <insight_id>` | 仅对指定洞察生成提案（默认全部 pending 洞察） |
| `--dry-run` | 仅展示提案，不写入文件 |

## 关联

- 洞察存储：`.chatlabs/flow-logs/insights/_index.jsonl`
- 提案存储：`.chatlabs/flow-logs/evolution-proposals/_pending.jsonl`
- 自审技能：`.claude/skills/self-reflect/SKILL.md`
- 洞察提炼：`.claude/skills/insight-extract/SKILL.md`
- GEPA 引擎：`.claude/scripts/gepa.py`

## GEPA 集成（可选）

在生成提案时，可选使用 GEPA 引擎自动优化目标文件：

```python
from gepa import GEPA

gepa = GEPA(population_size=5, max_generations=3)
variants = gepa.evolve(target_file_path)

# 获取帕累托最优变体
pareto_variants = [v for v in variants if v.pareto_rank == 0]

# 比较改进
comparison = gepa.compare_with_parent(variants)
print(f"改进: {comparison['improvement_pct']:.1f}%")
```

触发条件：
- 洞察数量 ≥ 5 条
- 同一维度问题重复出现 ≥ 3 次
- 用户显式要求优化

使用方式：
```
/evolution-propose --use-gepa          # 启用 GEPA 优化
/evolution-propose --gepa-only         # 仅生成 GEPA 优化，不生成人工提案
```
