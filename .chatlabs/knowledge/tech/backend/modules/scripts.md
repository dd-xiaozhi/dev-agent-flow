# 模块：scripts/

## Overview

5 个 Python 工具脚本，提供 Flow 的**控制平面**：路径 SSOT、流程编排、任务状态。`gc.py`、`worktree-manager.py`、`contract-drift-check.py`、`migrate_stories_to_task.py` 已下线（gc 改 skill；worktree 随子命令退场；契约漂移规则废弃；stories→task 迁移已完成）。

## API 端点

不适用（脚本被 hook / command / agent 调用，CLI 入口）。

## 领域模型

| Script | 职责 | 调用方 |
|--------|------|--------|
| `paths.py` | 集中路径常量（SSOT） | 所有 Python 模块 |
| `flow_advance.py` | 解释 flow 模板 + 推进 step | command / agent |
| `workflow-state.py` | 读写 workflow-state.json + events.jsonl | session-start / hook |
| `task.py` | task 生命周期 CLI（new / resume / report） | command / hook |
| `task_store.py` | task 数据存取层（被 task.py 引用） | task.py |

## 存储层

- 脚本读：所有 `.chatlabs/` 与 `.claude/templates/`
- 脚本写：因功能而异，全部走 paths.py 常量

## 依赖关系

```
所有 Python 模块（hook + script）
            ↓
       paths.py（SSOT）
            ↓
       pathlib.Path 对象
```

scripts 之间允许 import：

- `flow_advance.py` import `workflow-state` 操作状态
- `task.py` import `task_store` 完成持久化

## 文件路由

```
scripts/
├── paths.py                       SSOT 必读
├── flow_advance.py                flow 模板解释器
├── workflow-state.py              state machine
├── task.py                        task 生命周期 CLI
└── task_store.py                  task 数据存取层
```

## 关键 API

### paths.py

```python
from paths import (
    PROJECT_DIR,        # git 根
    CLAUDE_DIR,         # .claude/
    CHATLABS_DIR,       # .chatlabs/
    STORIES_DIR,        # .chatlabs/stories/
    REPORTS_DIR,        # .chatlabs/reports/
    STATE_DIR,          # .chatlabs/state/
    KNOWLEDGE_DIR,      # .chatlabs/knowledge/
    EVENTS_LOG,         # state/events.jsonl
    WORKFLOW_STATE,     # state/workflow-state.json
    # ... 详见源文件
)
```

### flow_advance.py

```bash
python .claude/scripts/flow_advance.py init --flow=<flow_id>
python .claude/scripts/flow_advance.py advance --step=<step_id>
python .claude/scripts/flow_advance.py check
```

### task.py

```bash
python .claude/scripts/task.py new <task_id>      # 新建任务（绑定 git 分支）
python .claude/scripts/task.py resume <task_id>   # 恢复任务
python .claude/scripts/task.py report <task_id>   # 生成任务报告
```

## 注意事项（团队手写段，禁止自动覆盖）

- **paths.py 是唯一路径来源**——任何路径变更先改 paths.py，再改文档
- 脚本入口要 `if __name__ == "__main__":`，便于 CLI 调用
- 跨平台：用 `pathlib.Path`，避免 `os.path` 与硬编码 `/`
