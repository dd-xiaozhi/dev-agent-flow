# 核心功能流程

## 故事生命周期

```mermaid
flowchart LR
    subgraph 入口
        A[用户输入]
    end

    A --> B{意图识别}

    B -->|TAPD工单| C[/tapd-story-start]
    B -->|本地需求| D[/story-start]
    B -->|恢复任务| E[/task-resume]

    C --> F[首次开工?]
    F -->|是| G[归档+分配STORY]
    F -->|否| H[auto-judge判断]

    G --> I[doc-librarian]
    H -->|AUTO_RESUME| I
    H -->|ALREADY_DONE| Z[跳过]
    H -->|NEED_MANUAL| Z

    D --> J[解析description]
    J --> K[分配STORY-NNN]
    K --> L[归档source]
    L --> I

    I --> M[生成契约文档]
    M --> N{PM评审通过?}
    N -->|通过| O[contract:frozen]
    N -->|打回| P[修改contract]
    P --> N

    O --> Q[TAPD共识推送]
    Q --> R[planner]

    R --> S[理解契约]
    S --> T[架构设计]
    T --> U[拆分cases]
    U --> V[初始化state.json]

    V --> W[谈判sprint-contract]
    W --> X[planner:all-cases-ready]

    X --> Y[tapd-subtask-emit]

    Y --> AA[generator循环]

    AA --> AB{查找未完成CASE}
    AB -->|有| AC[实现CASE]
    AC --> AD[fitness检查]
    AD --> AE[自测]
    AE --> AF[提交Evaluator]

    AB -->|完成| AG[收尾]
    AG --> AH[mvn install]
    AH --> AI[更新TAPD状态]
    AI --> AJ[sprint-review]
    AJ --> AK[handoff-artifact]
    AK --> AL[AI自我进化]
    AL --> I

    style I fill:#e8f5e9
    style R fill:#f3e5f5
    style AA fill:#ffebee
```

## Phase 流转

```
doc-librarian → waiting-consensus → planner → generator → evaluator → done
                              ↓
                    TAPD Consensus 评审
```

## 事件驱动机制

| 事件 | 发布方 | 消费方 | 说明 |
|------|--------|--------|------|
| `tapd:consensus-approved` | tapd-sync skill | session-start | PM 评审通过 |
| `planner:all-cases-ready` | planner | session-start | 所有 CASE 规划完成 |
| `generator:started` | generator | - | 开始实现 |
| `generator:all-done` | generator | session-start | 全部 CASE 完成 |
| `contract:frozen` | doc-librarian | tapd-sync | 契约冻结 |

## Generator 循环

```
┌─────────────────┐
│  查找未完成 CASE │
└────────┬────────┘
         │
    ┌────▼────┐
    │ 有 CASE  │
    └────┬────┘
         │ 是
    ┌────▼─────────────┐
    │  实现代码        │
    │  ↓              │
    │  fitness 检查    │
    │  ↓              │
    │  写单元测试      │
    │  ↓              │
    │  生成 openapi   │
    │  ↓              │
    │  自测通过        │
    │  ↓              │
    │  提交 Evaluator │
    └────┬─────────────┘
         │
    ┌────▼─────────────┐
    │  Verdict 判定    │
    └────┬─────────────┘
         │
    ┌────┴────┐
    │ PASS    │
    │ FAIL    │
    └────┬────┘
         │
    ┌────┴─────────────────┐
    │ PASS → 更新 verdicts │
    │ FAIL → 修复后重提交  │
    └────┬─────────────────┘
         │
    ┌────▼────┐
    │ 全部完成 │
    │ ↓       │
    │ 收尾    │
    └─────────┘
```

## AI 自我进化

```
触发点
    │
    ├── 自审（self-reflect）
    │       └── 写入 .chatlabs/flow-logs/
    │
    ├── 洞察提炼（insight-extract）
    │       └── 写入 .chatlabs/insights/
    │
    └── 进化提案（evolution-propose）
            └── 写入 .chatlabs/evolution-proposals/
                └── 用户确认后更新 spec/
```