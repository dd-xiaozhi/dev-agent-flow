# 模块：hooks/

## Overview

7 个事件钩子，挂载在 Claude Code 生命周期事件上。所有 hook 必须**三层降级**——绝不能因自身失败阻断主流程。

## API 端点

不适用（hook 通过 stdin 接收 JSON，stdout/stderr + exit code 反馈）。

## 领域模型

| Hook | 挂载事件 | 职责 | 阻断条件 |
|------|---------|------|---------|
| `session-start.py` | SessionStart | 还原任务状态 / 注入 task summary / 检测 worktree | 不阻断 |
| `session-end.py` | SessionEnd | 写 session 总结 / flush events | 不阻断 |
| `ctx-guard.py` | UserPromptSubmit + PreToolUse | context 占用监控 | > force_pct → exit 2 |
| `block-sensitive-files.py` | PreToolUse(Read/Edit/Write) | 拦截 .env / 含 token 的 .mcp.json | 命中 → exit 2 |
| ~~`contract-path-guard.py`~~ | ~~PreToolUse(Write/Edit)~~ | ~~防止往 source/ 写、防 doc-librarian 之外改 contract.md~~ | ~~已移除，改由 doc-librarian.md 声明~~ |
| ~~`file-tracker.py`~~ | ~~PostToolUse(Edit/Write/Read/Bash)~~ | ~~写 audit.jsonl 文件操作轨迹~~ | ~~已移除（失败信号驱动，不再做全量轨迹审计）~~ |
| `blocker-tracker.py` | PostToolUse(Bash) | 检测命令失败 → 写 blocker | 不阻断 |
| `post-tool-linter-feedback.py` | PostToolUse(Edit/Write) | 跑 linter 反馈给 Claude | 不阻断 |
| `post-tool-flow-advance.py` | PostToolUse | flow 步骤自动推进 | 不阻断 |

## 存储层

| Hook | 写入路径 |
|------|---------|
| session-start | 只读 `docs/task/store/<id>/task.json`（workflow section） |
| session-end | `docs/reports/handoffs/`（可选） |
| ctx-guard | `docs/reports/hook-failures.log`（失败时） |
| block-sensitive-files | stderr only |
| ~~contract-path-guard~~ | ~~已移除~~ |
| ~~file-tracker~~ | ~~已移除~~ |
| blocker-tracker | `docs/reports/tasks/<task_id>/blockers.md` |
| post-tool-linter-feedback | `docs/reports/fitness-failures.log` |

## 依赖关系

```
Claude Code 事件 → hook（stdin JSON）
                        ↓
                  paths.py（路径常量）
                        ↓
                  写产物 + exit code
```

hooks 之间**不互相调用**——通过文件系统协作（一个 hook 写 events.jsonl，另一个读）。

## 文件路由

```
hooks/
├── session-start.py            (457 lines) — 最大、最复杂
├── session-end.py              (167 lines)
├── ctx-guard.py                (117 lines) — context 阈值守卫
├── block-sensitive-files.py    ( 81 lines)
├── ~~contract-path-guard.py~~      ~~(已移除)~~
├── ~~file-tracker.py~~             ~~(已移除)~~
├── blocker-tracker.py          (206 lines)
├── post-tool-flow-advance.py
└── post-tool-linter-feedback.py (177 lines)
```

挂载配置：`.claude/settings.json::hooks`

## 注意事项（团队手写段，禁止自动覆盖）

- 任何 hook 的 `sys.exit(2)` 都必须有充分理由——会**阻断 Claude 工作**
- 新增 hook 必须三层降级：stdin 解析 / 配置缺失 / 探针失败
- hook 失败统一写 `docs/reports/hook-failures.log`
- hook 不能调用其他 hook（事件驱动，松耦合）
