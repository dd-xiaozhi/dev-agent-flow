---
name: context-reset
description: 当 ctx-guard hook 阻断（Context 占用超 80%）或主动需要开启新 session 时，产出结构化 handoff 工件，让新 session 无痕接续当前任务（非 compaction）。触发关键词：context reset、上下文重置、新开 session、切换 session、交接、handoff。
---

# Context Reset — 结构化交接协议

## 何时使用

1. `ctx-guard` hook 阻断（stderr 出现 "Context 占用超过硬阈值"）
2. 完成一个 sprint 需要开新 session
3. 感觉 context 混乱、任务跑偏、想要"白板"

**与 /compact 的区别**：compact 是压缩保留；reset 是**清空 + 交接工件**，消除 context anxiety。

## 执行步骤

### 1. 采集当前状态

- 读取最近 10-20 轮对话关键信息（user intent、已完成动作、活跃文件）
- 读取 `AGENTS.md` 的禁止清单
- 读取当前任务关联的 spec / 代码文件 / 测试文件路径
- 若存在 `.claude/tasks/` 或类似状态文件，也纳入

### 2. 填充 handoff 模板

复制 `templates/handoff-artifact.md` 为：
```
.chatlabs/reports/handoffs/YYYY-MM-DD-HHMM.md
```

逐节填充：
- **任务声明**：一句话，不超过 30 字
- **已完成**：只列可验证的成果（文件路径、commit、测试结果）
- **下一步**：明确到可立即执行的指令（例如 "运行 `pytest tests/test_foo.py::test_bar`"）
- **关键约束**：逐字复述来自 AGENTS.md 与用户明确要求的硬规则
- **活跃工件路径**：spec / code / test / data
- **未决问题**：所有等待用户回答或设计层面未定的问题
- **禁止事项**：本次任务特有的限制（若有）

### 3. 校验工件质量

运行（若存在）：
```bash
python fitness/handoff-lint.py .chatlabs/reports/handoffs/<file>
```

必须保证：所有必填字段齐全、引用路径存在、无悬空引用。

### 4. 记录指标

向 `.chatlabs/reports/handoffs.jsonl` 追加一条：
```json
{"ts": "...", "source": "context-reset", "reason": "auto_threshold|manual|sprint_end",
 "ctx_usage_pct": 0.42, "handoff_file": ".chatlabs/reports/handoffs/..."}
```

### 5. 提示用户

输出到对话：
```
Context Reset 工件已生成：.chatlabs/reports/handoffs/YYYY-MM-DD-HHMM.md
→ 建议退出当前 session，在新 session 用 "/context-resume <path>" 或手动读此文件继续。
→ 严禁继续在当前 session 推进实质工作（ctx-guard 将持续阻断）。
```

## 严格纪律

- ❌ 不得凭"记忆"重建状态，必须读当前 transcript 与文件系统
- ❌ 不得省略任何模板必填字段
- ❌ 工件写完 **不得** 在旧 session 继续推进任务
- ✅ 必须让新 session 仅凭工件 + AGENTS.md 能无痕接力（这是 Exit Gate）

## 反模式警示

不要做成"一键压缩" —— 那就退化为 compaction，丢失结构化交接的意义。
