# Agent 共享规范

> 所有 agent 必须遵守的跨 agent 通用规则。各 agent 的 frontmatter 通过 `rules:` 字段引用本文件。

## 1. Blocker 记录规范

**Agent 遇到以下情况，必须主动写入 `.chatlabs/reports/tasks/<task_id>/blockers.md`**：

| 场景 | Blocker 类型 | 填写要求 |
|------|------------|---------|
| 需求中某字段/规则完全缺失 | 信息-需求缺失 | 描述缺失内容、影响范围、"需谁补充、截止时间" |
| PM 口述与文档矛盾 | 信息-契约歧义 | 引用矛盾点、两种可能解释、"需 PM 裁决" |
| 状态机/业务规则无法确认 | 信息-契约歧义 | 列出可选方案及利弊 |
| 技术选型无足够信息判断 | 信息-技术决策 | 标注"非 doc-librarian 职责，需 Tech Lead 决策"，流向 = "planner" |
| 外部依赖（第三方 API）信息不足 | 信息-外部依赖 | 描述缺失字段、标注"需后端确认接口契约" |

**Blocker 条目格式（Agent 主动填写）**：

```markdown
## {timestamp} [Agent主动]
- **类型**: {信息-需求缺失|信息-契约歧义|...}
- **描述**: {具体阻塞内容}
- **根因**: {为什么会阻塞}
- **影响范围**: {阻塞了哪个部分}
- **解决状态**: 待解决/已解决
- **解决方案**: {已解决时填写，格式："发钉钉 @PM 确认 / 等 PM 回复 / 决定采用方案X"}
- **流向**: {反馈至 PM / 反馈至 planner / 反馈至 generator}
```

**强制要求**：
- 遇到上述场景**必须**写 blockers.md，不能假装没看到
- blockers.md **首次写入时由 writer 自动创建**（按需），无需预先 touch
- Blocker 条目填写时**必须包含根因分析**（不允许只写"有问题"）
- 所有待解决 Blocker 必须在 `task.json.workflow.summary.execution_log` 中摘要列出

## 2. task.json.workflow.summary 字段规范

**任务完成后，必须填写 `task.json.workflow.summary` 字段**（不再写独立的 summary.md 或 meta.json 文件，summary 已并入 task.json 的 workflow section）：

```json
{
  "task_id": "05-20-sf-token-retry",
  "workflow": {
    "phase": "done",
    "blocker_count": 2,
    "verdict": "PASS",
    "summary": {
      "completed_at": "2026-04-19T11:30:00+08:00",
      "execution_log": "[10:00] 读取 Figma 截图 ×3\n[10:15] 完成 §1 页面结构\n[10:40] 完成 §2 数据模型(字段 name 歧义→blocker #1)\n[11:00] 完成 §3 接口契约\n[11:20] 完成 §5 AC-001~AC-005\n[11:25] 提交 review\n阻塞:blocker #1 role 枚举待 PM 确认",
      "key_decisions": [
        "状态机选三态而非四态:Figma 中无草稿态,合并到 pending",
        "金额字段用 *_cents 而非 *_yuan(遵循 api-conventions.md)"
      ],
      "deliverables": [
        ".chatlabs/task/store/05-27-example/contract.md"
      ],
      "acceptance": "PASS:契约已冻结,2 条 blocker 已记录待 PM 回复"
    }
  }
}
```

**字段语义**：

| 字段 | 含义 |
|------|------|
| `summary.completed_at` | 任务真正完成的时刻(交付或明确阻塞) |
| `summary.execution_log` | 关键执行步骤(`[HH:MM] 描述` 格式,换行分隔) |
| `summary.key_decisions` | 影响实现方向的重要决策(含理由) |
| `summary.deliverables` | 产出文件路径列表 |
| `summary.acceptance` | 验收结论(PASS/FAIL + 简述) |

**强制要求**：
- `summary.completed_at` 和 `summary.acceptance` 必须在任务真正完成时填写
- `summary.execution_log` 每完成一个里程碑就追加一条
- 未解决 Blocker 必须在 `summary.execution_log` 末尾摘要列出
- 写完 summary 后,**输出 `[FLOW-COMPLETE: <agent-name>]` 信号**;phase 字段不再由 agent 自行更新(由主 Claude 通过 flow-engine skill 推进流程时双写)

## 3. GAN 三角协作纪律

```
Planner ── spec.md + contract.md ──▶ Generator
                                        │
                                        │ delivery（handoff-artifact）
                                        ▼
                                     Evaluator
                                        │
                                        ├ Phase 1: code review (git diff HEAD + 项目规范)
                                        ├ Phase 2: AI 自主执行集成测试
                                        ▼
                                     verdict (phases + 顶层聚合) ──▶ Generator
                                        ▲
                                        │ (修对应 phase 的 failures，重新发起)
                                        │
                                     Generator
```

**三角关系**：Planner 定规则 + 写 spec.md（含 AC↔Endpoint 映射），Generator 执行，Evaluator 双阶段独立验收（代码侧 review + JUnit 集成测试）。
三角必须独立 —— Evaluator 不看 Generator 自述，Generator 不改 spec，**Evaluator 独立生成 JUnit 测试代码（不复用 Generator 写的测试）**，**Evaluator 也不读 Generator 写的解释性注释/README 来判断代码质量**。

### GAN 边界纪律（核心铁律）

| 规则 | 说明 |
|------|------|
| **Evaluator verdict 是唯一关卡** | Evaluator PASS 之前，Generator 禁止做任何收尾动作 |
| **Evaluator 禁止提前触发** | Evaluator 只在 Generator 主动提交时跑，不在 Generator 流水线中途自动触发 |
| **Generator 不读自己的 verdict** | verdict 由 Evaluator 独立产出，Generator 只接收和执行 |
| **Generator 不宣布完成** | Generator 只能交付（handoff-artifact），"完成"由 Evaluator PASS 体现 |
