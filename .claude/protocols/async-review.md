---
status: Proposed
dogfood-judge: cross-family ≥ 2 project evidence
proposed-by: jchen2026
accepted: 2026-05-26
accepted-partial: true
deferred-component: skills/extension/async-review/(等 #14 拍后联动)
related-issue: https://github.com/chatlabs-ai/agent-dev-standard/issues/16
related-deferred-issue: https://github.com/chatlabs-ai/agent-dev-standard/issues/14(C 类 design-issue 路由目标)
sibling-protocol: protocols/tapd-worktime-integration.md / protocols/spec-tracker-sync.md(同档协议层)
upgrade-path: dogfood → ADR(候选) → active
---

# Async Review — 异步文档评审承载协议

> **定位:** standard 强制类协议(改 protocols/ 主体)/ 任何走异步评审必走此协议 / 与 `protocols/tapd-worktime-integration.md` + `protocols/spec-tracker-sync.md` 同档"协作通道"哲学。
>
> **接纳哲学(2026-05-26 用户拍板):** "(#16)只接 protocol + handoff kind 扩 / 缓 skill" — 部分接纳 / extension skill 等 #14 联动起 / 避免独起 skill 后 #14 决策变更导致 rework。
>
> **dogfood 升级判据:** 跨家族 ≥ 2 个项目实证(强制类规约)。
>
> **核心边界:**
> - ✅ standard 负责:评审**过程**的协作通道(承载机制 / 评论分类 / 两阶段闭环)
> - ❌ standard 不负责:评审**结论**如何写进文档(文档主导方负责 — PM / SA / TL 等)
> - `--confirm` 阶段**只输出结构化结论清单 / 不自动修改任何文档**

---

## 承载机制

评审通过 issue tracker / Task 系统的 comment 承载(不依赖特定平台):

1. 评审发起方为待评审文档创建评审承载 entity(Issue / Task)
2. entity 的 title 含 `[review]` 标识 + 文档名 + 版本
3. entity 的 body 含:文档链接 + 评审范围 + 关注点

### [v1 OPEN] 跨平台抽象(16.4)

`[v1 待 dogfood 反馈:jchen2026 试点 TAPD 反哺 / 跨平台具体适配(GitHub PR review vs TAPD Task vs Linear)由实证驱动]`

v0 仅声明"通过 issue tracker / Task 系统 comment 承载 / 不依赖特定平台" / 不预设具体平台 adapter。dogfood 期累积"实际承载平台 + 各平台 comment 能力差异" → v1 评估是否补 platform-specific adapter 段。

---

## 评论分类标记(强制)

每条评论第一行必须含分类标记:

| 标记 | 含义 |
|------|-----|
| `[决策]` | 需要拍板的方向选择 |
| `[建议]` | 提议修改但不强制 |
| `[问题]` | 发现的错误或矛盾 |
| `[LGTM]` | 整体通过 |
| `[补充]` | 提供上下文 / 不要求动作 |

### [v1 OPEN] 评论分类标记边界(16.3)

`[v1 待 dogfood 反馈:[决策] vs [建议] 边界 case 决策树由试点反哺]`

v0 列出 5 类标记 / 不预设边界 case 决策树(如:对方向选择的"建议" — 算 [建议] 还是 [决策]?对设计错误的"问题" — 算 [问题] 还是 [决策]?)。dogfood 期累积"实际评审中歧义 case + 团队怎么 resolve" → v1 收敛为决策树或边界 case 示例段。

---

## 两阶段闭环(仅承载 + 归集 + 输出结论 — 不修改文档)

### Stage 1: collect

1. 扫描评审承载 entity 的所有 comment
2. 按分类标记自动归类
3. 生成 `preview-v<N>.md`(决策段 / 建议段 / 问题段 / LGTM 段 / 补充段)
4. 输出供团队 review

### Stage 2: confirm

1. 团队对齐后 / 对每条标注落地动作(通过 / 驳回 / 延后 / 修复)
2. **输出 `conclusion.md`** 给文档主导方(含每条意见的落地决策)
3. 关闭评审承载 entity
4. **不自动修改任何文档** — 落地由文档主导方按 `conclusion.md` 执行

### [v1 OPEN] 多评审承载 entity 同时活跃(16.2)

`[v1 待 dogfood 反馈:批量扫 in-progress/ 输出统一报告的实施细节由 skill v1 补]`

v0 标 mitigation 方向(collect 阶段强制扫整个 in-progress/ / 输出统一报告)/ 但具体实施细节(报告格式 / 跨 entity 归集策略 / 优先级排序)由 skill v1 补(skill 已起 2026-05-26 / 见 §Skill 联动起说明)。当前 dogfood 期单 entity 评审先跑 / 多 entity 并发场景累积反馈后再补。

---

## conclusion.md 落地约束(16.1)

confirm 输出 `conclusion.md` 后 / 落地由文档主导方负责。**强制约束:**

- handoff `kind: review` frontmatter 必填 `review_doc_owner`(PM / SA / TL 等)
- handoff 闭环要求 `review_doc_owner` 在文档 commit 后 / 回 comment 标 commit hash
- 不回 comment 标 commit hash → handoff 不得标 completed(评审悬空 = 未闭环)

### [v1 OPEN] review_doc_owner 类型枚举(16.1 衍生)

`[v1 待 dogfood 反馈:文档主导方角色清单由试点反哺]`

v0 仅举例(PM / SA / TL 等)/ 不强制枚举清单(各团队角色命名不一 / 强制清单易过度规约)。dogfood 期累积"实际项目中谁主导哪类文档" → v1 评估是否补推荐枚举段。

---

## 与其他 rule 关系

### 与 `/audit` 关系(16.5)

不冲突:
- **audit** = 单方主导审查(SA 审 BE 产出 / 验证实施符合 spec)
- **async-review** = 多方对齐(评审同一份文档 / 寻求共识)

两者承载机制不同(audit 走 audit report artifact / async-review 走 issue tracker comment)/ 处置时机不同(audit 后置 / async-review 前置或同步)。

#### [v1 OPEN] audit ↔ async-review 边界 case(16.5 衍生)

`[v1 待 dogfood 反馈:同一文档同时需 audit + async-review 的次序与边界由试点反哺]`

v0 仅划清楚两者职能差异 / 不预设组合场景规则。dogfood 期累积"同一文档先 async-review 再 audit?还是 audit 发现问题后起 async-review?跨流派衔接边界?" → v1 评估是否补 §组合场景段。

### 与 `/handoff` 关系

定位为 handoff 的 `kind: review` 子类型 / 共享:
- pending / in-progress / completed 生命周期
- frontmatter schema(扩 3 字段)

差异:
- 多方汇聚(vs handoff 通常 1:1 推送)
- 评论分类承载(vs handoff 用文件 body)
- 两阶段闭环(vs handoff 单阶段执行)

详见 `skills/core/handoff/SKILL.md` §kind: review 段。

### 与 spec-to-code-flow 关系

`rules/core/spec-to-code-flow.md` §入口接口点已声明"共识文档评审通过版本"作为路径入口 / 但**评审过程本身** spec-to-code-flow 未规约。本协议补此节点 — 评审承载 = spec-to-code-flow 入口接口点的前置子流程。

---

## 反模式

- ❌ 评审散在外部聊天工具(无法机器化归集)
- ❌ 评论无分类标记
- ❌ collect 后不 confirm(评审悬空)
- ❌ confirm 阶段自动改文档(越界 — 落地由文档主导方负责)
- ❌ `review_doc_owner` 不回 comment 标 commit hash 而标 handoff completed(评审悬空 / 未闭环)

---

## Skill 联动起说明(2026-05-26)

本 protocol 的实施 skill `skills/extension/async-review/`(collect / confirm 两阶段)**已起**(2026-05-26 由 #14 接纳触发联动起 / 详见 handoff `code/docs/handoff/completed/2026-05/2026-05-26-issue-16-async-review-skill-linkage.md`)。

使用方式:
- 调用 `/async-review --collect [entity-id]` — Stage 1 拉取并归类评论
- 调用 `/async-review --confirm [entity-id]` — Stage 2 输出 conclusion.md

详见 `skills/extension/async-review/SKILL.md`。

Dogfood 期(2026-06 起 jchen2026 项目首跑):
- 累积 collect / confirm 实证
- 5 风险点 [v1 OPEN] 由实证反哺 v1 收敛
- 期满 SA review(2026-09 初评估)→ 走 ADR(候选)或保持 dogfood

**联动来源:**
- #14 C 类 `design-issue` 路由目标 = 本 protocol 评审承载
- #14 接受触发 #16 缓起 skill 联动起(2026-05-26 用户拍点 5 选 (a) "立即起")

---

## 关联

- `skills/core/handoff/SKILL.md` — `kind: review` 扩段(本批次同步落)
- `rules/core/artifact-based-handoff.md` — handoff 文件载体哲学(本协议沿用)
- `rules/core/spec-to-code-flow.md` §入口接口点 — 共识文档评审节点(本协议承载前置子流程)
- `rules/core/formalization-timing.md` §"类型 B 节点配套" — 本协议形式化依据(节点客观存在 + 配套缺失 + 违规会沉底)
- Issue #16 — 提案 + 接纳决策来源
- Issue #14 — C 类 design-issue 路由目标 / 决定 skill 起时机

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|----|----|
| 2026-05-26 | v0 (Proposed / Partial) | 初建 / jchen2026 提案原稿落盘 / 5 个 `[v1 OPEN]` 开放点 / extension skill 缓起等 #14 联动 / dogfood-judge: 跨家族 ≥ 2 项目实证 |
| 2026-05-26 | v0.1 (Proposed) | §缓起 skill 说明 替换为 §Skill 联动起说明(skill 由 #14 接纳触发联动起 / 2026-05-26 用户拍点 5 选 (a) 立即起)+ §多 entity [v1 OPEN] 段移除"缓起"措辞 |
