---
name: tapd-subtask
description: 子任务派发与状态机管理。emit 派发 cases 到 TAPD；close/reopen 双向同步状态。强制走"工作流前置三检查"。被 /tapd-subtask-emit、close、reopen 调用。触发关键词：子任务派发、subtask emit、QA 通过、QA 打回。
---

# TAPD Subtask Skill

> 子任务生命周期 + 状态机。**所有状态变更必须走"工作流前置三检查"**。

## Blocker 等级系统

| 等级 | 行为 | 触发条件 |
|------|------|----------|
| **FATAL** | 立即阻塞执行，抛出 Blocker | 状态不可达、TAPD API 失败、配置缺失 |
| **WARN** | 记录到 warnings[]，汇总后一次性展示 | 状态映射陈旧、检测到历史数据不一致 |
| **INFO** | 仅记录日志，不影响执行 | 发现潜在问题但不影响主流程 |

**原则**：非阻塞问题不逐个询问，汇总后一次性展示。

---

## 工作流前置三检查

```python
# 类型定义
@dataclass
class TransitionWarning:
    level: Literal["WARN", "INFO"]
    type: str
    message: str
    suggestion: str | None = None

class FatalBlocker(Exception):
    def __init__(self, error_type: str, message: str, **details):
        self.error_type = error_type
        self.details = details
        super().__init__(f"[FATAL-{error_type}] {message}")

def check_transition(entity_type, current_status, target_local_key) -> tuple[str, list[TransitionWarning]]:
    """
    检查状态转换合法性。

    Returns:
        tuple: (target_status, warnings)
        - target_status: 目标枚举状态
        - warnings: 非阻塞警告列表（汇总后展示）
    """
    config = read project-config.json
    warnings = []

    # 1. 获取目标状态
    target_status = config.status_map[entity_type][target_local_key]

    # 2. 检查目标状态是否在枚举中（WARN）
    if target_status not in config.status_enum[entity_type]:
        warnings.append(TransitionWarning(
            level="WARN",
            type="status_map_stale",
            message=f"状态映射陈旧：{target_local_key} → {target_status}",
            suggestion=f"建议更新为枚举中的状态值"
        ))

    # 3. 检查目标状态是否仍存在于当前工作流（WARN）
    map = mcp__chopard-tapd__get_workflows_status_map(system=entity_type, workitem_type_id=...)
    if target_status not in map:
        suggestions = [s for s in config.status_enum[entity_type] if s in map]
        warnings.append(TransitionWarning(
            level="WARN",
            type="status_not_in_workflow",
            message=f"状态 {target_status} 在当前工作流不存在",
            suggestion=f"建议更新为：{suggestions[0] if suggestions else '请重新探测'}"
        ))

    # 4. 检查流转是否合法（FATAL 立即阻塞）
    transitions = mcp__chopard-tapd__get_workflows_all_transitions(...)
    allowed_targets = [t[1] for t in transitions if t[0] == current_status]

    if target_status not in allowed_targets:
        raise FatalBlocker(
            "transition_invalid",
            f"状态不可达：{current_status} → {target_status}",
            current=current_status,
            target=target_status,
            allowed=allowed_targets
        )

    return target_status, warnings
```

---

## 警告汇总展示

```python
def summarize_warnings(warnings: list[TransitionWarning], command_name: str):
    """命令结束时统一展示非阻塞警告"""
    if not warnings:
        return

    print(f"\n⚠️ [{command_name}] 发现以下非阻塞问题：")
    print("─" * 50)

    for w in warnings:
        icon = "🔶" if w.level == "WARN" else "ℹ️"
        print(f"{icon} [{w.level}] {w.message}")
        if w.suggestion:
            print(f"   → 建议：{w.suggestion}")

    print("─" * 50)
    print("已自动继续执行。如需处理，请在适当时机运行 /tapd-init 更新配置。\n")
```

---

## Mode A：Emit

### 输入
| 参数 | 类型 |
|------|------|
| `ticket_id` | string |
| `force` | bool |
| `dry_run` | bool |

