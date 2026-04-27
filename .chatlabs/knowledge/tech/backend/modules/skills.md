# Skills 模块

## 概述

`.claude/skills/` 目录定义了可复用的 Skill 能力，被 Agent 调用。

## 模块列表

| Skill | 用途 | 触发关键词 |
|-------|------|-----------|
| tapd-sync | TAPD 事件同步 | tapd同步、TAPD事件 |
| tapd-consensus | Wiki 模式共识评审 | tapd-consensus |
| tapd-pull | 工单拉取缓存 | tapd拉取、ticket sync |
| tapd-subtask | 子任务派发管理 | 子任务派发、subtask emit |
| tapd-init | TAPD 集成初始化 | tapd初始化、tapd init |
| jenkins-deploy | Jenkins 构建部署 | jenkins-deploy |
| contract-test | OpenAPI 契约测试 | 契约测试、contract test |
| ltm | 长期记忆系统 | LTM、长期记忆 |
| gepa | 规则优化引擎 | GEPA、优化规则 |
| insight-extract | 洞察提炼 | insight-extract、提炼洞察 |
| evolution-propose | 进化提案生成 | evolution-propose、进化提案 |
| gc | 工作流熵管理 | gc、垃圾回收 |
| self-reflect | AI 自审 | 自审、self-reflect |
| fitness-run | 架构适应度检查 | fitness、架构检查 |
| context-reset | 上下文重置 | context reset、上下文重置 |

## 使用规范

### 调用方式

```python
# 通过 Skill tool 调用
Skill(skill="tapd-pull", args="1140062001234567")
```

### 触发关键词

Skills 根据用户输入的关键词自动触发，详见各 SKILL.md 的 trigger 字段。

## 文件路由表

```
skills/
├── tapd-sync/SKILL.md
├── tapd-consensus/SKILL.md
├── tapd-pull/SKILL.md
├── tapd-subtask/SKILL.md
├── tapd-init/SKILL.md
├── jenkins-deploy/SKILL.md
├── contract-test/SKILL.md
├── ltm/SKILL.md
├── gepa/SKILL.md
├── insight-extract/SKILL.md
├── evolution-propose/SKILL.md
├── gc/SKILL.md
├── self-reflect/SKILL.md
├── fitness-run/SKILL.md
└── context-reset/SKILL.md
```

## 依赖关系

```mermaid
flowchart TB
    TAPD_P[tapd-pull] --> TAPD_SYNC[tapd-sync]
    TAPD_SYNC --> TAPD_CON[tapd-consensus]
    TAPD_SYNC --> TAPD_SUB[tapd-subtask]

    PL[planner] --> TAPD_SUB
    GN[generator] --> TAPD_SYNC
    GN[generator] --> JD[jenkins-deploy]
    GN[generator] --> CT[contract-test]

    WR[workflow-reviewer] --> IE[insight-extract]
    IE --> EP[evolution-propose]
    EP --> GC[gc]

    SS[session-start] --> LTM[ltm]
    SS --> GC
    SE[session-end] --> SF[self-reflect]
```