# Flow 产物目录布局

> **存放位置**:`.claude/artifacts-layout.md` (flow 基础设施文档)
>
> **目录划分原则**:
> - `.claude/` → flow 基础设施(agents/commands/skills/hooks/templates/**本文件**)
> - `.chatlabs/` → 运行时产物 + 项目配置(task/reports/state/worktrees/flow-logs **+ project-config.json**)
>
> 所有产物路径在 `.claude/scripts/paths.py` 有 Python 常量定义(Python 侧 SSOT)。

---

## 顶层结构

```
.chatlabs/
├── task/                  # 任务层 SSOT（task.json 聚合 4 section）
│   ├── store/             #   业务需求型任务（原 stories/）
│   ├── bug-fix/           #   缺陷修复型任务
│   └── _index.jsonl       #   任务索引（task_id ↔ story_id ↔ ticket_id）
├── worktrees/             # git worktree 多分支隔离工作树（bug-fix 并行）
├── reports/               # 执行报告、task 报告、workflow 报告、fitness 产物
├── tapd/                  # TAPD 工单快照缓存（_index.jsonl 仍在此；ticket 详情已并入 task.json.tapd）
├── knowledge/             # 项目级规范索引(由 /init-project 生成)
├── state/                 # 机器状态文件(全局 workflow-state.json / events.jsonl，已被 task.json 替代但保留 fallback)
└── flow-logs/             # 进化机制产物(insights / evolution-proposals)
```

---

## task/ — 任务层产物（SSOT）

每个任务目录下的 `task.json` 聚合 4 个 section：`workflow` / `git` / `tapd` / `bug_fix`。
所有读写都经 `task_store.TaskJsonStore` 门面，禁止直写。

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `task/store/<story_id>/task.json` | 业务需求任务状态聚合 | TaskJsonStore（被 flow_advance / WorkflowState / tapd skill 调用） | session-start / task.py resume / 各 agent |
| `task/store/<story_id>/contract.md` | 业务契约 | doc-librarian | 所有 agent |
| `task/store/<story_id>/tapd-comment.md` | TAPD 工单评论汇总（按日期分组，特殊标记加粗） | tapd/scripts/comments_cache.py / tapd fetch | human review / doc-librarian |
| `task/store/<story_id>/spec.md` | 实现规格 | planner | generator |
| `task/store/<story_id>/cases/CASE-*.md` | 任务用例 | planner | generator/evaluator |
| `task/store/<story_id>/cases/<case_id>.tests.yaml` | curl 验收用例（GAN 判定依据） | planner | generator(自验)/evaluator(复跑) |
| `task/store/<story_id>/changelog.md` | 冻结后变更记录 | doc-librarian | 所有 agent |
| `task/store/<story_id>/source/` | 原始需求素材（**只读**） | (入口命令归档) | doc-librarian(只读) |
| `task/store/<story_id>/feedback/` | consensus/QA 反馈 | (外部系统/人工) | 各 agent |
| `task/bug-fix/<bug_id>/task.json` | 缺陷修复任务状态聚合（含 `bug_fix` section） | bug-fix command + TaskJsonStore | session-start / 各 agent |
| `task/bug-fix/<bug_id>/description.md` | bug 描述（TAPD 拉取或本地） | bug-fix command | 各 agent |
| `task/_index.jsonl` | 任务索引 | task.py / tapd pull | gc / workflow-reviewer |

---

## reports/ — 执行报告

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `reports/tasks/<task_id>/meta.json` | task 三件套元数据 | task.py new/agent | session-start/task.py resume |
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
| `reports/metrics/eval-verdicts.jsonl` | evaluator verdict 历史（二元 PASS/FAIL/ERROR） | evaluator agent | workflow-reviewer |
| `reports/integration-tests/<story>/<case>.generator.json` | generator 自验 verdict（仅参考） | integration-test skill (--role=generator) | generator / evaluator(差异比对) |
| `reports/integration-tests/<story>/<case>.evaluator.json` | evaluator 独立复跑 verdict（**最终判定**） | integration-test skill (--role=evaluator) | evaluator agent |
| `reports/integration-tests/<story>/<case>.<role>.log` | adapter 工具原始日志 | integration-test skill | 排错 |
| `reports/integration-tests/<story>/<case>.<role>.service.log` | 被测服务 stdout/stderr | integration-test skill | 排错 |
| `reports/members/<date>/activity.md` | 成员活动报告 | member-activity skill | team |

---

## state/ — 机器状态

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `state/workflow-state.json` | 全局 workflow fallback（per-story 已迁至 `task/store/<id>/task.json.workflow`） | 各 agent（无 story 上下文时） | session-start/hook |
| `state/events.jsonl` | 事件总线(append-only) | 各 agent | session-start/tapd-sync |
| `state/current_task` | 当前 task ID | task.py new/resume | session-start |
| `state/gc_last_run` | GC 最后运行时间 | gc skill | gc skill(去重) |

---

## tapd/ — TAPD 缓存

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `tapd/tickets/<ticket_id>.json` | 工单快照 | tapd skill | 各 TAPD 集成命令 |
| `tapd/tickets/_index.jsonl` | 工单索引 | tapd skill | /tapd start |

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
from paths import REPORTS_DIR, STORE_DIR, BUG_FIX_DIR, STATE_DIR, ...

# 而非硬编码路径字符串
path = REPORTS_DIR / "fitness" / "fitness-run.json"
```

关键常量速查:

| 常量 | 路径 |
|------|------|
| `CHATLABS_DIR` | `.chatlabs/` |
| `TASK_DIR` | `.chatlabs/task/` |
| `STORE_DIR` | `.chatlabs/task/store/`（业务需求任务） |
| `BUG_FIX_DIR` | `.chatlabs/task/bug-fix/`（缺陷修复任务） |
| `WORKTREES_DIR` | `.chatlabs/worktrees/`（git worktree 隔离） |
| `STORIES_DIR` | deprecated 别名 → `STORE_DIR` |
| `REPORTS_DIR` | `.chatlabs/reports/` |
| `STATE_DIR` | `.chatlabs/state/` |
| `TAPD_DIR` | `.chatlabs/tapd/` |
| `FLOW_LOGS_DIR` | `.chatlabs/flow-logs/` |
| `KNOWLEDGE_DIR` | `.chatlabs/knowledge/` |
| `FITNESS_DIR` | `.chatlabs/reports/fitness/` |
| `HANDOFFS_DIR` | `.chatlabs/reports/handoffs/` |
| `EVAL_VERDICTS` | `.chatlabs/reports/metrics/eval-verdicts.jsonl` |
