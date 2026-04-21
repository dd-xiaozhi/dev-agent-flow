# /tapd-consensus-push

> 把本地共识文档（contract.md 摘要）推送到 TAPD 工单评论。
>
> **用法**：`/tapd-consensus-push <ticket_id> [--dry-run]`

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

### 第三步：人工二次确认（强制）
用 AskUserQuestion 展示完整评论文本，让用户确认：
- 是 → 推送
- 否 → 退出，不推
- `--dry-run` → 跳过推送，仅打印

### 第四步：推送
1. `mcp__chopard-tapd__create_comments(workspace_id=..., entry_id=ticket_id, entry_type="stories", description=..., author=owner_nick)`
2. 拿到评论 id，追加到 `ticket.comments_cache`
3. 更新 `ticket.local_mapping.consensus_version = new_version`
4. 更新 `ticket.last_synced_at`

### 第五步：输出
```
✓ 共识文档 V{n} 已推送到 TAPD
  ticket: {ticket_url}
  comment_id: {id}
下一步：等待评审反馈 → /tapd-consensus-fetch <ticket_id>
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id>` | 是 | TAPD 工单 ID |
| `--dry-run` | 否 | 仅预览，不真推 |

## 产出

- TAPD 评论（带 [CONSENSUS-V{n}] 标记）
- 更新 `ticket.json.comments_cache` + `consensus_version`

## 失败处理

| 场景 | 行为 |
|------|------|
| contract.md 未冻结 | 拒绝，提示先冻结 |
| ticket 未绑定 story_id | 拒绝，提示先 /tapd-story-start |
| 评论字符超限 | 截断 + 链接补齐，但保留完整版到本地日志 |
| MCP 调用失败 | 写 Blocker（信息-外部依赖），不更新 consensus_version |

## 关联

- Skill: `.claude/skills/tapd-consensus/SKILL.md`
- 上游：doc-librarian 冻结 contract
- 配对：`/tapd-consensus-fetch`
