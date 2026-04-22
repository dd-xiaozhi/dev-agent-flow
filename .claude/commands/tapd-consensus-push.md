# /tapd-consensus-push

> **[Internal]** 由 start-dev-flow 或 session-start hook 内部调用，用户不直接使用。

> 把本地共识文档（contract.md 摘要）推送到 TAPD 工单评论。
>
> **用法**：`/tapd-consensus-push <ticket_id> [--dry-run] [--confirm]`

## 核心改进

**移除强制人工确认**。改为：
- `dry_run=true` → 显示预览 + 不执行
- `dry_run=false` → 直接执行 + 结果摘要
- `--confirm` → 可选显式确认（仅用于高风险场景）

## 行为

### 第一步：前置校验
1. 读 `.chatlabs/tapd/tickets/<ticket_id>.json`
2. 校验 `local_mapping.story_id != null`，否则拒绝
3. 读 contract.md：`.chatlabs/stories/<story_id>/contract.md`
4. 校验 contract.md frontmatter `status == "frozen"`，否则拒绝（草稿不外推）

### 第二步：构造评论
1. 计算新版本号：`new_version = local_mapping.consensus_version + 1`
2. 读 `tapd-config.json.comment_markers.consensus`，替换 `{n}` → `new_version`
3. 评论正文模板：
   ```
   [CONSENSUS-V{n}]

   📄 共识文档已更新（版本 {n}）

   摘要：
   - 页面数：N
   - 数据模型实体：M
   - API 端点：K
   - 业务规则：L 条
   - 验收条件：AC-001 ~ AC-NNN（共 X 条）

   完整文档：{repo_url}/blob/main/.chatlabs/stories/STORY-NNN/contract.md
   OpenAPI：{repo_url}/blob/main/.chatlabs/stories/STORY-NNN/openapi.yaml

   变更点（vs V{n-1}）：
   - {changelog 第一条}
   - ...

   ⚠️ 请评审。如同意，回复评论 [CONSENSUS-APPROVED]；如有异议，回复 [CONSENSUS-REJECTED:原因]
   ```
4. 评论字符上限保护：超 4000 字符 → 截断 + 链接补齐

### 第三步：预览（dry-run）或执行

**dry_run=true**：
```
┌─ 共识推送预览 ─────────────────────────────────────┐
│ Ticket: STORY-123                                  │
│ 版本: V3 → V4                                       │
├────────────────────────────────────────────────────┤
│ [CONSENSUS-V4]                                      │
│                                                    │
│ 📄 共识文档已更新（版本 4）                          │
│ ...（完整评论内容）                                  │
├────────────────────────────────────────────────────┤
│ 字符数：1234 / 4000                                 │
│ Dry-run：✓ 是                                       │
├────────────────────────────────────────────────────┤
│ 如需推送，请运行：                                   │
│   /tapd-consensus-push STORY-123                   │
└────────────────────────────────────────────────────┘
```

**dry_run=false**：
1. 直接推送，不等待确认
2. 评论字符超限仍截断，但保留完整版到本地日志
3. `mcp__chopard-tapd__create_comments(...)`

### 第四步：更新本地状态
1. 拿到评论 id，追加到 `ticket.comments_cache`
2. 更新 `ticket.local_mapping.consensus_version = new_version`
3. 更新 `ticket.last_synced_at`

### 第五步：输出结果

**成功**：
```
✓ [CONSENSUS-V{n}] 已推送到 TAPD
  Story: {story_id}
  版本: V{n}
  评论: {n_lines} 行
  URL: {comment_url}
```

**dry-run**：
```
🔍 Dry-run 完成（未实际推送）
  如需推送，请去掉 --dry-run 参数
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id>` | 是 | TAPD 工单 ID |
| `--dry-run` | 否 | 仅预览，不真推（默认） |
| `--confirm` | 否 | 显式确认后才执行（用于高风险场景） |

## 产出

- TAPD 评论（带 [CONSENSUS-V{n}] 标记）
- 更新 `ticket.json.comments_cache` + `consensus_version`

## 失败处理

| 场景 | 行为 |
|------|------|
| contract.md 未冻结 | 拒绝，提示先冻结 |
| ticket 未绑定 story_id | 拒绝，提示先 /tapd-story-start |
| 评论字符超限 | 截断 + 链接补齐，但保留完整版到本地日志 |
| MCP 调用失败 | FATAL Blocker（外部依赖失败），不更新 consensus_version |

## 关联

- Skill: `.claude/skills/tapd-consensus/SKILL.md`
- 上游：doc-librarian 冻结 contract
- 配对：`/tapd-consensus-fetch`
