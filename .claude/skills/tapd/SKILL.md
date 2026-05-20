---
name: tapd
description: TAPD 统一入口 skill。工单拉取、共识管理、子任务回填、事件驱动同步。触发关键词：tapd、初始化、ticket sync、共识、Wiki 评审、子任务、工时回填、QA 通过、QA 打回、TAPD 事件、契约推送、同步工单、拉工单。
model: sonnet
---

# TAPD Skill

> TAPD 统一入口 skill。合并原 tapd-init、tapd-pull、tapd-consensus、tapd-subtask、tapd-sync 五个 skill 的能力。

---

## ⚠️ 调用 MCP 前必读：铁律 7 条

所有 MCP 调用细节、状态枚举、自定义字段常量、流转矩阵、调用模板，统一引用：
**`.claude/skills/tapd/references/tapd-api-constants.md`**（业务源 `docs/TAPD_Ticket_操作规范.md` v1.0+）。

| 编号 | 铁律 | 详见 |
|------|------|------|
| R-01 | 状态用 `v_status`（中文名），禁用 `status` | constants §1 / §4 |
| R-02 | 创建 ticket 必须两步法（`get_workitem_types` → `workitem_type_id`），禁传 `workitem_type_name` | constants §3 / §7 |
| R-03 | 优先级用 `priority_label`，禁用数字 `priority` | constants §1 |
| R-04 | `entity_type`：工单 = `stories`（复数），工时 = `story`（单数） | constants §2 |
| R-05 | TAPD API 不强制流转矩阵，AI 必须自检 | constants §4 |
| R-06 | 待确认项必须传 `parent_id` | constants §4.3 / §7.4 |
| R-07 | 写入后必须 `get_stories_or_tasks` 回读校验 | — |

> **强约束**：本 skill 永不调用 `update_story_or_task` 推进 Story（父工单）状态。所有 Story 状态由 PM/PO 或外部自动化触发。

---

## 触发场景

| 场景 | 触发词 |
|------|--------|
| 初始化 | tapd 初始化、tapd init、配置 tapd、绑定项目 |
| 工单拉取 | tapd 拉取、ticket sync、同步工单、拉工单、tapd pull |
| 共识管理 | TAPD 共识、Wiki 评审、contract 推送、consensus、契约评审 |
| 子任务 | 工时回填、subtask emit、QA 通过、QA 打回、tapd subtask |
| 事件同步 | tapd同步、TAPD事件、契约推送 |

---

## 模块化能力

### init 模块

> 引导式初始化 TAPD 配置。

**职责**：
- 发现项目（调用 `get_user_participant_projects`）
- 探测工作流状态（调用 `get_workflows_status_map`）
- 智能匹配语义键（to_dev/to_review/to_test/done）
- 获取项目成员并按角色分类（PM/BE/QA/FE），**必须获取每个成员的完整用户名（真实姓名）**
- 生成配置写入 `.chatlabs/project-config.json`

**实际能力（脚本驱动，不依赖 MCP）**：
- 调用 `python .claude/skills/tapd/scripts/init.py setup --workspace-id <wid> --workspace-name "<name>"` 一键完成成员拉取 + 角色分类猜测 + 配置写入
- 脚本直接走 HTTP API（`GET https://api.tapd.cn/workspaces/users`），**必须设置 `${TAPD_TOKEN}` 环境变量**；token 缺失才回退到 MCP 工具 `get_workspace_members`
- 仅当 `team_roles` 全空时写入（保护已有分类），重复执行返回 `{ok: true, skipped: true}`
- 角色基于 `nick/user/email` 关键字猜测；**主流程 Claude 必须用 `AskUserQuestion` 让用户复核 `other` 桶并修正错分**
- 单独查看成员清单（不写配置）：`python .claude/skills/tapd/scripts/init.py members --workspace-id <wid>`

**触发词**：tapd 初始化、tapd init、配置 tapd、绑定项目

---

### pull 模块

