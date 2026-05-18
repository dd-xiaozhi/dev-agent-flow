---
name: tapd
description: TAPD 统一入口命令。通过子命令路由到具体动作：init/start/sync/push/fetch/emit/close/reopen。
model: sonnet
---

# /tapd

> TAPD 统一入口命令。通过子命令路由到具体动作，支持自然语言识别。
>
> **用法**：`/tapd <subcommand> [args...]`
>
> **快捷方式**：
> - `/tapd 123456789` → 自动识别为 `/tapd start 123456789`
> - `/tapd https://tapd.cn/...` → 自动解析工单 ID 后 `/tapd start`

> ⚠️ **MCP 调用强约束**：所有 TAPD MCP 调用必须遵守铁律 R-01 ~ R-07，
> 参数常量、状态枚举、流转矩阵、调用模板查 `.claude/skills/tapd/references/tapd-api-constants.md`。

## 子命令总览

| 子命令 | 说明 | 触发场景 |
|--------|------|----------|
| `init` | 初始化 TAPD 配置 | 首次使用或配置缺失 |
| `start <ticket_id|url>` | 从 TAPD 工单开工 | "我要做这个工单"、"开工" |
| `sync [--type] [--all]` | 同步工单到本地缓存 | "同步工单"、"拉工单" |
| `push <story_id> [--dry-run]` | 推送契约到 TAPD Wiki | "推送契约"、"Wiki 评审" |
| `fetch <ticket_id> [--purpose] [--entry-type] [--no-md]` | 拉取评审反馈并生成评论 MD | "检查评审"、"拉反馈" |
| `emit <ticket_id> [--dry-run]` | 创建子任务并标 done | "派发子任务"、"回填工时" |
| `close <case_id>` | 标记 case 完成，推送待测 | "case 通过"、"标 done" |
| `reopen <case_id> --reason <text>` | 重开子任务 | "打回了"、"QA 不通过" |

---

## 子命令详解

### /tapd init

> 引导式初始化 TAPD 配置。**首次使用必须运行**，生成 `.chatlabs/project-config.json`。

**用法**：`/tapd init [--workspace-id <id>]`

**行为**：
1. 调用 `mcp__chopard-tapd__get_user_participant_projects` 发现项目
2. 若 `--workspace-id` 已传 → 直接用；否则用 `AskUserQuestion` 让用户选择
3. 探测工作流状态：`get_workflows_status_map(system="story|task")`
4. 智能匹配语义键（to_dev/to_review/to_test/done）
5. **获取项目成员并分类**：调用 `get_workspace_members(workspace_id)` 拉取所有项目成员，通过 `AskUserQuestion` 让用户为每位成员标记角色（PM/BE/FE/QA/OTHER），支持一人多角色
6. 生成配置写入 `.chatlabs/project-config.json`
7. 追加到 `.gitignore`

**产出**：
- `.chatlabs/project-config.json`（含 `tapd.team_roles` 角色映射表）

---

### /tapd start <ticket_id|url>

> 从 TAPD 工单一键开工或重入。主流程入口。

**用法**：`/tapd start <ticket_id | tapd_url>`

**行为**：

**第一步：入参解析**
- 入参含 `tapd.cn` 或 `http(s)://` → 正则 `(\d{10,})` 提取 ticket_id
- 入参为纯数字 → 直接作为 ticket_id

**第二步：刷新本地缓存**
委派给 tapd skill 的 pull 模块拉最新工单数据，写 `.chatlabs/task/store/<story_id>/task.json.tapd`（保留 `local_mapping` / `subtasks` / `comments_cache`）。

**第三步：分支判断**
读 `task.json.tapd.local_mapping.story_id`：

| 情形 | story_id | 分支 |
|------|----------|------|
| 未关联 | null | first-start |
| 已关联 | 非 null | re-entry |

**第四步：first-start**
1. 生成 `story_id = {MM-dd}-{title-slug}`：
   - 取 `ticket.name` → LLM 翻译为英文 → slugify → 截断 30 字符
