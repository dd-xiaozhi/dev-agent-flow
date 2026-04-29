# Flow Manifest

> 所有使用本 Flow Repo 的项目，通过 `/flow-upgrade` 对齐本文件声明的版本。
> **Flow Repo 维护者**：每次 push 前更新本文件。

## 当前版本

`flow_version: "2.10"`

## 版本历史

---

### v2.10 — TAPD 与 GAN 链路解耦

**date**: 2026-04-29
**breaking**: false
**summary**: 把 TAPD 集成从 GAN 链路内剥离,降级为"输入适配 + 输出回填"的边界。GAN 链路(doc-librarian → planner → generator → evaluator)不再感知 TAPD。subtask 派发时机从 planner 后移到 jenkins-deploy 后,语义改为"工时台账回填"(创建即 done + AI 估算工时)。

**核心架构变化**:

```
v1: tapd-pull → doc-librarian → consensus-push → wait-approve → planner → subtask-emit → generator → evaluator → push → deploy → subtask-close → sprint-review → done
v2: doc-librarian → consensus-push → consensus-gate(单向) → planner → generator → evaluator → push → deploy → subtask-emit(部署后回填) → done
```

**新增文件**:
- `.claude/agents/estimator.md` — 工时估算 subagent(隔离调用,不污染主 context)

**修改文件**:
- `.claude/templates/flows/tapd-full.json` — v2 模板,10 step,删 tapd-pull step,subtask-emit 移到 deploy 后,gate 名 wait-approve → consensus-gate
- `.claude/templates/story/case-template.md` — frontmatter 新增必填字段 `affected_files`(estimator 工时估算依据)
- `.claude/agents/doc-librarian.md` — 去 TAPD 化:不感知工单来源,只读 stories/<id>/source/
- `.claude/agents/planner.md` — 删除"完成后调 /tapd-subtask-emit"指令,新增"必填 affected_files"要求
- `.claude/agents/generator.md` — 删除"发布 generator:started 触发 subtask 派发"逻辑
- `.claude/commands/tapd/tapd-story-start.md` — 内联 mcp__chopard-tapd__get_stories_or_tasks(替代 tapd-pull skill 依赖),不再传 TAPD 上下文给 doc-librarian
- `.claude/commands/tapd/tapd-subtask-emit.md` — 重写为部署后回填器:批量 create + 立即 done + add_timesheets,父工单状态不动
- `.claude/skills/tapd-subtask/SKILL.md` — Emit 模式重写,Close/Reopen 保留为向后兼容
- `.claude/commands/start-dev-flow.md` — TAPD 链路差异表更新
- `.chatlabs/knowledge/project/architecture.md` — 状态流转图同步,加入 input_adapter / consensus_gate / subtask_backfill 节点

**核心纪律**:
- GAN 链路不感知数据来源(TAPD/本地/将来其他来源同等对待)
- consensus-gate 是单向门:GAN 内任何阶段不可回退到评审
- subtask 是工时台账(创建即 done),不是任务派发;父工单状态由 PM 手工管理
- 工时估算通过 Task tool 启动 estimator subagent 隔离执行

**迁移步骤**:
1. 已有 v1 task 的 `workflow-state.json.flow.steps` 仍按 v1 模板 11 step 推进(向后兼容)
2. 新 task 自动使用 v2 模板 10 step
3. 已派发的 subtask 不受影响(/tapd-subtask-close/reopen 仍可手工调整旧数据)

---

### v2.9 — 移除 LTM 长期记忆系统

**date**: 2026-04-29
**breaking**: false
**summary**: 移除 LTM 长期记忆系统，Claude Code 自身具备上下文记忆能力，无需额外维护三层记忆结构。

**删除文件**：
- `.claude/scripts/ltm.py` — LTM 核心模块
- `.claude/skills/ltm/` — LTM skill 目录

**删除目录**：
- `.chatlabs/ltm/` — 运行时 LTM 数据（STM/ITM/LTM）

**修改文件**：
- `.claude/hooks/session-start.py` — 移除 LTM 注入逻辑
- `.claude/scripts/gc.py` — 移除 LTM consolidate 调用
- `.claude/scripts/reflect.py` — 移除 `--store-ltm` 选项和 `store_to_ltm` 函数
- `.claude/scripts/paths.py` — 移除 LTM 相关路径常量
- `.claude/commands/self-reflect.md` — 移除 LTM 关联说明
- `.claude/artifacts-layout.md` — 移除 ltm/ 章节
- `CLAUDE.md` — 移除版本标记中的 LTM
- `.claude/MANIFEST.md` — 添加 v2.9 版本历史

