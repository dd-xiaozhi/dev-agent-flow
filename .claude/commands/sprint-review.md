# /sprint-review

> 每个 task/sprint 结束后立即复盘。轻量分析当前 task 的执行过程 + Blocker，输出"以后怎么减少"的行动建议。
>
> **定位**：`/workflow-review` 是全量批量分析（周/月），`/sprint-review` 是即时轻量复盘（每次 task 结束）。
>
> **用法**：`/sprint-review [--task <task_id>]`

## 与 /workflow-review 的分工

| | `/sprint-review` | `/workflow-review` |
|--|---|---|
| 触发频率 | 每次 task 结束 | 周/每月 |
| 分析范围 | 当前 task 的 blockers | 全量任务 |
| 输出长度 | 5-10 行行动建议 | 200 行聚合报告 |
| 写入位置 | `.chatlabs/reports/sprints/<date>/review.md` | `.chatlabs/reports/workflow/blockers-summary.md` |
| 分析粒度 | 单条 Blocker 根因 | 频次聚合 + 趋势 |

## 行为

### 第一步：读取当前 task 上下文

> **2026-04-27 改造说明**：task 报告由五件套合并为三件套（meta.json / audit.jsonl / blockers.md）。原 summary.md / file-reads.md / diff-log.md 不再产生。本命令在 R-02 收敛时将整体迁移到 self-reflect(trigger=task-done),目前先适配新数据源。

1. 读 `.chatlabs/state/current_task`，或 `--task <id>` 指定的 task
2. 读 `.chatlabs/reports/tasks/<task_id>/meta.json` 的 `summary` 字段（执行过程 + 关键决策 + 验收）
3. 读 `.chatlabs/reports/tasks/<task_id>/blockers.md`（如有,按需创建,不存在则视为无 blocker）
4. 读 `.chatlabs/reports/tasks/<task_id>/audit.jsonl`（结构化事件流）：
   - filter `type=read` 识别重复读文件
   - filter `type in [edit,write]` 识别关键变更与回头路

### 第二步：复盘分析
对每个 Blocker 条目：

```
问题是什么？
  → 实际发生的错误/阻塞

为什么会发生？（根因）
  → 是疏忽 / 规则缺失 / 工具配置问题 / 信息不足

以后怎么减少？（行动项）
  → 改 agent 约束 / 改 hook / 改 template / 人工注意
```

对执行过程的回顾：
- 有没有重复读同一文件？（→ 上下文加载策略问题）
- 有没有走回头路？（→ 流程设计问题）
- Blocker 是新问题还是老问题？（→ 查 `.chatlabs/reports/workflow/blockers-summary.md` 趋势）

### 第三步：自动落实行动项（不询问）

> 行动项是工程流程改进，AI 直接执行，不需要人工确认。

对每个 P1/P2 行动项：
- **改 agent 定义文件**（generator.md / evaluator.md / planner.md）→ 直接 Edit
- **改 fitness 函数** → 直接修改脚本
- **改 template** → 直接修改模板文件

若目标文件不存在或路径不确定 → 改为追加到 `docs/tech-debt-backlog.md`（状态=open）

### 第四步：写 review.md

目录：`.chatlabs/reports/sprints/YYYY-MM/`
文件名：`review-<task_id>.md`

```markdown
# Sprint Review: <task_id>

## 基本信息
| 字段 | 值 |
|------|-----|
| task_id | TASK-STORY001-01 |
| story_id | STORY-001 |
| phase | generator |
| 时长 | 约 2h |
| verdict | PASS（Evaluator） |

## 执行过程回顾
- 成功：CASE-01、CASE-02 各自一次 PASS
- 教训：CASE-03 因为漏了字段 updated_at，FAIL 了 2 次才修对

## Blocker 分析

### [1] 环境-编译（mvn compile 失败）
- 根因：pom.xml 缺少 spring-boot-starter-validation 依赖
- 教训：骨架生成时没检查 starter 是否齐全
- 行动：下次骨架生成阶段先跑一次 compile 基线（建议：generator.md §4）

### [2] 执行-验收失败（字段缺失，FAIL ×2）
- 根因：schema 生成时漏了 updated_at 字段
- 教训：每次新增字段后要同步 openapi.yaml，没有强制检查
- 行动：fitness/openapi-lint.py 增加字段完整性检查（建议：fitness 函数）

## 趋势对比
| Blocker 类型 | 历史频次 | 本次 | 变化 |
|-------------|---------|------|------|
| 环境-编译 | 3次 | 1次 | ↓ 减少 |
| 执行-验收失败 | 1次 | 2次 | ↑ 新增 ⚠️ |

## 行动清单（按优先级）
1. **[P1]** generator.md 增加：骨架生成后先跑一次 compile 基线
2. **[P2]** fitness/openapi-lint.py 增加字段完整性检查
3. **[P2]** agent 约束增加：新增字段必须同步 openapi.yaml

生成时间: {timestamp}
```

### 第五步：Session 摘要输出

```
═══════════════════════════════════════
  📋 Sprint Review: TASK-STORY001-01

  verdict: PASS（3 CASE）

  ⚠️ 新增趋势：
    执行-验收失败：本次 2 次，历史累计 1 次 ↑

  行动清单（自动落实中）：
    1. [P1] 骨架生成后先跑 compile 基线
    2. [P2] openapi-lint 增加字段完整性检查
    3. [P2] 新增字段必须同步 openapi.yaml

技术债已写入：docs/tech-debt-backlog.md
完整报告：.chatlabs/reports/sprints/YYYY-MM/review-<task_id>.md
```

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `--task <task_id>` | 否 | 默认当前 task |

## 产出

- `.chatlabs/reports/sprints/YYYY-MM/review-<task_id>.md`
- `docs/tech-debt-backlog.md`（自动追加行动项）
- 直接修改相关文件（generator.md / fitness 函数等）

## 失败处理

| 场景 | 行为 |
|------|------|
| blockers.md 为空 | 输出"无 Blocker，干得漂亮！"，仍写 review.md |
| meta.json.summary 字段未填写 | 警告,用 blockers.md + audit.jsonl 单独分析 |
| 无需行动项 | 输出 PASS，跳过 tech-debt-backlog 写入 |

## 关联

- Agent: `.claude/agents/workflow-reviewer.md`（全量分析，供趋势对比）
- Command: `.claude/commands/workflow-review.md`（周/月全量审查）
- 依赖: `meta.json`(summary 字段)、`blockers.md`(按需)、`audit.jsonl`
