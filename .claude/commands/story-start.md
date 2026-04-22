# /story-start

> **本地 Story 入口命令**。不依赖 TAPD，直接从本地 description 开工。
>
> 适用于：技术债 refactor、线上 hotfix、突发想法、无 TAPD ticket 的任务。
>
> **编排层只做任务分配，不做语义理解。**

## 行为

### 第一步：解析 description

1. 入参为纯文本 description（可带换行）
2. description 为空 → 输出用法，退出
3. 用 `/story-start <description>` 或 heredoc 格式均可

### 第二步：分配 STORY-NNN（本地自增 ID）

扫描 `.chatlabs/stories/` 已有编号，递增分配 `STORY-NNN`：
- 本地 story 使用自增格式：`STORY-001`、`STORY-002`...
- ID 规则：`STORY-<三位序号>`，序号从项目内最大值 +1

### 第三步：归档 source

将 description 写到：
```
.chatlabs/stories/STORY-NNN/source/local-description-<YYYYMMDD-HHMMSS>.md
```
文件内容格式：
```markdown
---
source: local
created_at: <timestamp>
---

<description>
```

### 第四步：调用 /task-new

```
/task-new STORY-NNN --trigger first-start
```
得到 `task_id = TASK-STORYNNN-01`

### 第五步：路由 doc-librarian

- `story_id = STORY-NNN`
- `task_id = TASK-STORYNNN-01`
- `contract_path: .chatlabs/stories/STORY-NNN/contract.md`
- `source_dir: .chatlabs/stories/STORY-NNN/source/`
- `tapd_ticket_id: null`（本地入口无 TAPD 关联）
- `tapd_ticket_url: null`
- `comments_ref: []`（无 TAPD 评论）

### 第六步：更新 meta.json

```json
{
  "phase": "doc-librarian",
  "agent": "doc-librarian"
}
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<description>` | 是 | Story 描述（纯文本，可多行） |

## 产出

- 新建 `.chatlabs/stories/STORY-NNN/`
- 归档 `source/local-description-*.md`
- 新建 TASK 记录
- 启动 doc-librarian agent

## 与 /tapd-story-start 的关系

| 维度 | /tapd-story-start | /story-start |
|------|------------------|-------------|
| 来源 | TAPD 工单 | 本地 description |
| 入口 | URL / ticket_id | 纯文本 |
| TAPD 评论 | ✅ 拉取 | ❌ 无 |
| local_mapping | ticket→story | 无 TAPD 绑定 |
| 后续 PM 评审 | /tapd-consensus-push | 手动方式或跳过 |

两者最终都路由到 **doc-librarian**，后续流程完全一致。

## 失败处理

| 场景 | 行为 |
|------|------|
| description 为空 | 输出用法，退出 |
| STORY 目录已存在 | 正常幂等（扫描逻辑保证不冲突） |
| /task-new 失败 | 回滚 story 目录写入 |
| contract.md frontmatter 损坏 | 输出错误，退出 |

## 第七步：AI 自审（理解阶段）

在 doc-librarian 阶段完成后，调用 `self-reflect` skill：

```
Skill: self-reflect
trigger: story-start
context_ref: STORY-NNN
```

**时机**：当 doc-librarian 输出了对需求的理解（无论是生成新契约还是修订），在路由到下一步前，自审理解质量。

**重点自审**：
- understanding 维度：边界条件、异常路径、数据约束是否已识别
- compliance 维度：是否参照了 spec/INDEX.md 的规范

## 关联

- 下游调用：`/task-new`（分配 task_id）
- doc-librarian（生成契约，由 agent 自行判断 generate/revise 模式）
- 后续（可选）：`/tapd-consensus-push`（若需 TAPD 评审，需手动绑定 ticket）