> 工单拉取与本地缓存维护。**直接调 TAPD HTTP API（脚本 fetch 模式）**，避开 MCP 工具手抄链路。

**推荐入口（脚本直拉 HTTP API，需要 env `TAPD_TOKEN`）**：
```bash
# 1) 拉工单 description + 元信息 → source/description.md + task.json.tapd.raw
python .claude/skills/tapd/scripts/description.py fetch \
    --story-id <local-id> \
    --ticket-id <tapd-id> \
    [--workspace-id <id>]

# 2) 拉工单评论 → task.json.tapd.comments_cache + tapd-comment.md
python .claude/skills/tapd/scripts/comments.py fetch \
    --story-id <local-id> \
    [--ticket-id <tapd-id>] \
    [--limit 100]
```

**职责**：
- 拉取 TAPD 工单详情与评论到本地缓存
- 评论基于 `comment.id` 去重，累积写入 `task.json.tapd.comments_cache`
- 生成人类可读的 `tapd-comment.md`（按日期升序分组，关键评审标记 blockquote 突出）
- 首次拉取时自动 `TaskJsonStore.create` 任务目录

**输出**：
| 路径 | 内容 |
|------|------|
| `.chatlabs/task/store/<story_id>/source/description.md` | 工单正文（HTML→Markdown），含轻量 frontmatter |
| `.chatlabs/task/store/<story_id>/task.json` | 工单详情写入 `tapd` section（`ticket_id`、`workspace_id`、`local_mapping`、`comments_cache`、`raw`、`last_synced_at`） |
| `.chatlabs/task/store/<story_id>/tapd-comment.md` | 人类可读的评论汇总（frontmatter 含 ticket_id/last_synced_at/count，按日期升序分组，含 `[CONSENSUS-*]` / `[QA-*]` / `[SUBTASK-*]` 等评审标记的评论用 `> ⚠️ 关键评论` blockquote 突出） |

**流程**：
```
1. 解析 workspace_id：参数 > task.json.tapd.workspace_id > project-config.tapd.workspace_id
2. description.py fetch：GET https://api.tapd.cn/stories?workspace_id=&id=&fields=...
   → 提取 Story 字段 → HTML→Markdown → source/description.md
   → 元信息累积写入 task.json.tapd.raw（保留 local_mapping/wiki_id/consensus_* 等不被覆盖）
3. comments.py fetch：GET https://api.tapd.cn/comments?workspace_id=&entry_type=stories&entry_id=&limit=&order=created desc
   → _normalize_comment 标准化（id/author/created/content/title）
   → 复用 comments_cache.dedupe_comments 基于 comment.id 去重
   → 写入 task.json.tapd.comments_cache（累积）
   → 重写 tapd-comment.md（按日期升序 + 关键评论 blockquote）
```

**关键约束**：
- `local_mapping`、`subtasks`、`comments_cache`、`wiki_id`、`consensus_*` 是本地累积/缓存的，
  partial update（`TaskJsonStore.update_tapd`）保证不会被覆盖
- 所有 tapd 字段写入必须经 `TaskJsonStore.update_tapd`，禁止直接写 task.json
- HTTP 调用直读 `${TAPD_TOKEN}`（参考 `push_wiki.py._tapd_request`）
- MD 文档字段映射：评论时间（`created`）、评论人（`author`）、评论内容（`description`→HTML→Markdown，回退到 `_strip_html` 后的 `content`）、`comment_id`（用于追溯）

**兼容旧链路（deprecated）**：
- `description.py save < mcp_output.json`：接受 MCP `get_stories_or_tasks` 返回 JSON 落地（仅用于调试或离线复演，新流程不再调 MCP `get_stories_or_tasks`）
- `comments_cache.py process --comments-json '<json>'`：接受 MCP `get_comments` 返回 JSON 落地（仅历史兼容）

**触发词**：tapd 拉取、ticket sync、同步工单、拉工单、tapd pull

---

### consensus 模块

> 共识文档版本管理 + Wiki 驱动的双向同步。

