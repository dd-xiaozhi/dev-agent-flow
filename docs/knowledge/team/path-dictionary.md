# 路径占位符词典 — path-dictionary

> **定位**：所有文档、agent.md、skill.md、command.md、template 中出现的"路径占位符"权威定义。
> **执行原则**：
> - 新写的文件 → **必须**用权威形式
> - 修改老文件时 → **顺手**规范化（不发起专项批量替换，避免引入大面积风险）
> - 已知不规范变体 → 本文档"漂移记录"段保留作为知情承诺
>
> **真相源唯一**：本文档是占位符语义的单一真相源；与文档冲突时，本文档为准。

---

## 1. 权威占位符表

| 占位符 | 含义 | 取值示例 | 出现位置语境 |
|--------|------|---------|-------------|
| `<story_id>` | Story 唯一标识（任务存储目录名） | `05-21-wechat-login` | `docs/task/store/<story_id>/...` |
| `<task_id>` | Task 唯一标识（task.json 顶层的 task_id 字段） | `05-21-wechat-login` 或 `TASK-001` | `docs/reports/tasks/<task_id>/...` |
| `<bug_id>` | Bug 修复任务标识 | `bug-12345` | `docs/task/bug-fix/<bug_id>/...` |
| `<ticket_id>` | TAPD 工单 ID（纯数字 / 10+ 位） | `1000000001234567890` | TAPD URL、API 参数 |
| `<project_root>` | 被测项目根目录（绝对路径） | `/Users/xx/work/some-project` | evaluator / fitness 调用时上下文 |
| `<flow_id>` | Flow 模板标识 | `tapd-full` / `local-spec` / `bugfix-vibe` | `.claude/templates/flows/<flow_id>.json` |

**统一形式规则**：
- 使用 `<下划线>` 包裹（不用 `<短横线>`，不用 `{大括号}`）
- 全小写，多词用下划线分隔（snake_case）
- 不带前缀（不写 `<id_story>`、`<the_story_id>` 这类冗余形式）

---

## 2. 漂移记录（已知不规范变体）

> 本表记录现存文件中的漂移情况，**知情承诺，不立即批量修复**。当你修改这些文件时，顺手把命中的变体改为权威形式。

| 现存变体 | 权威形式 | 实际命中数 | 主要分布 |
|---------|---------|----------|---------|
| `<id>` | `<story_id>` 或 `<task_id>`（按上下文） | ~40 | agents/、commands/、scripts/ |
| `<story-id>` | `<story_id>` | 7 | doc-librarian.md、planner.md、spec.md 模板 |
| `{story_id}` | `<story_id>` | 4 | 散落于 ticket / skill 文档 |
| `{task_id}` | `<task_id>` | 1 | 单点 |
| `{ticket_id}` | `<ticket_id>` | 8 | tapd 相关文档 |

**`<id>` 特殊处理**：`<id>` 是历史遗留的模糊占位符（未明确是 story 还是 task）。修改时优先按上下文判断：
- 涉及 `task.json` / `contract.md` 路径 → 改为 `<story_id>`
- 涉及 `reports/tasks/` / `blockers.md` → 改为 `<task_id>`
- 实在不确定 → 加 TODO 注释，等后续上下文清晰再改

---

## 3. 常见路径模式（含占位符）

| 模式 | 用途 |
|------|------|
| `docs/task/store/<story_id>/contract.md` | doc-librarian 产出 |
| `docs/task/store/<story_id>/spec.md` | planner 产出 |
| `docs/task/store/<story_id>/task.json` | 任务级 SSOT（workflow / events / tapd） |
| `docs/task/store/<story_id>/source/` | 原始需求素材（只读） |
| `docs/task/bug-fix/<bug_id>/` | bug 修复任务存储 |
| `docs/reports/tasks/<task_id>/blockers.md` | Blocker 记录（task 元数据 + summary 已并入 task.json，不再独立 meta.json） |
| `docs/reports/integration-tests/<story_id>/verdict.json` | 集成测试统一 schema |
| `docs/reports/sprints/YYYY-MM/review-<task_id>.md` | sprint-review 产出 |
| `docs/knowledge/project/experience/YYYY-MM-<slug>.md` | 经验沉淀 |
| `.claude/templates/flows/<flow_id>.json` | flow 模板 |

---

## 4. 禁止事项

- ❌ 禁止硬编码绝对路径（如 `/Users/xx/...`）出现在 agent.md / skill.md / command.md / 文档中
  - 例外：`.claude/settings.local.json` 等机器级配置允许（gitignore 也可考虑）
- ❌ 禁止用 `{xxx}` 大括号包裹路径占位符（统一用 `<xxx>`）
- ❌ 禁止用 `<xxx-xxx>` 短横线分隔（统一用 `<xxx_xxx>` 下划线）
- ❌ 禁止把 `<story_id>` 和 `<task_id>` 混用——含义不同（story 是业务需求维度，task 是执行调度维度，目前实践中常重合但本质独立）

---

## 5. 检查工具（未来落地）

> 当前阶段：人工 + grep 抽查。后续可以加：

```bash
# 占位符变体扫描（一键自查）
grep -rE "(<[a-z]+-[a-z]+>|\{[a-z_]+\})" --include='*.md' .claude/ docs/knowledge/
```

后续可以做的（不强求）：
- pre-commit hook 拦截 `<id>` / `<story-id>` / `{story_id}` 等不规范形式
- `/fitness-run` skill 增加 placeholder-consistency 检查项

---

## 6. 变更纪律

- 新增占位符 → 先改本文档表 1，再在文档/代码中使用
- 修改占位符语义 → 改本文档 + sprint-review 沉淀为 experience
- 表 2 的漂移条目随实际修复缓慢减少 → 命中数变 0 时移出表 2

---

## 7. 与 fitness-rules 的关系

- `fitness-rules.md` §1.2 三层目录边界 — 规定"目录写权限"
- 本文档 — 规定"占位符语义"
- 两者互补：fitness-rules 保护**目录**，path-dictionary 保护**路径表达**
