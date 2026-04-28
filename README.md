# ChatLabs Dev-Flow — AI 驱动开发工作流

> 一套基于 Claude Code 的 AI Agent Flow 配置（`.claude/`）+ 规范文档（`docs/`），定义从产品需求到代码交付的全流程。
>
> 核心特性：**流程编排数据化** + **AI 自我进化** + **契约测试验收** + **CI/CD 自动部署**

---

## 执行流程总览

### 一级路由 + 流程模板

```mermaid
flowchart TD
    START["/start-dev-flow"] --> 识别{意图识别}
    识别 -->|TAPD ID/URL| F1["flow=tapd-full<br/>12 步完整链路"]
    识别 -->|本地复杂| F2["flow=local-spec<br/>6 步本地链路"]
    识别 -->|本地中型| F3["flow=local-plan<br/>4 步轻量"]
    识别 -->|本地小型| F4["flow=local-vibe<br/>3 步极简"]
    识别 -->|继续/恢复| RES["/task-resume<br/>读 flow.current_step"]
    识别 -->|复盘| REV[workflow-reviewer]

    F1 --> INIT["flow_advance.py init<br/>实例化 flow 子对象到<br/>workflow-state.json"]
    F2 --> INIT
    F3 --> INIT
    F4 --> INIT
    RES --> CHECK["flow_advance.py check"]
    CHECK --> EXEC

    INIT --> EXEC[按 step 顺序执行]
    EXEC --> KIND{step.kind?}
    KIND -->|agent| KA["doc-librarian / planner<br/>generator / evaluator"]
    KIND -->|skill| KS["tapd-pull / git-commit-push<br/>jenkins-deploy"]
    KIND -->|command| KC["/tapd-consensus-push<br/>/tapd-subtask-emit<br/>/tapd-subtask-close /sprint-review"]
    KIND -->|tool| KT["Edit / TaskCreate"]
    KIND -->|gate| KG["等待 events.jsonl 事件"]
    KIND -->|terminal| END["done"]

    KA --> ADV["/flow-advance &lt;step_id&gt;<br/>每步完成显式调用"]
    KS --> ADV
    KC --> ADV
    KT --> ADV
    KG --> ADV
    ADV --> KIND

    style START fill:#e1f5ff
    style INIT fill:#fff4cc
    style ADV fill:#fff4cc
    style END fill:#c8e6c9
```

### 4 个流程模板的步骤展开

| flow_id | 步骤序列 |
|---------|---------|
| **tapd-full** | tapd-pull → doc-librarian → consensus-push → wait-approve(gate) → planner → subtask-emit → generator → evaluator → **git-push** → **deploy** → subtask-close → sprint-review → done |
| **local-spec** | doc-librarian → planner → generator → evaluator → **git-push** → **deploy** → done |
| **local-plan** | todo-write → edit → **git-push** → **deploy** → done |
| **local-vibe** | edit → **git-push** → **deploy** → done |

模板存放：`.claude/templates/flows/<flow_id>.json`。改流程 = 改 JSON,不改代码。

---

## 详细执行步骤

> ⚠️ **以下小节描述各 step 内部行为(agent 职责、产物、质量门禁等)**。
>
> 步骤之间的衔接、自动派发、状态推进**已迁移到 flow 模板 + flow_advance.py**(见上方"4 个流程模板"表)。
>
> 历史描述里出现的"自动调 /xxx"、"phase = ..."、"hook 自动检测事件路由"等表述均已废弃,以模板内的 step 顺序为准。

### 步骤 1:入口与意图识别

**入口命令**：`/start-dev-flow`

用户只需描述意图，AI 自动识别并路由到对应流程：

| 用户输入 | 自动路由 | 说明 |
|---------|---------|------|
| `/start-dev-flow 1140062001234567` | tapd-story-start | TAPD 工单 ID |
| `/start-dev-flow https://tapd.cn/xxx` | tapd-story-start | TAPD URL |
| `/start-dev-flow 实现用户登录功能` | story-start | 本地需求 |
| `/start-dev-flow 继续上次的任务` | task-resume | 恢复任务 |
| `/start-dev-flow 复盘一下迭代` | workflow-reviewer | 周期复盘 |

**自动检测流程**：
```
用户意图
    ↓
检测 project-config.json
    ├── 不存在 → 自动调用 tapd-init
    └── 存在 → 继续
    ↓
检测 .chatlabs/state/current_task
    ├── 有 → 提示恢复
    └── 无 → 新建任务
    ↓
检测 git status
    └── 有变更 → 提示确认
```

