# /flow-upgrade

> 检测并更新项目中的 Flow 核心文件（agents / commands / skills / hooks），**不影响项目状态**（`.chatlabs/`、`docs/`、`src/` 目录永远不动）。
>
> 支持两种升级模式：
> - **增量升级**：Flow Repo 小版本更新（命令修复、agent 改进），直接合并
> - **迁移升级**：Flow Repo 跨了大版本，有破坏性变更，提供明确的迁移路径

## 前置条件

**必须先运行 `/init-project`**，它会在项目中写入：

```json
// .claude/.flow-source.json
{
  "version": 2,
  "flow_repo": "https://github.com/dd-xiaozhi/dev-agent-flow.git",
  "flow_branch": "master",
  "flow_version": "2.5",
  "last_commit": "<commit-hash>",
  "last_upgraded_at": "<ISO-timestamp>"
}
```

若此文件不存在，`/flow-upgrade` 输出错误并提示先运行 `/init-project`。

---

## Phase 0: 读取配置 + 检测更新

```
读取 .claude/.flow-source.json
    ↓
从 GitHub 克隆/更新 Flow Repo
    ↓
读取 Flow Repo 的 .claude/MANIFEST.md（获取 flow_version + breaking_changes）
    ↓
读取 Flow Repo HEAD commit hash
    ↓
比较 flow_version
    ├── 相同 → 比较 last_commit vs HEAD
    │            若相同 → ✅ 已最新，结束
    │            若不同 → 进入 Phase 1（增量升级）
    │
    └── 不同（跨版本）→ 进入 Phase M（迁移升级）
```

---

## Phase 1: 增量升级（flow_version 相同）

### 1.1 扫描变更

对以下目录逐文件与 Flow Repo 对比：

| 目录 | 更新策略 |
|------|---------|
| `.claude/commands/` | 强制覆盖（含子目录） |
| `.claude/agents/` | 强制覆盖 |
| `.claude/skills/` | 强制覆盖 |
| `.claude/hooks/` | 强制覆盖 |
| `.claude/templates/` | 智能合并（见下方） |

**templates/ 智能合并规则**：
- Flow Repo 新增目录 → 拷贝
- 文件内容不同 → diff 摘要，用户确认后覆盖
- 文件内容相同 → 跳过

**永远不触碰**：`.chatlabs/`、`docs/`、`src/`

### 1.2 输出变更报告

```
📦 Flow Repo 更新（v2.3 → v2.4，+3 commits）

🔧 新增/更新：
  🔴 更新   commands/doc-librarian.md     规范加载改为走 INDEX.md
  🟡 新增   commands/flow-upgrade.md     全新命令

✅ 无跳过的文件
```

---

## Phase M: 迁移升级（flow_version 不同）

当 Flow Repo 的 `flow_version` 与项目的 `flow_version` 不同时，触发迁移流程。

### M.1 读取破坏性变更清单

从 Flow Repo 的 `.claude/MANIFEST.md` 读取 `[breaking_changes]` 部分：

