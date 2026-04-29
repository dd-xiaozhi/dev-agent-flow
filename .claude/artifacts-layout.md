# Flow 产物目录布局

> **存放位置**:`.claude/artifacts-layout.md` (flow 基础设施文档)
>
> **目录划分原则**:
> - `.claude/` → flow 基础设施(agents/commands/skills/hooks/templates/**本文件**)
> - `.chatlabs/` → 运行时产物 + 项目配置(stories/reports/state/tapd cache/flow-logs **+ project-config.json**)
>
> 所有产物路径在 `.claude/scripts/paths.py` 有 Python 常量定义(Python 侧 SSOT)。

---

## 顶层结构

```
.chatlabs/
├── stories/              # Story 产物(contract/spec/cases/feedback)
├── reports/              # 执行报告、task 报告、workflow 报告、fitness 产物
├── tapd/                 # TAPD 工单快照缓存
├── knowledge/            # 项目级规范索引(由 /init-project 生成)
├── state/                # 机器状态文件(workflow-state.json / events.jsonl)
└── flow-logs/            # 进化机制产物(insights / evolution-proposals)
```

---

## stories/ — Story 产物

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `stories/<story_id>/contract.md` | 业务契约 | doc-librarian | 所有 agent |
| `stories/<story_id>/openapi.yaml` | HTTP 接口定义 | doc-librarian | 前端/后端/QA |
| `stories/<story_id>/spec.md` | 实现规格 | planner | generator |
| `stories/<story_id>/cases/CASE-*.md` | 任务用例 | planner | generator/evaluator |
| `stories/<story_id>/changelog.md` | 冻结后变更记录 | doc-librarian | 所有 agent |
| `stories/<story_id>/source/` | 原始需求素材（**只读**） | (入口命令归档) | doc-librarian(只读) |
| `stories/<story_id>/feedback/` | consensus/QA 反馈 | (外部系统/人工) | 各 agent |

---

## reports/ — 执行报告

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `reports/tasks/<task_id>/meta.json` | task 三件套元数据 | task-new/agent | session-start/task-resume |
| `reports/tasks/<task_id>/audit.jsonl` | 文件操作轨迹 | file-tracker hook | session-end/self-reflect |
| `reports/tasks/<task_id>/blockers.md` | blocker 记录 | blocker-tracker hook | workflow-reviewer |
| `reports/workflow/blockers-summary.md` | sprint blocker 汇总 | workflow-reviewer | sprint-review |
| `reports/sprints/<date>/review-*.md` | sprint 复盘报告 | sprint-review | team |
| `reports/fitness/fitness-run.json` | fitness 运行汇总 | fitness-run skill | self-reflect |
| `reports/fitness/<rule>.log` | 单条 fitness rule 日志 | fitness-run skill | self-reflect |
| `reports/fitness/fitness-backlog.md` | fitness 候选规则积压 | post-tool-linter-feedback hook | fitness-run |
| `reports/fitness-failures.log` | linter-feedback 失败日志 | post-tool-linter-feedback hook | self-reflect |
| `reports/handoffs/<ts>.md` | session handoff 工件 | context-reset skill | (下一 session 读取) |
| `reports/handoffs.jsonl` | handoff 指标 | context-reset skill | self-reflect |
| `reports/metrics/eval-verdicts.jsonl` | evaluator verdict 历史 | evaluator agent | workflow-reviewer |
| `reports/members/<date>/activity.md` | 成员活动报告 | member-activity skill | team |

---

## state/ — 机器状态

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `state/workflow-state.json` | 当前 story/task 状态 | 各 agent | session-start/hook |
| `state/events.jsonl` | 事件总线(append-only) | 各 agent | session-start/tapd-sync |
| `state/current_task` | 当前 task ID | task-new | session-start |
| `state/gc_last_run` | GC 最后运行时间 | gc skill | gc skill(去重) |

---

## tapd/ — TAPD 缓存

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `tapd/tickets/<ticket_id>.json` | 工单快照 | tapd-pull skill | 各 TAPD 集成命令 |
| `tapd/tickets/_index.jsonl` | 工单索引 | tapd-pull skill | tapd-story-start |

---

## knowledge/ — 项目规范

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `knowledge/README.md` | 项目规范索引 | /init-project | 各 agent |
| `knowledge/contract/*.md` | API 规范 | /init-project | doc-librarian |
| `knowledge/tech/backend/*.md` | 后端技术规范 | /init-project | generator/planner |

---

## flow-logs/ — 进化机制

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `flow-logs/YYYY-MM/FL-*.json` | 每次 flow 的结构化记录 | self-reflect | workflow-review |
| `flow-logs/insights/_index.jsonl` | 洞察索引 | insight-extract | evolution-propose |
| `flow-logs/evolution-proposals/_pending.jsonl` | 待确认的进化提案 | evolution-propose | evolution-apply |
| `flow-logs/evolution-proposals/_applied.jsonl` | 已应用的进化提案 | evolution-apply | self-reflect |

---

## Python 侧路径常量

以上所有路径在 `.claude/scripts/paths.py` 有 Python 常量定义。Python 代码应:

```python
import sys
sys.path.insert(0, ".claude/scripts")
from paths import REPORTS_DIR, STORIES_DIR, STATE_DIR, ...

# 而非硬编码路径字符串
path = REPORTS_DIR / "fitness" / "fitness-run.json"
```

关键常量速查:

| 常量 | 路径 |
|------|------|
| `CHATLABS_DIR` | `.chatlabs/` |
| `STORIES_DIR` | `.chatlabs/stories/` |
| `REPORTS_DIR` | `.chatlabs/reports/` |
| `STATE_DIR` | `.chatlabs/state/` |
| `TAPD_DIR` | `.chatlabs/tapd/` |
| `FLOW_LOGS_DIR` | `.chatlabs/flow-logs/` |
| `KNOWLEDGE_DIR` | `.chatlabs/knowledge/` |
| `FITNESS_DIR` | `.chatlabs/reports/fitness/` |
| `HANDOFFS_DIR` | `.chatlabs/reports/handoffs/` |
| `EVAL_VERDICTS` | `.chatlabs/reports/metrics/eval-verdicts.jsonl` |
