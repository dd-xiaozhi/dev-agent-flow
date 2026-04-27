# Scripts 模块

## 概述

`.claude/scripts/` 目录定义了 Python 工具脚本，供 Hook/Skill 调用。

## 脚本列表

| 脚本 | 用途 |
|------|------|
| workflow-state.py | workflow-state.json 读写 |
| paths.py | 路径常量定义 |
| flow_repo.py | Flow 仓库操作 |
| flow_sync.py | Flow 同步工具 |
| gc.py | 垃圾回收 |
| ltm.py | 长期记忆系统 |
| gepa.py | 规则优化引擎 |
| contract-drift-check.py | 契约漂移检查 |
| member_activity_skill.py | 成员活动 skill |
| member_log_utils.py | 成员日志工具 |
| worktree-manager.py | Worktree 管理 |

## workflow-state.py

**功能**: 读写 workflow-state.json

```python
from .workflow_state import WorkflowState

# 加载
state = WorkflowState.load(story_id)

# 保存
state.complete_case("CASE-01", "PASS")
state.save()

# 检查
if state.all_cases_complete():
    state.phase = "done"
```

## paths.py

**功能**: 定义项目路径常量

```python
from .paths import (
    KNOWLEDGE_DIR,
    STATE_DIR,
    STORIES_DIR,
    REPORTS_DIR,
    TAPD_DIR,
)
```

## gc.py

**功能**: 工作流熵管理

- 清理 stale TAPD cache
- 清理孤立 _index 条目
- 清理过期 task report
- 清理过量 source 快照
- LTM consolidate（ITM → LTM）

**触发**: 每日 3:00 或手动触发

## ltm.py

**功能**: 长期记忆系统

- STM (1小时)
- ITM (7天)
- LTM (永久)
- 语义检索
- 自动 consolidate

## gepa.py

**功能**: 规则优化引擎

- 遗传-帕累托提示词进化
- 7 种变异操作符
- 多目标评估
- 帕累托最优选择

## contract-drift-check.py

**功能**: 契约漂移检查

- spec.md contract_hash 校验
- 契约版本一致性检查

## 文件路由表

```
scripts/
├── workflow-state.py         # 状态读写
├── paths.py                   # 路径常量
├── flow_repo.py               # Flow 仓库
├── flow_sync.py               # Flow 同步
├── gc.py                      # 垃圾回收
├── ltm.py                     # 长期记忆
├── gepa.py                    # 规则优化
├── contract-drift-check.py    # 契约漂移检查
├── member_activity_skill.py   # 成员活动
├── member_log_utils.py        # 成员日志
└── worktree-manager.py        # Worktree 管理
```