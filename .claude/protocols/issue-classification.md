---
status: Proposed
dogfood-judge: cross-family ≥ 2 project evidence + ≥ 10 issue 分类实证
proposed-by: jchen2026
accepted: 2026-05-26
related-issue: https://github.com/chatlabs-ai/agent-dev-standard/issues/14
sibling-rule: rules/core/issue-handling.md(本 protocol 是其上游分类协议)
related-protocol: protocols/async-review.md(本 protocol C 类路由目标)
upgrade-path: dogfood → ADR-009(候选) → active
---

# Issue Classification — 问题来源四分类前置协议

> **定位:** standard 强制类协议 / `rules/core/issue-handling.md §一` 之前的**问题进入瞬间分类节点** / 影响所有 standard 项目 issue 流转。
>
> **形式化依据:** `rules/core/formalization-timing.md §"类型 B 节点配套"` — 节点客观存在(问题进来时的性质分类)+ 规则配套缺失(`issue-handling.md` 仅覆盖修复阶段 / 前置分类空白)+ 违规会沉底(业务需求被当 bug 修 / 设计问题被绕过 / 工作流缺陷被吃掉)。
>
> **dogfood 升级判据(强制类规约):** 跨家族 ≥ 2 项目实证 + ≥ 10 issue 分类实证。
>
> **接纳哲学(2026-05-26 用户拍板):** 全 6 决策点 OK / 强制类不降级 opt-in(分类失同 = 不同项目同一 issue 处理路径不同 = 同源失同)。

---

## 边界声明

✅ 本协议管:问题进来瞬间的**性质分类**(A / B / C / D 四类)+ 路由目标
❌ 本协议不管:
- 修复路径细分(B 类的 S1-S5 → 见 `rules/core/issue-handling.md §一` 5 场景)
- 状态机流转(→ 见 `protocols/issue-process.md`)
- 评审承载机制(C 类路由的承载 → 见 `protocols/async-review.md`)

---

## 四类定义

| 代码 | 类型 | 含义 | 标签 | 路由 |
|------|-----|------|------|------|
| A | business | 产品想要新功能或修改既有行为 | `type:business` | 产品决策流程(不走 `/issue`)|
| B | bug | 实现与设计 / 共识不符 | `type:bug` | `/issue` Step 0 → S1-S5 5 场景判定 |
| C | design-issue | 设计文档本身有错 / 漏 / 矛盾 | `type:design-issue` | 评审通道(详见 `protocols/async-review.md`)|
| D | workflow-improve | skill / 规则 / 协议本身有缺陷 | `type:workflow-improve` | 形式化评估(`rules/core/formalization-timing.md`)|

### D 类 — workflow-improve(元层议题)

含义: standard 的 skill / rule / protocol 本身有缺陷 / 需要改善

**自洽声明:** standard repo 自己的元层议题(改 standard rule / protocol / skill / template)→ 全部标 D 类。
即 standard 用自己定的本 protocol 处理自己的元层 issue / 这是 dogfood 自洽的体现。

路由: 触发 formalization-timing 评估 → ADR(候选)或直接 SA handoff

历史议题: 不强制回填(参考 14.3)/ 新议题应标 D 类。

---

## 分类判据决策树

```
问题进入 → 判断「现有设计 / 共识文档是否覆盖期望行为」
  ├─ 设计文档明确定义此行为 / 但实现错 → B (bug)
  ├─ 设计文档未定义此行为 / 产品想要新行为 → A (business)
  ├─ 设计文档有定义但本身错 / 漏 / 矛盾 → C (design-issue)
  └─ 问题不在产品功能层 / 而在 skill / 规则执行层 → D (workflow-improve)
```

### [v1 OPEN] 四类边界判断歧义(14.1)

`[v1 待 dogfood 反馈:jchen2026 dogfood 期 ≥ 10 issue 分类实证反哺]`

v0 提供决策树骨架(4 个判断分支)/ 不预设 5-10 边界 case 的具体决策示例。dogfood 期累积"实际 issue 落到哪类 + 为什么 + 是否有人有不同看法" → v1 收敛为决策树扩展段 + 边界 case 示例库。

典型潜在边界 case(等 dogfood 实证 / 不预设解):
- PM 描述模糊时是 A 还是 C?(需求未明 vs 设计未覆盖)
- 实现行为与设计文档轻微出入但符合 PM 口头意图 — 是 B 还是 A?
- 工作流问题源于 standard rule 缺失 vs 项目自身实施漏 — 是 D 还是非分类范畴?

---

## 与现有 S1-S5 的关系

```
Issue raised
  ↓ Step 0.5 — 四分类判定(本协议)
  ├─ A → 产品决策流程(不走 /issue)
  ├─ B → /issue Step 0 → S1-S5 场景判定(rules/core/issue-handling.md 现行)
  ├─ C → 评审通道(protocols/async-review.md)
  └─ D → 形式化评估(rules/core/formalization-timing.md)
```

四分类是 issue 进来的**前置分类**(性质判断)/ S1-S5 是 B 类型问题的**修复路径细分**(执行判断)。**不替换 / 不冲突 / 上下游关系**(本协议是 issue-handling 的上游)。

---

## 硬约束:Issue 必含分类标记

**约束:** Issue 第一条 comment 或 body 含 `[classification] <A/B/C/D>` 标记 / 或对应 `type:*` label / 否则视为未分类 → SA triage 时补打。

