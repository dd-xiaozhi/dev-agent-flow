---
name: ltm
description: LTM 长期记忆系统。提供三层记忆结构（STM/ITM/LTM），支持跨项目、跨时间的持久化记忆能力。触发关键词：LTM、长期记忆、记忆查询、注入记忆、存储模式。
---

# LTM — Long Term Memory System

## 概述

LTM 是 Flow 的长期记忆系统，提供三层记忆结构：

| 层级 | TTL | 存储位置 | 用途 |
|------|-----|---------|------|
| **STM** | 1 小时 | 内存缓存 | Session 内的即时记忆 |
| **ITM** | 7 天 | `.chatlabs/ltm/itm/` | 任务相关的临时记忆 |
| **LTM** | 永久 | `.chatlabs/ltm/ltm/` | 成功模式、验证规则、失败模式 |

## 记忆类型

| 类型 | 目录 | 用途 | TTL |
|------|------|------|-----|
| `pattern` | `patterns/` | 成功解决问题的模式 | 永久 |
| `rule` | `rules/` | 经验证的 Fitness 规则 | 永久 |
| `anti-pattern` | `anti-patterns/` | 已知失败模式 | 永久 |
| `insight` | `insights/` | 跨事件洞察 | 永久 |
| `context` | `itm/` | 任务上下文 | 7 天 |

## 核心 API

### 存储记忆

```python
from ltm import LTM, MemoryType

ltm = LTM()

# 存储成功模式
ltm.store(
    key="API 错误处理模式",
    content={
        "pattern": "使用指数退避重试，最多重试 3 次",
        "example": "requests.get(url, timeout=30) + retry decorator"
    },
    memory_type=MemoryType.PATTERN,
    tags=["api", "error-handling", "retry"],
    confidence=0.8,
    source="self-reflect"
)

# 存储失败模式
ltm.store(
    key="边界条件遗漏",
    content={
        "root_cause": "未在 contract 中明确定义边界条件",
        "fix": "在 spec 中增加边界条件清单"
    },
    memory_type=MemoryType.ANTI_PATTERN,
    tags=["boundary-condition", "spec-missing"],
    evidence=["FL-2026-04-23-001"],
    confidence=0.7,
    source="self-reflect"
)
```

### 检索记忆

```python
# 语义检索
memories = ltm.retrieve("API 错误处理")
for m in memories:
    print(f"{m.key}: {m.confidence}")

# 筛选类型
memories = ltm.retrieve(
    "边界条件",
    memory_types=[MemoryType.ANTI_PATTERN, MemoryType.INSIGHT]
)
```

### 注入到 Context

```python
# session-start 时调用，注入相关记忆
context = ltm.inject_to_context(query="API 设计", max_memories=5)
# 返回格式化的记忆列表，可直接注入到 Agent prompt
```

### 健康度检查

```python
status = ltm.get_health_status()
print(f"总记忆数: {status['total_memories']}")
print(f"建议: {status['recommendation']}")
```

## 存储时机

**自动存储**（由 self-reflect skill 调用）：
- `root_cause` 存在 → 存储为 anti-pattern
- 平均分 ≥ 8 → 存储为 pattern
- `insight_tags` 存在 → 存储为 insight

**手动存储**：
- 用户说"记住这个模式"时
- 成功解决复杂问题后
- 发现常见错误模式时

## CLI 使用

```bash
# 存储记忆
python3 .claude/scripts/ltm.py store --key "模式名" --type pattern --content '{"pattern": "..."}'

# 检索
python3 .claude/scripts/ltm.py retrieve --query "关键词"

# 健康度
python3 .claude/scripts/ltm.py health

# 注入测试
python3 .claude/scripts/ltm.py inject --query "API"
```

## GC 与 Consolidate

LTM 自动管理：

1. **Consolidate**（每日）：ITM → LTM 提升
   - 置信度 ≥ 0.8
   - 访问次数 ≥ 3 次
   → 提升到 LTM 永久存储

2. **GC**（每次 gc.py）：清理
   - 过期的 ITM 记忆
   - 孤立的索引条目
   - LTM 中 30 天未访问的条目

## 输出格式

```
═══════════════════════════════════════
  🧠 LTM 记忆注入

  注入 5 条相关记忆：

  [pattern] API 错误处理模式
    置信度: 0.8
    摘要: 使用指数退避重试，最多重试 3 次
    来源: self-reflect

  [anti-pattern] 边界条件遗漏
    置信度: 0.7
    摘要: 未在 contract 中明确定义边界条件
    来源: self-reflect
    证据: FL-2026-04-23-001

  ℹ️ LTM 健康度: ok (共 12 条记忆)
═══════════════════════════════════════
```

## 关联

- LTM 核心模块：`.claude/scripts/ltm.py`
- Self-Reflect：`.claude/skills/self-reflect/SKILL.md`
- GC：`.claude/scripts/gc.py`
- Session-Start：`.claude/hooks/session-start.py`
