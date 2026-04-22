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

> **Story ID 使用 TAPD ticket_id**：TAPD 工单使用 ticket_id 作为 story_id，保持源系统 ID 一致。

1. **直接使用 ticket_id 作为 story_id**
   - story_id = `<ticket_id>`（如 `1140062001234567`）
   - 写 `ticket.local_mapping.story_id = ticket_id`
   - 目录：`/stories/<ticket_id>/`（如 `/stories/1140062001234567/`）
2. **归档 description**：将 `fields_cache.description` 写到
   ```
   .chatlabs/stories/<ticket_id>/source/tapd-ticket-<ticket_id>-<YYYYMMDD-HHMMSS>.md
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
     - `source_dir: .chatlabs/stories/<ticket_id>/source/`（doc-librarian 自己看目录下文件来决定生成/修订）
     - `tapd_ticket_id`、`tapd_ticket_url`
     - `comments_ref: ticket.comments_cache`
6. 更新 `meta.json.phase = "doc-librarian"`、`agent = "doc-librarian"`

---

### BRANCH-B：auto-judge（已绑定，自动判断意图）

**核心改进**：移除 AskUserQuestion，改为自动判断 + 诊断输出。

读取当前状态：
- `story_id = ticket.local_mapping.story_id`
- 最近任务 = `reports/tasks/_index.jsonl` 中 `story_id` 匹配的 `updated_at` 最大的那条
- `contract_status`（读 contract.md frontmatter 的 `status`）、`contract_version`
- TAPD 最新 description 与本地最近 source 文件的修改时间对比

#### 自动判断逻辑

```
def auto_judge(situation):
    # 1. 等待评审且 TAPD 有 APPROVED 评论 → 自动 resume
    if (meta.phase == "waiting-consensus"
        and TAPD has "[CONSENSUS-APPROVED]" in recent comments):
        return "AUTO_RESUME"

    # 2. 已完成且 verdict == PASS → 提示已完成
    if meta.phase == "done" and meta.verdict == "PASS":
        return "ALREADY_DONE"

    # 3. 上次执行被中断（phase 非 done 且 verdict == null）→ 自动 resume
    if meta.phase != "done" and meta.verdict is None:
        return "AUTO_RESUME"

    # 4. TAPD description 有更新 → 自动 change-check
    if TAPD.description_modified_at > local.source_latest.timestamp:
        return "AUTO_CHANGE_CHECK"

    # 5. 其他情况 → 输出诊断 + 建议
    return "NEED_MANUAL"
```

#### AUTO_RESUME（自动恢复）

- 不调用 /task-new
- 读最近 task 的 `meta.json.phase` 和 `agent`，直接路由到对应 agent
- 将该 task_id 写回 `.current_task`
- 输出：
  ```
  ✓ 自动恢复 STORY-NNN
    Task: TASK-XXX
    Phase: <phase>
    Agent: <agent>
  ```

#### ALREADY_DONE（已完成）

- 输出：
  ```
  ℹ️ STORY-NNN 已完成
    Task: TASK-XXX
    Verdict: PASS
    如需重新开始，请使用 /task-new STORY-NNN --force
  ```

#### AUTO_CHANGE_CHECK（自动变更检查）

1. **归档新 description**（不覆盖旧版）
2. **读取当前 contract 版本**
3. **调用 /task-new**：`/task-new STORY-NNN --predecessor <最近 task_id> --trigger requirement-change-check`
4. **创建 checklog**：
   - 使用 `checklog.py` 的 `create_checklog()` 创建 checklog
   - trigger: `requirement_change`
   - trigger_source: `tapd_description_updated`
   - contract_version_before: 当前 contract 版本
   - 写入 `.chatlabs/stories/<story_id>/checklogs/`
5. **拉 TAPD 最新评论**
6. **路由 doc-librarian**（传入 `checklog_ref`）
7. 输出：
   ```
   ✓ 检测到需求变更，自动发起变更检查
     Task: TASK-XXX
     Story: STORY-NNN
     Checklog: CHECK-XXX
   ```

#### NEED_MANUAL（需手动判断）

输出诊断信息 + 建议：
```
⚠️ 无法自动判断意图，请检查以下状态：

STORY-NNN 当前状态：
  - 最近任务：TASK-XXX
  - Phase: <phase>
  - Verdict: <verdict>
  - Contract: <status> v<version>

建议操作：
  [1] 恢复执行：/task-resume TASK-XXX
  [2] 重新开始：/task-new STORY-NNN --force
  [3] 检查变更：手动归档新需求后路由到 doc-librarian
```

---

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id \| tapd_url>` | 是 | TAPD 工单 ID（纯数字）或工单 URL |

## 产出

- 更新/新建 `.chatlabs/tapd/tickets/<ticket_id>.json`
- BRANCH-A：新建 `.chatlabs/stories/STORY-NNN/`、归档 `source/*.md`、新建 TASK 记录、启动 doc-librarian
- BRANCH-B AUTO_RESUME：更新 `.current_task`、路由到现有 phase
- BRANCH-B AUTO_CHANGE_CHECK：新建 TASK 记录、归档新 `source/*.md`、启动 doc-librarian
- BRANCH-B ALREADY_DONE：仅输出状态
- BRANCH-B NEED_MANUAL：仅输出诊断信息

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
- **自动优先**：BRANCH-B 使用自动判断逻辑，只有无法判断时才输出诊断信息
- **task_id 链式追溯**：每次 BRANCH-A/BRANCH-B-AUTO_CHANGE_CHECK 都新建 task_id，`meta.json.predecessor_task_id` 串起历史
- **历史版本永不覆盖**：source/ 目录下的 TAPD 需求快照强制带时间戳，doc-librarian 基于目录做历史 diff
