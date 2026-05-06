# ChatLabs Dev-Flow

基于 Claude Code 的 AI 驱动开发工作流配置框架——把"产品需求 → 契约 → 实现 → 评估 → 部署"全链路编排为可配置的事件驱动流程。

## 知识库

入口索引：`.chatlabs/knowledge/README.md`

| 关注点 | 路径 |
|-------|------|
| 项目概述 / 技术栈 / 目录结构 | `.chatlabs/knowledge/project/overview.md` |
| 核心业务流程 | `.chatlabs/knowledge/project/core-functions.md` |
| 架构 / 模块依赖 | `.chatlabs/knowledge/project/architecture.md` |
| 编码规范 | `.chatlabs/knowledge/tech/backend/coding-style.md` |
| 架构红线 | `.chatlabs/knowledge/tech/backend/fitness-rules.md` |
| 模块详情 | `.chatlabs/knowledge/tech/backend/modules/` |
| 产物布局 | `.claude/artifacts-layout.md` |

## 快速开始

```bash
/start-dev-flow            # 主流程入口
/tapd-story-start <id>     # TAPD 工单开工
/story-start <描述>         # 本地需求开工
/task-resume               # 恢复任务
/init-project              # 重新生成知识库
```

## 禁止

- 不在 command / skill / agent / 代码文件中声明"改造 xxx"，这些文件只写关键信息，不写版本变更记录
- skill 是单一的技能，不在 skill 中关联或引用其他 skill
