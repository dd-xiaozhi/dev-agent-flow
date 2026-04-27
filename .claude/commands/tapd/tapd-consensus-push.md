# /tapd-consensus-push

> **[Internal]** 由 doc-librarian 自动调用（流程内）或用户手动调用。

> 把本地共识文档（contract.md）推送到 TAPD Wiki 进行评审。
>
> **核心变更**：从工单评论改为 Wiki 存储，目录结构：`共识文档/{store_name}/{文档名}.md`
>
> **dry-run 默认值**：自动化调用（doc-librarian）→ dry_run=false（真推）；手动调用（用户）→ dry_run=true（预览）
>
> **用法**：`/tapd-consensus-push <story_id> [--store-name <name>] [--dry-run]`

## 目录结构

```
共识文档/                    # 根目录
├── STORY-001/              # store 目录
│   ├── STORY-001 契约文档 v1.0.0.md
│   └── STORY-001 契约文档 v1.0.1.md
└── ...
```

## 行为

### 第一步：前置校验
1. 读取 `project-config.json` 获取 workspace_id
2. 读取 `.chatlabs/tapd/tickets/<ticket_id>.json`
   - 从 `local_mapping.story_id` 获取 story_id
3. 读取 `contract.md`：`.chatlabs/stories/<story_id>/contract.md`
4. 校验 frontmatter `status == "frozen"`，否则拒绝（草稿不外推）

### 第二步：确定 Wiki 层级结构
1. **根目录**：
   - 查找 `wiki_name = "共识文档"` 的 Wiki
   - 不存在则创建：`mcp__chopard-tapd__create_wiki(name="共识文档")`
2. **Store 目录**：
   - 优先级：`--store-name` 参数 > `ticket.local_mapping.store_name` > **实时派生**
   - **实时派生规则**：
     - TAPD story（有 `ticket_id`）：`{ticket_id}-{ticket.fields_cache.name 前30字符slug化}`
       - 示例：`1140062001234567-add-email-login`、`1140062001234567-企微机器人助手`
     - 非 TAPD（本地 story）：`contract.md frontmatter.story_id` 直接作为目录名
   - slug 规则：小写、汉字保留、空格替换为 `-`、去除 `/` 和特殊字符、截断到 50 字符
   - 查找父 Wiki 为根目录、name 为 `{store_name}` 的子 Wiki
   - 不存在则创建

### 第三步：创建/更新 Wiki
1. **版本号**：
   - 查询 store 目录下已有文档数量
   - 新版本 = count + 1，格式 `v{version}.0`（如 v1.0.0, v1.0.1）
2. **Wiki 名称**：`{store_name} 契约文档 v{version}`
3. **Wiki 内容**：
   - 使用完整 contract.md 内容
   - 头部添加评审元信息

### 第四步：预览（dry-run）或执行

**dry_run=true**：
```
┌─ 共识推送预览（Wiki 模式）──────────────────────────────┐
│ Story: STORY-001                                         │
│ Store: STORY-001                                         │
│ 版本: v1.0.0 → v1.0.1                                    │
│ 目录: 共识文档 / STORY-001                               │
│ Wiki 名: STORY-001 契约文档 v1.0.1                       │
│ 字符数: 19272 / 无限制（Wiki 完整推送）                  │
├──────────────────────────────────────────────────────────┤
│ Dry-run：✓ 是                                           │
│ 如需推送，请运行：/tapd-consensus-push STORY-001        │
└──────────────────────────────────────────────────────────┘
```

**dry_run=false**：
1. 调用 `mcp__chopard-tapd__create_wiki`
2. 记录 wiki_id 和 wiki_url

### 第五步：更新本地状态
1. 读取 ticket.json
2. 更新 `local_mapping`：
   - `wiki_id`: 新建的 wiki id
   - `wiki_url`: wiki 链接
   - `consensus_version++`
3. 追加更新记录到 ticket.json
4. 更新 `last_synced_at`

### 第六步：输出结果

**成功**：
```
✓ 契约文档已推送到 TAPD Wiki

  Story:     STORY-001
  Store:     STORY-001
  版本:      v1.0.1
  目录:      共识文档 / STORY-001
  Wiki:      STORY-001 契约文档 v1.0.1
  URL:       https://www.tapd.cn/{workspace_id}/markdown_wikis/show/{wiki_id}

  评审说明：
  - 请在 Wiki 页面进行评审
  - 评审通过后回复 [CONSENSUS-APPROVED]
  - 如有异议回复 [CONSENSUS-REJECTED:原因]
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<story_id>` | 是 | Story ID（如 STORY-001） |
| `--store-name` | 否 | Store 名称，默认从 ticket.json 读取 |
| `--dry-run` | 否 | 仅预览，不真推（默认） |

## 产出

- TAPD Wiki（完整契约文档）
- 更新 `ticket.json.local_mapping`

## 失败处理

| 场景 | 行为 |
|------|------|
| contract.md 未冻结 | 拒绝，提示先冻结 |
| ticket 未绑定 story_id | 拒绝，提示先 /tapd-story-start |
| 根目录创建失败 | 写 Blocker，终止 |
| Wiki 创建失败 | 写 Blocker，consensus_version 不变 |

## 关联

- Skill: `.claude/skills/tapd-consensus/SKILL.md`
- 上游：doc-librarian 冻结 contract
- 配对：`/tapd-consensus-fetch`（从 Wiki 评论拉取评审结果）
