---
name: tapd-consensus
description: 共识文档双向同步：本地 contract.md 摘要 → TAPD 评论；TAPD 评论 → 本地 feedback。被 /tapd-consensus-push 和 /tapd-consensus-fetch 调用。触发关键词：共识、consensus、推共识、拉评审反馈。
---

# TAPD Consensus Skill

> 共识文档版本管理 + 评论标记驱动的双向同步。

## 模式 A：Push（本地 → TAPD）

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `ticket_id` | string | 必填 |
| `version` | int | 自动从 ticket.local_mapping.consensus_version + 1 |
| `dry_run` | bool | 默认 false |

### 流程

```
1. 校验：ticket.local_mapping.story_id 非空
2. 读 contract.md，校验 frontmatter status == "frozen"
3. 提取摘要：
   - 第 1 节"页面结构"：统计页面数
   - 第 2 节"数据模型"：实体数
   - 第 3 节"接口契约"：端点数
   - 第 4 节"业务规则"：规则条数
   - 第 5 节"验收条件"：AC 总数 + 编号区间
   - 解析 changelog.md（如有）：本版本变更点
4. 构造评论文本（4000 字符上限）：
   [CONSENSUS-V{n}]\n\n摘要 + Repo 链接 + 变更点 + 评审请求
5. 人工二次确认（AskUserQuestion）
6. dry_run=true → 打印不推
7. dry_run=false → mcp__chopard-tapd__create_comments
8. 更新 ticket.json：
   - comments_cache 追加
   - local_mapping.consensus_version = new_version
   - last_synced_at = now()
```

## 模式 B：Fetch（TAPD → 本地）

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `ticket_id` | string | 必填 |
| `since` | iso? | 默认 ticket.last_synced_at |

### 流程

```
1. mcp__chopard-tapd__get_comments(entry_id=ticket_id, entry_type="stories", order="created desc", limit=50)
2. 过滤 created > since
3. **同步全量评论到 comments.json**：
   - 调用 comments_cache.sync_comments() 增量追加
   - comments.json 按 created ASC 升序存储所有评论
   - 支持按 marker_filter 和 since 过滤
4. 对每条，识别前缀标记（按 tapd-config.comment_markers 模式）
5. 路由到对应 feedback 目录：
   - APPROVED → feedback/<ts>-approved.md
   - REJECTED → feedback/<ts>-rejected.md + Blocker
   - QA-* → 在 session 输出提示，建议 /tapd-subtask-{close|reopen}
6. 追加 ticket.comments_cache + 更新 last_synced_at
```

### 评论缓存（新增）

**文件结构**：
```
.chatlabs/tapd/tickets/<ticket_id>/
├── <ticket_id>.json      # 现有工单缓存
├── comments.json          # 全量评论缓存
└── _metadata.json         # 增量同步元数据
```

**API 函数**：
- `comments_cache.sync_comments(ticket_id, raw_comments)` — 增量同步
- `comments_cache.get_comments(ticket_id, since, marker_filter)` — 查询
- `comments_cache.mark_as_read(ticket_id, comment_ids)` — 标记已读

## 关键约束

- **评论字符上限**：4000 字符。超 → 截断 + 链接补齐，不强行展开
- **版本号单调递增**：consensus_version 只增不减
- **标记前缀严格匹配**：模式来自 tapd-config.comment_markers，不允许容忍变体（避免歧义）
- **QA-* 标记不直接动状态**：consensus-fetch 只识别和提示，状态变更走 subtask-close/reopen

## 失败处理

| 场景 | 行为 |
|------|------|
| contract 未冻结 | 拒绝 push |
| 评论字符过长 | 截断 + 链接 |
| MCP 失败 | Blocker，consensus_version 不变 |
| 标记格式不规范 | 跳过 + 记 _seen_unparseable.log |

## 依赖 MCP 工具清单

- `mcp__chopard-tapd__create_comments`
- `mcp__chopard-tapd__get_comments`
- `mcp__chopard-tapd__update_comments`（暂不使用，预留）

## 关联

- Commands: `tapd-consensus-push.md`、`tapd-consensus-fetch.md`
- Schema: `tapd-config.schema.json`（comment_markers 段）
