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
用户输入（/story-start 或 /tapd-story-start）
    ↓
Flow Orchestrator（统一调度器）读取 flow/config.yaml
    ↓
doc-librarian → contract:frozen 事件
    ↓
Flow Orchestrator 调度适配器（push-consensus）
    ↓
等待 consensus:approved/rejected 事件
    ↓
planner → planner:cases-ready 事件
    ↓
Flow Orchestrator 调度适配器（emit-subtask）
    ↓
更新 phase = 'generator' → 路由到 generator agent
    ↓
Generator 自动执行所有 CASE（基于 state.json 状态追踪）
    ↓
全部 PASS → generator:all-done 事件
    ↓
Flow Orchestrator 调度适配器（sync-subtask）
```

**事件总线**（`.chatlabs/state/events.jsonl`）：

| 事件 | 发布方 | 消费方 |
|------|--------|--------|
| `contract:frozen` | doc-librarian | Flow Orchestrator |
| `consensus:approved` | 适配器 | Flow Orchestrator |
| `planner:cases-ready` | planner | Flow Orchestrator |
| `generator:started` | generator | - |
| `generator:all-done` | generator | Flow Orchestrator |

### 适配器架构（Pluggable Adapters）

适配器负责与外部服务交互（TAPD/GitHub/本地），Flow Orchestrator 统一调度，组件无需感知具体实现。

```
.claude/
├── flow/                      # Flow Orchestrator
│   ├── orchestrator.py       # 核心调度器
│   ├── config.yaml           # 流程配置
│   └── event_bus.py          # 事件总线
├── adapters/                 # 适配器层
│   ├── local/               # 本地适配器（默认）
│   └── tapd/                # TAPD 适配器
└── components/               # 组件元数据
    ├── doc-librarian/
    ├── planner/
    └── generator/
```

**切换适配器**：修改 `.claude/flow/config.yaml` 中的 `active_adapters` 即可，无需修改组件代码。

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
| **session-end.py** | session 结束时 | 保存 flow-logs 状态，触发阻断点自审 |
| **ctx-guard.py** | 每次提交指令前 | Context 占用 >40% 时阻断，提示 /context-reset |
| **blocker-tracker.py** | Bash 执行失败后 | 自动分析错误类型，追加到 blockers.md |
| **file-tracker.py** | 每次 Read/Edit/Write/Bash | 追踪文件操作，去重写入 file-reads.md / diff-log.md |
| **post-tool-linter-feedback.py** | 每次 Edit/Write 后 | 推断并运行 fitness rule，失败追加候选规则到 backlog |
| **pre-commit**（git） | git commit 前 | 契约漂移检测，漂移状态阻断 commit |

---

## AI 自我进化机制（Self-Evolution）

### AI 反馈闭环（Self-Reflect + Evolution）

```
触发点（story-start / tapd-reopen / workflow-review / manual / blocker）
    │
    ├── 自审（self-reflect）→ 四维度评分（理解/实现/遵守/流程）
    │                           → .chatlabs/flow-logs/FL-*.json
    │
workflow-review（定期）
    │
    ├── 洞察提炼（insight-extract）→ 跨事件模式识别
    │                                   → insights/_index.jsonl
    ├── 进化提案（evolution-propose）→ spec 变更提案
    │                                   → evolution-proposals/_pending.jsonl
    └── /evolution-apply --all（用户确认）→ spec/ 规范更新
```

**触发点说明**：

| 触发点 | 时机 | 重点 |
|--------|------|------|
| `story-start` | doc-librarian 阶段完成 | 理解质量 |
| `tapd-reopen` | QA 打回时 | 逃逸根因分析 |
| `workflow-review` | 周期审查 | 全维度 + 跨事件模式 |
| `manual` | 用户手动 | 按需 |
| `blocker` | 阻断发生时 | 根因 + 可预防性 |

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
| `self-reflect` | AI 自审（关键触发点四维度评分） |
| `insight-extract` | 洞察提炼（跨事件模式识别） |
| `evolution-propose` | 进化提案生成（spec 变更提议） |
| `fitness-run` | 架构适应度函数检查 |
| `contract-test` | OpenAPI 契约测试 |
| `context-reset` | Context 重置 + 结构化交接 |
| `gc` | 工作流熵管理（每日自动） |
| `tapd-*` | TAPD 工单同步、共识评审、子任务派发（适配器模式） |

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
| `/evolution-apply` | 应用进化提案（用户确认后更新 spec） |
| `/flow-upgrade` | Flow 版本升级 |
| `/member-activity` | 成员活跃度报告 |

---

## 规范文档（`docs/`）

| 文件 | 用途 |
|------|------|
| `team-workflow.md` | 团队工作流总纲（角色、阶段、验收流程） |
| `task-directory-convention.md` | 目录结构与命名约定 |
| `contract-template.md` | 产品契约文档模板 |

## 知识库（`.chatlabs/knowledge/`）

三层结构：项目层（做什么）→ 技术层（怎么做）→ 资产层（沉淀什么）

| 层级 | 目录 | 用途 |
|------|------|------|
| 项目层 | `knowledge/project/` | 项目概述、核心功能流程图、系统架构 |
| 技术层 | `knowledge/tech/` | 编码规范、API 约定、架构适应度函数 |
| 资产层 | `knowledge/asset/` | 契约原则、归档 PRD、技术债台账 |

详情见 [knowledge/README.md](.chatlabs/knowledge/README.md)。

---

## 目录结构

| 路径 | 职责 |
|------|------|
| `.claude/agents/` | 5 个 agent 定义 |
| `.claude/commands/` | 25 个 slash command（按功能域划分：tapd/flow/worktree/task/） |
| `.claude/skills/` | 12 个可复用 skill |
| `.claude/hooks/` | 6 个自动执行 hook |
| `.claude/scripts/` | Flow 内部工具 |
| `.claude/templates/` | 项目模板 |
| `.chatlabs/state/` | 状态文件（workflow-state.json、events.jsonl） |
| `.chatlabs/stories/` | 活跃 story 产物 |
| `.chatlabs/knowledge/` | 知识库（三层结构：project/tech/asset） |
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