```markdown
# Flow Manifest

## 当前版本

`flow_version: "3.0"`

## 破坏性变更（从 v2.x 迁移）

### v3.0

**破坏类型**：⚠️ 目录重组 + 命令重命名

| 变更 | 说明 | 项目影响 |
|------|------|---------|
| `.claude/agents/` → `.claude/roles/` | agent 目录改名 | **项目所有 agent 文件需迁移** |
| `/init-project` 拆分为 `/init` + `/scan-project` | 单命令变两命令 | 旧命令文件删除 |
| 删除 `/workflow-review` | 功能合并到 `/sprint-review` | 旧命令文件删除 |
| `templates/` 目录重组 | 模板全部重新组织 | 需重新生成项目模板 |

**迁移步骤**：
1. 备份当前 `.claude/`：`cp -r .claude .claude.backup-v2`
2. 迁移 agent 文件：`.claude/agents/*.md` → `.claude/roles/`
3. 删除旧命令：`/workflow-review`、`/init-project`
4. 从 Flow Repo 拷贝新命令：`/init`、`/scan-project`
5. 重新运行 `/init-project`（模式 B 增量更新）
6. 验证：确认 5 个 agent 能正常加载

**回滚**：删除新版 `.claude/`，恢复 `.claude.backup-v2`
```

### M.2 输出迁移报告

```
⚠️  检测到 Flow 版本跨越（v2.x → v3.0）

🚨 破坏性变更摘要：
  · 目录重组：`.claude/agents/` → `.claude/roles/`
  · 命令重命名：1 个删除，2 个新增
  · templates/ 全部重新组织

⚠️  此迁移不可逆，请先确认：
  1. 当前项目没有正在进行的 story（`.chatlabs/stories/` 下若有 draft/review 态，请先处理或备份）
  2. 项目对 `.claude/` 下文件的所有定制化修改已 commit

  如果不满足，请先完成再继续。

📖 迁移步骤（见 Flow Repo 的 .claude/MANIFEST.md §v3.0 breaking_changes）：
  1. 备份：cp -r .claude .claude.backup-v2
  2. 迁移 agent 目录
  3. 删除旧命令
  4. 拷贝新命令
  5. 重新运行 /init-project

迁移完成后会自动更新 .claude/.flow-source.json。
```

### M.3 执行迁移（交互）

```
是否执行迁移？（y/n）

  y = 执行迁移（自动执行上述步骤）
  n = 退出，稍后手动处理
  v = 查看详细迁移步骤

> v
```

**选 `y` 后的流程**：
1. 自动备份：`.claude` → `.claude.backup-v<旧版本>`
2. 按 MANIFEST.md 的迁移步骤执行（文件移动/删除/拷贝）
3. 重新运行 `/init-project`（自动进入增量更新，刷新模板）
4. 更新 `.flow-source.json`：`flow_version` → 新版本
5. 输出：
   ```
   ✅ 迁移完成
   📦 Flow v2.x → v3.0
   📁 备份：.claude.backup-v2/（可安全删除）
   📁 当前：.claude/（已迁移到 v3.0）
   ```

### M.4 保护规则（迁移时额外严格）

- `.chatlabs/stories/` 下若有 `status: draft` 或 `status: review` 的 story，**阻止迁移**，提示先处理
- 项目对 Flow 文件有未 commit 的本地修改，**阻止迁移**，提示先 commit 或 stash
- 迁移完成后，`.claude.backup-v*` 目录**不自动删除**，用户确认没问题后手动删除

---

## Phase 2: 执行更新（增量模式）

### 模式 A：自动（`--apply`）

```
✅ 自动模式 — 正在更新...

  ✅ 更新   commands/flow/flow-upgrade.md
  ✅ 更新   commands/init-project.md

✅ 更新完成（6 个文件，0 个跳过）
```

### 模式 B：交互确认

```
检测到 7 个文件。
逐个确认：[y=全部/n=跳过/q=退出/文件名=单独确认]
```

### Phase 2.1 保护规则

1. **项目在 last_commit 后有 commit**：warning，询问是否强制覆盖
2. **`/init-project` 产物**：`.claude/docs/` 下文件**不覆盖**（属于项目文档）
3. **`.chatlabs/`**：永远不动，检测到直接报错

---

## Phase 3: 更新 .flow-source.json

```json
{
  "version": 2,
  "flow_repo": "/path/to/flow-repo",
  "flow_version": "2.4",
  "last_commit": "<new HEAD>",
  "last_upgraded_at": "<ISO>",
  "updated_files": ["..."],
  "skipped_files": ["..."],
  "migration_from": null
}
```

若是迁移升级，`migration_from` 填旧版本号。

---

## 使用示例

```bash
# 检查增量更新（只读）
/flow-upgrade

# 检查 + 包含详细 diff
/flow-upgrade --diff

# 自动应用所有增量更新
/flow-upgrade --apply

# 只更新指定文件
/flow-upgrade agents/generator.md commands/init-project.md

# 强制重新检查迁移（不推荐）
/flow-upgrade --force-migrate
```

## Flow Repo 维护者指南

在 Flow Repo 的 `.claude/MANIFEST.md` 中维护版本变更历史：

```markdown
# Flow Manifest

## 当前版本
`flow_version: "3.0"`

## 版本历史

### v3.0
**date**: 2026-04-21
**breaking**: true
**summary**: 目录重组，agent 迁移到 roles/，命令拆分

### v2.4
**date**: 2026-04-20
**breaking**: false
**summary**: 新增 /flow-upgrade 命令，spec 规范外置化

### v2.0
**date**: 2026-04-19
**breaking**: true
**summary**: 首次发布，Flow 体系建立
```

**维护规则**：
- 每次 push 到 Flow Repo 前，先更新 MANIFEST.md
- 小版本（无破坏性）：`breaking: false`
- 大版本（有破坏性）：`breaking: true` + 写清楚迁移步骤
- 不写 MANIFEST.md 的变更 → 默认视为小版本

## 关联

- 项目初始化：`/init-project`
- Flow 元规范：`.claude/MANIFEST.md`（由 Flow Repo 维护者编写）
- 受保护目录：`.chatlabs/`、`docs/`、`src/`（永远不触碰）
