---
name: gepa
description: GEPA 规则优化引擎。遗传-帕累托提示词进化，自动优化 skill/rule 文件。触发关键词：GEPA、优化规则、提示词进化、规则优化、自动改进。
---

# GEPA — Genetic-Pareto Prompt Evolution

## 概述

GEPA 是 Flow 的规则优化引擎，通过遗传算法和帕累托最优选择，自动优化 skill 和 rule 文件。

核心思想：
- 读取现有 skill/rule 作为"父代"
- 通过变异和交叉生成"子代"变体
- 在历史数据（flow-logs、insights）上评估
- 帕累托最优选择最优变体
- 输出优化建议供用户确认

## 变异操作符

| 操作符 | 作用 | 示例 |
|--------|------|------|
| `expand_instruction` | 展开模糊指令 | "适当" → "必须" |
| `add_constraint` | 增加约束条件 | 添加验证前置条件 |
| `add_example` | 添加示例 | 在关键步骤后添加示例 |
| `reorder_steps` | 重排步骤顺序 | 错误处理提前 |
| `strengthen_condition` | 加强条件判断 | "若存在" → "必须确保...存在" |
| `weaken_constraint` | 放宽过严约束 | "必须" → "建议" |
| `clarify_output` | 明确输出格式 | 添加输出格式说明 |

## 评估指标

| 指标 | 权重 | 说明 |
|------|------|------|
| `completeness` | 30% | 包含必要章节（职责、行为、触发） |
| `specificity` | 25% | 有足够示例 |
| `clarity` | 20% | 步骤清晰度 |
| `constraint_strength` | 15% | 约束强度适中 |
| `improvement_potential` | 10% | 改进空间（基于洞察数量） |

## 核心 API

### 进化优化

```python
from gepa import GEPA

gepa = GEPA(
    population_size=5,    # 种群大小
    mutation_rate=0.1,  # 变异概率
    crossover_rate=0.7, # 交叉概率
    max_generations=3   # 进化代数
)

# 进化指定文件
variants = gepa.evolve("skills/self-reflect/SKILL.md")

# 获取帕累托最优变体
pareto_variants = [v for v in variants if v.pareto_rank == 0]

# 比较与父代差异
comparison = gepa.compare_with_parent(variants)
print(f"改进: {comparison['improvement_pct']:.1f}%")
```

### 查看变体

```python
for v in variants:
    print(f"[{v.id}] fitness={v.fitness:.4f}, rank={v.pareto_rank}")
    if v.mutations:
        print(f"  mutations: {', '.join(v.mutations[:3])}")
```

## CLI 使用

```bash
# 进化优化
python3 .claude/scripts/gepa.py ".claude/skills/self-reflect/SKILL.md" \
    --generations 3 --population 10

# 输出最佳变体
python3 .claude/scripts/gepa.py ".claude/skills/self-reflect/SKILL.md" \
    --output /tmp/optimized-skill.md
```

## 帕累托最优

帕累托最优是指：**在不损害任何目标的情况下，无法再改进任何其他目标**的解集。

- `pareto_rank = 0`：帕累托前沿，最优解
- `pareto_rank = 1`：被 rank 0 支配，但在剩余中非支配
- 以此类推

## 输出格式

```
🔬 开始进化: skills/self-reflect/SKILL.md

📊 进化结果:
  父代适应度: 0.7650
  最佳适应度: 0.7850
  改进: 0.0200 (2.6%)
  应用变异: 3 种

📋 变体列表:
⭐ [VAR-G1-28a08dd5] fitness=0.7850, rank=0, gen=1
    mutations: add_constraint, add_example
⭐ [VAR-G2-6212e0d3] fitness=0.7800, rank=0, gen=2
    mutations: add_constraint, crossover
```

## 触发时机

**自动触发**（通过 evolution-propose）：
- 洞察数量 ≥ 5 条
- 同一维度问题重复出现 ≥ 3 次

**手动触发**：
- 用户说"优化这个 skill"
- 用户说"GEPA 优化"
- workflow-review 时

## 使用参数

| 参数 | 说明 |
|------|------|
| `--use-gepa` | 启用 GEPA 优化 |
| `--gepa-only` | 仅生成 GEPA 优化，不生成人工提案 |
| `--generations <N>` | 进化代数（默认 3） |
| `--population <N>` | 种群大小（默认 5） |

## 关联

- GEPA 核心模块：`.claude/scripts/gepa.py`
- LTM：`.claude/scripts/ltm.py`
- Evolution-Propose：`.claude/skills/evolution-propose/SKILL.md`
- Self-Reflect：`.claude/skills/self-reflect/SKILL.md`