**核心变更**：共识文档推送到 TAPD Wiki 进行评审，而不是工单评论。

**目录结构**：
```
共识文档/
├── {ticket_id}-{slug}/
│   ├── {ticket_id}-{slug} 契约文档 v1.0.0.md
│   └── ...
```

#### Push（本地 → TAPD Wiki）

**输入**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `story_id` | string | 必填 |
| `store_name` | string | 可选 |
| `bump_version` | bool | 默认 false，仅契约业务规则变更时传 true |
| `dry_run` | bool | 默认 false |

**版本策略（默认同版本覆盖）**：

| 场景 | bump_version | 行为 |
|------|--------------|------|
| 合并 TBD 答复 / 措辞修订 / §0 增补 / 笔误修正 | `false`（默认） | 同版本覆盖现有 Wiki 节点（action=update） |
| 契约业务规则变更（新增/移除 AC、范围扩展、Non-Goals 调整） | `true` | 创建新 v{N+1} 节点（action=create） |
| 上一版被 `[CONSENSUS-REJECTED]` 且引入新业务规则 | `true` | 创建新 v{N+1} 节点 |
| 首次推送（无 wiki_id） | 无所谓 | 创建 v1 节点 |

**流程**：
```
1. 校验 task.json.tapd.local_mapping.story_id 非空
2. 读 contract.md，校验 status == "frozen"
3. 确定 store_name（参数 > task.json.tapd.local_mapping > 实时派生）
4. 确定父 Wiki（查找/创建根目录 "共识文档" + store 子目录）
5. 确定版本号 & action：
   - bump_version=true → action=create，版本号 = prev + 1
   - 已有 wiki_id 且 bump_version=false → action=update，沿用 prev 版本号
   - 无 wiki_id 且 bump_version=false → action=create，版本号 = 1
6. 构造 Wiki 内容（完整 contract.md + 元信息）
7. dry_run=true → 打印预览
8. dry_run=false → 调 TAPD API:
   - action=create → POST /tapd_wikis
   - action=update → POST /tapd_wikis 带 id 字段（TAPD 覆盖现有节点）
9. TaskJsonStore.update_tapd({wiki_id, wiki_url, consensus_version}) → save()
```

#### Fetch（TAPD → 本地）

**流程**：
```
1. 读取 task.json.tapd.wiki_id
2. 调用 get_wiki 获取 Wiki 详情
3. 调用 get_comments 拉取工单评论
4. 经 scripts/comments_cache.py 去重并更新 task.json.tapd.comments_cache
5. 生成/更新 tapd-comment.md（按日期分组，特殊标记加粗高亮）
6. 检查评审状态标记（[CONSENSUS-APPROVED] / [CONSENSUS-REJECTED]）
7. TaskJsonStore.update_tapd / update_workflow 写回状态
```

**触发词**：TAPD 共识、Wiki 评审、contract 推送、consensus、契约评审

---

### subtask 模块

> TAPD 子任务回填。Emit 批量创建、Close 推到待测、Reopen 回退开发态。

#### Emit

**输入**：
| 参数 | 类型 | 说明 |
|------|------|------|
| `ticket_id` | string | TAPD 父工单 ID |
| `force` | bool | 已 emitted 仍允许重派 |
| `dry_run` | bool | 仅预览 |
| `commit_range` | string | git diff 范围 |

**输出**：每个 case → 一个 TAPD subtask（`v_status=任务/测试完成`，含工时记录）

**工时来源**：
- `case.estimate_hours` 非空走人工值（`estimate_source=manual`）
- 为空时由主流程模型按 `affected_files` + `git diff <commit_range>` 自评（`estimate_source=auto`），规则详见 `/tapd emit` 命令文档"自评规则"表

