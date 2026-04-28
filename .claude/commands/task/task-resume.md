# /task-resume

> 续接已存在的任务，从上次断点继续执行。
>
> **使用**：`/task-resume <task-id> [--verbose]`
> - 例：`/task-resume TASK-STORY001-01`
> - `--verbose`：额外注入 audit.jsonl 末尾 50 行（默认只注入 meta.json.summary）

## 行为

### 第一步：解析与校验

1. 解析 `<task-id>`（格式：`TASK-<STORY>-<NN>`）
2. 检查 `.chatlabs/reports/tasks/<task-id>/meta.json` 是否存在
   - **不存在** → 输出：`❌ 任务不存在：<task-id>`
3. 读取 `meta.json`,获取 `story_id`(用于定位 workflow-state.json)
4. **读 flow 状态**:
   ```bash
   python .claude/scripts/flow_advance.py --story-id <story_id> check
   ```
   输出 JSON 含 `flow_id` / `current_step` / `next_step` / `is_terminal`,后续路由仅依赖此输出。
   - 输出 `{"ok": false, "error": "no flow initialized"}` → 任务未走流程编排,提示用户用 /start-dev-flow 重新开始

### 第二步：加载任务上下文

按需读取以下文件（**按需加载，不全部塞入 context**）：

| 文件 | 何时读取 | 注入方式 |
|------|---------|---------|
| `meta.json` | **始终** | 基本字段摘要 + `summary` 子对象全文 |
| `blockers.md` | 仅当存在且 `blocker_count > 0` | 注入摘要(文件不存在则 skip) |
| `audit.jsonl` | `--verbose` 时 | 注入末尾 50 行(每行一个事件) |

### 第三步：扫描相关历史任务

扫描 `_index.jsonl`，列出同 `story_id` 的已完成任务(以 `verdict == "PASS"` 或 task 自身 flow.is_terminal 判断)：

```bash
jq 'select(.story_id == "<story_id>" and .verdict == "PASS")' .chatlabs/reports/tasks/_index.jsonl
```

若有，输出：
```
📦 同 Story 已完成任务（共 N 个）：
  - TASK-STORY001-01: <flow_id> ✅ PASS
  （Agent 可选读取其 meta.json.summary 了解历史）
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

  Task ID:    TASK-STORY001-01
  Story:      STORY-001
  Flow:       {flow_id}(local-vibe / local-plan / local-spec / tapd-full)
  当前 Step:  {current_step.id} (kind={current_step.kind}, target={current_step.target})
  下一 Step:  {next_step.id 或 "(终点)"}
  History:   {history_count} 步已完成
  Blocker:    {blocker_count} 条(见 blockers.md,若存在)

  📂 历史产出:
    meta.summary: ✅ 已注入(含 execution_log / key_decisions / deliverables)
    blockers.md:  {blocker_count} 条(不存在时省略)
    audit.jsonl:  仅 --verbose 时注入末尾 50 行

  📝 上次执行摘要:
    {meta.summary.execution_log 前 300 字}

  ⏸️ 阻塞点(如有):
    {blockers.md 中待解决的条目,若文件不存在则省略本节}

  💡 提示:完整 audit.jsonl / blockers.md 可通过 Read 工具按需访问
═══════════════════════════════════════
```

### 第七步:根据 flow.current_step 续接

**唯一路由依据是 `current_step.kind` + `current_step.target`**(不再读 phase 字段)。

| current_step.kind | 续接动作 |
|-------------------|---------|
| `agent` | 路由至 `target` 指定的 agent(doc-librarian / planner / generator / evaluator) |
| `command` | 主 Claude 调用 `target` 指定的 slash command(如 /tapd-consensus-push) |
| `skill` | 主 Claude 调用 `target` 指定的 skill(如 tapd-pull) |
| `tool` | 主 Claude 直接用 `target` 工具(Edit / TaskCreate)继续 |
| `gate` | 检查 `gate_event` 是否在 events.jsonl 出现:已出现则提示用户调 `/flow-advance`,未出现则输出"等待中" |
| `terminal` | 输出 `✅ 任务已完成,无需续接` |

### 第八步:每步完成后

每个 step 完成后,主 Claude 必须调用一次 `/flow-advance <step_id>` 推进到下一步。
**禁止**直接修改 phase / agent 字段或 workflow-state.json,所有推进必须通过 flow_advance.py。

---

## 禁止事项

- ❌ 不重新执行 `phase: done` 的阶段
- ❌ 不删除历史 blockers.md（历史数据是趋势分析基础）
- ❌ 不修改已完成阶段的 audit.jsonl
- ❌ 不加载全部 audit.jsonl 到 context（仅 `--verbose` 时注入末尾 50 行）

---

## 错误处理

| 场景 | 处理 |
|------|------|
| task-id 格式错误 | 输出：`❌ 格式应为 TASK-<STORY>-<NN>：`/task-resume TASK-EXAMPLE-01`` |
| meta.json 不存在 | 输出：`❌ 任务目录不存在：`.chatlabs/reports/tasks/<task-id>/`` |
| flow.is_terminal == true | 输出：`✅ 此任务已走完 flow,无需续接`,不更新 .current_task |
| flow 未初始化(state.flow == null) | 输出:`❌ 任务未通过 /start-dev-flow 创建 flow,请重新开始或手动 init` |
