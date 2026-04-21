# Flow Manifest

> 所有使用本 Flow Repo 的项目，通过 `/flow-upgrade` 对齐本文件声明的版本。
> **Flow Repo 维护者**：每次 push 前更新本文件。

## 当前版本

`flow_version: "2.0"`

## 版本历史

---

### v2.0 — 规范外置化 + 增量升级体系

**date**: 2026-04-21
**breaking**: false（相对于 v1.0 的初始版本而言是全新体系，但对已接入项目而言是首次 init）
**summary**: spec 规范从 `docs/` 外置到 `.chatlabs/spec/`；新增 `/flow-upgrade` 增量更新命令；删除硬编码的 `docs/coding-convention.md`；Harness → Flow 术语清理。

**破坏性变更（对已接入项目的冲击）**：
- `docs/coding-convention.md` 已删除，内容迁移到 `.chatlabs/spec/backend/coding-style.md`
- Agent 文档（doc-librarian / generator / planner）中硬编码的 `docs/api-conventions.md`、`docs/fitness-functions.md` 引用已改为走 `.chatlabs/spec/INDEX.md`

**迁移步骤**（针对已在使用 v1.0 的项目）：
1. 运行 `/flow-upgrade --apply`（自动同步 agent/command/skill 文件）
2. `.chatlabs/spec/` 目录由 `/init-project` Phase 8 生成，无需手动迁移
3. 旧的 `docs/coding-convention.md` 已删除，如项目有本地副本可安全删除

---

### v1.0 — 初始版本

**date**: 2026-04-19
**breaking**: false
**summary**: Flow 体系首次发布（doc-librarian / planner / generator / evaluator 四 agent；完整 TAPD 集成；fitness-run / contract-test / gc / context-reset skill；slash commands 全套）

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