2. 写入 `task.json.tapd.local_mapping`：`tapd_ticket_id`、`story_id`（经 TaskJsonStore.update_tapd）
3. 归档 source 到 `.chatlabs/task/store/<story_id>/source/tapd-ticket-<ticket_id>-<ts>.md`
4. 调 `python .claude/scripts/task.py new <story_id>` 分配 task_id
5. **创建并绑定 git 分支**：
   - 前置：`git status --porcelain` 必须为空，脏工作区 → 阻塞流程
   - 调 git-branch skill：`action=create type=feature ticket_id=<ticket_id> description=<story_id> source_branch=master`
   - 输出 `{branch: "feature/<ticket_id>-<story_id>"}`
   - 调 `python .claude/scripts/task.py bind-branch <task_id> --branch <branch> --branch-type feature --source-branch master --merge-targets dev,uat`
   - 失败（如分支已存在）→ 阻塞，不继续到 flow 初始化
6. 调 `python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <story_id> init --flow-id tapd-full --task-id <task_id>` 初始化 flow
7. 路由 `doc-librarian`

**第五步：re-entry**
委派给 `python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <story_id> check` 读 flow 状态：
- `is_terminal == true` → 输出"已完成"，提示 `--force` 重启
- `is_terminal == false` → 按 flow 状态路由
- TAPD description 修改 → 归档新 source + 走变更检查

**产出**：
- 更新 `.chatlabs/task/store/<story_id>/task.json` 的 `tapd` section
- first-start：新建 `.chatlabs/task/store/<story_id>/`、`source/*.md`、TASK、`feature/<ticket_id>-<story_id>` 分支、初始化 flow、启动 doc-librarian

---

### /tapd sync [--type story|task|bug] [--all] [--iteration <id>]

> 拉取 TAPD 工单到本地缓存。

**用法**：`/tapd sync [--type story|task|bug] [--all] [--iteration <id>]`

**行为**：
1. 读 `.chatlabs/project-config.json`，校验存在（不存在 → 提示先 `/tapd init`）
2. 调用 `mcp__chopard-tapd__get_todo(workspace_id=..., entity_type=...)` 拉待办
3. 若 `--all` → 改用 `get_stories_or_tasks(owner=..., status!=完成)` 拉所有未完成
4. 若 `--iteration <id>` → 加 `iteration_id=<id>` 过滤
5. 对每条工单：
   - `get_stories_or_tasks(id=<ticket_id>)` 拿完整字段
   - 合并到 `task.json.tapd`（保留 local_mapping / subtasks / comments_cache）
   - schema 校验
6. 更新 `project-config.json.tapd.last_sync_at`

**产出**：
- 更新各任务目录下 `task.json.tapd` 字段

---

### /tapd push <story_id> [--dry-run]

> 把本地共识文档（contract.md）推送到 TAPD Wiki 进行评审。

**用法**：`/tapd push <story_id> [--dry-run]`

**注意**：
- 自动化调用（flow 触发）→ dry_run=false（真推）
- 手动调用（用户）→ dry_run=true（预览），加 `--force` 才会真推

**行为**：

**第一步：前置校验**
1. 读取 `project-config.json` 获取 workspace_id
2. 读取 `task.json.tapd` 获取 ticket_id
3. 读取 `contract.md`：`.chatlabs/task/store/<story_id>/contract.md`
4. 校验 frontmatter `status == "frozen"`，否则拒绝

**第二步：确定 Wiki 层级（严格三层）**

```
共识文档（root，全局唯一，name=「共识文档」，parent=0）
└── {story_id}（store 节点，每个 story 一个，仅承载目录语义，无契约正文）
    └── v{seq}（版本叶子，承载 contract.md 正文 + 评审 footer）
```

层级查找/创建规则（由 `push_wiki.py` 自动完成，幂等）：
1. **root**：name=`共识文档`、parent=0；查不到则自动创建，id 缓存到 `task.json.tapd.consensus_root_wiki_id`
2. **store**：name=`{story_id}`（TAPD 与本地同 schema，story_id 已含日期/slug），parent=root_id；查不到则自动创建，id 缓存到 `task.json.tapd.consensus_store_wiki_id`
3. **version**：name=`v{seq}`（v1 / v2 / ...），parent=store_id；
   - 首次 push 或 `--bump-version` → 创建新叶子
   - 同版本覆盖（`task.json.tapd.wiki_id` 已存在、未 bump）→ 更新已有叶子

