# Commands 模块

## 概述

`.claude/commands/` 目录定义了入口命令（slash commands），是用户与 Flow 交互的主要方式。

## 命令列表

### 主流程命令

| 命令 | 文件 | 用途 |
|------|------|------|
| `/init-project` | init-project.md | 扫描项目、生成知识库 |
| `/start-dev-flow` | start-dev-flow.md | 启动主流程 |
| `/story-start` | story-start.md | 本地需求开工 |
| `/task-resume` | task-resume.md | 恢复任务 |
| `/task-new` | task-new.md | 新建任务 |
| `/sprint-review` | sprint-review.md | 即时复盘 |
| `/workflow-review` | workflow-review.md | 周期复盘 |
| `/session-review` | session-review.md | Session 审查 |
| `/member-activity` | member-activity.md | 成员活动统计 |

### TAPD 命令

| 命令 | 文件 | 用途 |
|------|------|------|
| `/tapd-story-start` | tapd/tapd-story-start.md | TAPD 工单开工 |
| `/tapd-init` | tapd/tapd-init.md | TAPD 初始化 |
| `/tapd-ticket-sync` | tapd/tapd-ticket-sync.md | 工单同步 |
| `/tapd-subtask-emit` | tapd/tapd-subtask-emit.md | 子任务派发 |
| `/tapd-subtask-close` | tapd/tapd-subtask-close.md | 子任务关闭 |
| `/tapd-subtask-reopen` | tapd/tapd-subtask-reopen.md | 子任务重开 |
| `/tapd-consensus-push` | tapd/tapd-consensus-push.md | 共识推送 Wiki |
| `/tapd-consensus-fetch` | tapd/tapd-consensus-fetch.md | 共识评审拉取 |

### Flow 命令

| 命令 | 文件 | 用途 |
|------|------|------|
| `/flow-status` | flow/flow-status.md | 查看 Flow 状态 |
| `/flow-pull` | flow/flow-pull.md | 拉取 Flow 更新 |
| `/flow-push` | flow/flow-push.md | 推送 Flow 更新 |
| `/flow-link` | flow/flow-link.md | 链接 Flow 版本 |
| `/flow-version` | flow/flow-version.md | 查看版本信息 |
| `/flow-upgrade` | flow/flow-upgrade.md | 升级 Flow |

### Evolution 命令

| 命令 | 文件 | 用途 |
|------|------|------|
| `/evolution-apply` | evolution-apply.md | 应用进化提案 |

### Worktree 命令

| 命令 | 文件 | 用途 |
|------|------|------|
| `/worktree-start` | worktree/worktree-start.md | 创建 Worktree |
| `/worktree` | worktree/worktree.md | Worktree 管理 |

## 快速参考

```bash
# 启动
/start-dev-flow
/tapd-story-start <ticket_id>
/story-start <描述>

# 状态
/flow-status
/task-resume

# 复盘
/sprint-review
/workflow-review

# Flow 管理
/flow-upgrade --apply
/flow-pull
```

## 文件路由表

```
commands/
├── init-project.md
├── start-dev-flow.md
├── story-start.md
├── task-resume.md
├── task-new.md
├── sprint-review.md
├── workflow-review.md
├── session-review.md
├── member-activity.md
├── evolution-apply.md
├── tapd/
│   ├── tapd-story-start.md
│   ├── tapd-init.md
│   ├── tapd-ticket-sync.md
│   ├── tapd-subtask-emit.md
│   ├── tapd-subtask-close.md
│   ├── tapd-subtask-reopen.md
│   ├── tapd-consensus-push.md
│   └── tapd-consensus-fetch.md
├── flow/
│   ├── flow-status.md
│   ├── flow-pull.md
│   ├── flow-push.md
│   ├── flow-link.md
│   ├── flow-version.md
│   └── flow-upgrade.md
└── worktree/
    ├── worktree-start.md
    └── worktree.md
```