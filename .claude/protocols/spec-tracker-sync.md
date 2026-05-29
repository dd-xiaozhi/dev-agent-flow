---
status: Proposed
dogfood-period: 2026-06-01 ~ 2026-08-31
proposed-by: jchen2026
accepted: 2026-05-26
related-issue: https://github.com/chatlabs-ai/agent-dev-standard/issues/18
sibling-protocol: protocols/tapd-worktime-integration.md
---

# Spec ↔ Tracker Sync — 共识文档与项目跟踪工具的双向绑定协议

> **定位:** standard 的可选扩展协议——为已使用项目跟踪工具(TAPD / Jira / Linear 等)的团队提供"共识文档 §AC ↔ Tracker Story"的双向绑定机制 / 类比 `protocols/tapd-worktime-integration.md` 的协作工具桥接哲学(管"已存在两端怎么映射" / 不入侵 PM 工作流)。
>
> **dogfood 期:** 2026-06-01 ~ 2026-08-31(90 天)/ 由 jchen2026 在 1-2 个 TAPD 项目试点 / 反哺 5 个 `[v1 OPEN]` 开放点。
>
> **接纳哲学(2026-05-26 用户拍板):** "我们提供范式 / 各个 role 按需使用 / 没有则跳过;等待提出者后续的实证反馈 / 再决定范式的升级。"

---

## 边界声明

✅ 本协议管:已存在的 AC ↔ 已存在的 Story 的双向映射机制
❌ 本协议不管:
  - AC 内容怎么写(PM / SA 主导共识文档)
  - Story 怎么建 / 怎么排优先级(PM 主导 Backlog 管理)
  - 工时怎么算(参考 `protocols/tapd-worktime-integration.md`)

---

## 三态自适应(按团队当前工作模式自动选择)

| 模式 | 触发 | 行为 |
|------|------|------|
| **Story-First** | 项目跟踪工具中已有 Story 列表 | 校验补缺模式:验证共识文档 AC 与 Story 双向一致性 / **不新建 Story**(PM 主导)|
| **Design-First** | 共识文档已有 AC / 但项目跟踪工具未建 Story | 仅输出"待 PM 建 Story 清单"(不代 PM 建)|
| **Local** | 团队无项目跟踪工具 | 分配本地 SPEC ID(不与外部系统同步)|

**注意:v1 的"Design-First 批量建 Story"已删除** — 那部分越界(代 PM 创建 Backlog 项)/ 本提案只输出清单给 PM。

### [v1 OPEN] 三态判定机器化算法

`[v1 待 dogfood 反馈:由 jchen2026 试点中实际判定 patterns 反哺]`

v0 不预设机器化判定逻辑(三态由人工 / skill 启动时 prompt 用户选择)。dogfood 期累积"实际项目处于哪一态的判定依据" → v1 收敛为机器可执行算法(如:`tracker_story_count > 0 → Story-First` / `consensus_ac_count > 0 && tracker_story_count == 0 → Design-First` / 等)。

---

## 双向绑定 schema

**共识文档侧(AC 章节):**
- 每条 AC 含 `Tracker:` 字段(如 `[TAPD-12345]` 或 `[PENDING]`)

**项目跟踪工具侧(Story description / custom field):**
- `spec-ref: consensus-design.md §AC-NN`

### [v1 OPEN] spec-ref 字段位置(description vs custom field)

`[v1 待 dogfood 反馈:试点中字段位置实际可用性反哺]`

v0 不预设 protocol 层默认 / 各 adapter 按工具特性选择(详见对应 skill v0):

| 候选 | 优势 | 劣势 |
|------|------|------|
| Story description(主体内容)| 复杂度低 / 通用性强(各工具普遍支持)| 与人工编辑混在一起 / 易被改 |
| Custom field | 结构化 / 不被人工编辑触碰 | 需工具支持 custom field + 配置成本 |

dogfood 期累积"实际工具中哪个位置可读 / 可写 / 不易被覆盖" → v1 评估是否在 protocol 层规约默认。

