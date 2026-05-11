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

## 子命令总览

| 子命令 | 说明 | 触发场景 |
|--------|------|----------|
| `init` | 初始化 TAPD 配置 | 首次使用或配置缺失 |
| `start <ticket_id\|url>` | 从 TAPD 工单开工 | "我要做这个工单"、"开工" |
| `sync [--type] [--all]` | 同步工单到本地缓存 | "同步工单"、"拉工单" |
| `push <story_id> [--dry-run]` | 推送契约到 TAPD Wiki | "推送契约"、"Wiki 评审" |
| `fetch <ticket_id> [--purpose]` | 拉取评审反馈 | "检查评审"、"拉反馈" |
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
5. 生成配置写入 `.chatlabs/project-config.json`
6. 追加到 `.gitignore`

**产出**：
- `.chatlabs/project-config.json`

---

### /tapd start \<ticket_id\|url\>

> 从 TAPD 工单一键开工或重入。主流程入口。

**用法**：`/tapd start <ticket_id | tapd_url>`

**行为**：

**第一步：入参解析**
- 入参含 `tapd.cn` 或 `http(s)://` → 正则 `(\d{10,})` 提取 ticket_id
- 入参为纯数字 → 直接作为 ticket_id

**第二步：刷新本地缓存**
委派给 tapd skill 的 pull 模块拉最新工单数据，写 `.chatlabs/tapd/tickets/<ticket_id>.json`（保留 `local_mapping` / `subtasks`）。

**第三步：分支判断**
读 `ticket.local_mapping.story_id`：

| 情形 | story_id | 分支 |
|------|----------|------|
| 未关联 | null | first-start |
| 已关联 | 非 null | re-entry |

**第四步：first-start**
1. 生成 `story_id = {MM-dd}-{title-slug}`：
   - 取 `ticket.name` → LLM 翻译为英文 → slugify → 截断 30 字符
2. 写入 `local_mapping.tapd_ticket_id` 和 `local_mapping.story_id`
3. 归档 source 到 `.chatlabs/stories/<story_id>/source/tapd-ticket-<ticket_id>-<ts>.md`
4. 调 `python .claude/scripts/task.py new <story_id>` 分配 task_id
5. 调 `python .claude/scripts/flow_advance.py --story-id <story_id> init --flow-id tapd-full --task-id <task_id>` 初始化 flow
6. 路由 `doc-librarian`

**第五步：re-entry**
委派给 `python .claude/scripts/flow_advance.py --story-id <story_id> check` 读 flow 状态：
- `is_terminal == true` → 输出"已完成"，提示 `--force` 重启
- `is_terminal == false` → 按 flow 状态路由
- TAPD description 修改 → 归档新 source + 走变更检查

**产出**：
- 更新 `.chatlabs/tapd/tickets/<ticket_id>.json`
- first-start：新建 `.chatlabs/stories/<story_id>/`、`source/*.md`、TASK、初始化 flow、启动 doc-librarian

---

### /tapd sync [--type story|task|bug] [--all] [--iteration \<id\>]

> 拉取 TAPD 工单到本地缓存。

**用法**：`/tapd sync [--type story|task|bug] [--all] [--iteration <id>]`

**行为**：
1. 读 `.chatlabs/project-config.json`，校验存在（不存在 → 提示先 `/tapd init`）
2. 调用 `mcp__chopard-tapd__get_todo(workspace_id=..., entity_type=...)` 拉待办
3. 若 `--all` → 改用 `get_stories_or_tasks(owner=..., status!=完成)` 拉所有未完成
4. 若 `--iteration <id>` → 加 `iteration_id=<id>` 过滤
5. 对每条工单：
   - `get_stories_or_tasks(id=<ticket_id>)` 拿完整字段
   - 合并到 `.chatlabs/tapd/tickets/<ticket_id>.json`（保留 local_mapping 和 subtasks）
   - schema 校验
6. 更新 `.chatlabs/tapd/tickets/_index.jsonl`
7. 更新 `project-config.json.tapd.last_sync_at`

