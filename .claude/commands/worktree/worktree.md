# /worktree

> **Git Worktree 并行执行命令**。为不同需求创建独立工作区，实现多任务并行开发。
>
> 每个 worktree 拥有独立的 `.chatlabs/` 运行时目录，状态完全隔离。

## 子命令

| 子命令 | 说明 |
|--------|------|
| `/worktree new <story-id> [--description]` | 创建新 worktree 并启动独立 flow |
| `/worktree list` | 列出所有 worktree |
| `/worktree status` | 显示并行任务概览 |
| `/worktree switch <story-id>` | 切换到指定 worktree |
| `/worktree merge <story-id> [--no-delete]` | 合并已完成 story 到 master |
| `/worktree remove <story-id> [--force]` | 移除 worktree |
| `/worktree cleanup` | 清理已合并的 worktree 目录 |

## 架构说明

```
main-repo/
├── .claude/                      # 共享配置
├── .chatlabs/                    # 主仓库状态
│   └── worktree-manager.json      # worktree 索引
└── .worktrees/                   # worktree 根目录
    ├── story-001/                # STORY-001 worktree
    │   ├── .chatlabs/            # 独立运行时状态
    │   └── [项目文件]
    └── story-002/
        └── ...
```

**核心原则**：
- 共享 `.claude/` 配置（agents、commands、skills、hooks）
- 每个 worktree 拥有独立的 `.chatlabs/`（状态隔离）
- Worktree 在独立 git 分支上开发（如 `wt/story-001`）
- 完成合并回 master 后自动清理 worktree

---

## /worktree new

### 行为

**第一步：解析参数**

1. `story-id` 为必填（如 `STORY-001`）
2. `--description` 为可选 story 描述

**第二步：调用 worktree-manager 创建**

```python
from worktree_manager import WorktreeManager
wm = WorktreeManager()
info = wm.create_worktree(story_id, description)
```

**第三步：输出创建结果**

```
═══════════════════════════════════════════════════════════
  🆕 Worktree 创建成功

  Story:     STORY-001
  路径:      .worktrees/story-001/
  分支:      wt/story-001
  状态:      created

  启动方式:
  $ cd .worktrees/story-001 && claude
  $ /worktree-start --story STORY-001

  ℹ️ Worktree 内自动使用独立的 .chatlabs/ 目录
═══════════════════════════════════════════════════════════
```

**第四步：提示启动独立 session**

建议用户在新 terminal 启动：
```bash
open -a Terminal ".worktrees/story-001"
```

或在当前 session 提示：
```
→ 在新 session 中运行以下命令启动 flow:
  /worktree-start STORY-001
```

---

## /worktree list

### 行为

调用 `WorktreeManager.list_worktrees()`，输出格式：

```
═══════════════════════════════════════════════════════════
  📦 Worktree 列表

  STORY-001  |  running  |  .worktrees/story-001/  |  2026-04-22 10:00
  STORY-002  |  completed  |  .worktrees/story-002/  |  2026-04-22 11:30
  STORY-003  |  running  |  .worktrees/story-003/  |  2026-04-22 12:00

  共 3 个 worktree，2 个运行中
═══════════════════════════════════════════════════════════
```

---

## /worktree status

### 行为

调用 `WorktreeManager.get_status_summary()`，输出概览：

```
═══════════════════════════════════════════════════════════
  📊 并行任务概览

  总计:    3
  运行中:  2  ████████░░
  完成:   1  ████░░░░░░
  已合并: 0  ░░░░░░░░░░

  [=] STORY-001  ████████████████░░  80% (generator)
  [~] STORY-002  ████████████████░░  85% (evaluator)
  [-] STORY-003  ██████████░░░░░░░░  40% (planner)
═══════════════════════════════════════════════════════════
```

---

## /worktree switch

### 行为

切换到指定 worktree 工作目录：

1. 检查 worktree 是否存在
2. 输出切换指令（不能直接 cd，需要在新 session 启动）

```
═══════════════════════════════════════════════════════════
  🔄 切换到 STORY-001

  路径:  .worktrees/story-001/

  切换方式:
  $ cd .worktrees/story-001
  $ claude

  或在 Finder 中打开:
  $ open .worktrees/story-001
═══════════════════════════════════════════════════════════
```

---

## /worktree merge

### 行为

**第一步：检查完成状态**

检查 worktree 内是否存在 `generator:all-done` 事件。

**第二步：确认合并**

若存在未合并变更，提示确认：
```
⚠️ 检测到未提交的变更
是否强制合并？[y/N]
```

**第三步：执行合并**

```python
wm.merge_to_master(story_id, commit_message)
```

**第四步：输出结果**

```
═══════════════════════════════════════════════════════════
  ✅ STORY-001 已合并到 master

  提交:    Merge STORY-001 (用户反馈功能)
  分支:    wt/story-001 已删除
  目录:    .worktrees/story-001/ 已清理

═══════════════════════════════════════════════════════════
```

---

## /worktree remove

### 行为

移除指定 worktree：

- 不带 `--force`：检查是否有未合并变更，有则拒绝
- 带 `--force`：强制删除，忽略未合并状态

```
═══════════════════════════════════════════════════════════
  🗑️  Worktree STORY-001 已移除

  分支:  wt/story-001 已删除
  目录:  .worktrees/story-001/ 已清理
═══════════════════════════════════════════════════════════
```

---

## /worktree cleanup

### 行为

清理所有已合并但未删除目录的 worktree：

```
═══════════════════════════════════════════════════════════
  🧹 清理完成

  已清理 2 个已合并的 worktree 目录
═══════════════════════════════════════════════════════════
```

---

## 错误处理

| 场景 | 行为 |
|------|------|
| story-id 已存在 worktree | 输出错误，退出 |
| story-id 无对应 worktree | 输出错误，退出 |
| merge 时有冲突 | 输出冲突文件，退出（需手动解决） |
| 无 worktree 目录 | 提示运行 `/worktree cleanup` |

---

## 关联

- `/worktree-start` — Worktree 内启动 flow
- `worktree-manager.py` — 底层管理模块
- `worktree-merge.sh` — 自动合并脚本

---

## 使用示例

```bash
# 创建新 worktree 并行开发
/worktree new STORY-001 --description "新增用户反馈功能"
/worktree new STORY-002 --description "优化搜索性能"

/worktree status  # 查看并行进度

# STORY-001 完成，合并
/worktree merge STORY-001

# STORY-002 也完成
/worktree merge STORY-002

# 清理残留目录
/worktree cleanup
```