---

### 步骤 2：TAPD 工单处理（tapd-story-start）

**触发条件**：用户输入包含 TAPD 工单 ID 或 URL

#### 2.1 解析入参
```python
# 支持两种格式
/tapd-story-start 1140062001234567  # 纯数字
/tapd-story-start https://tapd.cn/1140062001234567/bugtrace  # URL
```

#### 2.2 刷新本地缓存

```
1. 读取 .chatlabs/tapd/tickets/<ticket_id>.json
   ├── 不存在 → is_new_ticket = true（首次开工）
   └── 存在 → is_new_ticket = false（重入）
2. 调用 tapd-pull skill 拉最新数据
3. 校验 entity_type == "stories"
```

#### 2.3 流程分支判断

| 情形 | local_mapping.story_id | 分支 |
|------|------------------------|------|
| 首次开工 | null | **BRANCH-A: first-start** |
| 重入 | 非 null | **BRANCH-B: auto-judge** |

#### BRANCH-A: 首次开工
```
1. story_id = ticket_id（直接使用 TAPD ID）
2. 归档 description 到 source/tapd-ticket-<id>-<timestamp>.md
3. 调用 /task-new STORY-NNN --trigger first-start
4. 拉取 TAPD 历史评论
5. 路由到 doc-librarian
```

#### BRANCH-B: 重入自动判断
```
auto_judge(situation):
  ├── 等待评审 + TAPD 有 APPROVED → AUTO_RESUME
  ├── 已完成 + verdict == PASS → ALREADY_DONE
  ├── phase 非 done + verdict == null → AUTO_RESUME
  ├── TAPD description 有更新 → AUTO_CHANGE_CHECK
  └── 其他 → NEED_MANUAL（输出诊断）
```

---

### 步骤 3：本地需求处理（story-start）

**触发条件**：用户直接描述功能需求（无工单）

```
1. 解析 description（纯文本，可多行）
2. 分配 STORY-NNN（本地自增 ID）
3. 归档 source/local-description-<timestamp>.md
4. 调用 /task-new STORY-NNN --trigger first-start
5. 路由到 doc-librarian
```

---

### 步骤 4：doc-librarian 阶段

**职责**：将散乱的需求整理为结构化契约文档

#### 4.1 输入
| 来源 | 文件 |
|------|------|
| TAPD 工单 | fields_cache.description + comments_cache |
| 本地需求 | local-description-*.md |

#### 4.2 产出
| 文件 | 位置 | 说明 |
|------|------|------|
| contract.md | .chatlabs/stories/<story_id>/ | 产品契约文档（6段式） |
| openapi.yaml | .chatlabs/stories/<story_id>/ | OpenAPI 3.0 接口定义 |
| changelog.md | .chatlabs/stories/<story_id>/ | 变更日志（冻结后维护） |

#### 4.3 质量门禁
```
✓ 所有业务规则有来源标注
✓ 所有 TBD 标注"需谁确认、截止时间"
✓ AC 编号连续（1,2,3...无跳号）
✓ openapi.yaml 通过 lint
✓ contract.md §3 端点表 ↔ openapi.yaml 100% 一致
✓ 状态机覆盖所有合法转换
```

#### 4.4 自审触发
```
doc-librarian 完成后 → self-reflect(trigger=story-start)
  → 评估 understanding 维度
  → 评估 compliance 维度
  → 产出 flow-log 条目
  → 若评分 < 6/10，输出警告
```

#### 4.5 等待评审
```
状态: waiting-consensus
    ↓
TAPD: /tapd-consensus-push 推送评审通知
本地: 手动评审
    ↓
PM 评审通过 → 状态更新为 frozen
    ↓
发布 contract:frozen 事件
```

---

### 步骤 5：planner 阶段

**职责**：消费契约，产出技术 spec 和 case 任务清单

#### 5.1 输入
```
contract.md (status: frozen)
openapi.yaml
```

#### 5.2 产出
| 文件 | 说明 |
|------|------|
| spec.md | 技术实现 spec（模块划分、schema、部署拓扑） |
| cases/CASE-01-*.md | 可独立执行的 case 任务清单 |
| state.json | CASE 状态追踪（verdicts） |
| sprint-contract.md | 与 Evaluator 的谈判合同 |

