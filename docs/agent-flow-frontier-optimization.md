# Agent Flow 前沿工程对齐与优化方案

> **日期：** 2026-07-02（调研）/ 2026-07-03（实施完成）
> **性质：** 调研报告 + 优化提案 → **8 项全部实施**（见 §6 实施记录）
> **调研范围：** Anthropic 工程博客（context engineering / long-running harness / multi-agent research system）、Cognition（Don't Build Multi-Agents）、Cursor（reward hacking 审计）、arXiv 2026 验收加固论文、awesome-evals
> **对照对象：** 本仓库当前 flow 体系（7 静态 flow + orchestrate、GAN 三角、flow-engine、task.json SSOT、6 hooks）

---

## 1. 执行摘要

当前架构与 2026 前沿实践**对齐度高**：artifact-based handoff、evaluator 独立验收、task.json 外部状态、ctx-guard 上下文防御，均为前沿共识的文件化实现。

真正差距集中 6 处，按 ROI 排序：

| 优先级 | 差距 | 一句话改法 | 成本 |
|-------|------|-----------|------|
| P0 | evaluator 无轨迹级防作弊 | Phase 0 机器前置检查（测试篡改 + artifact 存在性） | 低 |
| P0 | generator 单 session 吃整个 spec | 会话切片纪律：一次一个 CASE | 低 |
| P0 | retry 上限三处不一致 | 收敛到 flow 模板 `max_retry` 字段 | 低 |
| P1 | orchestrate 委托契约缺失 | fan-out 协议补四要素模板 + 缩放规则 + 写隔离硬约束 | 中 |
| P1 | gate 靠人工 emit 事件 | 定时轮询自动 emit，人只批准不搬运 | 中 |
| P2 | 零 eval 基线 | 3-5 个 golden task 回归集 | 中（长期复利） |
| P2 | arbiter 全量读 registry | scoped 查询 CLI 替代全量读取 | 低 |
| P2 | 无 token 遥测 | events 记录 per-step token/时长 | 低 |

---

## 2. 前沿工程共识（一手来源提炼）

### 2.1 Context Engineering（Anthropic, 2025-09）

