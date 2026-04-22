# ChatLabs Dev-Flow — AI 驱动开发工作流

> 一套 Agent Flow 配置（`.claude/`）+ 规范文档（`docs/`）的组合，定义从产品需求到代码交付的全流程。

---

## 快速开始

在任意 Claude Code session 中，进入本项目目录后：

```
/start-dev-flow            # 启动主流程（会引导你选择入口）
```

或直接进入具体环节：

- **首次接入项目** → `/tapd-init`
- **新开工单** → `/tapd-story-start <ticket-id>` 或 `/story-start <story-id>`
- **恢复任务** → `/task-resume`
- **迭代复盘** → `/sprint-review`

---

## 整体流程与执行机制

### 端到端流程图

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
│  ──────────────────────  │  │   恢复任务上下文  │
│  · 需求 → contract.md   │  └──────────────────┘
│  · 接口 → openapi.yaml   │
│  · 评审 → TAPD 评论同步   │
└──────────┬───────────────┘
           │ (contract frozen)
           ▼
┌──────────────────────────┐
│         planner           │
│  ──────────────────────  │
│  · contract → spec.md     │
│  · 拆分 case（原子任务）   │
│  · 与 Evaluator 谈判       │
│  · 发布 planner:all-cases │
│    -ready 事件            │
└──────────┬───────────────┘
           │ (事件驱动)
           ▼
┌──────────────────────────┐
│    tapd-subtask-emit      │
│  ──────────────────────  │
│  · 自动派发 TAPD 子工单    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│        generator          │
│  ──────────────────────  │
│  · 逐 case 实现代码        │
│  · 维护 state.json verdicts│
│  · 提交 Evaluator 验收     │
│  · CASE 间连续执行，无询问  │
└──────────┬───────────────┘
           │ (全部 case PASS)
           ▼
┌──────────────────────────┐
│        evaluator          │
│  ──────────────────────  │
│  · 独立跑契约测试          │
│  · 产出 verdict (PASS/FAIL)│
└──────────┬───────────────┘
           │ (所有 verdicts PASS)
           ▼
      ┌─────────────────┐
      │   收尾阶段       │
      │ · TAPD 状态推进  │
      │ · /sprint-review │
      │ · handoff 工件   │
      └─────────────────┘