**产出**：
- `.chatlabs/tapd/tickets/<ticket_id>.json`（多个）
- `.chatlabs/tapd/tickets/_index.jsonl`（覆盖写）

---

### /tapd push \<story_id\> [--dry-run]

> 把本地共识文档（contract.md）推送到 TAPD Wiki 进行评审。

**用法**：`/tapd push <story_id> [--dry-run]`

**注意**：
- 自动化调用（flow 触发）→ dry_run=false（真推）
- 手动调用（用户）→ dry_run=true（预览），加 `--force` 才会真推

**行为**：

**第一步：前置校验**
1. 读取 `project-config.json` 获取 workspace_id
2. 读取 `.chatlabs/tapd/tickets/<ticket_id>.json`
3. 读取 `contract.md`：`.chatlabs/stories/<story_id>/contract.md`
4. 校验 frontmatter `status == "frozen"`，否则拒绝

**第二步：确定 Wiki 层级**
1. 查找/创建根目录 `共识文档`（Wiki）
2. 派生 store 目录：TAPD story → `{ticket_id}-{slug}`；本地 → `story_id`
3. slug 规则：小写、汉字保留、空格替换为 `-`、去除特殊字符、截断 50 字符

**第三步：创建/更新 Wiki**
1. 版本号：新版本 = store 下已有数量 + 1，格式 `v{version}.0`
2. Wiki 名称：`{store_name} 契约文档 v{version}`
3. 内容：完整 contract.md + 评审元信息

**第四步：预览或执行**
- dry_run=true → 输出预览信息（不真推）
- dry_run=false → 调用 `mcp__chopard-tapd__create_wiki`

**第五步：更新本地状态**
更新 `ticket.json.local_mapping`（wiki_id、wiki_url、consensus_version++）

**产出**：
- TAPD Wiki（完整契约文档）
- 更新 `ticket.json.local_mapping`

---

### /tapd fetch \<ticket_id\> [--since \<iso\>] [--purpose startup|review]

> 拉取 TAPD 工单评论中的评审反馈。

**用法**：`/tapd fetch <ticket_id> [--since <iso>] [--purpose startup|review>]`

**参数说明**：

| `--purpose` | 场景 | 行为差异 |
|------------|------|---------|
| `startup`（默认） | `/tapd start` 调用 | 只拉评论写 cache；遇到 REJECTED 写 Blocker；**不写 feedback、不路由** |
| `review` | 正常评审流程 | 完整执行：写 feedback + 更新 meta + 自动路由 planner |

**行为**：

**第一步：拉评论**
1. 调用 `mcp__chopard-tapd__get_comments(workspace_id=..., entry_id=ticket_id, entry_type="stories", order="created desc", limit=50)`
2. 使用 `comments_cache.py` 增量追加到 `comments.json`
3. 若 `--since` 传了 → 过滤 `created > since`；否则取 `ticket.last_synced_at` 后的评论

**第二步：识别标记**
按 `project-config.json.tapd.comment_markers` 模式匹配：
- `[CONSENSUS-APPROVED]`
- `[CONSENSUS-REJECTED:reason]`
- `[QA-PASSED]`
- `[QA-REJECTED:reason]`

**第三步：处理反馈**

| 标记 | purpose=startup | purpose=review |
|------|----------------|----------------|
| APPROVED | 仅输出状态 | 写 feedback + 更新 meta.phase="planner" + 路由 planner |
| REJECTED | 写 Blocker | 写 Blocker + 写 feedback |
| QA-* | 提示（不直接动子任务状态） | 同左，由 `/tapd close/reopen` 处理 |

**第四步：更新缓存**
- 同步全量评论到 `comments.json`
- 更新 `ticket.last_synced_at`

**产出**（按 purpose）：
| purpose | feedback 文件 | meta 更新 | 自动路由 |
|---------|-------------|----------|---------|
| `startup` | ❌ | ❌ | ❌ |
| `review` | ✅ | ✅ | ✅ |

---

### /tapd emit \<ticket_id\> [--dry-run] [--force] [--commit-range \<range\>]

> 部署完成后批量创建 TAPD subtask 并立即标 done + 回填工时。