**创建规范（强约束）**：
- 调用前先 `get_workitem_types(name="子任务")` 拿到 `workitem_type_id` 缓存复用（R-02）
- 标题格式 `【{role}】{case_title}`，role 取自 case.kind 映射（`backend→BE` / `frontend→FE` / `qa→QA` / `infra→INFRA` / `doc→DOC`，见 constants §6）
- 必填：`workitem_type_id` / `owner`（单人）/ `priority_label`（默认 `Middle`）/ `effort`（人时）/ `iteration_name`（**必须与父 Story 一致**）/ `parent_id`
- 完成态用 `v_status="任务/测试完成"`（**禁止用 `status` 或英文 key**，R-01）
- 工时调用 `add_timesheets` 时 `entity_type` 用 **`story`（单数）**（R-04），先 `get_timesheets` 同人同天同 ticket 查重，已存在则改走 `update_timesheets`

**副作用**：父工单评论 `[SUBTASK-EMITTED]` 列出 subtask 与工时汇总；不修改父工单状态。

#### Close

**前置**：`meta.verdict == "PASS"`

**输出**：本地 `meta.phase=done`、TAPD subtask `v_status="任务/测试完成"`

**调用**：`update_story_or_task(entity_type="stories", id=<subtask_id>, v_status="任务/测试完成")`，写入后回读校验（R-07）

**副作用**：subtask 评论 `[QA-PASSED]`

#### Reopen

**前置**：`meta.phase == "done"`、`reason.length >= 5`

**输出**：本地 `meta.phase=in_progress / verdict=WIP`、TAPD subtask `v_status="实现中"`

**调用**：`update_story_or_task(entity_type="stories", id=<subtask_id>, v_status="实现中")`

**副作用**：`blockers.md` 追加 `[QA 打回]`、subtask 评论 `[QA-REJECTED:{reason}]`

#### 工作流前置自检（Close / Reopen，对应 R-05）

> TAPD API 不强制流转矩阵，AI 必须自行拒绝非法转换。

| 检查 | 数据源 | 不通过 |
|------|--------|--------|
| 目标 `v_status` 在 constants §4.2 Subtask 枚举内 | 本文档 + constants | FATAL |
| `current_v_status → target_v_status` 在 §4.2 流转矩阵中标 ✅ | constants | FATAL（拒绝调用） |
| 已结束状态（`任务/测试完成` / `关闭`）禁止回到 `实现中` | constants | FATAL |

**触发词**：工时回填、subtask emit、QA 通过、QA 打回、tapd subtask

---

### sync 模块

> 事件驱动的 TAPD 同步适配器。

**职责**：
- 监听 `contract:frozen` → 推送契约到 TAPD Wiki
- 监听 TAPD 评论 → 识别 `[CONSENSUS-APPROVED]`

**事件监听**：
| 事件 | 触发动作 |
|------|---------|
| `contract:frozen` | 若 TAPD enabled，推送契约到 Wiki |
| `tapd:consensus-approved` | 更新 phase = "planner"，自动路由 |

**状态隔离**：
- TAPD 相关状态全在 `task.json.tapd` section（任务级 SSOT，旧 `workflow-state.json.integrations.tapd` 已下线）
- TAPD 未启用时完全静默，不阻断主流程

**触发词**：tapd同步、TAPD事件、契约推送

---

## 待确认项（Item / Q&CO）协议

dev-flow 主流程不自动创建 Item（无 emit/close 子命令），但 AI 在被要求创建 Item 时必须遵守以下协议：

| 项 | 约束 |
|---|------|
| 创建方式 | 两步法：`get_workitem_types(name="待确认项")` → 取 id → `create_story_or_task(workitem_type_id=...)` |
| 父需求 | **必填** `parent_id`（R-06，TAPD 配置强制） |
| 迭代 | 必须与父需求 `iteration_name` 一致 |
| 标题 Prefix | `[Q]`（提问） / `[CO]`（变更补充） |
| 状态枚举 | 仅 `To do` / `进行中` / `已完成`（3 个） |
| 流转 | **单向不可回退**（constants §4.3）；如需重议→**新建 Item** |
| 关闭责任人 | 创建人补结论 → 创建人 close（不是处理人） |