#### 5.3 执行步骤
```
步骤 1: 理解契约
  → 提取领域模型/业务规则/状态机/外部依赖
  → 输出到 spec.md §1 契约引用
  【Gate】: pm-confirm-understand（可选）

步骤 2: 架构设计
  → 模块划分 / 数据库 schema / 技术选型 / 部署拓扑
  → 输出到 spec.md §2-§4
  → 追加 x-* 扩展到 openapi.yaml（如需要）
  【Gate】: architect-confirm（必做）

步骤 3: 拆分 cases
  → 按模块索引（§6）拆分
  → 每个 case 引用具体 AC-NNN
  → 填写 blocked_by 依赖关系
  → 产出 cases/CASE-NN-*.md
  【Gate】: plan-confirm（可选）

步骤 4: 初始化 state.json
  → phase: plan
  → cases 列表（初始 status: pending）
  → gates 列表

步骤 5: 起草 sprint-contract.md
  → 与 Evaluator 谈判
  → 双方达成一致后定稿
  ↓
发布 planner:all-cases-ready 事件
```

---

### 步骤 6：tapd-subtask-emit 阶段

**职责**：自动派发 TAPD 子工单到各 Agent

#### 6.1 触发条件
```
收到 planner:all-cases-ready 事件
    ↓
session-start hook 自动处理
```

#### 6.2 执行流程
```
1. 解析 planner 产出的 cases/*.md
2. 为每个 CASE 创建 TAPD 子任务
3. 设置子任务状态为 open
4. 关联到父 story
5. 更新 task meta
```

---

### 步骤 7：generator 阶段

**职责**：按 spec 实现功能，通过 Evaluator 验收

#### 7.1 三阶段流水线

```
┌─────────────────────────────────────────────────────────────┐
│                    阶段一：实现循环                           │
├─────────────────────────────────────────────────────────────┤
│ [CASE-N 循环 N=1..M]                                         │
│     实现代码（按 spec 分模块）                                  │
│         ↓                                                    │
│     跑 fitness/openapi-lint.py                               │
│         ↓                                                    │
│     写单元测试（自测用）                                       │
│         ↓                                                    │
│     生成 openapi.yaml（与代码同步）                            │
│         ↓                                                    │
│     自测通过                                                  │
│         ↓                                                    │
│     【向 Evaluator 发起验收】→ 等待 verdict                   │
│         ↓                                                    │
│     Evaluator verdict                                        │
│     ├── PASS → 更新 workflow-state.json verdicts，继续下一个   │
│     └── FAIL → 读 verdict.failures → 只修对应问题 → 重提交     │
│                （最多 3 次，超过 → 写 Blocker，人工介入）       │
│ [所有 CASE 收到 PASS verdict]                                │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                    阶段二：收尾                               │
├─────────────────────────────────────────────────────────────┤
│ 【阶段一全部 PASS 才能进入阶段二】                               │
│     mvn install（编译 + 打包验证）                              │
│         ↓                                                    │
│     发布 generator:all-done 事件                              │
│         ↓                                                    │
│     更新 TAPD 父 story 状态 → testing                         │
│         ↓                                                    │
│     调用 /sprint-review（技术债写入 backlog）                   │
│         ↓                                                    │
│     交付（写 handoff-artifact）                               │
└─────────────────────────────────────────────────────────────┘
```

#### 7.2 状态追踪（强制）

```python
# 进入时加载状态
ws = WorkflowState.load(story_id)

# CASE-N 完成后
ws.complete_case("CASE-01", "PASS")
ws.save()

# 检查是否全部完成
if ws.all_cases_complete():
    # 进入收尾阶段
    pass
```

#### 7.3 铁律
```
❌ Evaluator verdict 是唯一关卡
❌ Generator 禁止在所有 CASE PASS 之前做收尾动作
❌ Generator 不修改 spec（发现问题 → 向 Planner 发 issue）
❌ Generator 不自评通过（必须交 Evaluator）
```

---

### 步骤 8：evaluator 阶段

**职责**：独立跑契约测试，对 Generator 产物做无偏验收

#### 8.1 工作流程
```
接收 Generator 的交付（代码路径 + openapi.yaml）
    ↓
读取 sprint-contract.md（谈判结果）
    ↓
读取 evaluator-rubric.md（评分维度）
    ↓
启动被测服务（SpringBoot / FastAPI）
    ↓
运行契约测试 adapter
    ↓
对比 openapi.yaml 与实际响应
    ↓
按 rubric 打分
    ↓
产出 verdict
    ↓
写 reports/metrics/eval-verdicts.jsonl
    ↓
通知 Generator
```

