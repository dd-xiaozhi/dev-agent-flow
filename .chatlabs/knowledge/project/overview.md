# 项目概览

## 基本信息

| 字段 | 值 |
|------|-----|
| **项目名称** | ChatLabs Dev-Flow |
| **项目类型** | AI 工作流管理系统 |
| **版本** | v2.6 |
| **维护者** | Flow Team |

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **核心框架** | Claude Code SDK | AI Agent 编排框架 |
| **协议** | MCP (Model Context Protocol) | 模型上下文协议 |
| **脚本语言** | Python 3.x | 所有自动化脚本 |
| **数据格式** | JSON/YAML | 配置文件、API 定义 |
| **版本控制** | Git | 代码与配置管理 |

## 架构模式

### 事件驱动架构

```
事件总线 (events.jsonl)
    ↓
session-start hook 监听
    ↓
自动触发对应 skill/command
```

### Agent 三角关系

```
doc-librarian ──────▶ planner
    ▲                    │
    │ design-gap         │ spec-issue
    ▼                    ▼
generator ◀────────── evaluator
```

### 分层目录

| 目录 | 职责 |
|------|------|
| `.claude/agents/` | AI Agent 定义（doc-librarian/planner/generator/evaluator/workflow-reviewer） |
| `.claude/commands/` | Slash Command 入口（25+ 个） |
| `.claude/skills/` | 可复用 Skill（12 个） |
| `.claude/hooks/` | 自动执行 Hook（6 个） |
| `.claude/scripts/` | Python 工具脚本 |
| `.chatlabs/knowledge/` | 项目知识库 |
| `.chatlabs/state/` | 工作状态文件 |
| `.chatlabs/stories/` | Story 产物目录 |
| `.chatlabs/tapd/` | TAPD 工单缓存 |
| `.chatlabs/reports/` | 执行报告 |

## 核心组件

### AI Agents

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| doc-librarian | 产品契约整理 | 需求描述 | contract.md, openapi.yaml |
| planner | 技术规划 | 契约文档 | spec.md, cases/*.md |
| generator | 代码实现 | 技术 spec | 实现代码 + 测试 |
| evaluator | 契约测试 | 代码 + 契约 | verdict |
| workflow-reviewer | 周期复盘 | flow-logs | insights |

### MCP 集成

| 服务 | 用途 |
|------|------|
| TAPD | 工单管理、Wiki、Subtask |
| Jenkins | CI/CD 构建触发 |
| MiniMax | 图片理解、Web 搜索 |

## 构建与运行

### 项目初始化
```bash
# 首次使用
/init-project

# 升级 Flow 版本
/flow-upgrade --apply
```

### 开发流程
```bash
# 启动主流程
/start-dev-flow

# TAPD 工单开工
/tapd-story-start <ticket_id>

# 本地需求开工
/story-start <描述>
```

### 状态检查
```bash
# 查看 Flow 状态
/flow-status

# 恢复任务
/task-resume
```

## 依赖文件

- `pyproject.toml` - 项目元数据（无 Python 源码依赖）
- `.mcp.json` - MCP 服务器配置
- `project-config.json` - TAPD/Jenkins 集成配置
- `settings.json` / `settings.local.json` - Claude Code 配置

## 版本历史

详见 `.claude/MANIFEST.md`：
- v2.6: LTM + GEPA
- v2.5: Flow 仓库去中间层
- v2.4: TAPD Subtask 自动派发
- v2.3: Wiki 模式共识评审
- v2.2: 删除 orchestrator
- v2.1: 事件驱动架构