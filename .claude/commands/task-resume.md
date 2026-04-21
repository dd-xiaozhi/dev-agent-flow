# /task-resume

> 续接已存在的任务，从上次断点继续执行。
>
> **使用**：`/task-resume <task-id> [--verbose]`
> - 例：`/task-resume TASK-STORY001-01`
> - `--verbose`：额外注入 diff-log.md 末尾 30 行（默认只注入 summary）

## 行为

### 第一步：解析与校验

1. 解析 `<task-id>`（格式：`TASK-<STORY>-<NN>`）
2. 检查 `.chatlabs/reports/tasks/<task-id>/meta.json` 是否存在
   - **不存在** → 输出：`❌ 任务不存在：<task-id>`
3. 读取 `meta.json`，获取 `phase` 和 `agent`

### 第二步：加载任务上下文

按需读取以下文件（**按需加载，不全部塞入 context**）：

| 文件 | 何时读取 | 注入方式 |
|------|---------|---------|
| `meta.json` | **始终** | 摘要输出至 session |
| `summary.md` | **始终** | 注入全文 |
| `blockers.md` | **始终**（若 blocker_count > 0） | 注入摘要 |
| `diff-log.md` | `--verbose` 时 | 注入末尾 30 行 |
| `file-reads.md` | `--verbose` 时 | 注入文件列表 |

### 第三步：扫描相关历史任务

扫描 `_index.jsonl`，列出同 `story_id` 的已完成任务：

```bash
jq 'select(.story_id == "<story_id>" and .phase == "done")' .chatlabs/reports/tasks/_index.jsonl
```

若有，输出：
```
📦 同 Story 已完成任务（共 N 个）：
  - TASK-STORY001-01: doc-librarian ✅ PASS
  （Agent 可选读取其 summary.md 了解历史）
```

### 第四步：TaskUpdate 恢复任务

```bash
TaskUpdate(
  taskId="TASK-STORY001-01",
  status="in_progress"
)
```

### 第五步：更新 .current_task

```bash
echo "TASK-STORY001-01" > .chatlabs/state/current_task
```

### 第六步：上下文注入

```
═══════════════════════════════════════
  🔄 任务已续接

  Task ID:   TASK-STORY001-01
  Story:     STORY-001
  Phase:     {phase}（从 meta.json 读取）
  Agent:     {agent}
  Blocker:   {blocker_count} 条（见 blockers.md）

  📂 历史产出：
    summary.md:  ✅ 已读取
    blockers.md: {blocker_count} 条

  📝 上次执行摘要：
    {summary.md 前 300 字摘要}

  ⏸️ 阻塞点（如有）：
    {blockers.md 中待解决的条目}

  💡 提示：历史 summary 可通过 grep 或 Read 工具访问
═══════════════════════════════════════
```

### 第七步：根据 phase 续接

| phase | 续接动作 |
|-------|---------|
| `doc-librarian` | 路由至 doc-librarian agent |
| `waiting-consensus` | 自动执行 `/tapd-consensus-fetch` 检查 PM 评审结果 |
| `planner` | 路由至 planner agent |
| `generator` | 路由至 generator agent |
| `evaluator` | 路由至 evaluator agent |
| `done` | 输出：`✅ 任务已完成，无需续接` |

---

## 禁止事项

- ❌ 不重新执行 `phase: done` 的阶段
- ❌ 不删除历史 blockers.md（历史数据是趋势分析基础）
- ❌ 不修改已完成阶段的 diff-log.md
- ❌ 不加载全部 file-reads.md 到 context（只用 `--verbose` 时才注入末尾片段）

---

## 错误处理

| 场景 | 处理 |
|------|------|
| task-id 格式错误 | 输出：`❌ 格式应为 TASK-<STORY>-<NN>：`/task-resume TASK-EXAMPLE-01`` |
| meta.json 不存在 | 输出：`❌ 任务目录不存在：`.chatlabs/reports/tasks/<task-id>/`` |
| phase == done | 输出：`✅ 此任务已标记为完成`，不更新 .current_task |
