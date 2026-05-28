# Flow 产物目录布局

> **存放位置**:`.claude/artifacts-layout.md` (flow 基础设施文档)
>
> **目录划分原则**:
> - `.claude/` → flow 基础设施(agents/commands/skills/hooks/templates/**本文件**)
> - `.chatlabs/` → 运行时产物 + 项目配置(task/reports/state/worktrees **+ project-config.json**)
>
> Python 侧路径常量**已不再集中管理**(无 paths.py)。每个脚本在顶部自行计算 `PROJECT_DIR` 再拼接子路径,详见本文末"Python 侧路径常量"段。

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
└── state/                 # 机器状态文件（current_task / gc_last_run；workflow-state.json 已下线，events.jsonl 已废弃）
```

---

## task/ — 任务层产物（SSOT）

每个任务目录下的 `task.json` 聚合 4 个 section + 顶层事件流：`workflow` / `git` / `tapd` / `bug_fix` / `events`（append-only）。
所有读写都经 `task_store.TaskJsonStore` 门面，禁止直写；事件追加经 `flow-engine/events.py` 的 `emit_event`。

> **2026-05-27 起 meta.json 完全废除**：原 `reports/tasks/<task_id>/meta.json` 的全部字段并入 task.json
> （顶层 task_id / story_id / created_at / updated_at / trigger / predecessor_task_id / tags；
> tapd.ticket_id；workflow.phase / workflow.agent / workflow.flow.flow_id / workflow.blocker_count /
> workflow.verdict / workflow.summary）。`reports/tasks/<task_id>/` 目录仍保留作为 blockers.md 等执行期产物的容器。

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| `task/store/<story_id>/task.json` | 业务需求任务状态聚合 | TaskJsonStore（被 flow-engine skill / tapd skill / 各 agent 调用） | session-start / task.py resume / 各 agent |
| `task/store/<story_id>/contract.md` | 业务契约 | doc-librarian | 所有 agent |
| `task/store/<story_id>/tapd-comment.md` | TAPD 工单评论汇总（按日期分组，特殊标记加粗） | tapd/scripts/comments_cache.py / tapd fetch | human review / doc-librarian |
| `task/store/<story_id>/spec.md` | 实现规格（**含 AC-Endpoint 映射，java-testing skill 依赖**） | planner | generator / evaluator |
| ~~`task/store/<story_id>/cases/CASE-*.md`~~ | **DEPRECATED**：不再拆分 case，整个 story 作为一个实现单元 | — | — |
| ~~`task/store/<story_id>/cases/<case_id>.tests.yaml`~~ | **DEPRECATED**：集成测试由 java-testing skill 基于 spec.md 直接生成 JUnit | — | — |
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
| `reports/tasks/<task_id>/blockers.md` | blocker 记录（Bash exit≠0 自动归档；task 元数据本身已并入 task.json，不再独立 meta.json） | blocker-tracker hook | workflow-reviewer / sprint-review |
| `reports/workflow/blockers-summary.md` | sprint blocker 汇总 | workflow-reviewer | sprint-review |
| `reports/sprints/<date>/review-*.md` | sprint 复盘报告 | sprint-review | team |
| `reports/fitness/fitness-run.json` | fitness 运行汇总 | fitness-run skill | workflow-review / 人工 |
| `reports/fitness/<rule>.log` | 单条 fitness rule 日志 | fitness-run skill | workflow-review / 人工 |
| `reports/fitness/fitness-backlog.md` | fitness 候选规则积压 | post-tool-linter-feedback hook | fitness-run |
| `reports/fitness-failures.log` | linter-feedback 失败日志 | post-tool-linter-feedback hook | workflow-review / 人工 |
| `reports/handoffs/<ts>.md` | session handoff 工件 | context-reset skill | (下一 session 读取) |
| `reports/handoffs.jsonl` | handoff 指标 | context-reset skill | workflow-review / 人工 |
| `reports/metrics/eval-verdicts.jsonl` | evaluator verdict 历史（二元 PASS/FAIL/ERROR；含 `phases.code_review` + `phases.integration_test` 双阶段细节，顶层 `verdict` / `failures` 保留兼容） | evaluator agent | workflow-reviewer |
| `reports/integration-tests/<story_id>/verdict.json` | 集成测试 verdict（**与技术栈无关的统一 schema**，含 totals / ac_coverage / failures / meta.test_framework） | evaluator（自主选择测试方式） | evaluator agent |
| `reports/integration-tests/<story_id>/<TestFileName>` | 生成的集成测试源码（与技术栈相关：JUnit .java / pytest .py / Jest .js / .sh 等，进 git） | evaluator | CI / 后续回归测试 |
| `reports/integration-tests/<story_id>/<runner>.log` | 测试运行日志（mvn.log / pytest.log / jest.log 等） | evaluator | 排错 |
| `reports/members/<date>/activity.md` | 成员活动报告 | member-activity skill | team |

---

## state/ — 机器状态

| 路径 | 作用 | 产出方 | 消费方 |
|------|------|--------|--------|
| ~~`state/workflow-state.json`~~ | DEPRECATED：状态已全部迁入 `task/store/<id>/task.json.workflow`，全局 fallback 已下线，由 gc 后续清理 | — | — |
| ~~`state/events.jsonl`~~ | DEPRECATED：事件已迁入 `task.json.events[]`（flow-engine skill 维护），旧文件保留兜底，由 gc 后续清理 | — | — |
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

## Python 侧路径常量

所有路径**不再集中在 paths.py**。每个 Python 脚本在顶部自行计算 `PROJECT_DIR`,再拼接子路径:

```python
import os
from pathlib import Path

# parents[N]: hooks=2, skill scripts=4
PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[N])
))
# 用到哪些常量就在此局部定义
STORE_DIR = PROJECT_DIR / ".chatlabs" / "task" / "store"
BUG_FIX_DIR = PROJECT_DIR / ".chatlabs" / "task" / "bug-fix"
REPORTS_DIR = PROJECT_DIR / ".chatlabs" / "reports"

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
| `KNOWLEDGE_DIR` | `.chatlabs/knowledge/` |
| `FITNESS_DIR` | `.chatlabs/reports/fitness/` |
| `HANDOFFS_DIR` | `.chatlabs/reports/handoffs/` |
| `EVAL_VERDICTS` | `.chatlabs/reports/metrics/eval-verdicts.jsonl` |
