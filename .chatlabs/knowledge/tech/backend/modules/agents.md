# 模块：agents/

## Overview

7 个 AI 子代理，按"契约 → 规格 → 实现 → 评估"链路组织。每个 agent 有单一职责与明确铁律。

## API 端点

不适用（agent 通过 Claude Code Agent 工具调用，无 HTTP 接口）。

## 领域模型

| Agent | 模型 | 上游输入 | 下游输出 |
|-------|------|---------|---------|
| `doc-librarian` | opus | 散乱需求（Figma/PDF/会议纪要） | `contract.md` + `openapi.yaml` |
| `planner` | opus | 冻结的 contract | `spec.md` + `cases/CASE-*.md` |
| `generator` | sonnet/opus | spec + cases | 代码实现 + 单元测试 |
| `evaluator` | opus | spec + 实现 | verdict（pass/fail + score） |
| `estimator` | haiku | cases + git diff | 工时估算 JSON |
| `session-auditor` | opus | 当前会话 transcript | 审查报告 |
| `workflow-reviewer` | opus | blockers / 历史 verdict | 周/月趋势报告 |

## 存储层

- 输入读：`.chatlabs/stories/<id>/{source,contract,spec,cases,feedback}/`
- 输出写：见上表
- 状态写：通过 events.jsonl

## 依赖关系

```
doc-librarian ─→ planner ─→ generator ─→ evaluator
                                ↑           ↓
                              estimator   verdict
                                            ↓
                                    workflow-reviewer
```

`session-auditor` 横切所有 agent，监控会话健康。

## 文件路由

| 文件 | 作用 |
|------|------|
| `agents/doc-librarian.md` | 契约文档化 |
| `agents/planner.md` | 技术规格 + 用例拆解 |
| `agents/generator.md` | 代码实现（含单测） |
| `agents/evaluator.md` | 无偏验收（HTTP 契约测试） |
| `agents/estimator.md` | 工时估算（纯函数无副作用） |
| `agents/session-auditor.md` | 会话审查 |
| `agents/workflow-reviewer.md` | 工作流复盘 |

## 注意事项（团队手写段，禁止自动覆盖）

- doc-librarian 唯一可写 `contract.md` 的 agent，contract-path-guard hook 会强制
- 不要在 agent 文档里加版本变更记录（CLAUDE.md 红线）
