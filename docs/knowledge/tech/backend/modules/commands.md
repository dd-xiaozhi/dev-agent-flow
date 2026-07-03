# 模块：commands/

## Overview

8 个斜杠命令（扁平化结构，tapd 子目录已合并为单文件、worktree 子目录已下线）。命令是流程的**入口层**——用户输入 `/xxx` 后由 Claude Code 加载对应 .md 执行指令。

## API 端点

不适用（命令通过 Claude Code SlashCommand 工具调用）。

## 领域模型

按入口分类：

| 类别 | 命令 | 用途 |
|------|------|------|
| **唯一意图入口** | `start-dev-flow` | 自动路由到 tapd / local / resume / review |
| **本地需求** | `story-start` | 本地需求开工（跳过 TAPD） |
| **Bug 修复** | `bug-fix` | 单 bug / 多 bug 并行 worktree 修复 |
| **TAPD 入口** | `tapd` | TAPD 统一入口（子命令路由 init/start/sync/push/fetch/emit/close/reopen） |
| **项目初始化** | `init-project` | 扫描项目生成知识库 + AGENTS.md |
| **审查** | `session-review` | 实时会话审查（含 --fix 自动修复 Flow 配置） |
| **复盘** | `sprint-review` | 单个 task/sprint 即时复盘 |
| **复盘** | `workflow-review` | 周/月聚合复盘 |

## 存储层

- 命令本身：`.claude/commands/*.md`（提交到 git）
- 命令执行产物：写到 `docs/stories/` 或 `docs/state/`
- 命令调度状态：`docs/task/store/<story_id>/task.json` 的 `workflow` section（任务级 SSOT）

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

命令可以**链式调用**：`start-dev-flow` 路由到 `tapd start <id>`，后者通过 tapd skill 拉单。

## 文件路由

```
commands/
├── start-dev-flow.md         唯一入口路由
├── story-start.md            本地需求开工
├── bug-fix.md                Bug 修复（单 bug / 多 bug 并行）
├── tapd.md                   TAPD 统一入口（子命令路由）
├── init-project.md           扫描项目生成知识库 + AGENTS.md
├── session-review.md         实时审查
├── sprint-review.md          task 级复盘
└── workflow-review.md        周月聚合复盘
```

> 任务记录的 new/resume 由 `python .claude/scripts/task.py` 提供，不作为 slash command 暴露。

## 注意事项（团队手写段，禁止自动覆盖）

- 命令应**仅做编排**：调 agent / skill / script，不在 command 里写实现细节
- 命令文档里禁止"改造记录"或版本变更说明
- 命令的 frontmatter `description` 是触发判断依据——写"何时调用"而非"我能做什么"
