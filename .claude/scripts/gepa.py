"""
gepa.py — Genetic-Pareto Prompt Evolution

遗传-帕累托提示词进化引擎。

核心思想：
- 读取现有 skill/rule 作为"父代"
- 通过变异和交叉生成"子代"变体
- 在历史数据（flow-logs、insights）上评估
- 帕累托最优选择最优变体
- 输出优化建议供用户确认

Usage:
    from gepa import GEPA

    gepa = GEPA()
    variants = gepa.evolve("skills/self-reflect/SKILL.md")
    for v in variants:
        print(f"{v.id}: fitness={v.fitness:.2f}, pareto_rank={v.pareto_rank}")
"""
from __future__ import annotations

import json
import random
import re
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable
from enum import Enum
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import (
    FLOW_LOGS_DIR, INSIGHTS_DIR, INSIGHTS_INDEX,
    LTM_PATTERNS_DIR, LTM_RULES_DIR, LTM_ANTIPATTERNS_DIR
)


# ── 变异操作符 ──────────────────────────────────────────────────────

class MutationType(str, Enum):
    EXPAND_INSTRUCTION = "expand_instruction"     # 展开模糊指令
    ADD_CONSTRAINT = "add_constraint"             # 增加约束条件
    ADD_EXAMPLE = "add_example"                   # 添加示例
    REORDER_STEPS = "reorder_steps"               # 重排步骤顺序
    STRENGTHEN_CONDITION = "strengthen_condition" # 加强条件判断
    WEAKEN_CONSTRAINT = "weaken_constraint"      # 放宽过严约束
    CLARIFY_OUTPUT = "clarify_output"             # 明确输出格式


@dataclass
class Variant:
    """变体"""
    id: str
    source_file: str
    content: str
    mutations: list[str] = field(default_factory=list)  # 应用的变异类型
    fitness: float = 0.0
    metrics: dict = field(default_factory=dict)
    pareto_rank: int = 0
    generation: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class MutationOperators:
    """
    变异操作符集合
    """

    @staticmethod
    def expand_instruction(content: str) -> tuple[str, str]:
        """
        展开模糊指令

        模糊指标：
        - "适当"、"合适"、"合理" → 具体标准
        - "必要时" → 明确触发条件
        """
        replacements = [
            (r"（适当|应该|建议）", "必须"),
            (r"必要时", "当出现 blocker 或连续 2 次失败时"),
            (r"合理地", "按以下顺序：1. 2. 3."),
        ]
        result = content
        applied = []
        for pattern, replacement in replacements:
            if re.search(pattern, content):
                result, n = re.subn(pattern, replacement, result)
                if n > 0:
                    applied.append(f"expand: {pattern} → {replacement}")
        return result, "; ".join(applied) if applied else None

    @staticmethod
    def add_constraint(content: str) -> tuple[str, str]:
        """
        增加约束条件

        在关键步骤添加约束：
        - 在"执行"前添加"验证"
        - 在"输出"前添加"检查"
        """
        constraints = [
            ("\n1. ", "\n1. [验证前提条件] "),
            ("## 自审总结", "## 前置检查\n- [ ] 上下文文件存在\n- [ ] 评分有依据\n\n## 自审总结"),
        ]
        result = content
        applied = []
        for pattern, insertion in constraints:
            if pattern in content and insertion not in content:
                result = result.replace(pattern, insertion, 1)
                applied.append(f"add_constraint: {pattern[:20]}...")
        return result, "; ".join(applied) if applied else None

    @staticmethod
    def add_example(content: str) -> tuple[str, str]:
        """
        添加示例

        在关键指令后添加具体示例
        """
        examples = [
            (
                "### 第三步：写入 flow-log",
                """\n示例：\n```json\n{\n  "id": "FL-2026-04-23-001",\n  "dimensions": { ... }\n}\n```"""
            ),
        ]
        result = content
        applied = []
        for pattern, example in examples:
            if pattern in content and "示例" not in content[content.index(pattern):content.index(pattern)+500]:
                result = result.replace(pattern, pattern + example, 1)
                applied.append(f"add_example after {pattern[:20]}...")
        return result, "; ".join(applied) if applied else None

    @staticmethod
    def reorder_steps(content: str) -> tuple[str, str]:
        """
        重排步骤顺序

        原则：
        - 上下文收集 → 分析 → 输出
        - 错误处理提前
        """
        # 简单的步骤重排：把"错误处理"提前
        error_section = re.search(r"(## 错误处理.*?)(?=\n## |\n===|\Z)", content, re.DOTALL)
        if error_section:
            error_text = error_section.group(1)
            remaining = content[:error_section.start()] + content[error_section.end():]
            # 在第一个 ## 步骤 后插入错误处理
            match = re.search(r"(### 第[一二三]步.*?\n)", remaining, re.DOTALL)
            if match:
                new_content = remaining[:match.end()] + "\n" + error_text + remaining[match.end():]
                return new_content, "reorder: 错误处理提前"
        return content, None

    @staticmethod
    def strengthen_condition(content: str) -> tuple[str, str]:
        """
        加强条件判断
        """
        replacements = [
            (r"若.*存在", "必须确保...存在，否则报错"),
            (r"若为空", "若为空或不存在"),
        ]
        result = content
        applied = []
        for pattern, replacement in replacements:
            if re.search(pattern, content, re.IGNORECASE):
                result, n = re.subn(pattern, replacement, result, flags=re.IGNORECASE)
                if n > 0:
                    applied.append(f"strengthen: {pattern} → {replacement}")
        return result, "; ".join(applied) if applied else None

    @staticmethod
    def weaken_constraint(content: str) -> tuple[str, str]:
        """
        放宽过严约束
        """
        replacements = [
            (r"必须(确保|检查)", "建议"),
            (r"禁止.*?\n", ""),
        ]
        result = content
        applied = []
        for pattern, replacement in replacements:
            if re.search(pattern, content):
                result, n = re.subn(pattern, replacement, result)
                if n > 0:
                    applied.append(f"weaken: {pattern}")
        return result, "; ".join(applied) if applied else None

    @staticmethod
    def clarify_output(content: str) -> tuple[str, str]:
        """
        明确输出格式
        """
        clarifications = [
            ("### 第五步：输出", "### 第五步：输出\n\n输出格式：\n```\n═══════════════════════════════════════\n  🪞 AI 自审完成\n  ...\n═══════════════════════════════════════\n```")
        ]
        result = content
        applied = []
        for pattern, clarification in clarifications:
            if pattern in content and "输出格式" not in content:
                result = result.replace(pattern, clarification, 1)
                applied.append(f"clarify_output at {pattern}")
        return result, "; ".join(applied) if applied else None


