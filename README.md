# ChatLabs Dev-Flow — AI 驱动开发工作流

> 一套基于 Claude Code 的 AI Agent Flow 配置（`.claude/`）+ 规范文档（`docs/`），定义从产品需求到代码交付的全流程。
>
> 核心特性：**事件驱动编排** + **AI 自我进化** + **契约测试验收**

---

## 快速开始

```bash
/start-dev-flow            # 启动主流程（引导式）
/task-resume              # 恢复任务
/sprint-review            # 即时复盘
```

---

## 核心架构

### 事件驱动编排（Event-Driven Orchestration）

```
PM 评审通过（tapd:consensus-approved）
    ↓
planner 开始 → 完成 → 发布 planner:all-cases-ready 事件
    ↓
session-start hook 监听 → 自动触发 tapd-subtask-emit
    ↓
更新 phase = 'generator' → 路由到 generator agent
    ↓
Generator 自动执行所有 CASE（基于 state.json 状态追踪）
    ↓
全部 PASS → 收尾 + 发布 generator:all-done 事件
```

**事件总线**（`.chatlabs/state/events.jsonl`）：

| 事件 | 发布方 | 消费方 |
|------|--------|--------|
| `tapd:consensus-approved` | tapd-sync skill | session-start hook |
| `planner:all-cases-ready` | planner agent | session-start hook |
| `generator:started` | generator agent | - |
| `generator:all-done` | generator agent | session-start hook |
| `contract:frozen` | doc-librarian | tapd-sync skill |

### 单一状态源（workflow-state.json）

所有状态集中管理，无需分散读取 ticket.json / meta.json：

```json
{
  "task_id": "TASK-001",
  "story_id": "STORY-001",
  "phase": "generator",
  "verdicts": {"CASE-01": "PASS", "CASE-02": "WIP"},
  "integrations": { "tapd": { "enabled": true, "ticket_id": "..." }}
}
```

---

## 自动机制（Hooks）

Hooks 是在工具层自动执行的自动化脚本，由 `.claude/settings.json` 配置触发。

| Hook | 触发时机 | 功能 |
|------|----------|------|
| **session-start.py** | 每次新 session | 加载上下文、监听事件、触发 gc |
| **ctx-guard.py** | 每次提交指令前 | Context 占用 >40% 时阻断，提示 /context-reset |
| **blocker-tracker.py** | Bash 执行失败后 | 自动分析错误类型，追加到 blockers.md |
| **file-tracker.py** | 每次 Read/Edit/Write/Bash | 追踪文件操作，去重写入 file-reads.md / diff-log.md |
| **post-tool-linter-feedback.py** | 每次 Edit/Write 后 | 推断并运行 fitness rule，失败追加候选规则到 backlog |
| **pre-commit**（git） | git commit 前 | 契约漂移检测，漂移状态阻断 commit |

---

## AI 自我进化机制（Self-Evolution）

### Fitness Run（架构适应度函数）

每次代码修改后自动检查架构合规性：

| Rule | 目的 |
|------|------|
| `layer-boundary` | 目录依赖方向校验 |
| `openapi-lint` | OpenAPI spec 合法性 |
| `contract-diff` | 破坏性变更检测 |
| `handoff-lint` | 交接工件完整性 |

**触发方式**：
- 自动：`post-tool-linter-feedback.py` hook 在 Edit/Write 后运行
- 手动：`/fitness-run [rule-name]`
- 提交前：`pre-commit` git hook

### Blocker 分析与改进

```
Bash 失败 → blocker-tracker.py 自动记录类型
    ↓
周期性运行 /workflow-review → 分析 Blocker 趋势
    ↓
产出 blockers-summary.md → 识别 P0/P1 问题
    ↓
改进建议 → 更新 agent/command 规则
```

### Context 重置（防止退化）

```
Context 占用 > 40% → ctx-guard 阻断
    ↓
执行 /context-reset → 产出结构化 handoff 工件
    ↓
新 session 读取工件 + AGENTS.md → 无痕接力
```

---

## 端到端流程

