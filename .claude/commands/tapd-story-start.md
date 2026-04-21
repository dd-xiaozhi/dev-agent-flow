# /tapd-story-start

> **主流程入口命令**。从 TAPD 工单（URL 或 ID）一键开工或重入。
>
> 职责：解析入参 → 拉取/刷新缓存 → 归档 description 版本 → 分配 story/task → 路由 doc-librarian。
>
> **编排层只做粗粒度分支判断**，不做 description 语义对比——后者是 doc-librarian 的职责。
>
> **用法**：
> - `/tapd-story-start <ticket_id>`
> - `/tapd-story-start <tapd_url>`
>
> **支持场景**：
> 1. **首次开工**：ticket 从未绑定过本地 STORY
> 2. **重入**：ticket 已绑定。由用户明确意图（恢复挂起 / 检查需求变更 / 取消）

## 行为

### 第零步：入参解析（URL 兼容）

1. 接受 URL 或纯数字 `ticket_id`：
   - 入参含 `tapd.cn` 或以 `http(s)://` 开头 → 用正则 `/(\d{10,})(?:/?|$)` 从路径提取 ticket_id
   - 入参为纯数字 → 直接作为 ticket_id
   - 其它格式 → 输出用法，退出
2. 将解析后的 `ticket_id` 传给后续步骤

### 第一步：刷新本地缓存

1. 读 `.chatlabs/tapd/tickets/<ticket_id>.json`
   - **不存在**：首次接触，标记 `is_new_ticket = true`
   - **存在**：标记 `is_new_ticket = false`
2. 调用 `tapd-pull` skill 单 ticket 模式拉最新数据，覆盖 `fields_cache`（保留 `local_mapping` / `subtasks` / `comments_cache`）
3. 校验 `entity_type == "stories"`，否则拒绝（task/bug 不是开工入口）
4. 拉取失败（404 / 权限 / 网络） → 输出错误原因，退出

### 第二步：判定流程分支

根据 `ticket.local_mapping.story_id` 分两支：

| 情形 | `local_mapping.story_id` | 分支 |
|------|-------------------------|------|
| 首次开工 | null | **BRANCH-A: first-start** |
| 重入 | 非 null | **BRANCH-B: ask-user** |

**编排层不对比 description。** 是否有需求变更由 doc-librarian 在 BRANCH-B 选 2 时做语义 diff 判断。

---

### BRANCH-A：first-start（首次开工）

1. **分配 STORY-NNN**
   - 扫描 `.chatlabs/stories/` 已有编号，递增分配 `STORY-NNN`
   - 写 `ticket.local_mapping.story_id = "STORY-NNN"`
2. **归档 description**：将 `fields_cache.description` 写到
   ```
   .chatlabs/stories/STORY-NNN/source/tapd-ticket-<ticket_id>-<YYYYMMDD-HHMMSS>.md
   ```
   （强制带时间戳，后续版本才能沉淀为历史链）
3. **调用 /task-new**：
   ```
   /task-new STORY-NNN --trigger first-start
   ```
   得到 `task_id = TASK-STORYNNN-01`
4. **拉 TAPD 历史评论**：调 `/tapd-consensus-fetch <ticket_id> --purpose=startup`
5. **路由 doc-librarian**（不传 mode，agent 自行判断）：
   - 输入参数：
     - `story_id`、`task_id`、`contract_path: .chatlabs/stories/STORY-NNN/contract.md`
     - `source_dir: .chatlabs/stories/STORY-NNN/source/`（doc-librarian 自己看目录下文件来决定生成/修订）
     - `tapd_ticket_id`、`tapd_ticket_url`
     - `comments_ref: ticket.comments_cache`
6. 更新 `meta.json.phase = "doc-librarian"`、`agent = "doc-librarian"`

---

### BRANCH-B：ask-user（已绑定，等待用户意图）

读取当前状态（用于 prompt 上下文）：
- `story_id = ticket.local_mapping.story_id`
- 最近任务 = `reports/tasks/_index.jsonl` 中 `story_id` 匹配的 `updated_at` 最大的那条
- `contract_status`（读 contract.md frontmatter 的 `status`）、`contract_version`

用 `AskUserQuestion` 呈现三个选项：

```
检测到 STORY-NNN 已存在。
当前状态：
  - 最近任务：<task_id>，phase=<phase>，verdict=<verdict>
  - contract.md status=<status>，version=<version>

请选择：
  [1] 恢复上次挂起的流程（按 meta.phase 路由到对应 agent，不新建 task）
  [2] 检查 TAPD 最新需求是否有变更（新建 task，由 doc-librarian 做语义 diff）
  [3] 取消（仅刷新缓存，不做其它操作）
```

