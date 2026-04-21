# /tapd-ticket-sync

> 拉取我的 TAPD 工单到本地缓存。
>
> **用法**：`/tapd-ticket-sync [--type story|task|bug] [--iteration <id>] [--all]`

## 行为

### 第一步：读取配置
1. 读 `.claude/tapd-config.json`，校验存在
2. 不存在 → 提示先运行 `/tapd-init`，退出

### 第二步：拉取我的工单
1. 默认 `--type story`，可指定 task/bug
2. 调用 `mcp__chopard-tapd__get_todo(workspace_id=..., entity_type=...)` 拉待办
3. 若 `--all` → 改用 `mcp__chopard-tapd__get_stories_or_tasks(owner=..., status!=完成)` 拉所有未完成
4. 若 `--iteration <id>` → 加 `iteration_id=<id>` 过滤
5. 否则若 `tapd-config.json.current_iteration_id` 不为 null → 自动加过滤

### 第三步：写本地缓存
1. 对每条工单：
   - `mcp__chopard-tapd__get_stories_or_tasks(id=<ticket_id>, fields="...,description,iteration_id,module,...")` 拿完整字段
   - 与已有 `.chatlabs/tapd/tickets/<ticket_id>.json` 合并（保留 local_mapping 和 subtasks）
   - schema 校验
2. 更新 `.claude/tapd/_index.jsonl`（覆盖写整文件，因为是全量）
3. 更新 `tapd-config.json.last_sync_at`

### 第四步：输出摘要
```
✓ 已同步 N 条工单（M 新增 / K 更新）
  · STORY-001: 用户登录支持微信扫码（status: planning, 未关联本地）
  · STORY-002: 订单退款流程（status: in_progress, 关联 STORY-002）
下一步：选择 ticket 开工 → /tapd-story-start <ticket_id>
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `--type` | 否 | story/task/bug，默认 story |
| `--iteration <id>` | 否 | 限定迭代 |
| `--all` | 否 | 拉所有未完成（不仅是我的待办） |

## 产出

- `.chatlabs/tapd/tickets/<ticket_id>.json`（多个）
- `.claude/tapd/_index.jsonl`（覆盖写）
- 更新 `tapd-config.json.last_sync_at`

## 失败处理

| 场景 | 行为 |
|------|------|
| 配置文件不存在 | 提示 `/tapd-init`，退出 |
| 单条工单获取失败 | 跳过，记到 Blocker（信息-外部依赖），继续其他 |
| 全部失败 | 写 Blocker + 不动 _index.jsonl |

## 关联

- Skill: `.claude/skills/tapd-pull/SKILL.md`
- Schema: `.claude/templates/schemas/tapd/ticket.schema.json`
- 后续：`/tapd-story-start <ticket_id>`