**迁移步骤**：
1. LTM 相关路径常量和导入已移除
2. `/self-reflect` 命令不再支持 `--store-ltm` 选项
3. gc 报告不再包含 ltm_consolidate 区块

---

### v2.8 — 移除 GEPA 规则优化引擎

**date**: 2026-04-29
**breaking**: false
**summary**: 移除 GEPA 遗传-帕累托提示词进化引擎，保留 LTM 长期记忆系统。

**删除文件**：
- `.claude/skills/gepa/` — GEPA skill 目录
- `.claude/scripts/gepa.py` — GEPA 引擎
- `.claude/commands/evolution-propose.md` — 进化提案命令（含 GEPA 引用）

**修改文件**：
- `.claude/MANIFEST.md` — 清理 GEPA 版本历史
- `.claude/scripts/propose.py` — 移除 GEPA 优化函数
- `.claude/commands/evolution-apply.md` — 清理 GEPA 关联引用
- `.chatlabs/knowledge/tech/backend/modules/skills.md` — 移除 gepa
- `.chatlabs/knowledge/tech/backend/modules/scripts.md` — 移除 gepa
- `.chatlabs/knowledge/project/architecture.md` — 移除 Gepa

**迁移步骤**：
1. `/evolution-propose` 命令已删除，相关功能停止使用
2. 如需生成进化提案，请手动创建 spec 变更

---

### v2.7 — Skill 重构：Pipeline 架构解耦

**date**: 2026-04-28
**breaking**: false
**summary**: 将 self-reflect、insight-extract 从 skill 重构为 command，消除 skill 之间的循环依赖，建立清晰的 Pipeline 数据流。

**核心变更**：

1. **Skill → Command 重构**
   - `self-reflect` skill → `/self-reflect` command + `reflect.py`
   - `insight-extract` skill → `/insight-extract` command + `extract.py`

2. **Pipeline 数据流**
   ```
   workflow-review（编排器）
       ├── /self-reflect      → flow-log/*.json
       └── /insight-extract   → insights/_index.jsonl
   ```

3. **Skill 保留为独立工具**
   - `ltm`：独立存储系统，无跨 skill 依赖

**新增文件**：
- `.claude/scripts/reflect.py` — 自审辅助脚本
- `.claude/scripts/extract.py` — 洞察提炼辅助脚本
- `.claude/commands/self-reflect.md` — 自审命令
- `.claude/commands/insight-extract.md` — 洞察提炼命令

**修改文件**：
- `.claude/commands/workflow-review.md` — 改用 command 编排
- `.claude/skills/self-reflect/SKILL.md` → stub
- `.claude/skills/insight-extract/SKILL.md` → stub
- `.claude/skills/ltm/SKILL.md` — 移除跨 skill 引用
- `.claude/commands/session-review.md` — 更新关联
- `.claude/commands/evolution-apply.md` — 更新关联
- `.claude/agents/session-auditor.md` — 更新关联

**迁移步骤**：
1. `/self-reflect` 命令仍然可用（通过 stub 转发）
2. `/workflow-review` 自动使用新的 command 编排
3. 无需手动迁移

---

### v2.6 — LTM 长期记忆系统

**date**: 2026-04-23
**breaking**: false
**summary**: 新增 LTM 长期记忆系统，实现 Flow 自我进化的核心机制。

**核心功能**：

1. **LTM 长期记忆系统**（`.claude/scripts/ltm.py`）
   - 三层记忆结构：STM（1小时）、ITM（7天）、LTM（永久）
   - 记忆类型：pattern、rule、anti-pattern、insight
   - 语义检索能力
   - 自动 consolidate（ITM → LTM）
   - 健康度监控

2. **集成到现有流程**
   - session-start.py：自动注入相关记忆到 context
   - self-reflect：自动存储根因/模式到 LTM
   - gc.py：每日 consolidate + GC

**新增文件**：
- `scripts/ltm.py` — LTM 核心模块
- `skills/ltm/SKILL.md` — LTM 使用文档

**修改文件**：
- `scripts/paths.py` — 添加 LTM 路径常量
- `scripts/gc.py` — 集成 LTM consolidate
- `hooks/session-start.py` — 注入 LTM 记忆
- `skills/self-reflect/SKILL.md` — 自动存储到 LTM

**存储结构**：
```
.chatlabs/ltm/
├── stm/                    # Short-Term (session)
├── itm/                    # Intermediate (7 days)
└── ltm/
    ├── patterns/           # 成功模式
    ├── rules/              # 验证规则
    ├── anti-patterns/      # 失败模式
    ├── insights/           # 洞察
    └── _index.jsonl       # 永久记忆索引
```

