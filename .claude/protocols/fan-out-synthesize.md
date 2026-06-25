# Fan-Out-and-Synthesize Protocol — 并行扇出编排协议

**定位：** 子代理并行编排的项目级通用协议。当一个任务可拆成多个**互相独立**的子任务时,把它们扇出到多个 `Agent` 子代理并行执行,再在**单点 join** 汇总——压缩墙钟时间、给每个子任务干净隔离的上下文窗口,规避单上下文的三类失败(代理懒惰 / 自我偏好偏差 / 目标漂移)。

**提炼源:** `.claude/skills/java-testing/references/ac-split-parallel.md`(已在生产验证的 AC-split 并行集成测试模式)。本协议把该模式从单 skill 内部细节抽象为通用编排契约,供 audit / sprint-review / orchestrate 等多场景复用。

**何时用:** 任务含 ≥ N 个同类可独立处理的对象(audit 的 7 phase、sprint-review 的多 blocker、迁移的多文件、调研的多来源),且瓶颈在 LLM 串行生成而非执行。**何时不用:** 对象数低于阈值 / 子任务间强依赖 / 简单任务(文章警告:workflows 并非每个任务都需要,可能消耗显著更多 token)。

---

## 一、四种编排模式

### 1. fan-out-and-synthesize(扇出汇总)— 核心模式

```
输入(N 个独立对象)
  ├─ Step 1  共享 prelude(串行):建立公共上下文 / 读历史状态 / 切分维度
  ├─ Step 2  并行 fan-out:一条消息内并行发起 N 个 Agent 调用,每对象一个子代理
  ├─ Step 3  各子代理独立产出 → 写独立 artifact + 返回结构化结果(不回贴正文)
  └─ Step 4  单点 join:主 Claude 单线程汇总 / 写 living artifact / 生成聚合产物
```

适用:固定维度、可枚举的独立对象集。墙钟 = 最慢单链,而非串行总和。

### 2. loop-until-done(循环至完成)

工作量未知时,持续扇出至停止条件(无新发现 / 无错误日志 / 达上限)。

**已落地实例:** GAN 三角的 generator 自修 + evaluator retry(`retry_count` 跨 phase 共用上限 3 次,见 `agents/generator.md` / `agents/evaluator.md`)就是本模式的**有界实例**——evaluator FAIL → generator 修 → 重新交付,循环至 PASS 或达 retry 上限写 Blocker 升级人工。有界上限是铁律,无界循环会掩盖深层问题(对齐 `task-lifecycle.md` 迭代上限)。

### 3. classify-and-act(分类路由)

**已落地实例:** `commands/start-dev-flow.md` 意图识别 → 路由到 vibe/plan/spec/orchestrate 档 + 对应 flow 模板。本协议不重写,作为已实现范例引用。

### 4. tournament(锦标赛)— 按需启用

N 个子代理用不同策略竞争同一任务,评判子代理成对比较选胜者。当前无固定场景,标注**按需启用**;真要用时遵守本协议的 join 铁律(评判由单点汇总,不让候选子代理互评)。

---

## 二、单点 join 铁律(核心约束)

**living artifact / registry 只能由主 Claude 在 join 点单线程写,子代理一律不直接写共享状态。** 这是 fan-out 不出错的根本契约,直接继承 `~/.claude/rules/agent-dev-standard/artifact-based-handoff.md`:

1. **子代理只写独立 artifact**(各自的报告 / 测试文件,天然不冲突),**返回消息只含结构化结果 + 文件路径**(契约 3:不回贴整份 JSON / Markdown 正文)。
2. **共享 living artifact(registry / 汇总文件)的写入,全部收敛到 join 点**,由主 Claude 单线程批量执行。registry 守 INSERT-only + 单写者(audit-agent 类子代理只能产"INSERT 建议",由父会话代写)。
3. **强制时序:** 若子代理产出有依赖(如都 `extends` 同一支撑类),依赖项必须在 fan-out 前的 prelude 中先落盘。

---

## 三、安全阀(沿用 ac-split-parallel)

| 阀 | 触发 | 动作 |
|----|------|------|
| 小批量跳过 | 独立对象数 ≤ 阈值(典型 ≤ 3~4) | 退串行单线程,不值得扇出开销 |
| 嵌套降级 | 执行环境不支持嵌套子代理 | 自动串行,**绝不阻塞主流程** |
| 有界重试 | 某子代理没产出 / 产物不合格 | 对该对象单独修复重试 ≤ 2 次;超限标 ERROR + 现场信息 |
| 无声截断禁止 | 因上限丢弃部分对象 | 必须 `log` 说明丢了什么,不得静默截断当"全覆盖" |

---

## 四、fan-out 子代理 prompt 契约

主 Claude 在**一条消息内并行发起多个 Agent 调用**,每对象一个。每个子代理 prompt 必含:

- **输入:** 本对象的子集数据 + 它需读的源路径(不给全局噪声,遵守"最小有效上下文")。
- **约束:** 边界纪律逐条写进 prompt(如 GAN 场景:禁止读他方产物判断 / 禁止重复定义共享 fixture)。
- **输出:** 写到约定路径的独立 artifact;返回消息**只含路径 + 结构化结果摘要**。
- **子代理类型:** 默认 `general-purpose`(保持验收侧独立时不用 `generator`)。

---

## 五、反模式(禁止)

- ❌ 子代理回贴整份内容到返回消息(违反 artifact-based-handoff 契约 3,消息会被压缩丢失)。
- ❌ 多个子代理并发争抢同一 living artifact / registry 写权(状态冲突 + 审计链断裂)。
- ❌ 横切对象(无独立上下文 / 依附主流程的关注点)拆成独立子代理——应跟随它贯穿的主对象组。
- ❌ fan-out 前漏落盘共享依赖(子产物无法编译 / 无法引用)。
- ❌ 无界 loop-until-done(无上限会掩盖深层问题,必须有界 + 超限升级)。
- ❌ 对象数低于阈值仍强行扇出(开销 > 收益)。

---

## 六、关联

- **Worked example:** `skills/java-testing/references/ac-split-parallel.md`(AC-split 并行集成测试,6 步协议 + 两级分组 + 支撑类 prelude)。
- **铁律来源:** `~/.claude/rules/agent-dev-standard/artifact-based-handoff.md`(契约 1/2/3 + registry 生命周期 + 单写者)。
- **有界上限:** `~/.claude/rules/agent-dev-standard/task-lifecycle.md`(迭代上限,防死循环)。
- **消费方:** `skills/audit/SKILL.md`(`all` 模式 7 phase 扇出)、`commands/sprint-review.md`(多 blocker 扇出)、`skills/orchestrate/SKILL.md`(动态编排逃生舱)。
