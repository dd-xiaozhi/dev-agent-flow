---
name: python-design
description: "USE WHEN: 读/写/重构 Python CLI 脚本或工具(.claude/scripts/ / .claude/skills/*/scripts/)、规划模块拆分、code review Python 改动。OUTPUT: 设计建议 + 复杂度评估,基于 Ousterhout《A Philosophy of Software Design》。DO NOT USE: 业务代码逻辑设计 / pytest 用法咨询 / 性能调优 / Web 框架问题。"
---

# Python Design for CLI Scripts

> 基于 *A Philosophy of Software Design* (Ousterhout) 的设计原则,针对 CLI 脚本与工具场景。

## 核心命题

**核心挑战是管理复杂度,不是增加功能。** 复杂度有三个症状:

1. **Change Amplification** — 小改动需要在多处编辑
2. **Cognitive Load** — 安全改动需要持有过多上下文
3. **Unknown Unknowns** — 不知道自己不知道(最危险)

复杂度是增量累积的,通过数百个小决策而不是一次灾难性错误。所以:**关注小事**(sweat the small stuff)。

## Gotchas（项目踩过的具体坑）

1. **Rule of Three** 别破坏:两个实例是巧合,三个才抽象 —— 过早抽象比重复更糟
2. 禁止 `sys.path.insert(0, ...)` 黑魔法 —— 修包结构(用 `python -m` 或 `__init__.py`)
3. `common/*` 函数不加 `_` 前缀(被复用就是 public API,加 `_` 会让 import 看起来违规)
4. 单文件 > 500 行检查多职责,> 300 行评估拆分(按 information hiding 拆,不按 execution order)
5. 解析 `subprocess` 输出别 `.strip()`,会破坏语义空格(如 `git submodule status` 行首前缀字符 ` `/`-`/`+`)—— 用 `.rstrip("\n\r")`

## 9 大原则（按需读 references）

| # | 原则 | 一句话摘要 | 详读 |
|---|------|-----------|------|
| 1 | Deep Modules | 模块价值 = 封装功能 / 暴露接口的比率 | [01-deep-modules.md](references/01-deep-modules.md) |
| 2 | Type-First Development | 类型先定义契约,实现满足类型 | [02-type-first.md](references/02-type-first.md) |
| 3 | Information Hiding | 同一知识不该出现在多个模块 | [03-information-hiding.md](references/03-information-hiding.md) |
| 4 | Pull Complexity Down | 复杂度由模块内部吸收,不推给调用方 | [04-pull-complexity.md](references/04-pull-complexity.md) |
| 5 | Define Errors Out | 用 postcondition 设计 API,让错误不再是错误 | [04-pull-complexity.md](references/04-pull-complexity.md) |
| 6 | KISS + Rule of Three | 选最简方案;三次重复才抽象 | [05-kiss-and-srp.md](references/05-kiss-and-srp.md) |
| 7 | Single Responsibility | 每个模块一个改变理由;按 information 拆分不按 execution | [05-kiss-and-srp.md](references/05-kiss-and-srp.md) |
| 8 | Consistent Shared Infra | 多脚本需要的能力放 `common/`,一次实现 | [06-shared-infra.md](references/06-shared-infra.md) |
| 9 | Structured CLI Parsing | 解析 shell 输出尊重语义空格 | [06-shared-infra.md](references/06-shared-infra.md) |

## 速查（按需读）

| 你在做… | 读这个 |
|---------|--------|
| Code review / 自审 | [red-flags.md](references/red-flags.md) — 12 类反模式速查 |
| 写代码前 / review 中 | [checklist.md](references/checklist.md) — 6 项设计自检清单 |

## 战略投入

每次改动花 **10-20%** 时间改善周边设计 —— 不是完美主义,是复利。可工作的代码必要但不充分,软件开发的增量应该是**抽象**,不只是 feature。