---

### v2.5 — Flow 仓库去中间层（直接 Git 管理）

**date**: 2026-04-22
**breaking**: false
**summary**: Flow 配置直接从 `.claude/` 目录管理 git 仓库，无需本地缓存目录中间层。简化同步流程，提升可靠性。

**核心变更**：
1. **删除本地缓存关联**：移除 `.chatlabs/flow/` 和 `.flow-source.json` 的间接关联
2. **直接 Git 操作**：在 `.claude/` 目录直接 `git push/pull` 到 GitHub
3. **简化 flow-upgrade**：直接从 GitHub 拉取更新，不再依赖本地缓存

**删除文件**：
- `.chatlabs/flow/` 目录（不再需要）

**修改文件**：
- `commands/flow/flow-upgrade.md` — 改为直接 git pull
- `commands/flow/flow-push.md` — 改为直接 git push（移除 .flow-source.json 依赖）
- `commands/flow/flow-pull.md` — 改为直接 git pull

**迁移步骤**（针对已有项目）：
1. 运行 `/flow-upgrade --apply` 拉取最新 flow
2. 删除 `.chatlabs/flow/` 目录（如果存在）
3. 如果有 `.chatlabs/flow/.flow-source.json`，可以删除

---

### v2.4 — 新增 TAPD Subtask 自动派发 + Jenkins 部署

**date**: 2026-04-22
**breaking**: false
**summary**: 完善开发流程闭环：planner 拆分 cases 后自动派发 TAPD subtask；开发完成后自动触发 Jenkins 部署并通知。

**核心变更**：

1. **自动派发 TAPD Subtask**：planner 完成后自动调用 `/tapd-subtask-emit`，将本地 cases 作为 task 创建到 TAPD 工单下，填写标题/描述/验收标准/负责人，不包含具体实现代码
2. **自动 Jenkins 部署**：task 标记完成后自动调用 `/jenkins-deploy`，触发 `bde-debeers-be-staging` 构建，轮询状态，发送企微通知

**新增文件**：
- `.claude/skills/jenkins-deploy/SKILL.md` — Jenkins 部署 skill
- `.chatlabs/project-config.json` — Jenkins 任务配置（job 名/分支/通知开关）

**修改文件**：
- `commands/tapd/tapd-story-start.md` — 新增"后续完整流程"章节（Step 1-5），明确 subtask 派发和 Jenkins 部署的自动触发时机

**完整流程时序**：
```
doc-librarian → [冻结] → planner → [自动派发 subtask] → generator → [自动 Jenkins 部署] → done
```

**迁移步骤**（针对已有项目）：
1. 无需迁移，新 story 自动使用新流程
2. 运行 `/flow-upgrade --apply` 拉取最新 flow 文件

---

### v2.3 — 共识文档评审改用 Wiki 模式

**date**: 2026-04-22
**breaking**: false
**summary**: 共识文档评审从 TAPD 工单评论改为 Wiki 存储，方便完整内容展示和多人协作评审。

**核心变更**：
- 共识文档推送到 TAPD Wiki 进行评审
- 目录结构：`共识文档/{store_name}/{文档名}.md`
- 每个 store 单独一个目录，存放多版本契约文档
- 子任务派发仍在工单下进行（不变）

**新增文件**：
- `.claude/skills/tapd-consensus/SKILL.md` — Wiki 模式共识同步
- `.claude/commands/tapd/tapd-consensus-push.md` — Wiki 推送命令
- `.claude/commands/tapd/tapd-consensus-fetch.md` — Wiki 评审拉取命令

**修改文件**：
- `MANIFEST.md` — 添加 v2.3 版本历史

**Wiki 目录结构**：
```
共识文档/                    # 根目录
├── STORY-001/              # store 目录
│   ├── STORY-001 契约文档 v1.0.0.md
│   └── STORY-001 契约文档 v1.0.1.md
└── STORY-002/
    └── ...
```

**评审流程**：
1. doc-librarian 冻结契约 → `/tapd-consensus-push` 推送到 Wiki
2. PM 在 Wiki 上进行评审，回复 `[CONSENSUS-APPROVED]` 或 `[CONSENSUS-REJECTED:原因]`
3. `/tapd-consensus-fetch` 检测评审结果，更新本地状态

**迁移步骤**（针对已有项目）：
1. 无需迁移，旧数据继续有效
2. 新 story 自动使用 Wiki 模式
3. 已有的工单评论评审记录保留（向后兼容）

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
