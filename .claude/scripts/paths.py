"""Centralized path constants for Flow internals.

Single source of truth for all Python-side paths used by hooks and scripts.
Markdown documents (agents/commands/skills) intentionally use plain string
paths for readability — they are natural-language instructions for AI/humans,
not executed code.

Layout:
  .claude/      → Flow 代码与配置（agents、commands、skills、hooks、templates）
  .chatlabs/    → 运行时产物 + 项目配置（task/store、task/bug-fix、worktrees、reports、state、project-config.json）
  docs/         → 人类读的规范文档

任务层（task）目录：
  .chatlabs/task/store/<story_id>/     业务需求型任务（原 stories/）
  .chatlabs/task/bug-fix/<bug_id>/     缺陷修复型任务
  .chatlabs/worktrees/<branch_slug>/   git worktree 多分支隔离工作树

每个任务目录下的 task.json 是 SSOT：聚合 workflow / git / tapd / meta 4 个 section。
旧的 stories/、tapd/tickets/、reports/tasks/<task_id>/meta.json 在迁移完成后退役。

Usage:
    from paths import TASK_REPORTS, STORE_DIR, BUG_FIX_DIR
    story_dir = STORE_DIR / story_id
"""
from pathlib import Path
import os

PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    str(Path(__file__).resolve().parents[2])
))

# ── Functional root (.claude/) ────────────────────────────────────
CLAUDE_DIR = PROJECT_DIR / ".claude"
SCRIPTS_DIR = CLAUDE_DIR / "scripts"

# Templates & schemas (constraints / starter files — static, committed)
TEMPLATES_DIR = CLAUDE_DIR / "templates"
SCHEMAS_DIR = TEMPLATES_DIR / "schemas"
TAPD_SCHEMAS_DIR = SCHEMAS_DIR / "tapd"
TAPD_TICKET_SCHEMA = TAPD_SCHEMAS_DIR / "ticket.schema.json"
TAPD_CONFIG_SCHEMA = TAPD_SCHEMAS_DIR / "tapd-config.schema.json"
TASK_META_SCHEMA = SCHEMAS_DIR / "task-meta.json"
STORY_TEMPLATE_DIR = TEMPLATES_DIR / "story"
TASK_REPORT_TEMPLATE = TEMPLATES_DIR / "task-report"

# ── Runtime artifacts root (.chatlabs/) ───────────────────────────
CHATLABS_DIR = PROJECT_DIR / ".chatlabs"

# TAPD cache (ticket JSON snapshots — legacy path, content merging into task.json)
TAPD_DIR = CHATLABS_DIR / "tapd"
TAPD_TICKETS_DIR = TAPD_DIR / "tickets"
TAPD_INDEX = TAPD_TICKETS_DIR / "_index.jsonl"

# ── Task layer (新 SSOT) ──────────────────────────────────────────
# task.json 在每个任务目录下，整合 workflow / git / tapd / meta 4 section。
TASK_DIR = CHATLABS_DIR / "task"
STORE_DIR = TASK_DIR / "store"           # 业务需求型任务
BUG_FIX_DIR = TASK_DIR / "bug-fix"       # 缺陷修复型任务
TASK_LAYER_INDEX = TASK_DIR / "_index.jsonl"

# Worktree 隔离目录（多 bug 并行）
WORKTREES_DIR = CHATLABS_DIR / "worktrees"

# Backward-compat aliases (deprecated — 历史 stories/ 已迁移完毕，保留以兼容遗留引用)
STORIES_DIR = STORE_DIR
TASKS_DIR = STORE_DIR

# Reports (task execution outputs, workflow reviews, gc logs)
REPORTS_DIR = CHATLABS_DIR / "reports"
TASK_REPORTS = REPORTS_DIR / "tasks"
MEMBER_REPORTS = REPORTS_DIR / "members"
MEMBER_INDEX = MEMBER_REPORTS / "_index.jsonl"
TASK_INDEX = TASK_REPORTS / "_index.jsonl"
WORKFLOW_DIR = REPORTS_DIR / "workflow"
GC_REPORTS = REPORTS_DIR / "gc"

# Fitness 产物
FITNESS_DIR = REPORTS_DIR / "fitness"
FAILURES_LOG = REPORTS_DIR / "fitness-failures.log"
BACKLOG_FILE = FITNESS_DIR / "fitness-backlog.md"

# Handoffs 产物
HANDOFFS_DIR = REPORTS_DIR / "handoffs"
HANDOFF_METRICS = REPORTS_DIR / "handoffs.jsonl"

# Evaluator verdicts
METRICS_DIR = REPORTS_DIR / "metrics"
EVAL_VERDICTS = METRICS_DIR / "eval-verdicts.jsonl"

# Integration-test 产物（由 integration-test skill 写入，evaluator agent 消费）
INTEGRATION_TEST_REPORTS = REPORTS_DIR / "integration-tests"

# Knowledge（项目级规范索引，由 /init-project 生成）
KNOWLEDGE_DIR = CHATLABS_DIR / "knowledge"
KNOWLEDGE_README = KNOWLEDGE_DIR / "README.md"

# 项目配置文件（由 /init-project 生成空骨架，/tapd init 填充 tapd 段）
PROJECT_CONFIG = CHATLABS_DIR / "project-config.json"

# State files (session-local, transient)
STATE_DIR = CHATLABS_DIR / "state"
CURRENT_TASK = STATE_DIR / "current_task"
GC_LAST_RUN = STATE_DIR / "gc_last_run"
# DEPRECATED：events 已迁入 task.json.events（由 flow-engine/events.py 维护）。
# 保留常量供 gc / 迁移脚本清理旧 jsonl 文件；新代码不应再写此路径。
EVENTS_LOG = STATE_DIR / "events.jsonl"

# Flow-logs（进化机制产物）
FLOW_LOGS_DIR = CHATLABS_DIR / "flow-logs"
INSIGHTS_DIR = FLOW_LOGS_DIR / "insights"
INSIGHTS_INDEX = INSIGHTS_DIR / "_index.jsonl"
EVOLUTION_PROPOSALS_DIR = FLOW_LOGS_DIR / "evolution-proposals"
PROPOSALS_PENDING_PATH = EVOLUTION_PROPOSALS_DIR / "_pending.jsonl"
PROPOSALS_APPLIED_PATH = EVOLUTION_PROPOSALS_DIR / "_applied.jsonl"

# ── External project paths ────────────────────────────────────────
DOCS_DIR = PROJECT_DIR / "docs"