**实施位置:**
- Issue 创建时(template form / 第一条 comment / body)
- SA triage 阶段(若 contributor 未标 / SA 补打)
- 流转阶段(若分类变更 / 显式重新标 + 说明)

### [v1 OPEN] label 命名(14.2)

`[v1 待业界 + dogfood 实证决定是否改名]`

v0 用提案者原稿 4 个 label 名:`type:business` / `type:bug` / `type:design-issue` / `type:workflow-improve`。

业界存在不同惯例(如 `type:feature` / `type:requirement` / `type:enhancement` 等同义命名)。v0 暂用提案者命名 / dogfood 期累积"业界提案者 / 跨团队是否对 label 名有改名建议" → v1 评估是否重命名。

---

## 现存 issue 处理

### [v1 OPEN] 历史 issue 回填策略(14.3)

`[v1 待评估:何时清理历史 unclassified issue]`

v0 **不强制回填**(参考 14.3)/ 新 issue 开始执行本协议。

历史已 closed 的 governance / proposal / meta 类 issue(如 #6 / #10 / #12 / #19 等)— 不强制补 D 类 label。等 dogfood 期满 → SA 评估"是否值得清理历史 unclassified issue / 还是接受未分类历史层"。

---

## 跨平台抽象

### [v1 OPEN] 跨平台 adapter(14.4)

`[v1 待 TAPD adapter 反哺(jchen2026 dogfood)]`

v0 仅 GitHub label 实施 — 标签层即 `type:*` label。

跨平台抽象(TAPD 字段 / Linear / Jira 等):
- GitHub: `type:*` label(本 v0 范围)
- TAPD: 字段映射待 dogfood(jchen2026 试点 TAPD 反哺)
- Linear / Jira: 等实际项目需求触发(类比 `protocols/spec-tracker-sync.md` adapter 模式)

dogfood 期累积"实际跨平台 adapter 落地需要 / 平台 label 能力差异" → v1 补 §跨平台 adapter 段。

---

## 与其他 rule / protocol 的关系

### 与 `rules/core/issue-handling.md` 关系

**上下游关系:** 本协议是 `issue-handling.md` 的**上游**:
- 本协议:issue 进入瞬间的**分类判定**(A / B / C / D)
- `issue-handling.md`:B 类 issue 进入后的**修复路径判定**(S1-S5)

`issue-handling.md` 新加 §一.5 "Step 0.5 — 问题分类(前置节点)" 段 = 本协议在 issue-handling 流程中的承载入口 / 详见该 rule。

### 与 `protocols/async-review.md` 关系

**上下游关系:** 本协议是 `async-review` 的**上游**:
- C 类 design-issue 路由目标 = `async-review` 评审承载
- 即 issue 分类为 C → 起 async-review handoff(`kind: review`)

### 与 `rules/core/formalization-timing.md` 关系

### [v1 OPEN] D 类 ↔ formalization-timing 衔接细节(14.5)

`[v1 待 dogfood 反馈:D 类触发 formalization-timing 评估的具体衔接 SOP]`

v0 显式声明 "D 类触发 formalization-timing 评估" / 但具体衔接 SOP 标占位:
- D 类触发后 / 如何走 type A(跨项目阈值)vs type B(节点配套)评估?
- 评估结果走 ADR(候选)还是直接 SA handoff?
- 评估周期 / 决策方 / 触发频率?

v0 不预设具体 SOP / 等 dogfood 期累积"实际 D 类 issue 处理路径实证" → v1 收敛为衔接 SOP 段。

### 与 `protocols/issue-process.md` 关系

本协议是 `issue-process` **状态机** 的入口前置节点。状态机定义"issue 进入后的状态流转" / 本协议定义"issue 进入时的分类标记"。两者协同(本协议补状态机入口处的分类标签维度)/ 不冲突。

---

## 反模式

- ❌ Issue 不标分类直接进 `/issue` 流程(假设全是 B 类 → 业务需求被当 bug 修)
- ❌ 把设计问题(C 类)按 B 类直接改代码(改完代码 / 设计文档仍错 / 下次再踩)
- ❌ 把工作流问题(D 类)在项目层修(应该回流 standard / 不应在项目层局部 patch)
- ❌ 历史 issue 强制回填(违反 14.3 / 接受未分类历史层)
- ❌ Label 命名跨流派强行统一(违反 14.2 / 等业界惯例稳定)

---

## 关联

- `rules/core/issue-handling.md` §一.5 — Step 0.5 入口承载段(本批次同步落)
- `rules/core/formalization-timing.md` §"类型 B 节点配套" — 本协议形式化依据
- `protocols/async-review.md` — C 类路由的评审承载协议
- `protocols/issue-process.md` — 状态机定义(本协议是其入口前置)
- `templates/labels.yml.template` — 4 type label 模板(本批次同步加)
- `install/modules/09-github-labels.sh` — 项目 label 同步入口
- Issue #14 — 提案来源 + 接纳决策
- 候选 ADR-009 — 跨家族实证累积后走的形式化路径

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|----|----|
| 2026-05-26 | v0 (Proposed) | 初建 / jchen2026 提案原稿落盘 / D 类自洽声明段(SA 视角补)/ 5 个 `[v1 OPEN]` 开放点 / dogfood-judge 跨家族 ≥ 2 项目 + ≥ 10 issue 实证 / 候选 ADR-009 |
