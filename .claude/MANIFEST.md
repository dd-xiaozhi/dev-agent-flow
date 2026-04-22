# Flow Manifest

> 所有使用本 Flow Repo 的项目，通过 `/flow-upgrade` 对齐本文件声明的版本。
> **Flow Repo 维护者**：每次 push 前更新本文件。

## 当前版本

`flow_version: "2.6"`

## 版本历史

---

### v2.6 — Flow 健康检查机制

**date**: 2026-04-22
**breaking**: false
**summary**: 新增 `/flow-check` 命令，实现 Flow 自我审查机制。在任意时刻评估 Flow 配置、命令/Skill 可用性、运行时状态、架构合规性、会话上下文的健康状况，产出结构化报告和优先级建议。

**新增文件**：
- `.claude/commands/flow/flow-check.md` — Flow 健康检查命令
- `.claude/scripts/flow-check.py` — 核心诊断脚本

**检查维度**：

| 维度 | 检查内容 | 数据来源 |
|------|---------|---------|
| 配置健康度 | settings.json、tapd-config.json、workflow-state.json | paths.py |
| 命令/Skill 可用性 | commands/ 和 skills/ 目录完整性 | 扫描文件系统 |
| 运行时状态 | phase、verdict、blocker、未处理事件 | workflow-state.py |
| 架构合规性 | fitness 规则检查结果 | fitness-run.json |
| 会话上下文 | phase 偏差、flow-log 评分趋势 | workflow-state.py、flow-logs/ |

**触发方式**：
- 用户手动：`/flow-check`
- 指定范围：`/flow-check --check-type runtime`

**迁移步骤**（针对已有项目）：
1. 无需迁移，新功能按需使用

---

### v2.5 — Git Worktree 并行执行

**date**: 2026-04-22
**breaking**: false
**summary**: 新增 Git Worktree 并行执行支持。为不同需求创建独立 worktree，实现多任务并行开发。Worktree 共享 `.claude/` 配置，拥有独立的 `.chatlabs/` 运行时目录，状态完全隔离。完成合并回 master 后自动清理。

**新增文件**：
- `.claude/scripts/worktree-manager.py` — Worktree 状态管理核心模块
- `.claude/commands/worktree/worktree.md` — Worktree 管理命令入口
- `.claude/commands/worktree/worktree-start.md` — Worktree 内 Flow 启动命令
- `.claude/scripts/worktree-merge.sh` — 自动合并脚本

**修改文件**：
- `.claude/hooks/session-start.py` — 新增 worktree 模式检测，加载独立运行时状态
- `.claude/MANIFEST.md` — 记录 v2.5 版本

**Worktree 架构**：
```
main-repo/
├── .claude/                      # 共享配置
├── .chatlabs/                    # 主仓库状态
│   └── worktree-manager.json      # worktree 索引
└── .worktrees/                   # worktree 根目录
    ├── story-001/                # STORY-001 worktree
    │   ├── .chatlabs/            # 独立运行时状态
    │   └── [项目文件]
    └── story-002/
```

**迁移步骤**（针对已有项目）：
1. 无需迁移，新功能按需使用
2. 原有的主仓库流程（`/story-start`、`/tapd-story-start`）行为不变
3. Worktree 模式完全可选，不影响现有工作流

---

### v2.4 — AI 反馈闭环（自审 + 进化）

**date**: 2026-04-22
**breaking**: false
**summary**: 新增 AI 自审 + 洞察提炼 + 进化提案机制。AI 在关键触发点对自身行为进行四维度评分（理解/实现/遵守/流程），结构化日志存储，workflow-review 时自动提炼跨事件洞察并生成 spec 变更提案，经用户确认后更新规范，实现 AI 行为质量的持续进化。

**新增文件**：
- `.claude/skills/self-reflect/SKILL.md` — AI 自审核心技能
- `.claude/skills/insight-extract/SKILL.md` — 洞察提炼技能
- `.claude/skills/evolution-propose/SKILL.md` — 进化提案生成技能
- `.claude/commands/evolution-apply.md` — 提案应用命令（独立命令）

**修改文件**：
- `.claude/commands/workflow-review.md` — 集成自审三步链（自审→洞察→提案）
- `.claude/commands/story-start.md` — 第七步增加 story-start 触发自审
- `.claude/commands/tapd/subtask-reopen.md` — 第七步增加 tapd-reopen 触发自审
- `.claude/skills/gc/SKILL.md` — 增加 flow-logs 清理规则
- `docs/team-workflow.md` — 新增第四阶段 AI 反馈闭环文档

**迁移步骤**（针对已有项目）：
1. 无需迁移，flow-logs 目录按需自动创建
2. 原 workflow-review 行为不变，新增自审三步在 Blocker 审查后自动执行

---

### v2.3 — 长程任务自动执行 + 消除打断

**date**: 2026-04-22
**breaking**: false
**summary**: Planner 完成后自动触发 TAPD 子工单派发；Generator 基于 state.json 自动追踪 CASE 状态并连续执行；移除 command 末尾硬编码的"下一步建议"。