### [v1 OPEN] AC ID schema 稳定性

`[v1 待 dogfood 反馈:试点中 AC ID 实际用法反哺 / SA 评估是否升 spec-to-code-flow 主体]`

v0 假设共识文档 §AC 段每条 AC 有稳定 ID(形如 `§AC-NN`)/ 但 standard 主体 `rules/core/spec-to-code-flow.md` 未规约 AC ID 命名约定。dogfood 期累积"AC ID 实际怎么编 / 变更时怎么迁移" → v1 评估是否将 AC ID schema 升入 spec-to-code-flow 主体。

### [v1 OPEN] AC ↔ Story 多对多聚合策略

`[v1 待 dogfood 反馈:试点中实际场景反哺选择默认]`

v0 列出 3 种候选 / 不预设默认:

| 候选 | 含义 |
|------|------|
| 按业务能力 | 1 Story 覆盖 1 业务能力(N 个 AC)/ 适合粗粒度 |
| 按用例 | 1 Story 覆盖 1 用例(1-2 个 AC)/ 适合细粒度 |
| 按章节 | 1 Story 对应共识文档 1 章节(M 个 AC)/ 适合文档驱动 |

dogfood 期累积"jchen2026 项目实际选了哪种 + 为什么" → v1 收敛为推荐默认策略 + 边界条件。

---

## 状态机映射(adapter 实施)

各团队状态机不同 / 由 adapter 适配标准生命周期:

| 标准生命周期 | 含义 |
|------|------|
| `planned` | AC 已写 / Story 已建 / 未启动 |
| `in-progress` | 实施中 |
| `awaiting-test` | 实施完成 / 待测 |
| `tested` | 已验证 |

各 adapter 负责把标准生命周期 ↔ 团队具体状态机(如 TAPD `planning / developing / resolved / closed`)做映射。

---

## sync-state 文件

每次同步产出 `sync-state-<feature>.md` 记录本次同步明细(供审计 + 跨工具迁移重建依据)。

### [v1 OPEN] sync-state 文件 schema

`[v1 待 dogfood 反馈:试点中字段实际用法反哺]`

v0 仅声明用途 + 示例(给 2-3 行 YAML 示例)/ schema 字段由提案者 dogfood 反哺:

```yaml
# 示例(非权威 schema)
feature: <feature-name>
sync-date: 2026-06-15
mode: Story-First  # Story-First | Design-First | Local
mappings:
  - ac: "§AC-01"
    tracker: "TAPD-12345"
    state: in-progress
  - ac: "§AC-02"
    tracker: "[PENDING]"
    state: planned
```

完整 schema(必填字段 / 可选字段 / 跨工具兼容性 / migration 字段)由 dogfood 反哺 → v1 规约。

---

## Adapter 实施清单

### v0 范围

- ✅ `skills/extension/tapd-story-binding/` — TAPD adapter(本批次新建 / 实施本协议)

### v1 候选(等 protocol stable + 实际项目需求触发)

- `skills/extension/jira-story-binding/`
- `skills/extension/linear-story-binding/`
- `skills/extension/github-issue-binding/`

**不预先起其他 adapter** / 等 TAPD adapter dogfood 稳定 + 有跨工具需求时再起。

---

## 关联

- `protocols/tapd-worktime-integration.md` — sibling protocol / 同档次"协作工具桥接"哲学
- `skills/extension/tapd-story-binding/` — 本协议的 TAPD 执行 skill
- `rules/core/spec-to-code-flow.md` §"共识文档"节点 — AC 所在的上游节点
- `rules/core/formalization-timing.md` §"类型 B 节点配套" — 本协议形式化依据
- Issue #18 — 提案 + 接纳决策来源

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|----|----|
| 2026-05-26 | v0 (Proposed) | 初建 / jchen2026 提案原稿落盘 / 5 个 `[v1 OPEN]` 开放点显式标注 / 等 dogfood 反哺 v1 收敛 |