⚠️ Wiki 名称**禁止**再包含 story_id 前缀或 `契约文档` 后缀——store 节点已经表达了 story 维度，version 节点只保留 `v{seq}`。

**第三步：创建/更新 Wiki**
1. 版本号：`consensus_version_next = consensus_version_prev + (1 if --bump-version else 0)`，首次推送 = 1
2. Wiki 名称（叶子节点）：`v{consensus_version_next}`（如 `v1`、`v2`）
3. 内容：完整 contract.md + 评审元信息（自动 @ `team_roles.pm 列表通知评审）

**Wiki 元信息格式：末尾追加角色通知**
```
---
评审通知：@PM1 @PM2 请评审契约文档
后端负责人：@BE1 @BE2
前端负责人：@FE1
```

**第四步：预览或执行**
- dry_run=true → 输出预览信息（`push_wiki.py prepare` 不调 TAPD API，仅拼装 body）
- dry_run=false → 调用 `push_wiki.py push`：自动 ensure root → ensure store → 推 v{seq} → 回写 task.json

**第五步：更新本地状态**
更新 `task.json.tapd`：
- `consensus_root_wiki_id`（root 层 id）
- `consensus_store_wiki_id`（store 层 id）
- `consensus_parent_wiki_id`（=store id，向后兼容字段）
- `wiki_id` / `wiki_url`（版本叶子 id 与链接）
- `consensus_version`（已推送的版本序号，bump 后 +1）

**产出**：
- TAPD Wiki 三层结构：`共识文档/{story_id}/v{seq}`
- 更新 `task.json.tapd` 含三层 id 缓存

---

### /tapd fetch <ticket_id> [--since <iso>] [--purpose startup|review] [--entry-type stories|tasks|bugs] [--no-md]

> 拉取 TAPD 工单评论中的评审反馈，生成人类可读的评论 MD 文档。

**用法**：`/tapd fetch <ticket_id> [--since <iso>] [--purpose startup|review] [--entry-type stories|tasks|bugs] [--no-md]`

**参数说明**：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--purpose` | 执行场景（影响后续路由行为） | `startup` |
| `--entry-type` | 工单实体类型（stories/tasks/bugs） | 自动从 `task.json.tapd.entity_type` 读取，读取失败 fallback 为 `stories` |
| `--since` | 只拉取指定时间后的评论 | `task.json.tapd.last_synced_at` |
| `--no-md` | 不生成评论 MD 文档 | 默认为 false（生成 MD） |

**purpose 行为差异**：

| `--purpose` | 场景 | 行为差异 |
|------------|------|---------|
| `startup`（默认） | `/tapd start` 调用 | 只拉评论写 cache；遇到 REJECTED 写 Blocker；**不写 feedback、不路由** |
| `review` | 正常评审流程 | 完整执行：写 feedback + 更新 meta + 自动路由 planner |

**行为**：

**第一步：拉评论**
1. 读取 `task.json.tapd.entity_type` 确定 entry_type；若不存在则用 `--entry-type` 参数或 fallback 为 `stories`
2. 调用 `mcp__chopard-tapd__get_comments(workspace_id=..., entry_id=ticket_id, entry_type=entry_type, order="created desc", limit=50)`
3. 若 `--since` 传了 → 过滤 `created > since`；否则取 `task.json.tapd.last_synced_at` 后的评论

**第二步：更新缓存与 MD 生成**
1. 调用 `python .claude/skills/tapd/scripts/comments_cache.py process --story-id <story_id> --ticket-id <ticket_id> --entry-type <entry_type> --comments-json '<comments_json>'`
2. 脚本自动去重（基于 `comment.id`）并增量更新 `task.json.tapd.comments_cache`
3. 若未传 `--no-md` → 生成 `.chatlabs/task/store/<story_id>/tapd-comment.md` 或 `.chatlabs/task/bug-fix/<bug_id>/tapd-comment.md`

