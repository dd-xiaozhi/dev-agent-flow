# ChatLabs Dev-Flow

基于 Claude Code 的 AI 驱动开发工作流配置框架——把"产品需求 → 契约 → 实现 → 评估 → 部署"全链路编排为可配置的事件驱动流程。

> **入口约定**：本仓库遵循 [agents.md](https://agents.md/) 开放规范，统一以 `AGENTS.md` 作为所有 AI agent 的唯一入口。`CLAUDE.md` 为指向本文件的软链接，保留以兼容 Claude Code。

## 核心公式

> **代码产出 = AI 能力 × 上下文质量**

乘法不是加法：上下文趋零时，模型再强产出也趋零。模型能力靠厂商升级、不可控；上下文质量靠团队基建、完全可控。
本仓库的全部投入——`team/` 团队规范、`project/` 服务知识、`flow-engine` 流程模板、`task.json` 事件流——都是在做**上下文乘数**：把隐性规范、历史决策、契约约束显式化为可机读、可版本化、可演进的工程制品。

## 知识库

入口索引：`docs/knowledge/README.md`

| 关注点 | 路径 |
|-------|------|
| 项目概述 / 技术栈 / 目录结构 | `docs/knowledge/project/overview.md` |
| 核心业务流程 | `docs/knowledge/project/core-functions.md` |
| 架构 / 模块依赖 | `docs/knowledge/project/architecture.md` |
| 编码规范 | `docs/knowledge/tech/backend/coding-style.md` |
| 架构红线 | `docs/knowledge/tech/backend/fitness-rules.md` |
| 模块详情 | `docs/knowledge/tech/backend/modules/` |
| 产物布局 | `.claude/artifacts-layout.md` |

## Rules（共享规范）

跨 agent / skill / command 通用的规范统一收敛到 `.claude/rules/`，避免在多个文件中重复。

| Rule | 适用 | 内容 |
|------|------|------|
| `.claude/rules/agent-conventions.md` | 所有 agent | Blocker 记录 / summary 字段 / GAN 协作 |
| `.claude/rules/evaluator-rules.md` | evaluator agent | Phase 1 fallback 硬规则白名单 |

**引用机制**：agent / skill / command 文件的 frontmatter 通过 `rules:` 字段声明依赖：

```yaml
---
name: doc-librarian
description: ...
model: opus
rules:
  - agent-conventions
---
```

AI 加载该文件时会自动读取并应用对应 rule 的约束。

## 快速开始

```bash
/start-dev-flow            # 主流程入口（自动路由到子命令）
/tapd start <id|url>       # TAPD 工单开工
/story-start <描述>         # 本地需求开工（spec 模式）
/bug-fix <url|--all>       # Bug 修复（单/多 bug 自动并行）
/init-project              # 扫描项目生成知识库
```

> 任务恢复：`python .claude/skills/task/scripts/task.py resume <task_id>`（非 slash 命令）

## 禁止

- 禁止在 command / skill / agent / 代码文件中写入与功能无关的信息！！！
- skill 是单一的技能，不在 skill 中关联或引用其他 skill
- skill 相关的脚本放在对应 skill 的 script 目录下统一管理
