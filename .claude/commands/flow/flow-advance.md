# /flow-advance

> **流程编排推进器**。每个 step 完成后由主 Claude 显式调用一次,推进 flow 到下一步。

## 用法

```
/flow-advance <step_id>
```

例：
```
/flow-advance doc-librarian
/flow-advance planner
/flow-advance generator
```

## 行为

封装 `python .claude/scripts/flow_advance.py complete <step_id>`,职责：

1. 校验 `workflow-state.json.flow.current_step_id == step_id`(防止跳步/错步)
2. 写入 history 条目(含 kind、target、completed_at、result)
3. `current_step_idx += 1`
4. 双写 `phase` / `agent` 字段(等于 next step 的 phase_alias / target)
5. 输出下一步信息:
   ```json
   {
     "ok": true,
     "advanced_from": "doc-librarian",
     "advanced_to": "consensus-push",
     "current_step": {"id": "consensus-push", "kind": "command", "target": "/tapd-consensus-push"},
     "next_step": {...},
     "is_terminal": false
   }
   ```

## 幂等

- 声明的 step_id 已在 history → 输出 `{"ok": true, "noop": true}`,不重复 advance
- 声明的 step_id 与当前不匹配且未 advance 过 → 报错,提示用户检查

## 何时调用

| 调用方 | 触发时机 |
|--------|---------|
| 主 Claude | agent 输出 `[FLOW-COMPLETE: <step_id>]` 后立即调用 |
| 主 Claude | tool kind 的 step 执行完成后(如 vibe 模式 Edit 完成) |
| 主 Claude | gate kind 的 step 收到等待事件后(如 wait-approve 收到 [CONSENSUS-APPROVED]) |

## 不要做什么

- ❌ 不要由 agent 自己调(agent 无 advance 权限,只输出 `[FLOW-COMPLETE]` 信号)
- ❌ 不要在 step 中途调(必须等当前 step 真正完成)
- ❌ 不要跳步(advance 是顺序的,如需跳步用 `--force`)

## 子命令(供调试)

直接调脚本:
```bash
# 检查当前状态(只读)
python .claude/scripts/flow_advance.py check

# 重置到第一步(debug)
python .claude/scripts/flow_advance.py reset

# 初始化(/start-dev-flow 内部调用,用户通常不直接用)
python .claude/scripts/flow_advance.py init --flow-id local-spec --story-id STORY-001 --task-id TASK-...
```