**第三步：识别标记**
按 `project-config.json.tapd.comment_markers` 模式匹配：
- `[CONSENSUS-APPROVED]`
- `[CONSENSUS-REJECTED:reason]`
- `[QA-PASSED]`
- `[QA-REJECTED:reason]`

**第四步：处理反馈**

| 标记 | purpose=startup | purpose=review |
|------|----------------|----------------|
| APPROVED | 仅输出状态 | 写 feedback + 更新 meta.phase="planner" + 路由 planner |
| REJECTED | 写 Blocker | 写 Blocker + 写 feedback |
| QA-* | 提示（不直接动子任务状态） | 同左，由 `/tapd close/reopen` 处理 |

**产出**：
| 产物 | 路径 | 说明 |
|------|------|------|
| comments_cache | `task.json.tapd.comments_cache` | 已去重的评论列表（结构化） |
| 评论 MD 文档 | `.chatlabs/task/*/<id>/tapd-comment.md` | 人类可读的评论汇总（`--no-md` 时不生成） |
| feedback | `feedback/` 目录下 | 仅 `purpose=review` 时生成 |

**字段映射说明**：
- 评论去重键：`comment.id`
- MD 文档字段：评论时间（`created`）、评论人（`author`）、评论内容（`content`）
- 特殊标记自动加粗：`[CONSENSUS-*]`、`[QA-*]`、`[SUBTASK-*]`

---

### /tapd emit <ticket_id> [--dry-run] [--force] [--commit-range <range>]

> 部署完成后批量创建 TAPD subtask 并立即标 done + 回填工时。

**用法**：`/tapd emit <ticket_id> [--dry-run] [--force] [--commit-range <range>]`

**行为**：

> subtask 按 **spec.md §7 的角色分组**（BE / FE / QA / PM / INFRA / DOC）+ 实际 git diff 估工时。每个角色一个 subtask（如本次有多角色，则多个 subtask；纯后端则只产 BE + 一个 QA 测试 subtask）。

**第一步：前置校验**
1. 读 `task.json.tapd`，要求 `local_mapping.story_id` 已绑定且 `spec.md` 存在（含 §7 AC ↔ 实现 + 测试映射）
2. `comments_cache.subtask_emitted == true` 且无 `--force` → 拒绝
3. 读 `git diff <commit_range>`（默认 `master...HEAD` 或最近一次部署的 commit 范围）

**第二步：工时估算与角色分组**（主流程模型自评，不调外部 agent）

**分组维度**：
- 从 spec.md §7 提取所有 AC 的"实现位置"，按文件路径推断角色：
  - `src/main/...java` / `service/` / `controller/` / `mapper/` 等 → **BE**
  - `frontend/` / `*.tsx` / `*.vue` / `*.css` 等 → **FE**
  - `src/test/...IntegrationTest` / `*.feature` / `qa/` 等 → **QA**
  - 仅文档/配置 → **INFRA** 或 **DOC**
- 同一角色的所有实现合并为一个 subtask（标题=`【{role}】<故事题目>`）

**工时自评规则**（基于实际 diff，无 cases 维度）：

| 维度 | 规则 |
|------|------|
| 代码量基线 | 每 100 行实质代码（排除注释 / `.lock` / `.json` / fixture）≈ 1 小时 |
| 角色归属 | `git diff` 中匹配该角色文件路径的所有 added+deleted 行 → 该角色 subtask |
| 业务密集（多 if / 状态机） | ×1.5 |
| 纯 CRUD / 模板代码 | ×0.7 |
| 并发 / 事务 / 第三方集成 | ×2 |
| 仅改配置 / 文案 | ×0.3 |
| 单测代码 | 计入开发者角色（BE/FE）的工时，不单独成 subtask |
| 集成测试代码 | 计入 QA subtask 工时（即使是 Evaluator 自动生成） |
| 上限 | 单角色 subtask ≤ 16h（超出说明 story 拆得不细，标 `oversized: true`） |
| 下限 | 单角色 subtask ≥ 0.5h |
| 舍入 | 保留 0.25h 倍数（0.25 / 0.5 / 0.75 / 1.0 …） |

