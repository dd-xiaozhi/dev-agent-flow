---
name: worktree-start
description: Worktree 内 Flow 启动命令——在独立 worktree 中绑定 .chatlabs/、初始化 workflow-state.json、启动 flow。前置条件：已通过 /worktree new 创建 worktree。
model: sonnet
---

# /worktree-start

> **Worktree 内 Flow 启动命令**。在独立 worktree 中启动开发流程。
>
> **前置条件**：已通过 `/worktree new` 创建 worktree。
>
> **职责**：绑定独立 `.chatlabs/`，初始化 workflow-state.json，启动 flow。

## 行为

### 第一步：检测 Worktree 模式

检查是否在 worktree 内运行：

```python
import os
# 方式 1: 检查 .git 文件
is_worktree = (Path(".git").exists() and Path(".git").is_file()
               and Path(".git").read_text().startswith("gitdir:"))

# 方式 2: 检查环境变量
is_worktree = os.environ.get("GIT_WORKTREE_ROOT") is not None
```

### 第二步：获取 Worktree 信息

从 `.worktrees/<name>/.chatlabs/` 加载 story 信息：

```python
# 从 worktree 目录推断 story_id
worktree_path = Path.cwd()
story_id = infer_story_id(worktree_path)  # .worktrees/story-001 -> STORY-001
```

### 第三步：初始化 workflow-state.json

若 worktree 内的 `workflow-state.json` 不存在，初始化：

```json
{
  "task_id": "TASK-<story_id>-01",
  "story_id": "<story_id>",
  "phase": "doc-librarian",
  "agent": "doc-librarian",
  "integrations": {
    "tapd": {"enabled": false}
  },
  "artifacts": {
    "contract": {"path": null},
    "spec": {"path": null}
  },
  "verdicts": {},
  "worktree_mode": true,
  "created_at": "<timestamp>"
}
```

### 第四步：更新 worktree-manager 状态

```python
from worktree_manager import WorktreeManager
wm = WorktreeManager()
wm.update_status(story_id, "running")
```

### 第五步：检测 Source

检查是否有 source 文件：

```
.chatlabs/stories/<story_id>/source/
```

若存在，读取 source 路径；若不存在，提示从命令行传入。

### 第六步：路由到 Doc-Librarian

启动 doc-librarian agent：

```
═══════════════════════════════════════════════════════════
  🚀 Worktree Flow 启动

  Story:     <story_id>
  模式:      worktree
  路径:      <worktree_path>
  状态:      running

  启动 Doc-Librarian...
═══════════════════════════════════════════════════════════
```

### 第七步：监听完成事件

Flow 完成（`generator:all-done`）后：

1. 更新 worktree-manager 状态为 `completed`
2. 发布 `worktree:completed` 事件
3. 提示用户合并

```
═══════════════════════════════════════════════════════════
  ✅ Worktree Flow 完成

  Story:     <story_id>
  状态:      completed

  下一步:
  /worktree merge <story_id>  # 合并到 master
═══════════════════════════════════════════════════════════
```

---

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<story-id>` | 否 | Story ID（如未指定，从目录推断） |
| `--source` | 否 | Source 文件路径 |

---

## 产出

- 初始化/更新 `.chatlabs/state/workflow-state.json`
- 启动 doc-librarian agent
- 更新 worktree-manager 状态

---

## 与 /story-start 的区别

| 维度 | `/story-start` | `/worktree-start` |
|------|---------------|-------------------|
| 运行位置 | 主仓库 | Worktree |
| .chatlabs | 主仓库 | Worktree 独立 |
| story_id 推断 | 必须显式传入 | 从目录推断 |
| worktree 状态更新 | 无 | 自动更新 |
| 完成后提示 | 无 | 提示 `/worktree merge` |

---

## 使用示例

```bash
# 在 worktree 内启动
cd .worktrees/story-001
/worktree-start

# 或指定 story_id
/worktree-start STORY-001

# 指定 source
/worktree-start STORY-001 --source ./requirements.md
```

---

## 错误处理

| 场景 | 行为 |
|------|------|
| 不在 worktree 内 | 提示使用 `/story-start` 或先运行 `/worktree new` |
| story_id 无法推断 | 输出用法，退出 |
| worktree-manager.json 不存在 | 提示先运行 `/worktree new` |

---

## 关联

- `/worktree` — Worktree 管理命令
- `/story-start` — 主仓库 story 启动（worktree 外）
- `worktree-manager.py` — 底层状态管理