#### 8.2 Verdict 规格
```json
{
  "verdict": "PASS | FAIL",
  "fail_count": 2,
  "failures": [
    {
      "endpoint": "/api/v1/users",
      "method": "GET",
      "reason": "response schema 缺少字段 updated_at",
      "actual": "{\"id\":1,\"name\":\"alice\"}",
      "expected": "应含 updated_at ISO8601",
      "reproduce": "curl -s http://localhost:8080/api/v1/users | jq ."
    }
  ],
  "next_action": "交付 | 修复后重提交"
}
```

#### 8.3 评分维度
| 维度 | 权重 | 通过阈值 |
|------|------|---------|
| functionality | 40% | ≥ 2 |
| contract_compliance | 30% | ≥ 2 |
| code_quality | 20% | ≥ 2 |
| maintainability | 10% | ≥ 2 |

**通过条件**：总分 ≥ 2.5 且每个维度 ≥ 2

---

### 步骤 9：收尾阶段

**触发条件**：所有 CASE 收到 PASS verdict

```
1. mvn install（编译 + 打包验证）
2. 发布 generator:all-done 事件
3. 更新 TAPD 父 story 状态 → testing
4. 调用 /sprint-review
5. 交付（写 handoff-artifact）
```

---

## 事件机制（仅审计 + gate 用）

> **重要变更**：`events.jsonl` 中的事件**不再触发自动路由**。流程推进改由 `flow_advance.py` 显式驱动。
>
> 事件保留两个用途:
> 1. **审计日志** — 留存历史轨迹,用于 insight-extract / workflow-review
> 2. **gate step 触发条件** — 例如 `wait-approve` step 等待 `tapd:consensus-approved` 事件出现后才允许 advance

### 事件清单

| 事件 | 发布方 | 用途 |
|------|--------|------|
| `contract:frozen` | doc-librarian | 审计 |
| `tapd:consensus-pushed` | /tapd-consensus-push | 审计 |
| `tapd:consensus-approved` | tapd-sync skill | gate 触发(`wait-approve` step) |
| `tapd:subtask-emitted` | /tapd-subtask-emit | 审计 |
| `planner:all-cases-ready` | planner agent | 审计 |
| `generator:all-done` | generator agent | 审计 |
| `evaluator:done` | evaluator agent | 审计 |
| `git:pushed` | git-commit-push skill | 审计 |
| `jenkins:deployed` | jenkins-deploy skill | 审计 |
| `tapd:subtask-closed` | /tapd-subtask-close | 审计 |

---

## 状态管理

### workflow-state.json（单一状态源 + flow 子对象）

```json
{
  "task_id": "TASK-001",
  "story_id": "STORY-001",
  "phase": "generator",
  "agent": "generator",
  "flow": {
    "flow_id": "tapd-full",
    "version": "1.0",
    "frozen_template_hash": "a1b2c3d4e5f67890",
    "current_step_idx": 6,
    "current_step_id": "generator",
    "steps": [ /* 模板 step 副本,创建时锁定 */ ],
    "history": [
      {"step_id": "tapd-pull", "completed_at": "...", "result": "ok"},
      {"step_id": "doc-librarian", "completed_at": "...", "result": "ok"}
    ]
  },
  "verdicts": {"CASE-01": "PASS", "CASE-02": "WIP"},
  "integrations": {
    "tapd": {"enabled": true, "ticket_id": "1140062001234567"}
  }
}
```

### Phase 字段已 deprecated

> `phase` 字段保留为兼容字段,由 `flow_advance.py` 在 advance 时双写(等于 `current_step.phase_alias`)。
>
> **所有路由读取必须走 `flow.current_step`**——不要再基于 `phase ==` 做分支判断,这种代码已彻底清理。

---

## 核心架构

### AI Agent 三角关系

```
doc-librarian  ──────────▶  planner
    ▲                        │
    │ design-gap             │ spec-issue
    │                        ▼
    │                  generator
    │                      │   │
    │                      │   └──▶ evaluator
    │                      │           │
    └──────────────────────┘           │
            FAIL ◀─────────────────────┘
```