**第三步：批量回填（强约束）**

对每个角色 subtask 顺序：**查类型 ID → 创建 subtask → 推完成态 → 写工时**，失败则跳过。

| 调用 | 必传参数 | 备注 |
|------|---------|------|
| `get_workitem_types(name="子任务")` | — | **每对话首次执行，缓存复用**（R-02） |
| `create_story_or_task` | `entity_type="stories"`（复数，R-04） / `workitem_type_id=<上一步id>`（**禁传 `workitem_type_name`**） / `name="【{role}】<story.title>"` / `owner=<角色对应人，从 project-config.tapd.team_roles[role] 取>` / `priority_label="Middle"`（R-03） / `effort=<人时>` / `iteration_name=<与父Story一致>` / `parent_id=<父Storyid>` | R-02 / R-03 / R-04 |
| `update_story_or_task` | `entity_type="stories"` / `id=<subtask_id>` / `v_status="任务/测试完成"`（R-01，禁用 `status`） | 写入后回读校验（R-07） |
| `get_timesheets` → `add_timesheets` / `update_timesheets` | 工时 API `entity_type="story"`（**单数**，R-04） / 单人单天单 ticket 去重 | timespent 精度 0.5h |

**标题角色 prefix**（按 spec.md §7 推断的角色决定，详见 `references/tapd-api-constants.md §6`）：

| 推断角色 | prefix | 例 |
|-----------|--------|----|
| `backend` | `【BE】` | 【BE】SF Token 失效自动刷新与重试机制 |
| `frontend` | `【FE】` | 【FE】登录页静态搭建 |
| `qa` | `【QA】` | 【QA】SF Token 重试机制集成测试 |
| `pm` | `【PM】` | 【PM】确认权限规则 |
| `ui` | `【UI】` | 【UI】登录页走查 |
| `infra` / `doc` 等 | `【INFRA】` / `【DOC】` | 按推断角色 |

**第四步：本地落库**
- 追加 `task.json.tapd.subtasks[]`（含 subtask_id / role / owner / effort / timesheet_id）
- 置 `task.json.tapd.subtask_emitted = true` + `total_estimated_hours`
- 父工单发评论 `[SUBTASK-EMITTED]`（子任务列表 + 工时汇总，自动 @ `team_roles.pm + team_roles.qa`）

**产出**：
- TAPD 子任务 N 个，`v_status="任务/测试完成"` + 已填工时
- 更新 `task.json.tapd.subtasks` 与 `subtask_emitted`

---

### /tapd close <case_id>

> 标记本地 case 完成 + 把 TAPD 子任务推到"待测试"状态。

**用法**：`/tapd close <case_id>`

**行为**：

**第一步：前置校验**
1. 读本地 `task.json.workflow.verdicts.<case_id>`
2. 校验 verdict == "PASS"，否则拒绝

**第二步：流转矩阵自检（R-05，API 不强制）**
1. 目标 `v_status="任务/测试完成"` 必须在 constants §4.2 Subtask 状态枚举内
2. `current_v_status → 任务/测试完成` 必须在 §4.2 矩阵中标 ✅
3. 不满足 → 写 Blocker，退出

**第三步：更新 TAPD**
1. `mcp__chopard-tapd__update_story_or_task(options={entity_type="stories", id=<subtask_id>, v_status="任务/测试完成"})`
   - ⚠️ `entity_type="stories"`（复数，R-04），**禁用 `tasks`**
   - ⚠️ 用 `v_status` 中文名（R-01），**禁用 `status` 英文 key**
2. 回读 `get_stories_or_tasks(id=<subtask_id>)` 校验 status 已切换（R-07）

**第四步：发评论**
`mcp__chopard-tapd__create_comments(entry_id=<subtask_id>, entry_type="stories", description="[QA-PASSED] 本地 case 完成验收 (verdict=PASS)，等待 QA 测试。本地 case: <case_id>。@<qa_list> 请验收")`

> 自动 @ `team_roles.qa` 列表，通知 QA 人员进行测试验收