```

### Agent 协作机制

**单向数据流 + 职责隔离**：

| Agent | 输入 | 输出 | 约束 |
|-------|------|------|------|
| `doc-librarian` | PM 需求（Figma/PDF/口述） | `contract.md` + `openapi.yaml` | 不写 spec，不写代码 |
| `planner` | `contract.md` + `openapi.yaml` | `spec.md` + `cases/*.md` + 发布 `planner:all-cases-ready` 事件 | 不改契约业务字段，不写代码 |
| `generator` | `spec.md` + `cases/*.md` | 实现代码 + 自测 + 更新 `workflow-state.json` verdicts | 不自评通过，必须交 Evaluator；CASE 间连续执行 |
| `evaluator` | 代码 + `openapi.yaml` | verdict（PASS/FAIL） | 独立测试，不读 Generator 自述 |

**状态单向推进**（TAPD）：
```
draft → review → frozen → in_dev → testing → completed → deployed
```

**契约冻结后变更**：
```
业务变更/设计问题 → doc-librarian 受理
→ bump version（semver）→ changelog 更新
→ 通知下游重入（planner/generator）
```

### 执行质量门禁

| 阶段 | Gate | 通过标准 |
|------|------|---------|
| doc-librarian | `status: frozen` | 所有 AC 编号完整，TBD 已澄清，openapi.yaml 通过 lint |
| planner | `architect-confirm` | 模块划分清晰，case 无循环依赖，AC→case 映射完整 |
| generator | `evaluator verdict = PASS` | 所有 case 契约测试通过，TAPD 状态已推进 |
| evaluator | `sprint-contract` 谈判 | 与 Generator 就测试范围达成共识 |

### 适应度函数（Fitness Run）

每个阶段编码中持续运行，确保架构合规：
- `layer-boundary.sh` — 分层边界检查
- `openapi-lint.sh` — OpenAPI 合法性与业务字段一致性
- `case-dag.sh` — case 依赖无环校验
- `contract-drift-check.py` — 实现与契约 drift 检测

---

## 顶层目录导航

| 路径 | 职责 | 谁读 / 谁写 |
|------|------|-----------|
| `.claude/agents/` | 5 个 agent 定义（doc-librarian / planner / generator / evaluator / workflow-reviewer） | Claude Code 自动加载 |
| `.claude/MANIFEST.md` | Flow 版本治理清单（version / breaking_changes / 升级路径） | Flow 维护者 + `/flow-upgrade` |
| `.claude/commands/` | 14 个 slash command | 用户手动调用 |
| `.claude/skills/` | 8 个可复用 skill（tapd-* / fitness-run / contract-test / context-reset / gc） | Claude 根据触发关键词自动加载 |
| `.claude/templates/` | 项目模板目录（`spec-skeleton/` / `schemas/`） | `/init-project` 写入 + `/flow-upgrade` 同步 |
| `.claude/hooks/` | 6 个 hook（session-start / ctx-guard / blocker-tracker / file-tracker / post-tool-linter-feedback / danger-block） | `.claude/settings.json` 驱动 |
| `.claude/scripts/` | Flow 内部工具（gc.py / gc-run.sh / contract-drift-check.py / paths.py） | 被 skill / agent / hook 调用 |
| `.claude/tasks/stories/` | 活跃 story 产物（contract.md / openapi.yaml / spec.md / cases/）| agent 写入 |
| `.claude/reports/tasks/` | 任务执行报告（summary / meta / blockers / diff-log / file-reads）| hook + agent 写入 |
| `.claude/reports/workflow/` | 周期工作流分析（blockers-summary.md）| workflow-reviewer 写入 |
| `.claude/reports/gc/` | GC 日志 | gc skill 写入 |
| `.claude/tapd/` | TAPD 工单缓存 + schema | tapd-pull skill 维护 |
| `.claude/settings.json` | Hook 链配置（immutable） | — |
| `.claude/settings.local.json` | 本地覆盖配置 | 用户手改 |
| `docs/` | 人类读的规范文档（见下方） | 人类 + agent 参考 |
| `.mcp.json` | MCP 服务声明（chopard-tapd / jenkins / context7 等） | Claude Code 加载 |

---

## 规范文档（`docs/`）

| 文件 | 用途 |
|------|------|
| [`docs/team-workflow.md`](docs/team-workflow.md) | **团队工作流总纲**（角色、阶段、验收流程）—— 新人从这读起 |
| [`docs/task-directory-convention.md`](docs/task-directory-convention.md) | `.claude/tasks/stories/` 目录结构与命名约定 |
| [`docs/contract-template.md`](docs/contract-template.md) | 产品契约文档模板（doc-librarian 产出的格式） |
| [`docs/tech-debt-backlog.md`](docs/tech-debt-backlog.md) | 技术债 backlog |

---

## Agents（`.claude/agents/`）

| Agent | 职责 | 触发 |
|-------|------|------|
| `doc-librarian` | 将产品需求整理为契约文档（contract.md + openapi.yaml） | 需求阶段 |
| `planner` | 契约冻结后拆分 case + spec | `/story-start` 后续 |
| `generator` | 按 case 编码 + 测试 | planner 派发后 |
| `evaluator` | 跑契约测试产出 verdict | Generator 交付后 |
| `workflow-reviewer` | 周期性扫描 blocker / 产出趋势报告 | `/workflow-review` |

---

## 主要 Slash Commands（`.claude/commands/`）

| 命令 | 用途 |
|------|------|
| `/start-dev-flow` | 启动主流程（引导式） |
| `/story-start <id>` | 不走 TAPD，直接启动本地 story |
| `/task-new <story-id>` | 分配 task_id + 建目录 |
| `/task-resume` | 恢复最后一个 active task |
| `/tapd-init` | 首次引导式配置 TAPD 集成 |
| `/tapd-story-start <ticket>` | TAPD 工单开工 |
| `/tapd-ticket-sync` | 批量拉取 TAPD 工单到本地 |
| `/tapd-consensus-push` / `/tapd-consensus-fetch` | 契约评审双向同步 |
| `/tapd-subtask-emit` / `/tapd-subtask-close` / `/tapd-subtask-reopen` | 子任务派发与状态机 |
| `/sprint-review` | 即时复盘 |
| `/workflow-review` | 周期性工作流分析 |
| `/flow-upgrade` | 检测 + 应用 Flow Repo 增量更新（需先运行 `/init-project`） |

---

## Skills（`.claude/skills/`）

| Skill | 用途 |
|-------|------|
| `tapd-pull` / `tapd-init` / `tapd-consensus` / `tapd-subtask` | TAPD 集成的四个子能力 |
| `contract-test` | 对已实现 HTTP API 跑 OpenAPI 契约测试 |
| `fitness-run` | 架构适应度函数检查 |
| `context-reset` | ctx-guard 阻断时 handoff 到新 session |
| `gc` | 工作流熵管理（stale cache / orphan index / 过期 report 清理） |

---

## 扩展指南

- 新增 agent → 在 `.claude/agents/` 放一个 md
- 新增 slash → 在 `.claude/commands/` 放一个 md
- 新增 skill → 在 `.claude/skills/<name>/SKILL.md` 定义
- 新增 hook → 改 `.claude/settings.json`（用 `/update-config` skill）
- 新增 Python 路径常量 → 加到 `.claude/scripts/paths.py`

Python hook / script 必须：
```python
sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "scripts"))
from paths import TASK_REPORTS, STORIES_DIR  # 按需导入
```

Markdown 文档（agents / commands / skills）中**不强行常量化路径**——md 是给 AI/人类读的自然语言指令，保持可读性。