**数据流向**：
- doc-librarian → planner：契约文档（单向，不回写）
- planner → generator：技术 spec + cases
- generator → evaluator：交付物
- evaluator → generator：verdict (FAIL 时打回)

**反馈通道**：
- generator 发现 spec 问题 → 报告给 planner
- planner 发现契约问题 → 反馈给 doc-librarian
- evaluator FAIL → generator 修复后重提

### 职责边界

| Agent | 职责 | 禁止 |
|-------|------|------|
| doc-librarian | 产品契约（业务规则、AC、接口） | 不写代码 |
| planner | 技术 spec（模块、schema、cases） | 不改契约业务字段 |
| generator | 实现代码 + 自测 | 不自评通过 |
| evaluator | 独立契约测试 | 不读 generator 自述 |

---

## 自动机制（Hooks）

| Hook | 触发时机 | 功能 |
|------|----------|------|
| **session-start.py** | 每次新 session | 加载上下文、监听事件、触发 gc |
| **session-end.py** | session 结束 | 保存 flow-logs，触发自审 |
| **ctx-guard.py** | 每次提交前 | Context >40% 阻断 |
| **blocker-tracker.py** | Bash 失败 | 分析错误，追加 blockers |
| **file-tracker.py** | 文件操作 | 追踪到 file-reads/diff-log |
| **post-tool-linter-feedback.py** | Edit/Write 后 | 运行 fitness rule |

---

## AI 自我进化机制

```
触发点（story-start / tapd-reopen / workflow-review / manual）
    │
    ├── 自审（self-reflect）→ 四维度评分
    │                           → .chatlabs/flow-logs/FL-*.json
    │
workflow-review（定期）
    │
    ├── 洞察提炼（insight-extract）→ 跨事件模式
    │                                   → insights/_index.jsonl
    ├── 进化提案（evolution-propose）→ spec 变更提案
    │                                   → evolution-proposals/
    └── /evolution-apply --all → spec/ 规范更新
```

---

## 快速开始

```bash
/start-dev-flow             # 启动主流程(自动选 flow_id 并 init)
/tapd-story-start <ticket>  # TAPD 工单开工(走 tapd-full)
/story-start <描述>         # 本地复杂需求(走 local-spec)
/task-resume <task-id>      # 恢复任务(读 flow.current_step 路由)
/flow-advance <step_id>     # 推进当前 flow 到下一步
/sprint-review              # 即时复盘
```

---

## 目录结构

| 路径 | 职责 |
|------|------|
| `.claude/agents/` | 5 个 agent 定义（doc-librarian/planner/generator/evaluator/workflow-reviewer） |
| `.claude/commands/` | slash commands(tapd/flow/worktree/task/start-dev-flow 等) |
| `.claude/skills/` | 13 个可复用 skill(含 git-commit-push / jenkins-deploy) |
| `.claude/hooks/` | 自动执行 hooks |
| `.claude/scripts/` | Python 工具(flow_advance.py / workflow-state.py 等) |
| `.claude/templates/flows/` | **流程模板 JSON**(tapd-full / local-spec / local-plan / local-vibe) |
| `.chatlabs/stories/` | 活跃 story 产物(每 story 一份 workflow-state.json) |
| `.chatlabs/state/` | 全局状态(current_task / events.jsonl) |
| `.chatlabs/tapd/` | TAPD 工单缓存 |
| `.chatlabs/reports/` | 任务执行报告 |
| `.chatlabs/knowledge/` | 知识库(三层:project/tech/asset) |
| `.chatlabs/flow-logs/` | AI 自审日志 |

---

## 扩展指南

- 新增 agent → 在 `.claude/agents/` 放一个 md
- 新增 hook → 在 `.claude/hooks/` 实现 + 配置 `settings.json`
- 新增 fitness rule → 在 `fitness/` 目录放 `{rule}.py`
- 新增 skill → 在 `.claude/skills/<name>/SKILL.md` 定义
- **新增 flow 模板** → 在 `.claude/templates/flows/<flow_id>.json` 写 step 列表;在 `/start-dev-flow.md` 加路由判定;`flow_advance.py init --flow-id` 自动支持

---

## 规范文档

| 文件 | 用途 |
|------|------|
| `docs/team-workflow.md` | 团队工作流总纲 |
| `.claude/artifacts-layout.md` | Flow 产物目录布局与常量速查 |
| `.claude/templates/contract-template.md` | 产品契约文档模板 |
| `.chatlabs/knowledge/README.md` | 知识库索引 |
