# 知识库索引

> 渐进式披露索引 — 从快速入口到深度文档

## §0 快速入口

```bash
# 查看项目状态
/flow-status

# 启动开发流程
/start-dev-flow
```

## §1 项目层

| 文件 | 内容 |
|------|------|
| `project/overview.md` | 项目概览（技术栈、架构模式、核心组件） |
| `project/core-functions.md` | 核心功能流程（故事生命周期、事件驱动） |
| `project/architecture.md` | 系统架构（模块依赖、领域模型、文件路由） |

## §2 技术层

### 编码与约束

| 文件 | 内容 | 阅读者 |
|------|------|--------|
| `tech/backend/coding-style.md` | 编码规范（命名、import、测试） | 所有人 |
| `tech/backend/fitness-rules.md` | 架构约束（分层、API、数据） | Agent |

### 模块索引

| 文件 | 内容 | 阅读者 |
|------|------|--------|
| `tech/backend/modules/agents.md` | AI Agent 定义 | Agent |
| `tech/backend/modules/skills.md` | Skill 能力定义 | Agent |
| `tech/backend/modules/commands.md` | 命令入口 | 用户 |
| `tech/backend/modules/hooks.md` | 自动执行 Hook | Agent |
| `tech/backend/modules/scripts.md` | Python 工具脚本 | Agent |

## §3 资产层

| 目录 | 内容 |
|------|------|
| `asset/contract/` | 契约原则文档 |
| `asset/frozen/` | 归档 PRD |
| `asset/tech-proposals/` | 技术方案 |
| `asset/test-cases/` | 归档测试用例 |
| `asset/tech-debt/` | 技术债台账 |

## §4 Flow 元规范

| 文件 | 内容 |
|------|------|
| `.claude/MANIFEST.md` | Flow 版本历史与治理 |
| `.claude/artifacts-layout.md` | Flow 产物目录布局 |
| `docs/team-workflow.md` | 团队工作流总纲 |

## §5 使用模式

### 三条硬规则

1. **知识库优先**：遇到不熟悉的模块，先查 `.chatlabs/knowledge/`
2. **契约驱动**：所有实现必须基于冻结的契约文档
3. **测试验收**：Generator 不自评，必须通过 Evaluator

### 常见场景

| 场景 | 操作 |
|------|------|
| 新项目接入 | `/init-project` |
| TAPD 工单开工 | `/tapd-story-start <ticket_id>` |
| 本地需求开工 | `/story-start <描述>` |
| 恢复任务 | `/task-resume` |
| 周期复盘 | `/workflow-review` |

## 目录结构

```
.chatlabs/knowledge/
├── README.md              ← 本文件
├── project/              ← 项目层
│   ├── overview.md
│   ├── core-functions.md
│   └── architecture.md
├── tech/                 ← 技术层
│   └── backend/
│       ├── coding-style.md
│       ├── fitness-rules.md
│       └── modules/
│           ├── agents.md
│           ├── skills.md
│           ├── commands.md
│           ├── hooks.md
│           └── scripts.md
└── asset/                ← 资产层
    ├── contract/
    ├── frozen/
    ├── tech-proposals/
    ├── test-cases/
    └── tech-debt/
```