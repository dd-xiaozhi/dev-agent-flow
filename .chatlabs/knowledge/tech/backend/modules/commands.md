# 模块：commands/

## Overview

18 个斜杠命令，按功能聚合到三个子目录 + 5 个根级命令。命令是流程的**入口层**——用户输入 `/xxx` 后由 Claude Code 加载对应 .md 执行指令。

## API 端点

不适用（命令通过 Claude Code SlashCommand 工具调用）。

## 领域模型

按入口分类：

| 类别 | 命令 | 用途 |
|------|------|------|
| **根级入口** | `start-dev-flow` | 唯一意图入口（自动路由到 tapd/local/resume/review） |
| **根级入口** | `story-start` | 本地需求开工（跳过 TAPD） |
| **根级入口** | `init-project` | 扫描项目生成知识库 |
| **根级入口** | `session-review` | 实时会话审查 |
| **根级入口** | `sprint-review` | 单个 task/sprint 复盘 |
| **根级入口** | `workflow-review` | 周/月聚合复盘 |
| **tapd/** | `tapd-init` | 初始化 TAPD 配置 |
| **tapd/** | `tapd-story-start` | TAPD 工单开工 |
| **tapd/** | `tapd-ticket-sync` | 拉取我的工单 |
| **tapd/** | `tapd-consensus-push` | 推契约到 Wiki |
| **tapd/** | `tapd-consensus-fetch` | 拉评审反馈 |
| **tapd/** | `tapd-subtask-emit` | 部署后回填工时 |
| **tapd/** | `tapd-subtask-close` | QA 通过 |
| **tapd/** | `tapd-subtask-reopen` | QA 打回 |
| **task/** | `task-new` | 创建任务记录 |
| **task/** | `task-resume` | 续接已有任务 |
| **worktree/** | `worktree` | 创建并行工作区 |
| **worktree/** | `worktree-start` | 在 worktree 内启动 flow |

## 存储层

- 命令本身：`.claude/commands/**/*.md`（提交到 git）
- 命令执行产物：写到 `.chatlabs/stories/` 或 `.chatlabs/state/`
- 命令调度状态：`.chatlabs/state/workflow-state.json`

## 依赖关系

```
用户 → /<command>
       ↓
       Claude Code 加载 .md 指令
       ↓
       command 调用：agent / skill / script / 其他 command
       ↓
       写产物 + 推进 flow
```

命令可以**链式调用**：`start-dev-flow` 路由到 `tapd-story-start`，后者调用 `tapd-pull` skill。

## 文件路由

```
commands/
├── init-project.md           扫描项目生成知识库
├── start-dev-flow.md         唯一入口路由
├── story-start.md            本地需求开工
├── session-review.md         实时审查
├── sprint-review.md          task 级复盘
├── workflow-review.md        周月聚合复盘
├── tapd/
│   ├── tapd-init.md
│   ├── tapd-story-start.md
│   ├── tapd-ticket-sync.md
│   ├── tapd-consensus-push.md
│   ├── tapd-consensus-fetch.md
│   ├── tapd-subtask-emit.md
│   ├── tapd-subtask-close.md
│   └── tapd-subtask-reopen.md
├── task/
│   ├── task-new.md
│   └── task-resume.md
└── worktree/
    ├── worktree.md
    └── worktree-start.md
```

## 注意事项（团队手写段，禁止自动覆盖）

- 命令应**仅做编排**：调 agent / skill / script，不在 command 里写实现细节
- 命令文档里禁止"改造记录"或版本变更说明
- 命令的 frontmatter `description` 是触发判断依据——写"何时调用"而非"我能做什么"
