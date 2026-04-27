# /task-new

> **纯任务分配命令**。为指定 Story 创建任务记录，分配 task_id，建立目录结构。
>
> **职责边界**：
> - ✅ 解析 story-id、分配 task-id、建目录、写 .current_task、调 TaskCreate
> - ❌ 不判断 contract 状态
> - ❌ 不启动任何 agent
> - ❌ 不做流程编排（编排职责归 `/tapd-story-start` 等流程入口命令）
>
> **使用**：`/task-new <story-id> [--predecessor <task_id>] [--trigger <reason>]`
> - 例：`/task-new STORY-001`
> - 例：`/task-new STORY-001 --predecessor TASK-STORY001-01 --trigger requirement-change`

## 行为

### 第一步：解析 story-id

1. 解析 `<story-id>`（如 `STORY-001`、`1140062001234567`）
2. story-id 为空 → 输出 `用法：/task-new <story-id>`，退出
3. **不校验 contract.md**（那是流程入口命令的职责，/task-new 不关心）

### 第二步：分配 Task ID

扫描 `.chatlabs/reports/tasks/_index.jsonl`，找出该 story 的最大 CASE 编号：

**Task ID 格式**：`TASK-<story_id>-<NN>`
- story_id 是数字（tapd ticket）→ `TASK-<ticket_id>-<NN>`（如 `TASK-1140062001234567-01`）
- story_id 是本地自增（STORY-XXX）→ `TASK-STORY-XXX-<NN>`（如 `TASK-STORY-001-01`）

NN 取 story 内最大值 +1，不足补零：
- 例：`1140062001234567` 已有 `TASK-1140062001234567-01` → 分配 `TASK-1140062001234567-02`
- 例：`STORY-001` 已有 `TASK-STORY-001-01` → 分配 `TASK-STORY-001-02`
- 例：`STORY-001` 无记录 → 分配 `TASK-STORY-001-01`

### 第三步：创建任务目录与 Story 目录

**a. 任务报告目录**（填充模板,**三件套**）：

```
.chatlabs/reports/tasks/TASK-<story_id>-<NN>/
├── meta.json        # 从 _template/meta.json 填充(含 summary 子对象)
├── audit.jsonl      # 从 _template/audit.jsonl 复制(空文件,hook 追加事件)
└── blockers.md      # 不预创建,首次 blocker 写入时由 writer 自动创建
```

> summary.md / file-reads.md / diff-log.md **不再创建** —— summary 合进 meta.json.summary 字段;file-reads 与 diff-log 合并为 audit.jsonl。

**b. Story 目录**（`mkdir -p`，幂等）：

```
.chatlabs/stories/<story-id>/
```

这只是"确保目录存在"，**不创建 contract.md**，也不判断它是否存在。

### 第四步：写入 meta.json 追溯字段

若传入了 `--predecessor` 或 `--trigger`，写入 `meta.json`：

```json
{
  "task_id": "TASK-STORY001-02",
  "story_id": "STORY-001",
  "predecessor_task_id": "TASK-STORY001-01",
  "trigger_reason": "requirement-change",
  ...
}
```

`trigger_reason` 取值：`first-start` | `requirement-change` | `manual` | `defect-fix`（由上游命令决定语义，`/task-new` 不解释）。

未传入 → 两字段保持 `null`。

### 第五步：注册任务索引

追加一行到 `.chatlabs/reports/tasks/_index.jsonl`：

```json
{"task_id":"TASK-STORY001-02","story_id":"STORY-001","phase":"created","keywords":[],"created_at":"2026-04-19T10:00:00+08:00","updated_at":"2026-04-19T10:00:00+08:00","blocker_count":0,"verdict":null,"tags":[]}
```

> 注意：`phase` 初始为 `"created"`（中性），表示"任务已分配，尚未分配到具体 agent"。上游流程入口命令负责后续 phase 流转。

### 第六步：写入 .current_task

```
TASK-STORY001-02
```

### 第七步：TaskCreate

```bash
TaskCreate(
  taskId="TASK-STORY001-02",
  subject="[STORY-001] 任务已创建，等待上游命令路由",
  description="任务记录已分配。Story: STORY-001。\n后续由上游流程入口命令（如 /tapd-story-start）决定 phase 和 agent 路由。"
)
```

### 第八步：输出摘要（不启动 agent）

```
═══════════════════════════════════════
  🆕 任务记录已创建

  Task ID:   TASK-<story_id>-<NN>
  Story:     <story_id>
  任务目录:  .chatlabs/reports/tasks/TASK-<story_id>-<NN>/
  Story 目录: .chatlabs/stories/<story_id>/

  predecessor: <predecessor_task_id>（如有）
  trigger:     <trigger_reason>（如有）

  ℹ️ 任务分配完成，agent 路由由上游命令负责。
═══════════════════════════════════════
```

> **Story ID 规则**：
> - TAPD 工单：直接使用 `ticket_id`（如 `1140062001234567`）
> - 本地 Story：使用 `STORY-<三位序号>`（如 `STORY-001`）

---

## 错误处理

| 场景 | 处理 |
|------|------|
| story-id 为空 | 输出 `用法：/task-new <story-id>`，退出 |
| `_template/meta.json` 或 `_template/audit.jsonl` 缺失 | 输出 `❌ 任务模板缺失（仅需 meta.json + audit.jsonl），请修复 .claude/templates/task-report/`，退出 |
| _index.jsonl 格式损坏 | 尝试修复，备份原文件 |
| 目录已存在（重复创建） | 追加时间戳后缀 |

## 独立调用场景

`/task-new` 可被以下主流程入口命令调用，也可独立使用：

| 调用方 | 场景 |
|--------|------|
| `/tapd-story-start` | TAPD 工单开工，自动分配 task_id |
| 手动执行 | 临时切分子任务（如手动记录一次调试过程） |

**独立执行时，不会自动启动任何 agent**——这是设计意图，避免职责蔓延。
