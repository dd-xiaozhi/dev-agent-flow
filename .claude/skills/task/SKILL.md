---
name: task
description: "USE WHEN: 创建任务记录 / 恢复已有任务 / 列任务索引 / 绑定 git 分支到任务 / 查询历史任务。OUTPUT: task.json (SSOT) + _index.jsonl 注册 + .current_task 切换。DO NOT USE: 推进 flow 步骤(走 flow-engine) / TAPD 工单同步(走 tapd) / git 分支创建本身(走 git)。"
model: sonnet
---

# Task — 任务记录管理

> task.json 单一写者门面 + _index.jsonl 全局索引。所有任务级状态读写过这里。

## 触发

创建任务 / 新任务 / new task / 恢复任务 / resume task / 列任务 / list tasks / 切换任务 / 绑定分支 / bind-branch / search task。

## 边界

- ✅ 创建 / 恢复 / 列任务记录（CLI 入口）
- ✅ task.json 读写（`TaskJsonStore` 类，被其他 skill import）
- ✅ `_index.jsonl` 维护（task_index 模块）
- ✅ 绑定 git 分支到任务的 `git` section
- ❌ 推进 flow 步骤（那是 `flow-engine` 的职责）
- ❌ TAPD 同步（那是 `tapd` 的职责）
- ❌ 创建 git 分支本身（那是 `git` 的职责;本 skill 只做"分支已建好后绑定到任务"）

## Gotchas

1. **task_id 格式固定** `{MM}-{dd}-{description}`（小写字母+数字+连字符，长度 3-40）—— `--name` 强制必填，无前缀
2. **同日重名** 自动加 `-{YYYYMMDD-HHMMSS}` 时间戳后缀，所以 task_id ≠ story_id 在极少数情况发生
3. **task.json 必须经 `TaskJsonStore.save()`** 写入（原子 rename + fcntl 锁）—— 禁直接 `json.dump()` 写文件
4. **`TaskJsonStore` 默认骨架字段** 未填充时是 `None` 不是 `{}` —— 区分"未初始化"vs"已初始化但空"
5. **bind-branch 配置驱动** —— 不传 `--source-branch` / `--merge-targets` 时会从 `project-config.json.git.branches.<type>` 读，显式参数始终最高优先级
6. **被 import 时路径** —— 调用方需 `sys.path.insert(0, str(parents[3] / "skills" / "task" / "scripts"))` 才能 `from task_store import TaskJsonStore`

## CLI

```bash
# 创建任务（task_id 自动 = {MM}-{dd}-{name}）
python .claude/skills/task/scripts/task.py new <story_id> --name <description> \
    [--trigger first-start|defect-fix|...] [--predecessor <task_id>]

# 恢复任务（读 flow 状态 + 写 .current_task + 输出注入材料）
python .claude/skills/task/scripts/task.py resume <task_id>

# 绑定 git 分支到任务（配置驱动）
python .claude/skills/task/scripts/task.py bind-branch <task_id> \
    --branch <name> [--branch-type feature|bugfix|hotfix|release] \
    [--source-branch ...] [--merge-targets ...] [--worktree-path ...]

# 列任务索引
python .claude/skills/task/scripts/task.py list [--story-id <id>]

# 任务存储调试 CLI
python .claude/skills/task/scripts/task_store.py show <story_id>
python .claude/skills/task/scripts/task_store.py list-active
python .claude/skills/task/scripts/task_store.py find-branch <branch>
python .claude/skills/task/scripts/task_store.py find-tapd <ticket_id>
```

## Python API（被其他 skill import）

```python
import sys
from pathlib import Path
# 在调用方脚本顶部
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "task" / "scripts"))
from task_store import TaskJsonStore

# 加载（按 story_id / bug_id / branch / tapd_id）
store = TaskJsonStore.load_by_story("04-30-wechat-login")
store = TaskJsonStore.load_by_bug("BUG-123")
store = TaskJsonStore.find_by_branch("feature/04-30-wechat-login")
store = TaskJsonStore.find_by_tapd_id("12345")

# 读 section
wf = store.get_workflow()    # {phase, agent, flow, blockers, ...}
git = store.get_git()        # {branch, source_branch, merge_targets, ...}
tapd = store.get_tapd()      # {ticket_id, wiki_id, subtasks, ...}

# 写 section（partial update）
store.update_workflow({"phase": "implement", "agent": "generator"})
store.update_git({"branch": "feature/...", "worktree_path": "..."})
store.save()                 # 原子 rename + fcntl 锁

# 事件流（append-only）
store.append_event("planner:all-cases-ready", {"actor": "planner"})
store.save()
events = store.get_events("planner:all-cases-ready")

# 跨任务查询
active = TaskJsonStore.list_active()         # 所有非 done 任务
all_stores = TaskJsonStore.iter_all()        # 遍历 store/ + bug-fix/
```

`task_index` 模块（被 gc skill 复用）：
```python
import task_index
task_index.read_index(TASK_INDEX)
task_index.upsert_index_entry(task_id, entry)
task_index.parse_contract_for_meta(task_dir)
task_index.git_log_for_task(task_id)
task_index.infer_complexity_from_flow_id(flow_id)
```

## 状态文件

| 路径 | 写入者 | 内容 |
|------|--------|------|
| `.chatlabs/task/store/<story_id>/task.json` | `TaskJsonStore` | 业务需求型任务 SSOT |
| `.chatlabs/task/bug-fix/<bug_id>/task.json` | `TaskJsonStore` | 缺陷修复型任务 SSOT |
| `.chatlabs/reports/tasks/_index.jsonl` | `task.py` + `task_index` | 全局任务索引 |
| `.chatlabs/state/current_task` | `task.py new/resume` | 当前活跃 task_id |

## 流程

```mermaid
flowchart LR
  A[new --name] --> B[分配 task_id]
  B --> C[初始化 task.json]
  C --> D[append _index.jsonl]
  D --> E[写 .current_task]
  E --> F[输出 todo_hint]
```

## 关联

- 脚本：`.claude/skills/task/scripts/{task.py, task_store.py, task_index.py}`
- 路径常量：**每个调用方在自己脚本顶部硬编码**(`PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", parents[N]))` + 子路径拼接),不再共享 paths.py
- 调用方：hooks/ (5 个) + flow-engine / jenkins-deploy / tapd / context-reset / gc / remote-log-fetch / skill-author 等
- 文档：AGENTS.md / README.md / commands/{bug-fix,story-start,start-dev-flow}.md