### 流程
```
1. 校验：consensus_version > 0、subtask_emitted == false（除非 --force）
2. 读 cases/*.md 列表
3. 对每个 case，构造 task 对象
   - 前缀规则：按 case type 确定实现者角色前缀
     - `type=backend → 【BE】`（后端实现）
     - `type=frontend → 【FE】`（前端实现）
     - `type=infra → 【INFRA】`（基础设施）
     - `type=doc → 【DOC】`（文档）
     - type 未知或为空 → 不加前缀
   - 去掉 title 中已有的项目标识前缀（如 `[bde-simple-report]`、`[xxx]`、`【xxx】`）
4. dry_run=true → 显示预览 + 不执行
5. dry_run=false → 批量 mcp__chopard-tapd__create_story_or_task(...)
6. 失败的 case 记录到 failures[] + 继续执行
7. 写回 ticket.subtasks
8. 评论 [SUBTASK-EMITTED]
9. summarize_warnings(warnings)
```

### 关键约束
- **无需人工确认**：预览通过 dry_run 模式展示
- **失败不阻塞**：单个 case 失败记录后继续派发其他 case

---

## Mode B：Close

### 输入
| 参数 | 类型 |
|------|------|
| `case_id` | string（本地 TASK-* ID） |

### 流程
```
1. 读 meta.json，校验 verdict == "PASS"（否则 FATAL）
2. 反查 ticket_id（_index.jsonl + ticket.subtasks 匹配 local_case_id）
3. 走"工作流前置三检查"：current_status → to_test
4. mcp__chopard-tapd__update_story_or_task(..., v_status=to_test_chinese)
5. 验证：mcp__chopard-tapd__get_stories_or_tasks(id=..., fields="id,status")
6. 评论 [QA-PASSED] 占位
7. 更新 ticket.subtasks[*].local_phase=done、tapd_status=...
8. summarize_warnings(warnings)
```

### 关键约束
- **verdict != PASS → FATAL**：必须 evaluator 通过才能 close
- **本地状态先更**：失败可自然回滚

---

## Mode C：Reopen

### 输入
| 参数 | 类型 |
|------|------|
| `case_id` | string |
| `reason` | string（≥5字符） |

### 流程
```
1. 校验 reason 非空（≥5字符）、meta.phase == "done"
2. 反查 ticket + subtask
3. 工作流三检查：current_status → to_dev
4. 本地：meta.phase = in_progress、verdict = WIP
5. blockers.md 追加 [QA 打回] 条目（首次写入时由 writer 自动创建）
6. mcp__chopard-tapd__update_story_or_task(..., v_status=to_dev_chinese)
7. mcp__chopard-tapd__create_comments [QA-REJECTED:{reason}]
8. 更新 ticket.subtasks[*].local_phase=in_progress
9. summarize_warnings(warnings)
```

### 关键约束
- **reason 太短 → FATAL**：防止无效打回理由
- **phase != done → FATAL**：防止重复打回

---

## Blocker 类型定义

| error_type | FATAL 条件 | 处理建议 |
|------------|-----------|----------|
| `transition_invalid` | 状态不可达 | 检查 transitions 配置 |
| `verdict_not_pass` | verdict != PASS | 先运行 evaluator |
| `phase_invalid` | phase != done | 检查 subtask 当前状态 |
| `reason_too_short` | reason 长度 < 5 | 提供更详细的打回理由 |
| `mcp_api_failed` | MCP 调用失败 | 检查 MCP 连接或 TAPD 权限 |
| `config_missing` | 配置文件不存在 | 运行 /tapd-init 初始化 |

## 依赖 MCP 工具清单

- `mcp__chopard-tapd__create_story_or_task`
- `mcp__chopard-tapd__update_story_or_task`
- `mcp__chopard-tapd__get_stories_or_tasks`
- `mcp__chopard-tapd__get_workflows_status_map`
- `mcp__chopard-tapd__get_workflows_all_transitions`
- `mcp__chopard-tapd__create_comments`

## 关联

- Commands: `tapd-subtask-emit.md`、`tapd-subtask-close.md`、`tapd-subtask-reopen.md`
- Schema: `ticket.schema.json`（subtasks 段）+ `tapd-config.schema.json`（status_enum/transitions 段）
- Types: `status-enum.ts`（状态枚举定义）
