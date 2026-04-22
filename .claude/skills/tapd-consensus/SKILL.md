# TAPD Consensus Skill（Wiki 模式）

> 共识文档版本管理 + Wiki 驱动的双向同步。
>
> **核心变更**：共识文档推送到 TAPD Wiki 进行评审，而不是工单评论。
> - 根目录：`共识文档`
> - 每个 store（需求）单独一个目录
> - 目录下存放多个版本的契约文档
> - 文档名：`{store_name} 契约文档 v{version}`

## 目录结构

```
共识文档/
├── {store_name}/
│   ├── {store_name} 契约文档 v1.0.0.md
│   ├── {store_name} 契约文档 v1.0.1.md
│   └── ...
└── ...
```

## 模式 A：Push（本地 → TAPD Wiki）

### 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `story_id` | string | 必填，如 STORY-001 |
| `store_name` | string | 可选，默认从 ticket.json.local_mapping 读取 |
| `dry_run` | bool | 默认 false |

### 流程

```
1. 校验：ticket.json.local_mapping.story_id 非空
2. 读 contract.md，校验 frontmatter status == "frozen"
3. 确定 store_name：
   - 优先使用参数传入的 store_name
   - 次优先：ticket.json.local_mapping.store_name
   - 默认：从 story_id 推导（如 STORY-001 → "STORY-001"）
4. 确定父 Wiki ID：
   - 尝试查找根目录 "共识文档"（wiki_name = "共识文档"）
   - 如不存在，创建根目录
   - 查找/创建 store 子目录
5. 确定版本号：
   - 查询 store 目录下已有的文档数
   - 新版本 = count + 1
6. 构造 Wiki 内容：
   - 使用完整 contract.md 内容（Markdown）
   - 头部添加元信息（版本、状态、评审状态）
7. dry_run=true → 打印预览
8. dry_run=false → 创建/更新 Wiki
9. 更新 ticket.json：
   - local_mapping.wiki_id = 新建的 wiki id
   - local_mapping.wiki_url = wiki 链接
   - local_mapping.consensus_version++
   - last_synced_at = now()
```

### Wiki 命名规则

- 根目录：`共识文档`
- Store 目录：`{store_name}`（如 "STORY-001"、"企微机器人助手"）
- 文档：`{store_name} 契约文档 v{version}.md`

## 模式 B：Fetch（TAPD Wiki → 本地评审状态）

### 流程

```
1. 读取 ticket.json，获取 local_mapping.wiki_id
2. 调用 get_wiki 获取 Wiki 详情
3. 检查 Wiki 内容中的评审状态标记：
   - [CONSENSUS-APPROVED] → 评审通过
   - [CONSENSUS-REJECTED:reason] → 评审拒绝
4. 更新本地状态
```

### 评审流程说明

评审在 TAPD Wiki 上进行，评审人通过以下方式反馈：
- Wiki 评论：[CONSENSUS-APPROVED] / [CONSENSUS-REJECTED:reason]
- 或工单评论引用 Wiki 链接

## 关键约束

- **文档内容完整**：Wiki 推送完整的 contract.md，不截断
- **版本号单调递增**：consensus_version 只增不减
- **目录结构稳定**：根目录和 store 目录创建后复用
- **向后兼容**：旧的评论模式仍然可用（已废弃）

## Wiki 元信息模板

```markdown
---
title: {store_name} 契约文档 v{version}
story_id: {story_id}
status: frozen
version: v{version}
created_at: {timestamp}
评审状态: 待评审
---

# {store_name} 契约文档

> **版本**: v{version}
> **状态**: frozen
> **STORY**: [{story_id}]({tapd_story_url})
> **评审状态**: 🔄 待评审

---

## 完整契约文档内容

...（contract.md 全文）...

---

*此文档由 Flow 自动生成于 {timestamp}*
```

## 失败处理

| 场景 | 行为 |
|------|------|
| contract 未冻结 | 拒绝 push |
| Wiki 创建失败 | 写 Blocker，consensus_version 不变 |
| 根目录查找失败 | 自动创建 "共识文档" 目录 |

## 依赖 MCP 工具清单

- `mcp__chopard-tapd__create_wiki` - 创建 Wiki
- `mcp__chopard-tapd__get_wiki` - 获取 Wiki 详情
- `mcp__chopard-tapd__update_wiki` - 更新 Wiki（如需）
- `mcp__chopard-tapd__get_comments` - 获取 Wiki 评论（评审反馈）

## 关联

- Commands: `tapd-consensus-push.md`、`tapd-consensus-fetch.md`
- Schema: `tapd-config.schema.json`
