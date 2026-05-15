---
name: flow-engine
description: 流程编排引擎。推进 task.json.flow 步骤（init/check/complete/reset）并维护事件总线 events.jsonl（emit/check/recent）。触发关键词：flow advance、推进流程、当前步骤、初始化流程、emit event、查事件、events.jsonl、flow-engine。
model: haiku
---

# Flow Engine — 流程编排引擎

> 主流程的状态机。读模板 + 写 task.json.flow 推进 step；同时维护事件总线供 hook / agent / gc 消费。
> 流程推进与事件记录是同一回事的两面：step 跨越 → 事件追加；事件查询 → 反推流程状态。合并为一个 skill。

## 边界

- ✅ 推进 `task.json` 的 workflow.flow 子对象（current_step_idx / history / phase / agent 双写）
- ✅ 追加/查询 `.chatlabs/state/events.jsonl`（追加只写，不修改既往）
- ✅ 加载 `.claude/templates/flows/*.json` 流程模板（创建时锁定 hash）
- ❌ 不创建/删除 task（由 task.py / tapd skill 负责）
- ❌ 不解释业务规则（由 contract.md 负责）
- ❌ 不触发 agent（由主 Claude 按 next_step 决定）

## CLI

### flow_advance — 流程推进器

```bash
python .claude/skills/flow-engine/scripts/flow_advance.py [--story-id <id>] <sub>
```

| 子命令 | 用法 | 说明 |
|--------|------|------|
| `init` | `init --flow-id <flow> [--task-id <id>] [--force]` | 创建 flow 子对象，模板 hash 锁定 |
| `check` | `check` | 只读输出当前 step / next step / is_terminal |
| `complete` | `complete <step_id> [--result ok\|failed]` | 声明 step 完成，advance 到下一步（幂等） |
| `reset` | `reset` | 重置到 idx=0（debug 用） |

支持的 flow-id：`tapd-full` / `local-spec` / `local-plan` / `local-vibe` / `bugfix-spec` / `bugfix-plan` / `bugfix-vibe`

**退出码**：0=ok / 1=error（含 step 不匹配 / flow 未初始化等）

### events — 事件总线

```bash
python .claude/skills/flow-engine/scripts/events.py <sub>
```

| 子命令 | 用法 | 说明 |
|--------|------|------|
| `emit` | `emit <type> [--story-id <id>] [--task-id <id>] [--data '<json>']` | 追加事件到 events.jsonl |
| `check` | `check <type> --story-id <id>` | 检查该 story 是否存在该类型事件（退出码 0/1） |
| `recent` | `recent --story-id <id> [--type <type>] [--limit 20]` | 读取最近事件（JSON 输出） |

## 模块化（Python import）

事件总线同时支持 Python 模块方式（hook 内部用）：

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / ".claude" / "skills" / "flow-engine" / "scripts"))
from events import emit_event, check_event, get_recent_events

emit_event("session:start", {"task_id": "TASK-...", "story_id": "..."})
if check_event("04-30-wechat-login", "planner:all-cases-ready"):
    ...
```

> hook 走 import（同进程、零启动开销）；agent / command 走 CLI（隔离）。

## 状态文件

| 路径 | 写入者 | 读取者 |
|------|--------|--------|
| `.chatlabs/task/store/<story_id>/task.json` 的 `workflow` section | flow_advance 的 init/complete/reset | session-start、task.py resume、各 agent |
| `.chatlabs/state/events.jsonl` | events.emit / emit_event | session-start、gc、agent 自检 |
| `.chatlabs/state/workflow-state.json` | 全局 fallback（无 story_id 时） | 同上 |

## 触发方式

| 场景 | 调用方 | 命令 |
|------|--------|------|
| TAPD 工单开工 | `/tapd start` | `flow_advance init --flow-id tapd-full --story-id <id> --task-id <id>` |
| 本地需求开工 | `/story-start` | `flow_advance init --flow-id local-spec --story-id <id>` |
| Bug 修复 | `/bug-fix` | `flow_advance init --flow-id bugfix-{spec,plan,vibe} --story-id <bug>` |
| Agent 完成 | 主 Claude | `flow_advance complete <step_id>` |
| 状态恢复 | `task resume` | `flow_advance check --story-id <id>` |
| 关键事件 | hook / agent | `emit_event("...", {...})` 或 `events.py emit ...` |

## 关联文件

- 脚本：`.claude/skills/flow-engine/scripts/{flow_advance,events}.py`
- 流程模板：`.claude/templates/flows/*.json`
- 共享依赖：`.claude/scripts/{paths,task_store}.py`（通过 sys.path 加载）
