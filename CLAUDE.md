# ChatLabs Dev-Flow

AI 驱动开发工作流系统，基于 Claude Code 的事件驱动编排框架。

## 知识库

项目文档统一存储在 `.chatlabs/knowledge/` 目录，入口索引：`.chatlabs/knowledge/README.md`

### 目录结构

- `project/` - 项目概览（overview / architecture / core-functions）
- `tech/backend/` - 技术层（coding-style / fitness-rules / modules/）
- `asset/` - 资产层（contract/契约原则、frozen/归档PRD、tech-proposals/技术方案、test-cases/归档用例、tech-debt/技术债）

### 运行时目录

- `.claude/` - Flow 运行时配置（agents/ commands/ skills/ hooks/ scripts/）
- `.chatlabs/` - 项目数据（knowledge/知识库、stories/故事产物、state/状态、tapd/工单缓存、reports/报告）

## 技术栈

- 语言: Python 3.x
- 框架: Claude Code SDK + MCP (Model Context Protocol)
- 构建: 无源码编译，纯配置驱动

## 编码规范

详见: `.chatlabs/knowledge/tech/backend/coding-style.md`

## 架构约束

详见: `.chatlabs/knowledge/tech/backend/fitness-rules.md`

## 快速开始

```bash
/start-dev-flow            # 启动主流程
/tapd-story-start <id>     # TAPD 工单开工
/story-start <描述>         # 本地需求开工
/flow-status               # 查看状态
/task-resume               # 恢复任务
```

## 版本

Flow 版本: v2.6（LTM + GEPA）