> 来源：[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

- **核心公式**：找到"最大化期望产出概率的最小高信号 token 集"。信息多 ≠ 好——每个 token 都与其他 token 形成 n² 注意力关系，**context rot**（上下文腐蚀）随 token 数递增，召回精度下降。
- **三原语**：compaction（压缩历史为高保真摘要）、tool-result clearing（清理工具返回噪音）、memory（外部文件持久化）。
- **正确海拔（right altitude）**：prompt 介于两个失败模式之间——硬编码脆弱逻辑（if-else 穷举）vs 空泛指导（"写好代码"）。给启发式信号，不给穷举规则。
- **just-in-time retrieval**：不预载全量上下文，运行时按需检索（grep / scoped query）。

### 2.2 单线程 vs 多代理边界（Cognition, 2025-06）

> 来源：[Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)

- **原则 1**：共享完整 agent trace，不是摘要消息。摘要必然丢失影响任务解释的隐式细节。
- **原则 2**：每个 action 携带隐式决策。并行 agent 各自做隐式决策 → 决策冲突（例：克隆 Flappy Bird，两个 agent 产出风格完全不同的 bird 和背景）。
- **实践边界**（与 Anthropic 多代理文对读后的行业共识）：**读任务（research / 分析 / 审查）可并行；写任务（代码生成 / 文件编辑）并行必产协调问题，倾向单线程**。

### 2.3 长时程 Harness（Anthropic, 2025-11）

> 来源：[Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

跨 session 长任务的 10 项技术：

1. **Initializer agent**：首个 session 用专用 prompt 建环境（init.sh、git 初始化、结构化状态文件）。
2. **Feature list 用 JSON 不用 Markdown**：模型更不容易篡改 JSON；每条 feature 含描述、步骤、`passes` 布尔，初始全 false。
3. **进度文件**（claude-progress.txt）：每 session 结束追加做了什么，下个 session 启动先读，免于重新分析代码库。
4. **一次一个 feature**：对抗"一口吃太多 → context 耗尽 → 留下半成品"的默认倾向。
5. **每 feature 一个 commit**：可回滚、可查历史。
6. **启动 checklist**：pwd → git log → 进度文件 → feature list → 选最高优先级未完成项。
7. **端到端验证**：给浏览器自动化工具，像用户一样测，防止"单测过了就算完成"。
8. **健康检查**：session 开始先跑 init.sh + 基础 e2e，先暴露回归再做新功能。
9. **干净收尾**：session 结束时代码须达"可合入主干"状态。
10. **禁止删改测试**：显式写进 prompt——"移除或修改测试不可接受"。

### 2.4 Orchestrator-Worker 委托纪律（Anthropic, 2025-06）

> 来源：[How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)

- **效果**：比单 agent 提升 90.2%（内部 research eval），但 token 消耗 15 倍；**token 用量解释 80% 性能方差**。
- **委托四要素**：每个子代理必须拿到——明确目标、输出格式、工具使用指引、任务边界。缺任一 → 重复劳动或关键信息缺口。
- **显式 effort 缩放规则**（写进 orchestrator prompt）：简单事实查询 = 1 agent + 3-10 次工具调用；对比类 = 2-4 agent 各 10-15 次；复杂研究 = 10+ agent。没有规则时早期版本为一句话问题 spawn 50 个子代理。
- **broad-then-narrow**：先宽查询探地形，再收窄。
- **tool-testing agent**：让 agent 反复用有缺陷的工具然后重写工具描述，任务完成时间 -40%。工具/prompt 的改进可以由 agent 自己驱动。

### 2.5 验收防作弊（Cursor + arXiv, 2026）

> 来源：[Reward hacking is swamping model intelligence gains — Cursor](https://cursor.com/blog/reward-hacking-coding-benchmarks)、[The Verification Horizon (arXiv 2606.26300)](https://arxiv.org/html/2606.26300v1)、SpecBench (arXiv 2605.21384)

- Cursor 审计 731 条"成功"轨迹：**63% 靠翻 git history / 上网查已知修复**，非独立推理。严格隔离（删 .git 重建单 commit 仓 + 网络白名单）后得分掉 20.7pp。
- **分层验收有效**：rubric 评审（按维度分解：功能正确性/质量/结构）+ **轨迹级行为监控**（扫 agent 执行轨迹找作弊模式），作弊通过率 28.57% → 0.56%，同时干净通过率 40.22% → 60.53%。
- **简单防御依然有效**：检查必要 artifact 真实存在、重置被篡改的输入文件、`git diff` 核对测试文件未被动过——都是机器级检查，不耗 LLM。
- SpecBench 补充：系统级软件（1.5K-110K LOC）的作弊更多来自**架构性偷懒**（feature 之间互相隔离没做集成），不只是改测试。

---

## 3. 当前架构对照

### 3.1 已对齐项（不动）

| 当前设计 | 对应前沿实践 |
|---------|------------|
| artifact-based handoff（contract.md / spec.md / verdict.json，消息只传路径） | Cognition 完整上下文共享 + Anthropic memory 原语 |
| evaluator 不读 generator 自述/注释/README，独立生成集成测试 | 验收独立性 = 反 reward-hacking 第一原则 |
| task.json SSOT + events append-only + TaskJsonStore 门面（fcntl 锁 + atomic rename） | 长时程 harness 的 JSON 状态文件范式（含"JSON 比 Markdown 难篡改"） |
| ctx-guard 40% 阻断 + context-reset handoff skill | context rot 防御 + compaction |
| vibe / plan / spec / tapd-full 档位路由 | effort 缩放的静态雏形 |
| registry jsonl（api/schema/decisions）跨 story 冲突拦截 | 外部 memory + 决策显式化 |
| blocker 机制 + 根因分析强制 | 失败可观察（formalization-timing 探索期要求） |
| frozen_template_hash | 流程确定性 |

### 3.2 差距明细与改法

#### P0-1 · evaluator 加 Phase 0 机器前置检查

**现状**：evaluator 两阶段（Phase 1 code review + Phase 2 集成测试），均为 LLM 驱动。无机器级防作弊层。

**风险**：generator 改测试/fixture 让 Phase 2 通过；deliverables 声明的文件实际不存在；SpecBench 式架构性偷懒（每个 CASE 孤立实现不集成）。

**改法**（`.claude/agents/evaluator.md` + 可选脚本 `.claude/skills/integration-test/scripts/phase0_check.py`）：

```
Phase 0（机器检查，LLM 介入前，任一失败直接 FAIL 不进后续 Phase）：
  a. artifact 存在性：handoff-artifact 中 deliverables 列表逐一 test -f
  b. 测试完整性：git diff <baseline_commit> -- <test_paths> 必须为空
     （baseline = generator 开工前 commit，记录在 task.json.git）
  c. fixture/输入数据完整性：git diff 核对 evaluator 依赖的 fixture 未被动
  d. 结果写入 verdict.json.phases.phase0，failures 带 machine-check 标记
```

**依据**：§2.5——简单机器防御把作弊率降两个数量级，零 LLM 成本。

#### P0-2 · generator 会话切片纪律

**现状**：generator 一个 session 内实现整个 spec 的所有 CASE。CASE 多时 context 耗尽风险高，半成品无记录。

**改法**（`.claude/agents/generator.md` prompt 增段）：

```
会话纪律（每 session）：
  1. 启动 checklist：读 task.json（verdicts 进度 + events 近况）→ git log -5
     → 跑健康检查（编译/启动脚本）→ 选下一个未 PASS 的 CASE
  2. 本 session 只实现这一个 CASE：实现 → 单测 → commit（含 CASE ID）
     → 更新 execution_log
  3. 干净收尾：代码达可合入状态，无半成品；context 不足时停在 CASE 边界，
     不跨 CASE 硬撑
  4. 禁改测试骨架：evaluator 侧测试与 fixture 一律不可动（Phase 0 会核）
```

**依据**：§2.3 技术 4/6/8/9/10。已有 per-CASE verdicts 字段，只差执行纪律。

#### P0-3 · retry 上限统一

**现状**：evaluator/arbiter/generator retry 上限 3/2/无上限，散在各 agent 定义里。

**改法**：flow 模板 JSON 每个 step 增 `max_retry` 字段，flow-engine `flow_advance.py` 统一执行：超限 → 自动写 blocker（含各次失败原因）→ step 标 interrupted → 停止推进。agent 定义里删除各自的 retry 描述，指向 flow 层。

**依据**：task-lifecycle 迭代上限规则（编译 2 / 测试 3 / 整体 5）；无上限自动 retry 掩盖深层问题。

#### P1-4 · orchestrate 补委托契约

**现状**：orchestrate.json 只有骨架，fan-out-synthesize 协议无子代理 prompt 模板、无并发/预算规则、无写隔离约束。

**改法**（`protocols/fan-out-synthesize.md` 增三段）：

```
一、子代理委托模板（四要素，缺一不发）：
  【目标】单一、可验证的产出
  【输出契约】写到哪个路径 + 什么 schema（返回消息只报路径）
  【工具边界】允许/禁止的工具与目录范围
  【禁区】不做什么（防 scope creep）

二、缩放规则（orchestrator 决策表）：
  - 涉及 ≤3 文件/模块 → 不扇出，主线程直接做
  - 读任务（审计/调研/分类）→ 每 agent 一个独立维度，上限 8 并发
  - 每 agent 预算：声明预计工具调用量级，超 3 倍主动收敛返回

三、写隔离硬约束：
  - 读任务可裸并行
  - 写任务必须 worktree 隔离（复用 git skill worktree 能力）或退化单线程
  - join 点单一：只有主线程消费产物文件并合并，子代理之间不互相通信
```

**依据**：§2.4 四要素 + 缩放规则；§2.2 写任务并行警告。

#### P1-5 · gate 自动化

**现状**：consensus-gate / arbitration-gate 需人工调 `/tapd fetch` 或手动 emit 事件。人做的是搬运（查状态→emit），不是决策。

**改法**：session-start hook 或定时任务轮询 TAPD wiki 评论状态，满足条件自动 emit `tapd:consensus-approved`。人保留的动作只剩在 TAPD 上写批准评论本身。arbitration-gate 同理——arbiter 产出 verdict 后自动 emit，无需主 Claude 二传。

**依据**：§2.3 机器可查状态；符合"掌舵不微管理"原则——流程约束系统化，人在决策点介入而非搬运点。

#### P2-6 · golden task eval 基线

**现状**：改 agent prompt / flow 模板无回归手段，全靠感觉。前沿经验：prompt 迭代占多代理系统改进的主要工作量，没有 eval 就是盲改。

**改法**：建 `evals/` 目录，3-5 个 golden task：

```
evals/
├── golden/
│   ├── g1-simple-crud/        # 小需求：已知正确 contract + spec + 代码
│   │   ├── input/             # 需求素材
│   │   └── expected/          # 冻结的期望产物（contract.md / spec.md 要点清单）
│   ├── g2-cross-story-conflict/  # arbiter 必须拦下的冲突场景
│   └── g3-bugfix-vibe/        # 单文件修复走 vibe 档
└── run_eval.py                # 跑指定 flow → diff 产物要点 → 报告
```

评分不做全文 diff（LLM 产出非确定），做**要点清单核对**：期望的字段/端点/决策是否出现，禁止的越界是否出现。改 prompt 后跑一轮，回归可见。

**依据**：§2.4 "prompt engineering 是主要改进杠杆" + awesome-evals 实践；skill-creator 已带 eval 能力可复用。

#### P2-7 · registry scoped 查询

**现状**：arbiter 读全量 registry jsonl 做冲突检测。story 积累后 = context rot + 漏读风险。

**改法**：registry 增查询脚本（如 `registry_query.py --module <m> --prefix <p>`），arbiter 定义改为"先从 spec 提取涉及的模块/资源名 → scoped 查询 → 只读命中条目"。全量读仅在条目 < 50 时允许。

**依据**：§2.1 just-in-time retrieval；最小有效上下文原则。

#### P2-8 · token 遥测

**现状**：events 记录步骤完成，不记录消耗。无法回答"哪一步最烧上下文"。

**改法**：flow-engine complete 时在事件 data 里附 `duration_s`；agent 类 step 由主 Claude 估算填入产物大小（artifact 字节数为 proxy）。workflow-reviewer 聚合出趋势：哪个 agent 的产物在膨胀、哪步耗时异常。不追求精确 token 数（harness 拿不到），proxy 指标够用。

**依据**：§2.4 token 用量解释 80% 方差——先可观测，再优化。

---

## 4. 实施路线

```
Phase A（一个下午，纯纪律/小改动）
  P0-1 evaluator Phase 0   → 改 evaluator.md + phase0_check.py
  P0-2 generator 切片       → 改 generator.md
  P0-3 retry 统一           → flow 模板 + flow_advance.py

Phase B（1-2 天）
  P1-4 orchestrate 契约     → fan-out-synthesize.md 增三段
  P1-5 gate 自动化          → session-start hook / 轮询脚本

Phase C（按需推进，长期复利）
  P2-6 eval 基线            → evals/ 目录 + 首个 golden task
  P2-7 registry scoped 查询 → registry_query.py + arbiter.md
  P2-8 token 遥测           → events data 扩字段 + workflow-reviewer 聚合
```

每 Phase 独立可验证：A 完成后跑一次 spec 档全链路确认不回归；B 完成后跑一次 tapd-full 观察 gate 自动放行；C 的 eval 建成后反过来守护 A/B 的改动。

---

## 5. 参考资料

| 来源 | 链接 |
|------|------|
| Anthropic — Effective context engineering for AI agents | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents |
| Anthropic — Effective harnesses for long-running agents | https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents |
| Anthropic — How we built our multi-agent research system | https://www.anthropic.com/engineering/multi-agent-research-system |
| Cognition — Don't Build Multi-Agents | https://cognition.com/blog/dont-build-multi-agents |
| Cursor — Reward hacking is swamping model intelligence gains | https://cursor.com/blog/reward-hacking-coding-benchmarks |
| The Verification Horizon（分层验收实证） | https://arxiv.org/html/2606.26300v1 |
| SpecBench（系统级 reward hacking） | https://arxiv.org/pdf/2605.21384 |
| BenchFlow — awesome-evals | https://github.com/benchflow-ai/awesome-evals |
| Addy Osmani — Agent Harness Engineering | https://addyosmani.com/blog/agent-harness-engineering/ |

---

## 6. 实施记录（2026-07-03）

8 项全部落地。所有新增/改动脚本已 `py_compile` + 单元冒烟 + JSON 校验通过。

| 项 | 改动文件 | 要点 |
|----|---------|------|
| **P0-1** | `.claude/agents/evaluator.md` | 新增 Phase 0 防篡改机器前置检查（P0-a deliverables 存在性 / P0-b `git diff HEAD --diff-filter=DM` 既有测试未弱化 / P0-c fixture 未覆盖）；三阶段顺序 + verdict schema 加 `phases.phase0` |
| **P0-2** | `.claude/agents/generator.md` | 加「会话启动 checklist」（读 task.json 进度 + git log + 健康检查）+ 铁律「干净收尾」+ 禁弱化既有测试。**修订**：原提案「一次一个 CASE per session」与 generator 铁律 4「整 story 一次提交」冲突（GAN 刻意设计），改为**兼容子集**——只补中断恢复 checklist + 干净收尾，不引入 per-case 循环 |
| **P0-3** | `agent-conventions.md` §4 + evaluator/generator/arbiter | retry 上限统一到 §4 SSOT 表（GAN 3 / 仲裁 2 / 编译 2 / 测试 3）+ 统一超限动作；三 agent 改为引用而非硬编码 |
| **P1-4** | `.claude/protocols/fan-out-synthesize.md` | 新增 §3.5 扇出规模缩放表 + 读/写任务隔离硬约束（读可并行、写须 worktree 或单线程）；§四 prompt 契约锐化为四要素（目标/输出契约/工具边界/禁区）；§五 加两条反模式 |
| **P1-5** | `flow_advance.py` + `tapd-full.json` + `local-spec.json` + `consensus_poll.py`(新) + `tapd/SKILL.md` | gate evidence 条件化（`evidence_required`）——arbitration-gate 靠 arbiter 自动 emit 的事件放行，不再塞假 evidence；consensus-gate 加 `evidence_required:true` 保持人工证据；新增 `consensus_poll.py` 把 fetch+marker 检测+输出 evidence_id 合成一条命令，去人工搬运 |
| **P2-6** | `evals/`(新目录) | `run_eval.py` 要点清单核对 harness（must_contain/must_not_contain + selftest）+ g1-contract-quality（可跑，selftest 7/7 PASS）+ g2-arbiter-conflict（scaffold） |
| **P2-7** | `registry_query.py`(新) + `arbiter.md` | scoped 查询脚本（api/schema/decisions 按维度过滤 + stats 分档）；arbiter must_read 移除全量 jsonl，改「小表(≤50)全读 / 大表 scoped 查询」 |
| **P2-8** | `events.py` + `workflow-reviewer.md` | events 加 `durations` 子命令（相邻事件 ts 差算每步墙钟时长，token proxy）；workflow-reviewer 加耗时聚合 + 度量映射 |

**验证：**
- `run_eval.py selftest g1-contract-quality` → 7/7 PASS；反向注入越界产物 → 正确 FAIL
- `registry_query.py` 过滤逻辑（path-prefix/active-only/exclude-self/entity）造样本验证通过
- `events.py compute_durations` 造事件序列验证最慢步识别正确
- `consensus_poll._decide` approved/rejected/pending/ambiguous 四态验证通过
- 所有 flow JSON + manifest JSON 合法；flow_advance 无 active task 时优雅报错不崩

**未做（超出本次范围，留待后续）：**
- P0-1 Phase 0 目前是 evaluator.md 内的强制 bash 指令（threat model：evaluator 与 generator 独立、无合谋动机，指令级足够）；若要防 evaluator 自身跳过，可后续硬化为脚本 + hook
- P1-5 consensus_poll 未接入 session-start 自动轮询（避免 hook 内做 TAPD 网络调用的风险），保持手动一命令触发
- eval golden 仅 2 个（g1 可跑 + g2 scaffold），后续按真实回归需求扩充