```
用户意图（口述/工单ID/描述）
        │
        ▼
┌─────────────────────────────────────────────┐
│           /start-dev-flow（统一入口）           │
│     AI 识别意图 → 自动路由到对应阶段            │
└──────────────────────┬──────────────────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   【TAPD 工单】    【本地需求】    【恢复任务】
   /tapd-story-     /story-start   /task-resume
   start
         │             │             │
         ▼             ▼             ▼
┌──────────────────────────┐  ┌──────────────────┐
│      doc-librarian       │  │   读取 .current   │
│  · 需求 → contract.md   │  │   恢复任务上下文  │
│  · 接口 → openapi.yaml   │  └──────────────────┘
│  · 发布 contract:frozen  │
└──────────┬───────────────┘
           │
           ▼ 事件驱动
┌──────────────────────────┐
│         planner           │
│  · contract → spec.md     │
│  · 拆分 case + 发布事件   │
└──────────┬───────────────┘
           │
           ▼ 事件驱动
┌──────────────────────────┐
│      tapd-subtask-emit    │
│  · 自动派发 TAPD 子工单    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│        generator          │
│  · 逐 case 实现代码        │
│  · 维护 state.json        │
│  · 提交 Evaluator 验收     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│        evaluator          │
│  · 独立跑契约测试          │
│  · 产出 verdict          │
└──────────┬───────────────┘
           │
           ▼
      ┌─────────────────┐
      │   收尾阶段       │
      │ · TAPD 状态推进  │
      │ · /sprint-review │
      └─────────────────┘
```

---

## Agents（AI 角色）

| Agent | 输入 | 输出 | 约束 |
|-------|------|------|------|
| `doc-librarian` | PM 需求 | `contract.md` + `openapi.yaml` | 不写代码 |
| `planner` | 契约文档 | `spec.md` + `cases/*.md` + 事件 | 不改契约 |
| `generator` | 技术 spec | 代码 + 更新 `verdicts` | 必须交 Evaluator 验收 |
| `evaluator` | 代码 + 契约 | verdict（PASS/FAIL） | 独立测试 |
| `workflow-reviewer` | blockers.md | 趋势报告 + 改进建议 | 周期性分析 |

---

## Skills（可复用能力）

| Skill | 用途 |
|-------|------|
| `fitness-run` | 架构适应度函数检查 |
| `contract-test` | OpenAPI 契约测试 |
| `context-reset` | Context 重置 + 结构化交接 |
| `gc` | 工作流熵管理（每日自动） |
| `tapd-*` | TAPD 工单同步、共识评审、子任务派发 |

---

## 主要 Commands

| 命令 | 用途 |
|------|------|
| `/start-dev-flow` | 启动主流程 |
| `/story-start` | 本地 story 开工 |
| `/task-resume` | 恢复任务 |
| `/tapd-init` | 首次配置 TAPD |
| `/tapd-story-start` | TAPD 工单开工 |
| `/tapd-consensus-push/fetch` | 共识评审同步 |
| `/tapd-subtask-emit/close/reopen` | 子任务管理 |
| `/sprint-review` | 即时复盘 |
| `/workflow-review` | 周期工作流分析 |
| `/flow-upgrade` | Flow 版本升级 |

---

## 规范文档（`docs/`）

| 文件 | 用途 |
|------|------|
| `team-workflow.md` | 团队工作流总纲（角色、阶段、验收流程） |
| `task-directory-convention.md` | 目录结构与命名约定 |
| `contract-template.md` | 产品契约文档模板 |
| `tech-debt-backlog.md` | 技术债 backlog |

---

## 目录结构

| 路径 | 职责 |
|------|------|
| `.claude/agents/` | 5 个 agent 定义 |
| `.claude/commands/` | 14 个 slash command |
| `.claude/skills/` | 9 个可复用 skill |
| `.claude/hooks/` | 5 个自动执行 hook |
| `.claude/scripts/` | Flow 内部工具 |
| `.claude/templates/` | 项目模板 |
| `.chatlabs/state/` | 状态文件（workflow-state.json、events.jsonl） |
| `.chatlabs/stories/` | 活跃 story 产物 |
| `.chatlabs/reports/` | 任务执行报告 |

---

## 扩展指南

- 新增 agent → 在 `.claude/agents/` 放一个 md
- 新增 hook → 在 `.claude/hooks/` 实现 + 配置 `settings.json`
- 新增 fitness rule → 在 `fitness/` 目录放 `{rule}.sh`
- 新增 skill → 在 `.claude/skills/<name>/SKILL.md` 定义

**Python Hook 规范**：
```python
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import TASK_REPORTS, STORIES_DIR
```