# ── 评估函数 ────────────────────────────────────────────────────────

class Evaluator:
    """
    变体评估器

    在历史数据上评估变体效果
    """

    def __init__(self):
        self.flow_logs = self._load_flow_logs()
        self.insights = self._load_insights()

    def _load_flow_logs(self) -> list[dict]:
        """加载 flow logs"""
        logs = []
        if FLOW_LOGS_DIR.exists():
            for month_dir in FLOW_LOGS_DIR.glob("????-??"):
                for log_file in month_dir.glob("FL-*.json"):
                    try:
                        logs.append(json.loads(log_file.read_text()))
                    except Exception:
                        continue
        return logs

    def _load_insights(self) -> list[dict]:
        """加载 insights"""
        insights = []
        if INSIGHTS_INDEX.exists():
            try:
                with INSIGHTS_INDEX.open("r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            insights.append(json.loads(line))
            except Exception:
                pass
        return insights

    def evaluate(self, variant: Variant) -> dict:
        """
        评估变体

        返回指标：
        - success_rate: 成功率
        - avg_attempts: 平均尝试次数
        - blocker_rate: Blocker 发生率
        - consistency: 与现有规则的一致性
        """
        metrics = {
            "success_rate": 0.0,
            "avg_attempts": 0.0,
            "blocker_rate": 0.0,
            "consistency": 0.0,
            "improvement_potential": 0.0,
        }

        # 基于 insights 评估
        if self.insights:
            # 提取与该 skill 相关的洞察
            related_insights = [
                i for i in self.insights
                if any(tag in variant.content.lower() for tag in i.get("insight_tags", []))
            ]

            # 洞察越多，改进空间越大
            metrics["improvement_potential"] = min(len(related_insights) / 10, 1.0)

        # 基于内容特征评估
        content = variant.content

        # 1. 完整性评估
        required_sections = ["职责", "行为", "触发"]
        completeness = sum(1 for s in required_sections if s in content) / len(required_sections)
        metrics["consistency"] = completeness

        # 2. 具体性评估（示例数量）
        example_count = content.count("示例") + content.count("```")
        metrics["has_examples"] = min(example_count / 3, 1.0)

        # 3. 约束强度评估
        constraint_count = content.count("必须") + content.count("禁止") + content.count("应该")
        metrics["constraint_strength"] = min(constraint_count / 10, 1.0)

        # 4. 步骤清晰度
        step_count = len(re.findall(r"第[一二三四五六七八九十]+步", content))
        metrics["step_clarity"] = min(step_count / 5, 1.0)

        # 综合得分
        metrics["completeness"] = completeness
        metrics["specificity"] = metrics.get("has_examples", 0.5)
        metrics["clarity"] = metrics["step_clarity"]

        return metrics

    def compute_fitness(self, variant: Variant) -> float:
        """
        计算适应度

        多目标优化：
        - 完整性 (30%)
        - 具体性 (25%)
        - 清晰度 (20%)
        - 约束强度 (15%)
        - 改进潜力 (10%)
        """
        m = variant.metrics
        fitness = (
            m.get("completeness", 0) * 0.30 +
            m.get("specificity", 0) * 0.25 +
            m.get("clarity", 0) * 0.20 +
            m.get("constraint_strength", 0) * 0.15 +
            m.get("improvement_potential", 0) * 0.10
        )
        return round(fitness, 4)


# ── 帕累托最优选择 ──────────────────────────────────────────────────

class ParetoSelector:
    """
    帕累托最优选择

    在多目标优化中，选择帕累托前沿上的个体
    """

    @staticmethod
    def dominates(a: dict, b: dict, objectives: list[str]) -> bool:
        """
        判断 a 是否支配 b

        a 支配 b：a 在所有目标上不差于 b，且至少在一个目标上严格优于 b
        """
        better_in_any = False
        for obj in objectives:
            if a.get(obj, 0) < b.get(obj, 0):
                return False
            if a.get(obj, 0) > b.get(obj, 0):
                better_in_any = True
        return better_in_any

    @staticmethod
    def select_front(variants: list[Variant], objectives: list[str]) -> list[Variant]:
        """
        选择帕累托前沿

        返回所有非支配个体
        """
        pareto_front = []
        for candidate in variants:
            is_dominated = False
            for other in variants:
                if other == candidate:
                    continue
                other_metrics = {k: other.metrics.get(k, 0) for k in objectives}
                candidate_metrics = {k: candidate.metrics.get(k, 0) for k in objectives}

                if ParetoSelector.dominates(other_metrics, candidate_metrics, objectives):
                    is_dominated = True
                    break
            if not is_dominated:
                pareto_front.append(candidate)
        return pareto_front

    @staticmethod
    def assign_ranks(variants: list[Variant], objectives: list[str]) -> list[Variant]:
        """
        分配帕累托秩

        - rank 0: 帕累托前沿
        - rank 1: 被 rank 0 支配，但在剩余中非支配
        - 以此类推
        """
        remaining = variants.copy()
        rank = 0
        while remaining:
            front = ParetoSelector.select_front(remaining, objectives)
            for v in front:
                v.pareto_rank = rank
                remaining.remove(v)
            rank += 1
        return variants


# ── GEPA 控制器 ─────────────────────────────────────────────────────

class GEPA:
    """
    遗传-帕累托提示词进化控制器
    """

    def __init__(
        self,
        population_size: int = 5,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        max_generations: int = 3
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.max_generations = max_generations
        self.evaluator = Evaluator()
        self.mutations = MutationOperators()

    def _generate_id(self, content: str, generation: int) -> str:
        """生成变体 ID"""
        hash_val = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"VAR-G{generation}-{hash_val}"

    def _apply_mutations(self, content: str, generation: int) -> list[Variant]:
        """应用变异生成子代"""
        variants = []

        mutation_methods = [
            ("expand_instruction", self.mutations.expand_instruction),
            ("add_constraint", self.mutations.add_constraint),
            ("add_example", self.mutations.add_example),
            ("reorder_steps", self.mutations.reorder_steps),
            ("strengthen_condition", self.mutations.strengthen_condition),
            ("weaken_constraint", self.mutations.weaken_constraint),
            ("clarify_output", self.mutations.clarify_output),
        ]

        for mutation_name, mutation_fn in mutation_methods:
            if random.random() < self.mutation_rate:
                mutated_content, applied = mutation_fn(content)
                if applied:
                    variant = Variant(
                        id=self._generate_id(mutated_content, generation),
                        source_file="",
                        content=mutated_content,
                        mutations=[applied],
                        generation=generation
                    )
                    variant.metrics = self.evaluator.evaluate(variant)
                    variant.fitness = self.evaluator.compute_fitness(variant)
                    variants.append(variant)

        return variants

    def _crossover(self, parent1: Variant, parent2: Variant, generation: int) -> Optional[Variant]:
        """交叉两个父代"""
        if random.random() > self.crossover_rate:
            return None

        # 简单交叉：按行数分割
        lines1 = parent1.content.split("\n")
        lines2 = parent2.content.split("\n")

        if len(lines1) < 5 or len(lines2) < 5:
            return None

        # 随机选择交叉点
        split1 = random.randint(len(lines1) // 3, 2 * len(lines1) // 3)
        split2 = random.randint(len(lines2) // 3, 2 * len(lines2) // 3)

        # 拼接
        child_content = "\n".join(lines1[:split1] + lines2[split2:])
        child_mutations = parent1.mutations + parent2.mutations + ["crossover"]

        child = Variant(
            id=self._generate_id(child_content, generation),
            source_file="",
            content=child_content,
            mutations=child_mutations,
            generation=generation
        )
        child.metrics = self.evaluator.evaluate(child)
        child.fitness = self.evaluator.compute_fitness(child)
        return child

    def evolve(
        self,
        source_file: str,
        target_metric: str = "fitness"
    ) -> list[Variant]:
        """
        进化流程

        1. 读取当前文件作为父代
        2. 生成候选变体（变异 + 交叉）
        3. 评估所有变体
        4. 帕累托最优选择
        5. 返回最优变体
        """
        # 读取源文件
        source_path = Path(source_file)
        if not source_path.exists():
            # 尝试相对于 PROJECT_DIR
            source_path = Path(__file__).resolve().parents[2] / source_file

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_file}")

        parent_content = source_path.read_text()

        # 父代
        parent = Variant(
            id=self._generate_id(parent_content, 0),
            source_file=str(source_path),
            content=parent_content,
            mutations=["original"],
            generation=0
        )
        parent.metrics = self.evaluator.evaluate(parent)
        parent.fitness = self.evaluator.compute_fitness(parent)

        all_variants = [parent]

        # 进化迭代
        for gen in range(1, self.max_generations + 1):
            # 变异
            mutated = self._apply_mutations(parent_content, gen)
            all_variants.extend(mutated)

            # 交叉（与其他个体）
            for i in range(len(all_variants)):
                for j in range(i + 1, len(all_variants)):
                    child = self._crossover(all_variants[i], all_variants[j], gen)
                    if child:
                        all_variants.append(child)

        # 帕累托选择
        objectives = ["completeness", "specificity", "clarity"]
        pareto_variants = ParetoSelector.select_front(all_variants, objectives)
        ParetoSelector.assign_ranks(all_variants, objectives)

        # 按适应度和帕累托秩排序
        all_variants.sort(key=lambda v: (v.pareto_rank, -v.fitness))

        return all_variants

    def compare_with_parent(self, variants: list[Variant]) -> dict:
        """
        比较变体与父代

        返回改进摘要
        """
        if not variants:
            return {}

        parent = variants[0]  # 原始个体
        best = variants[1] if len(variants) > 1 else parent

        return {
            "parent_fitness": parent.fitness,
            "best_fitness": best.fitness,
            "improvement": best.fitness - parent.fitness,
            "improvement_pct": (best.fitness - parent.fitness) / parent.fitness * 100 if parent.fitness > 0 else 0,
            "mutation_count": len(best.mutations),
            "pareto_rank": best.pareto_rank,
        }


# ── CLI 入口 ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="GEPA CLI")
    parser.add_argument("source_file", help="源文件路径")
    parser.add_argument("--population", type=int, default=5, help="种群大小")
    parser.add_argument("--generations", type=int, default=3, help="进化代数")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    gepa = GEPA(
        population_size=args.population,
        max_generations=args.generations
    )

    print(f"🔬 开始进化: {args.source_file}")
    variants = gepa.evolve(args.source_file)

    comparison = gepa.compare_with_parent(variants)
    print(f"\n📊 进化结果:")
    print(f"  父代适应度: {comparison['parent_fitness']:.4f}")
    print(f"  最佳适应度: {comparison['best_fitness']:.4f}")
    print(f"  改进: {comparison['improvement']:.4f} ({comparison['improvement_pct']:.1f}%)")
    print(f"  应用变异: {comparison['mutation_count']} 种")

    print(f"\n📋 变体列表:")
    for v in variants[:10]:
        prefix = "⭐" if v.pareto_rank == 0 else "  "
        print(f"{prefix} [{v.id}] fitness={v.fitness:.4f}, rank={v.pareto_rank}, gen={v.generation}")
        if v.mutations:
            print(f"    mutations: {', '.join(v.mutations[:3])}")

    # 输出最佳变体
    if variants and args.output:
        best = variants[1] if len(variants) > 1 else variants[0]
        Path(args.output).write_text(best.content)
        print(f"\n✅ 最佳变体已保存到: {args.output}")