**第五步：更新本地**
- `subtask.local_phase = "done"`
- `subtask.tapd_v_status = "任务/测试完成"`
- `task.json.tapd.last_synced_at = now()`

**产出**：
- TAPD 子任务 `v_status → "任务/测试完成"`
- TAPD 评论 `[QA-PASSED]`

---

### /tapd reopen <case_id> --reason <text>

> QA 打回时使用：本地 case phase 回退 + TAPD 子任务回退到开发态。

**用法**：`/tapd reopen <case_id> --reason "<打回原因>"`

**前置**：`--reason` 必填，且长度 ≥ 5 字符

**行为**：

**第一步：前置校验**
1. `--reason` 必填（≥5 字符）
2. 读本地 `task.json.workflow.verdicts.<case_id>`
3. 校验 verdict == "PASS"，否则拒绝

**第二步：流转矩阵自检（R-05）**
1. 目标 `v_status="实现中"` 必须在 §4.2 Subtask 枚举内
2. `current_v_status → 实现中` 必须在矩阵中标 ✅
   - ⚠️ 已结束的子任务（`任务/测试完成` / `关闭`）**不可回退到 `实现中`**，必须先重置为 `To do`
3. 不满足 → Blocker，退出

**第三步：本地状态回退**
1. 更新 `task.json.workflow.verdicts.<case_id> = "WIP"`
2. 在 `blockers.md` 追加打回记录

**第四步：更新 TAPD**
1. `update_story_or_task(entity_type="stories", id=<subtask_id>, v_status="实现中")`（R-01 / R-04）
   - 若 current_v_status 不允许直接到 `实现中`，按矩阵先转 `To do` 再转 `实现中`
2. 回读校验（R-07）
3. `create_comments(entry_id=<subtask_id>, entry_type="stories", description="[QA-REJECTED:{reason}] 本地 case 已重置为 in_progress，将重新开发。@<be_list> @<fe_list> 请处理")`

> 自动 @ `team_roles.be` + `team_roles.fe` 列表，通知对应开发人员处理打回问题

**第五步：更新缓存**
- `subtask.local_phase = "in_progress"`
- `subtask.tapd_v_status = "实现中"`

**产出**：
- 本地 case phase: done → in_progress
- TAPD 子任务: `任务/测试完成` → `实现中`
- TAPD 评论 `[QA-REJECTED:reason]`

---

## 快捷方式识别

| 输入格式 | 自动路由 |
|---------|---------|
| `/tapd 123456789` | `/tapd start 123456789` |
| `/tapd https://tapd.cn/1140062001234567/s/...` | `/tapd start 1140062001234567` |
| `/tapd`（无参数） | 输出子命令帮助 |

---

## 自然语言理解提示

Agent 可根据以下关键词自动路由到对应子命令：

| 关键词 | 路由 |
|--------|------|
| "初始化"/"首次配置"/"绑定 TAPD" | `/tapd init` |
| "做这个工单"/"开工"/"开始" + TAPD ID/URL | `/tapd start` |
| "同步工单"/"拉工单"/"更新缓存" | `/tapd sync` |
| "推送契约"/"Wiki 评审"/"发到 TAPD" | `/tapd push` |
| "检查评审"/"拉反馈"/"看结果" | `/tapd fetch` |
| "派发子任务"/"回填工时"/"创建 subtask" | `/tapd emit` |
| "完成了"/"标 done"/"case 通过" | `/tapd close` |
| "打回了"/"QA 不通过"/"重新来" | `/tapd reopen` |

---

## 关联

- Skill: `.claude/skills/tapd/SKILL.md`
- **MCP 调用常量速查**：`.claude/skills/tapd/references/tapd-api-constants.md`（必读）
- 业务规范源：`docs/TAPD_Ticket_操作规范.md`
- 配置: `.chatlabs/project-config.json`
- 状态: `.chatlabs/task/store/<id>/task.json`（含 tapd section）
- 评论脚本: `.claude/skills/tapd/scripts/comments_cache.py`
- 评论 MD 输出: `.chatlabs/task/*/<id>/tapd-comment.md`