**用法**：`/tapd emit <ticket_id> [--dry-run] [--force] [--commit-range <range>]`

**行为**：

**第一步：前置校验**
1. 读 `.chatlabs/tapd/tickets/<ticket_id>.json`，要求 `local_mapping.story_id` 已绑定且 `cases/CASE-*.md` 存在
2. `local_mapping.subtask_emitted == true` 且无 `--force` → 拒绝

**第二步：工时估算**
- `case.estimate_hours` 已填 → 直接使用
- 未填 → 调 estimator agent 批量估算

**第三步：批量回填**
对每个 case 顺序创建 task → 标 done → 写工时，失败则跳过。

任务名按 `case.type` 加角色前缀：`backend→【BE】` / `frontend→【FE】` / `infra→【INFRA】` / `doc→【DOC】`

**第四步：本地落库**
- 追加 `ticket.subtasks[]`
- 置 `local_mapping.subtask_emitted = true` + `total_estimated_hours`
- 父工单发评论 `[SUBTASK-EMITTED]`（子任务列表 + 工时汇总）

**产出**：
- TAPD 子任务 N 个，全部 done + 已填工时
- 更新 `ticket.json.subtasks` 与 `local_mapping.subtask_emitted`

---

### /tapd close \<case_id\>

> 标记本地 case 完成 + 把 TAPD 子任务推到"待测试"状态。

**用法**：`/tapd close <case_id>`

**行为**：

**第一步：前置校验**
1. 读本地 `.chatlabs/reports/tasks/<case_id>/meta.json`
2. 校验 `meta.verdict == "PASS"`，否则拒绝

**第二步：状态机检查**
1. 读 `project-config.json.tapd.status_map.task.to_test`
2. 二次确认目标态英文名仍存在
3. 确认从当前状态可达 `to_test`
4. 不可达 → 写 Blocker，退出

**第三步：更新 TAPD**
1. `mcp__chopard-tapd__update_story_or_task(options={entity_type="tasks", id=tapd_task_id, v_status=to_test_chinese_name})`
2. 验证更新生效

**第四步：发评论**
`mcp__chopard-tapd__create_comments(entry_id=tapd_task_id, entry_type="tasks", description="[QA-PASSED] 本地 case 完成验收 (verdict=PASS)，等待 QA 测试。本地 case: <case_id>")`

**第五步：更新本地**
- `subtask.local_phase = "done"`
- `subtask.tapd_status = <to_test 英文名>`
- `ticket.last_synced_at = now()`

**产出**：
- TAPD 子任务状态变更（→ 待测试）
- TAPD 评论 `[QA-PASSED]`

---

### /tapd reopen \<case_id\> --reason \<text\>

> QA 打回时使用：本地 case phase 回退 + TAPD 子任务回退到开发态。

**用法**：`/tapd reopen <case_id> --reason "<打回原因>"`

**前置**：`--reason` 必填，且长度 ≥ 5 字符

**行为**：

**第一步：前置校验**
1. `--reason` 必填（≥5 字符）
2. 读本地 `.chatlabs/reports/tasks/<case_id>/meta.json`
3. 校验 `meta.phase == "done"`，否则拒绝

**第二步：状态机检查**
1. 确认 `to_dev` 状态可达
2. 不可达 → Blocker，退出

**第三步：本地状态回退**
1. 更新 `meta.json`：`phase = "in_progress"`，`verdict = "WIP"`
2. 在 `blockers.md` 追加打回记录
3. 在 `meta.json.summary.execution_log` 追加

**第四步：更新 TAPD**
1. `update_story_or_task(v_status=to_dev_chinese)`
2. `create_comments(description="[QA-REJECTED:{reason}] 本地 case 已重置为 in_progress，将重新开发。")`

**第五步：更新缓存**
- `subtask.local_phase = "in_progress"`
- `subtask.tapd_status = <to_dev 英文>`

**产出**：
- 本地 case phase: done → in_progress
- TAPD 子任务: 待测试 → 进行中
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
- 配置: `.chatlabs/project-config.json`
- 状态: `.chatlabs/state/workflow-state.json`、`.chatlabs/tapd/tickets/`