# 模块：scripts/

## Overview

6 个 Python 工具脚本，提供 Flow 的**控制平面**：路径 SSOT、流程编排、状态机、契约漂移检测、GC、worktree 管理。

## API 端点

不适用（脚本被 hook / command / agent 调用，CLI 入口）。

## 领域模型

| Script | 职责 | 调用方 |
|--------|------|--------|
| `paths.py` | 集中路径常量（SSOT） | 所有 Python 模块 |
| `flow_advance.py` | 解释 flow 模板 + 推进 step | command / agent |
| `workflow-state.py` | 读写 workflow-state.json + events.jsonl | session-start / hook |
| `contract-drift-check.py` | 检测 contract.md 与代码漂移 | fitness-run skill |
| `gc.py` | 清理 stale 缓存 / 报告 / 索引 | gc skill / cron |
| `worktree-manager.py` | git worktree 创建/绑定/清理 | worktree command |

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
- `gc.py` import `paths` 拿目录常量

## 文件路由

```
scripts/
├── paths.py                    ( 98 lines) — SSOT 必读
├── flow_advance.py             (272 lines) — flow 模板解释器
├── workflow-state.py           (361 lines) — state machine
├── contract-drift-check.py     (212 lines) — 契约漂移
├── gc.py                       (459 lines) — 最大、清理逻辑复杂
└── worktree-manager.py         (408 lines) — worktree 管理
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

## 注意事项（团队手写段，禁止自动覆盖）

- **paths.py 是唯一路径来源**——任何路径变更先改 paths.py，再改文档
- 脚本入口要 `if __name__ == "__main__":`，便于 CLI 调用
- 跨平台：用 `pathlib.Path`，避免 `os.path` 与硬编码 `/`
