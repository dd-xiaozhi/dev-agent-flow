# 模块：scripts/

## Overview

Flow 的**控制平面**：路径 SSOT、任务生命周期、task.json 单一写者门面。流程编排（`flow_advance.py`）与事件总线（`events.py`)按 skill 边界拆到 `skills/flow-engine/scripts/`，但仍 import 本目录的 `paths.py` 与 `task_store.py`。

`gc.py`、`worktree-manager.py`、`contract-drift-check.py`、`migrate_stories_to_task.py` 已下线（gc 改 skill；worktree 随子命令退场；契约漂移规则废弃；stories→task 迁移已完成）。

## API 端点

不适用（脚本是 CLI / library，被 hook / command / agent / skill 调用）。

## 领域模型

| Script | 位置 | 职责 | 调用方 |
|--------|------|------|--------|
| `paths.py` | `scripts/` | 路径常量 SSOT | 所有 Python 模块 |
| `task_store.py` | `scripts/` | task.json 单一写者门面（fcntl 锁 + atomic rename） | task.py / flow_advance / events / 各 skill |
| `task.py` | `scripts/` | task 生命周期 CLI（new / resume / bind-branch / list） | command / hook |
| `flow_advance.py` | `skills/flow-engine/scripts/` | 解释 flow 模板 + 推进 step（init/check/complete/reset） | command / agent |
| `events.py` | `skills/flow-engine/scripts/` | 任务级事件读写（task.json.events） | hook / agent / skill |

## 存储层

- 读：`.chatlabs/` 与 `.claude/templates/` 全域
- 写：仅经 `task_store.TaskJsonStore` 写 `task.json`；其他产物（blockers.md、_index.jsonl）各 CLI 自行管理
- task.json 是任务级 SSOT，整合 `task_id / task_type / story_id / workflow / git / tapd / events` 等顶层段；旧的 `reports/tasks/<id>/meta.json` 与 `.chatlabs/state/events.jsonl` 已废弃

## 依赖关系

```
        所有 Python 模块（hook + script + skill）
                       ↓
                  paths.py（SSOT）
                       ↓
              task_store.TaskJsonStore（task.json 唯一写者）
                       ↓
                 .chatlabs/task/store/<story_id>/task.json
```

允许的 import 关系：

- `task.py`、`flow_advance.py`、`events.py` 均 import `task_store` 持久化
- `flow_advance.py` import `events.check_event / get_recent_events / emit_event` 实现 gate 事件依赖
- skill 与 hook 通过 `sys.path.insert(...)` 引 `.claude/scripts/` 复用

## 文件路由

```
.claude/scripts/
├── paths.py                              路径 SSOT
├── task_store.py                         task.json 单一写者门面
└── task.py                               task 生命周期 CLI

.claude/skills/flow-engine/scripts/
├── flow_advance.py                       flow 模板解释器（含 consensus-gate TBD 预检）
└── events.py                             任务级事件总线
```

## 关键 API

### paths.py（常量导入）

```python
from paths import (
    PROJECT_DIR,        # git 根
    CLAUDE_DIR,         # .claude/
    CHATLABS_DIR,       # .chatlabs/
    STORE_DIR,          # .chatlabs/task/store/           业务任务
    BUG_FIX_DIR,        # .chatlabs/task/bug-fix/         缺陷任务
    WORKTREES_DIR,      # .chatlabs/worktrees/            git worktree 隔离
    TASK_REPORTS,       # .chatlabs/reports/tasks/        blockers.md 等产物
    TASK_INDEX,         # .../reports/tasks/_index.jsonl
    STATE_DIR,          # .chatlabs/state/
    CURRENT_TASK,       # .chatlabs/state/current_task
    KNOWLEDGE_DIR,      # .chatlabs/knowledge/
    PROJECT_CONFIG,     # .chatlabs/project-config.json
    TEMPLATES_DIR,      # .claude/templates/
    # STORIES_DIR / TASKS_DIR 是 STORE_DIR 的兼容别名（保留以兼容遗留引用）
)
```

### task.py（CLI）

```bash
# 创建任务记录（task_id = {MM}-{dd}-{slug}，--name 必填，3-40 字符 a-z 0-9 -）
python .claude/scripts/task.py new <story_id> --name <slug> \
       [--predecessor <task_id>] [--trigger <reason>]

# 续接已存在任务（task_id 必须匹配 {MM}-{dd}-{slug}）
python .claude/scripts/task.py resume <task_id>

# 把 git 分支绑定到 task.json.git（支持 store / bug-fix 两种 task_type）
python .claude/scripts/task.py bind-branch <task_id> --branch <name> \
       [--branch-type feature|bugfix|hotfix|release] \
       [--source-branch <branch>] [--merge-targets dev,uat] \
       [--worktree-path <path>]

# 列任务索引（可按 story 过滤）
python .claude/scripts/task.py list [--story-id <id>]
```

### flow_advance.py（CLI）

```bash
# 初始化 flow（task 创建后由 /start-dev-flow 调用）
python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <id> init \
       --flow-id <tapd-full|local-vibe|local-plan|local-spec|bugfix-...> \
       --task-id <task_id> [--force]

# 推进 step（agent / command 完成后调用；gate 步骤需带证据）
python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <id> complete <step_id> \
       [--evidence-type wiki-comment-id --evidence-id <comment_id>]

# 只读当前状态（task.py resume 内部调用）
python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <id> check

# 重置到第一步（debug）
python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <id> reset
```

### events.py（CLI + Python）

```bash
# emit：data 必须含 story_id，缺失则丢弃（session 级事件已废弃）
python .claude/skills/flow-engine/scripts/events.py emit <type> --story-id <id> \
       [--task-id <id>] [--data '<json>']

# check：退出码 0=存在 / 1=不存在
python .claude/skills/flow-engine/scripts/events.py check <type> --story-id <id>

# recent：读最近 N 条（默认 20）
python .claude/skills/flow-engine/scripts/events.py recent --story-id <id> \
       [--type <t>] [--limit 20]
```

Python 直接调用（hook 同进程）：

```python
from events import emit_event, check_event, get_recent_events
emit_event("planner:all-cases-ready", {"story_id": "05-27-wechat-login"})
```

## 注意事项（团队手写段，禁止自动覆盖）

- **paths.py 是唯一路径来源**——任何路径变更先改 paths.py，再改文档
- **task.json 的写入必须经 `TaskJsonStore`**——禁止手写 `open(...).write(json.dumps(...))`，会绕开 fcntl 锁
- `task_id` 格式锁定 `{MM}-{dd}-{slug}`（同日重名时附加 `-YYYYMMDD-HHMMSS` 兜底），正则见 `task.py._TASK_ID_RE`
- 跨平台：用 `pathlib.Path`，避免 `os.path` 与硬编码 `/`
- 脚本入口要 `if __name__ == "__main__":`，便于 CLI 调用
