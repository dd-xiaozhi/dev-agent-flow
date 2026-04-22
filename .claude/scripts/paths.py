"""Centralized path constants for Flow internals.

Single source of truth for all Python-side paths used by hooks and scripts.
Markdown documents (agents/commands/skills) intentionally use plain string
paths for readability — they are natural-language instructions for AI/humans,
not executed code.

Layout:
  .claude/      → Flow 代码与配置（agents、commands、skills、hooks、templates）
  .chatlabs/    → 纯运行时产物（tapd 缓存、story 文件、reports、state）
  docs/         → 人类读的规范文档

Usage:
    from paths import TASK_REPORTS, STORIES_DIR
    report_dir = TASK_REPORTS / task_id
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

# TAPD cache (ticket JSON snapshots)
TAPD_DIR = CHATLABS_DIR / "tapd"
TAPD_TICKETS_DIR = TAPD_DIR / "tickets"
TAPD_INDEX = TAPD_TICKETS_DIR / "_index.jsonl"

# Stories (active contract/spec/cases artifacts)
STORIES_DIR = CHATLABS_DIR / "stories"
# Backward-compat alias; some legacy code paths still reference TASKS_DIR
TASKS_DIR = STORIES_DIR

# Reports (task execution outputs, workflow reviews, gc logs)
REPORTS_DIR = CHATLABS_DIR / "reports"
TASK_REPORTS = REPORTS_DIR / "tasks"
MEMBER_REPORTS = REPORTS_DIR / "members"
MEMBER_INDEX = MEMBER_REPORTS / "_index.jsonl"
TASK_INDEX = TASK_REPORTS / "_index.jsonl"
WORKFLOW_DIR = REPORTS_DIR / "workflow"
GC_REPORTS = REPORTS_DIR / "gc"

# State files (session-local, transient)
STATE_DIR = CHATLABS_DIR / "state"
CURRENT_TASK = STATE_DIR / "current_task"
GC_LAST_RUN = STATE_DIR / "gc_last_run"
CONTRACT_HASH = STATE_DIR / "contract_hash"
WORKFLOW_STATE = STATE_DIR / "workflow-state.json"
EVENTS_LOG = STATE_DIR / "events.jsonl"

# ── External project paths ────────────────────────────────────────
DOCS_DIR = PROJECT_DIR / "docs"
