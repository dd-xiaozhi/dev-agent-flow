# /tapd-consensus-fetch

> **[Internal]** 由 start-dev-flow 或 session-start hook 内部调用，用户不直接使用。

> 拉取 TAPD 工单评论中的评审反馈，写入本地 feedback。
>
> **用法**：`/tapd-consensus-fetch <ticket_id> [--since <iso-timestamp>] [--purpose startup|review]`

## 参数说明

| `--purpose` | 场景 | 行为差异 |
|------------|------|---------|
| `startup`（默认） | `/tapd-story-start` 调用 | 只拉评论写 cache；遇到 REJECTED 写 Blocker；**不写 feedback 文件、不路由** |
| `review` | 正常评审流程 | 完整执行：写 feedback + 更新 meta + 自动路由 planner |

## 行为

### 第一步：拉评论
1. 读 `.chatlabs/tapd/tickets/<ticket_id>.json`
2. **同步全量评论到 comments.json**（新增）：
   - 调用 `mcp__chopard-tapd__get_comments(workspace_id=..., entry_id=ticket_id, entry_type="stories", order="created desc", limit=50)`
   - 使用 `comments_cache.py` 的 `sync_comments()` 增量追加到 `comments.json`
   - 按 `created ASC` 升序排序
3. 若 `--since` 传了 → 过滤 `created > since`；否则取 `ticket.last_synced_at` 后的评论

### 第二步：识别标记
1. 对每条评论 `description`，按 `tapd-config.json.comment_markers` 模式匹配前缀
2. 关注：`[CONSENSUS-APPROVED]`、`[CONSENSUS-REJECTED:reason]`、`[QA-PASSED]`、`[QA-REJECTED:reason]`
3. **评论缓存详情**：
   - 使用 `comments_cache.py` 的 `get_comments()` 读取已缓存的全量评论
   - 支持按 `marker_filter` 过滤特定标记类型的评论
   - 支持按 `since` 时间过滤新评论

### 第三步：处理反馈（按反馈类型）

#### 3a. APPROVED

**`--purpose=review` 时**：
- 在 `.chatlabs/stories/<story_id>/feedback/` 下追加 `feedback/<timestamp>-approved.md`
- 更新 `meta.json`：`phase = "planner"`，`verdict = null`
- **自动路由到 planner agent**
- session 输出：
  ```
  ════════════════════════════════════════
    ✅ 契约评审通过（[CONSENSUS-APPROVED] by @{author}）
    自动路由到 planner agent...
  ════════════════════════════════════════
  ```

**`--purpose=startup` 时**：仅输出评审通过状态，不写文件不路由，由调用方决定后续动作

#### 3b. REJECTED

**两种 purpose 都处理**：
- 写 Blocker（信息-契约歧义）到当前 active task 的 `.chatlabs/reports/tasks/<task_id>/blockers.md`
- 标流向：`doc-librarian`
- session 明显提示

**`--purpose=review` 时额外**：
- 写 `feedback/<timestamp>-rejected.md`

#### 3c. QA-* 类

- 与 `/tapd-subtask-close|reopen` 配合，本命令只识别和提示，不直接动子任务状态
- 两种 purpose 行为一致

### 第四步：更新缓存
1. 把识别到的评论追加到 `ticket.comments_cache`（快速索引）
2. **同步全量评论到 comments.json**：
   - 调用 `comments_cache.sync_comments(ticket_id, raw_comments)` 增量追加
   - comments.json 按 `created ASC` 升序存储所有评论
3. 更新 `ticket.last_synced_at = now()`

### 第五步：输出

```
✓ 拉取评论 N 条（M 条带标记）
  · [CONSENSUS-APPROVED] by @lisa, 2026-04-19 21:00
  · [QA-REJECTED:登录后跳转错误] by @qa-bob, 2026-04-19 22:15
✓ 全量评论已缓存至 .chatlabs/tapd/tickets/<ticket_id>/comments.json（N 条，按时间排序）
建议动作：
  · STORY-001 共识已通过，可继续开发
  · TASK-STORY001-03 被打回 → /tapd-subtask-reopen TASK-STORY001-03
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id>` | 是 | TAPD 工单 ID |
| `--since <iso>` | 否 | 起始时间，默认 ticket.last_synced_at |
| `--purpose` | 否 | `startup` 或 `review`，默认 `startup` |

## 产出（按 purpose）

| purpose | feedback 文件 | meta 更新 | 自动路由 |
|---------|-------------|----------|---------|
| `startup` | ❌ | ❌ | ❌ |
| `review` | ✅ | ✅ | ✅ |

## 失败处理

| 场景 | 行为 |
|------|------|
| 无新评论 | 输出"无新反馈"，退出 0 |
| MCP 失败 | 写 Blocker，退出 |
| 标记格式不规范 | 跳过该条，记到 _seen_unparseable.log |

## 关联

- Skill: `.claude/skills/tapd-consensus/SKILL.md`
- 配对：`/tapd-consensus-push`
- 调用方：`/tapd-story-start`（purpose=startup）、`session-start hook`（purpose=review）
