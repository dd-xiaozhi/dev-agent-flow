# Flow Manifest

> 所有使用本 Flow Repo 的项目，通过 `/flow-upgrade` 对齐本文件声明的版本。
> **Flow Repo 维护者**：每次 push 前更新本文件。

## 当前版本

`flow_version: "2.3"`

## 版本历史

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
