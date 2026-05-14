# 模块：templates/

## Overview

产物模板与流程模板的存放处，是 Flow 的**数据化骨架**——改流程 = 改 JSON / Markdown，不改代码。`evaluator-rubric.md` 已下线（验收 rubric 改由 spec.md 内联）。

## API 端点

不适用。

## 领域模型

| 子目录 / 文件 | 类型 | 用途 |
|-------------|------|------|
| `contract-template.md` | 模板 | doc-librarian 写 contract.md 的骨架 |
| `sprint-contract.md` | 模板 | sprint 级契约骨架 |
| `spec.md` | 模板 | planner 写 spec.md 的骨架（含验收 rubric） |
| `flows/` | 数据 | flow 编排定义（7 个：tapd-full / local-{spec,plan,vibe} / bugfix-{spec,plan,vibe}） |
| `story/` | 模板 | story 目录骨架（case-template.md / curl-tests-template.yaml） |
| `task-report/` | 模板 | task 报告骨架（meta.json / audit.jsonl） |

## 存储层

- 模板自身：`.claude/templates/**`（提交到 git）
- 模板渲染产物：写到 `.chatlabs/stories/` 或 `.chatlabs/reports/`

## 依赖关系

```
agent / command 启动 → 读对应模板 → 填充实际数据 → 写到产物路径
```

模板与代码完全解耦——`flow_advance.py` 不 hardcode 任何步骤名，全部从 `flows/<flow_id>.json` 读。

## 文件路由

```
templates/
├── contract-template.md         doc-librarian 用
├── sprint-contract.md           sprint 级契约
├── spec.md                      planner 用（含验收 rubric）
├── flows/                       7 个 flow 模板（JSON）
│   ├── tapd-full.json
│   ├── local-spec.json
│   ├── local-plan.json
│   ├── local-vibe.json
│   ├── bugfix-spec.json
│   ├── bugfix-plan.json
│   └── bugfix-vibe.json
├── story/
│   ├── case-template.md
│   └── curl-tests-template.yaml
└── task-report/
    ├── meta.json
    └── audit.jsonl
```

## 关键设计

### flows/*.json 的 step 类型

| kind | 说明 |
|------|------|
| `agent` | 调用 agent（doc-librarian / planner / generator / evaluator） |
| `skill` | 调用 skill（git-commit-push / jenkins-deploy / tapd） |
| `command` | 调用斜杠命令（/sprint-review） |
| `tool` | 直接用 Claude Code 内置工具（Edit / TaskCreate） |
| `gate` | 等待 events.jsonl 中的事件（如 consensus-approved） |
| `terminal` | 流程结束（done） |

### 添加新流程

1. 写 `templates/flows/<new_flow>.json`
2. 列出 step 序列
3. 在 `start-dev-flow` 命令中加意图识别规则
4. **无需改 Python 代码** —— flow_advance.py 自动解释

## 注意事项（团队手写段，禁止自动覆盖）

- 模板里的占位符用 `{{var}}`（mustache 风格）
- 新增模板要在 README.md / artifacts-layout.md 注册路径
- flows/*.json 改动要写 sprint-review，记录改动原因