#### 选 1：resume

- 不调用 /task-new
- 读最近 task 的 `meta.json.phase` 和 `agent`，直接路由到对应 agent
- 将该 task_id 写回 `.current_task`
- 输出：`已恢复 TASK-XXX 到 <phase>，agent=<agent>`

#### 选 2：change-check

1. **归档新 description**（不覆盖旧版）：
   ```
   .chatlabs/stories/STORY-NNN/source/tapd-ticket-<ticket_id>-<YYYYMMDD-HHMMSS>.md
   ```
2. **读取当前 contract 版本**：从 `contract.md` frontmatter 读 `version` → `contract_version_at_start`
3. **调用 /task-new**：
   ```
   /task-new STORY-NNN --predecessor <最近 task_id> --trigger requirement-change-check
   ```
   得到新 `task_id`（如 `TASK-STORYNNN-02`）。将 `contract_version_at_start` 回填到新 task 的 `meta.json`
4. **拉 TAPD 最新评论**：调 `/tapd-consensus-fetch <ticket_id> --purpose=change-check`
5. **路由 doc-librarian**（参数同 BRANCH-A，但 source_dir 里此时有多份带时间戳的历史）：
   - doc-librarian 自行决定：
     - 对 source/ 下所有历史版本做语义 diff
     - 无实质变化 → 在 summary.md 写 `verdict=skip-no-change`，不 bump version，退出
     - 有实质变化 → 增量修订 contract.md，按 semver bump version + 写 changelog.md
6. 更新 `meta.json.phase = "doc-librarian"`、`agent = "doc-librarian"`

> **备注**：`trigger_reason = requirement-change-check` 表达的是"**来检查有没有变更**"的意图，而不是"确定有变更"。最终 verdict 由 doc-librarian 写入 summary.md，支持审计追溯（每次检查都留痕迹）。

#### 选 3：cancel

- 仅保留已刷新的 `fields_cache`（无副作用）
- 不调用 /task-new，不启动 agent
- 输出：`已刷新 ticket 缓存，未做其他操作`

---

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id \| tapd_url>` | 是 | TAPD 工单 ID（纯数字）或工单 URL |

## 产出

- 更新/新建 `.chatlabs/tapd/tickets/<ticket_id>.json`
- BRANCH-A：新建 `.chatlabs/stories/STORY-NNN/`、归档 `source/*.md`、新建 TASK 记录、启动 doc-librarian
- BRANCH-B 选 2：新建 TASK 记录、归档新 `source/*.md`、启动 doc-librarian
- BRANCH-B 选 1：更新 `.current_task`、路由到现有 phase
- BRANCH-B 选 3：仅刷新 ticket 缓存

## 失败处理

| 场景 | 行为 |
|------|------|
| 入参格式无法识别 | 输出用法提示，退出 |
| TAPD 拉取失败（404/权限/网络） | 输出错误原因，退出；不创建任何本地记录 |
| entity_type 不是 stories | 拒绝，输出 hint |
| /task-new 失败（BRANCH-A） | 回滚 `local_mapping.story_id` 写入 |
| /task-new 失败（BRANCH-B 选 2） | 保留 `local_mapping.story_id`（原本就存在），归档的 source 文件保留（供下次重试） |
| contract.md frontmatter 格式损坏 | 输出错误 + 提示手动修复，退出；不启动 agent |

## 关联

- 下游调用：
  - `tapd-pull` skill（拉取缓存）
  - `/task-new`（分配 task_id）
  - `/tapd-consensus-fetch`（拉评论）
  - `doc-librarian` agent（生成 / 修订契约，**由 agent 自己判断模式**）
- 后续：`/tapd-consensus-push` 在 contract 冻结后触发

## 设计原则

- **主流程编排在这里，不在 /task-new**：/task-new 只做任务分配
- **编排层不做语义理解**：description 是否有变更、要不要 bump version，由 doc-librarian agent 判断
- **用户意图显式化**：已绑定 ticket 重入时用 AskUserQuestion 让用户明确目的，不自动推断
- **task_id 链式追溯**：每次 BRANCH-A/BRANCH-B 选 2 都新建 task_id，`meta.json.predecessor_task_id` 串起历史；选 1/3 不制造噪音
- **历史版本永不覆盖**：source/ 目录下的 TAPD 需求快照强制带时间戳，doc-librarian 基于目录做历史 diff