调用模板见 `references/tapd-api-constants.md §7.4`。

---

## MCP 工具清单

**初始化类**：
- `get_user_participant_projects`
- `get_workspace_info`
- `get_workspace_members`（获取项目所有成员列表，含 user/id/nick/email）
- `get_workitem_types`
- `get_workflows_status_map`
- `get_workflows_all_transitions`
- `get_entity_custom_fields`

**工单操作类**：
- `get_todo`
- `get_stories_or_tasks`
- `create_story_or_task`
- `update_story_or_task`
- `add_timesheets`

**Wiki 操作类**：
- `create_wiki`
- `get_wiki`
- `update_wiki`

**评论/通知类**：
- `get_comments`
- `create_comments`
- `send_qiwei_message`

---

## 关键约束

1. **父工单状态不动**：由 PM 手工管理，本 skill 永不调用 `update_story_or_task` 推进父工单（Story）
2. **TAPD 可选**：enabled == false 时静默退出
3. **版本号语义**（已替代旧"单调递增"约束）：
   - **同版本覆盖**（默认）：TBD 澄清答复、措辞修订、§0 修订记录追加、笔误修正 → 沿用 prev_version，覆盖现有 Wiki 节点
   - **新版本**（`--bump-version` / `bump_version=true`）：契约业务规则变更（新增/移除 AC、范围扩展、Non-Goals 调整）→ 版本号 +1，创建新 v{N+1} 节点
   - 不允许版本号回退；不允许跨级跳跃（v1 → v3）
4. **本地状态保留**：`local_mapping`、`subtasks`、`comments_cache` 是本地累积的
5. **API 调用强约束**：所有 MCP 调用必须遵守 R-01 ~ R-07 铁律（见顶部），细节查 `references/tapd-api-constants.md`

---

## 配置结构说明

### `tapd.team_roles（项目角色映射）

初始化时通过 `get_workspace_members` 拉取项目成员列表，用户交互标记角色后持久化。

**数据结构**：
```json
{
  "pm": [
    {"user": "张三", "nick": "zhangsan", "id": "123456"}
  ],
  "be": [
    {"user": "李四", "nick": "lisi", "id": "123457"},
    {"user": "王五", "nick": "wangwu", "id": "123458"}
  ],
  "fe": [...],
  "qa": [...],
  "other": [...]
}
```

**角色定义**：
| 角色 | 说明 | TAPD @ 用法 |
|------|------|-------------|
| pm | 产品经理 | `@{user}({nick})` 用于需求评审、契约确认 |
| be | 后端开发 | `@{user}({nick})` 用于技术方案、后端实现 |
| fe | 前端开发 | `@{user}({nick})` 用于前端实现、联调通知 |
| qa | 测试人员 | `@{user}({nick})` 用于提测、验收确认 |
| other | 其他角色 | 不自动 @ |

**用户名存储格式**：
初始化时需获取每个成员的完整用户名（含真实姓名），格式为：
```json
{
  "user": "许迪智",
  "nick": "DDXu",
  "id": "123456"
}
```
@ 提及时必须使用 `@{user}({nick})` 格式，例如 `@许迪智(DDXu)`。

**使用场景**：
- `consensus push 推送 Wiki 时自动 @ pm 列表
- subtask emit 时按 case.type 自动 @ 对应角色
- QA 通过/打回时自动 @ qa 列表

---

## 关联

- Command: `.claude/commands/tapd.md`
- **API 常量速查**：`.claude/skills/tapd/references/tapd-api-constants.md`（AI 调用 MCP 时的强引用源）
- 业务规范源（人工维护）：`docs/TAPD_Ticket_操作规范.md`
- 配置: `.chatlabs/project-config.json`
- 状态：`.chatlabs/task/store/<story_id>/task.json` 的 `tapd` section（per-task SSOT，全局 fallback 已下线）
- 索引：`.chatlabs/task/_index.jsonl`
- Schema: `ticket.schema.json`、`tapd-config.schema.json`