**修改文件**：
- `planner.md` — 增加 `planner:all-cases-ready` 事件发布
- `session-start.py` — 增加对 `planner:all-cases-ready` 事件的处理，自动派发子工单 + 路由到 generator
- `generator.md` — 强化 CASE 连续执行规则，强制维护 workflow-state.json verdicts
- `workflow-state.py` — 增加 `get_pending_cases()`、`complete_case()`、`all_cases_complete()` 方法

**移除硬编码提示**：
- `tapd-subtask-emit.md`
- `tapd-consensus-push.md`
- `tapd-ticket-sync.md`
- `tapd-subtask-reopen.md`
- `workflow-review.md`

**迁移步骤**（针对已有项目）：
1. `/flow-upgrade --apply` 自动同步修改
2. 新的 planner 完成流程将自动触发后续步骤

---

### v2.2 — 删除 orchestrator Agent（简化 Harness）

**date**: 2026-04-22
**breaking**: false
**summary**: 删除 orchestrator Agent，其功能已被 session-start.py + workflow-state.json 覆盖。事件驱动架构保持，TAPD 同步由 session-start hook 处理。

**删除文件**：
- `.claude/agents/orchestrator.md` — 功能已被 session-start.py 取代

**修改文件**：
- `generator.md` — 标注 orchestrator 引用（注释说明事件处理方式不变）
- `tapd-sync/SKILL.md` — 标注 orchestrator 引用（session-start hook 已处理）

**迁移步骤**（针对已有项目）：
1. 无需迁移，orchestrator 是可选组件
2. 原 `events.jsonl` 事件处理现在由 session-start.py 处理

---

### v2.1 — 共识文档生成与代码实现解耦（事件驱动架构）

**date**: 2026-04-22
**breaking**: false
**summary**: TAPD 同步从硬编码改为事件驱动；新增单一状态源 workflow-state.json；Generator 纯化，TAPD 调用改为发布事件；新增 orchestrator agent；契约版本锁定增强。

**新增文件**：
- `.claude/scripts/workflow-state.py` — 状态读写工具
- `.claude/skills/tapd-sync/SKILL.md` — 事件驱动的 TAPD 同步适配器
- `.claude/agents/orchestrator.md` — 事件驱动的编排器

**Story ID 规则**：
- TAPD 工单：直接使用 `ticket_id` 作为 story_id（如 `1140062001234567`），保持与源系统一致
- 本地 Story：使用 `STORY-<三位序号>` 格式（如 `STORY-001`），自增分配

**修改文件**：
- `doc-librarian.md` — 末尾改为发布 contract:frozen 事件，不再硬编码 /tapd-consensus-push
- `generator.md` — 删除 TAPD 直接调用，改为发布 generator:started 和 generator:all-done 事件
- `session-start.py` — 支持 workflow-state.json，向后兼容 meta.json
- `contract-drift-check.py` — 添加 spec.md contract_ref.hash 校验（Phase 4）
- `planner.md` — spec.md frontmatter 增加 contract_hash 字段

**新增状态文件**：
- `.chatlabs/state/workflow-state.json` — 单一状态源（替代 ticket.json + meta.json）
- `.chatlabs/state/events.jsonl` — 事件总线（append-only）

**迁移步骤**（针对已有项目）：
1. 运行 `/init-project` 生成新的 workflow-state.json 模板
2. 旧项目已有的 ticket.json 和 meta.json 继续有效（向后兼容）
3. 新 story 自动使用 workflow-state.json

---

## 如何发布新版本

### 小版本更新（breaking: false）

1. 在上方"版本历史"追加新条目：`### vX.Y`
2. 更新顶部的 `flow_version`（如 2.0 → 2.1）
3. push 后，项目运行 `/flow-upgrade --apply` 自动合并

### 大版本更新（breaking: true）

1. 在上方"版本历史"追加新条目：`### vX.0`
2. 更新顶部的 `flow_version`
3. **必须填写** `breaking_changes` 部分，包含：
   - 每个破坏性变更的说明
   - 对项目的具体影响
   - 明确的迁移步骤（可自动化执行的）
   - 回滚方法
4. push 后，项目运行 `/flow-upgrade`，自动进入 Phase M（迁移升级流程）

## 破坏性变更分级

| 级别 | 影响 | 处理方式 |
|------|------|---------|
| **A**：目录/文件重命名 | 引用断裂 | 自动 mv + 更新所有引用 |
| **B**：命令删除/拆分 | 旧命令不可用 | 删除 + 提示新命令 |
| **C**：数据格式变更 | 旧数据不兼容 | 脚本迁移或提示手动处理 |
| **D**：理念/原则变化 | 行为不同 | 文档说明 + agent 规则更新 |

---

## Flow 版本治理原则

1. **向后兼容优先**：尽量通过新增而非删除来演进
2. **破坏性变更必须文档化**：不在 MANIFEST.md 声明的变更视为小版本
3. **迁移步骤必须可执行**：不能让项目手动猜怎么迁移
4. **保护运行时状态**：`.chatlabs/` 永远不动，包括迁移时
