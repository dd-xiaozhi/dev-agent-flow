# TAPD Ticket Operations Protocol — 通用层

> **定位:** TAPD 全 ticket 类型(Story / Subtask / Item / Epic / Long-term Task / Bug)字段操作的**通用层硬约束**。本 protocol 落地 PM 规范 v1.5 §1 通用铁律 8 段 + 跨类型角色权限矩阵到执行层。
>
> **2026-05-25 起源(ADR-006 / Issue #12):** 原 `tapd-mcp-operations.md` 仅覆盖 Bug 字段层 / 5 类非 Bug ticket 无 protocol / §1 通用铁律 8 段未提炼。本文件是通用层 / 类型 sub-protocol 见 §九。
>
> **类型:** 节点配套类形式化(参考 `rules/core/formalization-timing.md` 类型 B)。
>
> **关联:**
> - `protocols/tapd-bug-operations.md` — Bug 类型 sub-protocol(2026-05-25 从 mcp-operations.md 重命名)
> - `protocols/tapd-worktime-integration.md` — 工时集成(独立 protocol / 不属本通用层)
> - `rules/core/issue-handling.md` — Issue / Bug 5 场景协作流纪律
> - `docs/maintenance/tapd-spec-sync-cadence.md` — PMO ↔ standard pull 同步节奏
> - **SSoT:** `docs/requirements/2026-05-20-tapd-bug-handoff-flow/source/pm-tapd-ticket-spec-v1.5.md`(PMO 规范 / 本 protocol 是其执行层落地)

---

## 一、通用铁律(适用所有 ticket 类型)

### IC-0.1 — 状态更新必须用 `v_status` / 禁止 `status`

**铁律:** 所有 ticket 类型(Story / Subtask / Item / Epic / Long-term / Bug)的状态更新 MCP 调用 **must** 传 `v_status`(中文值)/ **must not** 传 `status` 字段。

**理由:** API 不基于 `status` 触发流转规则 / `v_status` 是唯一被 portal 认可的状态字段。

**反模式:** `update_story_or_task v_status="待开发" status="open"` → portal 显示不一致 / 必须删除 `status` 参数。

**来源:** v1.5 §1.1。

### IC-0.2 — 创建 ticket 用两步法 / 禁止 `workitem_type_name`

**铁律:** 创建任何 ticket 类型 **must** 用两步法:

```
第 1 步: tapd:get_workitem_types(workspace_id) → 取目标类型的 id 字段
第 2 步: tapd:create_story_or_task(workitem_type_id=<上步 id>)
```

**must not** 传 `workitem_type_name` 字段(会触发 MCP 交互式列表 / 阻塞自动化)。

**优化:** 同对话内首次查询某类型 workitem_type_id / 后续复用(不需每次查)。

**来源:** v1.5 §1.2。

### IC-0.3 — 流转规则:API 不强制 / 必须自行遵守

**铁律:** TAPD API **不基于流转矩阵** 拦截非法状态转换 / 调用任何 `v_status` 值 API 都成功 / **必须 AI / Dev 协议层 self-discipline** 遵守 v1.5 各类型 §X.5 状态定义与流转矩阵。

**反模式:** Dev AI 推 Bug 到 `已上线`(API 完全放行 / portal 显示状态已被错误更新 / 需 QA reopen 纠正)。

**实测案例:** Bug 模块 IC-4 段(`protocols/tapd-bug-operations.md`)Obs-37 / AP-1。

**来源:** v1.5 §1.3 流转规则段。

### IC-0.4 — 优先级用 `priority_label` / 禁止 `priority` 数字

**铁律:** 优先级字段 **must** 传 `priority_label`(枚举中文值如 `High` / `Middle` / `Low` / `Nice To Have`)/ **must not** 传 `priority`(数字 1-5)。

**Bug 例外:** Bug 模块 portal 用 `priority` 但值是中文(`紧急` / `高` / `中` / `低`)/ 详见 `tapd-bug-operations.md`。

**来源:** v1.5 §1.3 优先级段(原文档编号重复 / 见 G5 backflow PMO §1.3 renumber 建议)。

### IC-0.5 — 自定义字段常量表(跨项目一致)

**铁律:** v1.5 §1.4 列出 9 个 `custom_field_192~200` 字段 / 枚举值跨项目一致 / **可直接写死 / 不需查询**。

**字段清单(完整枚举值见 v1.5 SSoT §1.4):**

| 字段 | API field | 类型 | 适用 ticket |
|---|---|---|---|
| 需求性质 | `custom_field_199` | 单选 | Story / Epic / Long-term |
| 协作类型 | `custom_field_198` | 单选 | Story / Epic |
| 来源 | `custom_field_197` | 单选 | Story / Epic / Long-term / Item |
| 前端 LOE(h) | `custom_field_196` | 数值 | Story / Subtask |
| 后端 LOE(h) | `custom_field_195` | 数值 | Story / Subtask |
| QA LOE(h) | `custom_field_194` | 数值 | Story / Subtask |
| 关联业务线 | `custom_field_193` | 多选 | 全 ticket |
| 受影响客户 | `custom_field_192` | 多选 | 全 ticket |
| 需求完整度评分 | `custom_field_200` | 数值 | Story |

**反模式:** 凭记忆猜测枚举值(必须查 v1.5 §1.4 / 或本 protocol §六枚举值速查)。

**来源:** v1.5 §1.4。

### IC-0.6 — 标签字段 `label` 枚举值

**铁律:** label 字段值跨项目一致 / 多选用 `|` 分隔:

`阻塞` / `开发受阻` / `有风险` / `等待设计走查` / `方案已沟通` / `等待转测`

**来源:** v1.5 §1.5。

### IC-0.7 — 动态字段必须查询(不可写死)

**铁律:** 以下字段每项目 / 每迭代 / 每票不同 / **must** 每次查询 / **must not** 写死:

| 字段 | 原因 | 查询方式 |
|---|---|---|
| `iteration_id` | 每项目每迭代不同 | `get_stories_fields_info` / 或用 `iteration_name` |
| `owner` | 人员列表每项目不同 | 输入中文名 |
| `parent_id` | 父需求 ID 每票不同 | 查询获取 |

**来源:** v1.5 §1.6。

### IC-0.8 — 12 条禁止事项清单

跨类型通用禁止 / 任一违反 = 协议层违规。详见 v1.5 §1.8 完整列表。本 protocol 摘要 12 条核心:

1. ❌ 禁止 `status` 参数更新状态(用 `v_status` / IC-0.1)
2. ❌ 禁止 create_story_or_task 传 `workitem_type_name`(用 ID / IC-0.2)
3. ❌ 禁止 `priority` 数字设优先级(用 `priority_label` / IC-0.4)
4. ❌ 禁止凭记忆猜 custom_field 枚举值(查 IC-0.5 / 或 v1.5 §1.4)
5. ❌ 禁止跳过回读验证(写入后 must `get_stories_or_tasks` 回读)
6. ❌ 禁止混淆 entity_type:stories(复数 / Story/Subtask 增删改查)vs story(单数 / 工时)
7. ❌ 禁止依赖 API 拦截非法流转(IC-0.3 / 协议层是唯一防线)
8. ❌ 禁止 get_timesheets 不传 `entity_type`(详见 worktime-integration)
9. ❌ 禁止 create_bug 用 `iteration_name`(Bug 模块特例 / 必须 `iteration_id`)
10. ❌ 禁止 update_bug 只改 v_status 不改 current_owner(成对操作 / Bug 模块 IC)
11. ❌ 禁止 Dev AI 推 Bug 越权状态(Bug 模块 IC-4)
12. ❌ 禁止把 API 返回 `status: resolved` 解读为"已解决"(Bug 模块 IC-5)

**来源:** v1.5 §1.8。

---

## 二、跨类型角色权限矩阵

**6 ticket 类型 × 5 角色 × 2 维度(创建 / 状态流转)= 60 cell**(从 v1.5 §2.2 / §3.2 / §4.2 / §5.2 / §6.2 / §7.2 整合)。

### 2.1 创建权限矩阵

| 角色 | Story | Subtask | Item | Epic | Long-term | Bug |
|---|---|---|---|---|---|---|
| PM / PO | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Dev(FE / BE)| ❌ | ✅(自分子任务)| ✅(提问) | ❌ | ❌ | ✅(自报)|
| QA | ❌ | ✅(测试子任务)| ✅(提问) | ❌ | ❌ | ✅(发现)|
| UI | ❌ | ❌ | ✅(提问)| ❌ | ❌ | ❌ |
| AM | ❌ | ❌ | ✅(提问)| ❌ | ❌ | ❌ |

**铁律:** Story / Epic / Long-term 的唯一创建者 = PM/PO。其他角色需求走 Item 提问通道反馈给 PM。

### 2.2 状态流转权限矩阵

| 角色 | Story | Subtask | Item | Epic | Long-term | Bug |
|---|---|---|---|---|---|---|
| PM / PO | ✅ 全 | ❌ | ✅ 全 | ✅ 全 | ✅ 全 | ✅ 部分(`已上线` / `已关闭`)|
| Dev(FE / BE)| ❌ | ✅ 自己的 | ❌ | ❌ | ❌ | ✅ Dev 端流转(`进行中` / `待测试`)|
| QA | ❌ | ✅ 自己的 | ❌ | ❌ | ❌ | ✅ 测试流转(`测试中` / `测试完成`)|
| UI | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| AM | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 自动化 | ✅(PM 等同)| ✅(执行者等同)| — | ✅ | ✅ | — |

**详细 Bug 流转规则:** 见 `tapd-bug-operations.md` IC-4(Dev v_status 推进上限 / 详细禁推清单 / API 行为)。

**详细 Story 流转规则:** 见 v1.5 §2.5 状态定义与流转 / §2.6 标准工作流。

**违规判据:** 角色超权操作 = 协议层违规 / 即使 API 调用成功(API 不基于角色拒绝调用 / IC-0.3)。

---

## 三、Ticket 标识协议(创建时显式标记)

**铁律:** 创建任何 ticket 时 / **must** 在 title 前加类型标识 + 角色标识(facilitate cross-team grep + 流转追溯):

| 类型 | 前缀 | 例 |
|---|---|---|
| Story | `[需求]` 或角色【PM】 | `【PM】用户登录 Story` |
| Subtask | `[子任务]` | `[子任务] FE 实现登录页` |
| Item | `[Q]` 提问 / `[CO]` 跟进 | `[Q] 是否需要支持 SSO?` / `[CO] 待 PM 答复 SSO` |
| Epic | `[Epic]` | `[Epic] Q2 Auth 系统重构` |
| Long-term | `[长期]` | `[长期] Spike: 引入 Redis` |
| Bug | (无前缀 / Bug 类型已显式) | `登录失败` |

**来源:** v1.5 §2.6 / §3.6 / §4.6 / §5.6 / §6.6 / §7.6 标准工作流段。

---

## 四、回读验证铁律(跨类型通用)

**铁律:** 任何 create / update MCP 调用后 **must** 立即用 `get_*` API 回读 / 确认写入字段实际值与预期一致。

```bash
# 模板
tapd:create_story_or_task(...)  # 返回 id
tapd:get_stories_or_tasks(id=<上步 id>)  # 回读
# 比对: v_status / current_owner / custom_field_* / priority_label
# 不一致 → escalate 或 retry
```

**理由:** API 返回 success 不代表写入正确(IC-0.3 / 字段被错误更新仍可能 return success)。

**来源:** v1.5 §1.8 第 5 条。

---

## 五、Entity Type 字段约定

**铁律:** entity_type 是 MCP 调用中区分 ticket 类型的关键字段 / 跨 API 不一致 / **必须按 API 文档查约定:**

| API | entity_type 值 | 适用 |
|---|---|---|
| `get_stories_or_tasks` / `create_story_or_task` / `update_story_or_task` | `stories`(复数) | Story / Subtask / Item / Epic / Long-term |
| `get_bug` / `create_bug` / `update_bug` | `bug`(单数) | Bug |
| `add_timesheets` / `get_timesheets` / `update_timesheets` | `story`(单数)| Story / Subtask 工时 |
| `add_timesheets` for Bug | `bug` | Bug 工时 |

**反模式:** `get_timesheets entity_type="stories"` → 422 错误(必须用单数 `story`)/ 详见 IC-0.8 第 6/8 条。

**来源:** v1.5 §1.8 第 6/8 条。

---

## 六、自定义字段枚举值速查(跨项目一致 / 可写死)

> **完整枚举值清单见 v1.5 SSoT §1.4。本 protocol 摘要常用字段。**

### 6.1 需求性质 `custom_field_199`(单选)

`新需求` / `需求变更` / `内部优化` / `手动调整数据`

### 6.2 协作类型 `custom_field_198`(单选)

`FE + BE + QA` / `FE + QA` / `BE + QA`

### 6.3 关联业务线 `custom_field_193`(多选 / `|` 分隔)

`定制项目` / `CLM` / `CLS` / `CLD` / `360` / `CLL` / `DC Connector` / `MC Connector` / `SXP` / `LANBAO`

### 6.4 受影响客户 `custom_field_192`(多选 / 27+ 项)

完整枚举见 v1.5 SSoT §1.4 / 本 protocol 不重复(避免 sync 维护开销)。

---

## 七、跨类型动作 SOP(标准操作流程)

### 7.1 创建 ticket 通用 SOP

1. 查 workitem_type_id(IC-0.2 Step 1 / 同对话首次)
2. 准备字段(static fields per v1.5 §X.3 创建规范 + custom_field per §1.4)
3. 调 create API(IC-0.2 Step 2 / 用 workitem_type_id)
4. 回读验证(§四)
5. (按需)创建 worktime entry(若 ticket 类型支持工时 / 见 worktime-integration)

### 7.2 状态流转通用 SOP

1. `get_*` 读当前 v_status / current_owner
2. 验证流转合法性(对照 v1.5 §X.5 状态定义与流转)+ 角色权限(§二)
3. 调 update API / `v_status=<目标>` + `current_owner=<下游>`(成对)
4. 回读验证(§四)
5. (Bug 特殊)comment 说明流转原因(详见 `tapd-bug-operations.md`)

### 7.3 跨类型联动 SOP(Story → Subtask / Story → Bug)

- Story 进 `开发中` 触发自动创建 Subtask(若 PM 已分子任务)
- Bug 关联 Story 走 `tapd-bug-operations.md` §IC-7

---

## 八、违规处置

跨类型违规(IC-0.1~0.8 任一)处置:

1. **立即:** AI / Dev 自检发现违规 → comment 详细说明 + 调正确 API 修复(若可)
2. **持久化:** 记 problem-registry P-NNN 条目 + 标 type = "tapd-protocol-violation"
3. **升级:** 同类违规复发 ≥ 2 次 → audit 起 finding + handoff PM/SA review 是否升级硬门禁

**详细 Bug 模块违规处置:** 见 `tapd-bug-operations.md` §C 违规识别表。

---

## 九、类型 sub-protocol 索引

本通用层提供跨类型铁律 + 角色权限。**类型特定字段层硬约束**在各 sub-protocol:

| Ticket 类型 | Sub-protocol 路径 | 状态 |
|---|---|---|
| Bug | `protocols/tapd-bug-operations.md` | ✅ 已建(2026-05-25 从 mcp-operations.md 重命名 / 7 IC 完整)|
| Story | `protocols/tapd-story-operations.md` | ⏳ 未建 / future issue 触发 |
| Subtask | `protocols/tapd-subtask-operations.md` | ⏳ 未建 / future issue 触发 |
| Item | `protocols/tapd-item-operations.md` | ⏳ 未建 / future issue 触发 |
| Epic | `protocols/tapd-epic-operations.md` | ⏳ 未建 / future issue 触发 |
| Long-term Task | `protocols/tapd-longterm-operations.md` | ⏳ 未建 / future issue 触发 |

**触发判据(sub-protocol 起建):**

- 该类型出现高频 standard 缺位场景(累积 ≥ 2 实证)
- 字段层硬约束足够独特(不能仅由本通用层 + v1.5 SSoT 覆盖)
- 与 audit / issue SKILL 有具体 sub-protocol ref 需求

未触发前 / AI / Dev 操作非 Bug ticket 类型时 **must** 按本通用层 + v1.5 SSoT §X 章节(各类型详细规范)执行。

---

## 十、与 audit / install / issue skill 的接口

### audit SKILL ref

`code/skills/core/audit/SKILL.md` issue-process / TAPD 平台分支 应:
- 通用铁律违规检查(本 protocol IC-0.1~0.8 / 跨所有 ticket 类型)
- 角色权限违规检查(本 protocol §二 / 60 cell)
- Bug 类型字段违规检查(`tapd-bug-operations.md` IC-1~7)

### install SKILL ref

`code/skills/core/install/SKILL.md` 项目初始化时:
- 项目 CLAUDE.md `## TAPD 配置` 段配置 `tapd_enabled: true` + workspace_id + project mapping
- 启停门(global skill 与本 protocol 配套)/ 未启用 TAPD 项目零影响

### issue SKILL ref

`code/skills/core/issue/SKILL.md` TAPD 平台分支:
- Step 0 自检表含 TAPD ticket 字段
- 收尾段含 TAPD 工时填写(走 `tapd-worktime-integration.md`)
- Bug 流转(走 `tapd-bug-operations.md`)

---

## 十一、Pull 同步节奏

**触发:** PMO 发布 v1.5 / v1.6 / v2 等新版本时 / standard 需评估跟进。

**节奏:** 月度 review / PMO 通知触发(详见 `docs/maintenance/tapd-spec-sync-cadence.md`)。

**Standard ↔ PMO 漂移检测:** issue#12 类反馈即漂移检测结果 / 团队成员 + EL + SA 任一发现差集 → 起 standard issue + `type:rule-mismatch`。

---

## 十二、字段内容颗粒度边界(content granularity discipline)

> **2026-05-27 加 / 起源 evidence:** workspace `37320255` / story `1047382`(Baozun BFF 模板参数透传 / 4 子任务拆解)/ 单人多角色场景下"产出"字段含方法签名重构细节 + "验收点"含 family scan 自检项 → SA review 识别越界。

### 12.1 铁律 — Ticket 字段颗粒度 = "协作时点可消费层"

**铁律:** Ticket 任何文本字段(description / 产出 / 验收点 / comment)的内容颗粒度 **must** 停在"协作时点可消费层" / **must not** 下沉到实现细节层。

**判据 4 问(写 ticket 字段时 self-check):**

1. **谁消费?** PM / QA / 团队下游 / 未来交接人 / audit
2. **何时消费?** 评审 / 验收 / 历史回溯 / 角色切换
3. **拿什么对照?** 文档 / commit / mvn 输出 / portal 状态
4. **任一条答不上 → 下沉**(commit message / PR description / 共识文档实施记录 / self-review checklist)

### 12.2 字段语义边界表

| Ticket 字段 | 应该包含 | 不应该包含 | 下沉到哪里 |
|---|---|---|---|
| **产出 / Deliverable** | artifact 清单(文档名 / 类名 / 文件路径 / commit hash 链接)/ 模块级改造范围("14 处 exec* 方法 + 6 分支") | 方法签名重构 / 私有方法返参变化 / 字面量收敛位置 / 内部重构动机 | commit message + PR description + 共识文档 §实施记录 |
| **验收点 / AC** | 可由 PM / QA / 团队验证的行为或属性(编译 PASS / 测试 PASS / 字段对应关系核查 / 决策可追溯) | family scan 一级 / 私有方法唯一调用入口 / fix-pattern-scan 二级 pattern / 内部不变量 | BE self-review checklist(`task-lifecycle.md` Check 段) |
| **description / 背景** | 业务动机 + 改造目标 + 决策依据 + 影响范围 | 完整代码片段 / 完整测试用例代码 | 共识文档 + ADR |

### 12.3 单人多角色场景适用性(PM + EL 同体)

单人多角色场景下判据**依然成立**(不豁免)/ 但论证依据调整:

| 多人协作场景的依据 | 单人多角色场景的依据 |
|---|---|
| 协作传递失真(QA 看不到内部) | **SSoT 不漂移**(ticket / commit / 共识文档 / PR 是 4 个不同载体 / 颗粒度过细 → 半年后不知信哪份)|
| 角色权限 + 跨方可读性 | **长期可读性 + 历史回溯**(代码改了 ticket 字段过时 / commit hash 才是 source of truth)|
| 跨方时间不同步 | **角色切换成本**(PM-hat 写时点 vs EL-hat 写时点 / 不应混进一份载体)|

**反模式:** "反正一人写一人看 / 写多详细都没事" — 这是单人多角色豁免**不覆盖**的范围(豁免覆盖载体形态 / 不覆盖语义颗粒度 / 详见 issue #10)。

### 12.4 反模式实证(evidence case workspace 37320255 / story 1047382)

**Case:** Baozun BFF 模板参数透传改造 / 4 子任务拆解 / 单人 BE 同时承担 PM + EL 角色。

**越界示例 1(产出层下沉过深):**

```
子任务 3/4 产出(节录):
- pushRepairStatus 私有方法签名重构: (RepairOrderPO, BaozunRepairStatusEnum, Map<String,String>)
- execReviewCompleteNotification 入参重构为 boolean passed
  (解决原 reviewResult 双重语义隐患)
```

→ 方法签名 + 重构动机属代码层 / 应下沉到 commit message + PR description / ticket 产出停留 "改造 WechatSubscribeMessageService 14 处 + 6 分支" + commit hash 链接即可。

**越界示例 2(验收点混 self-review):**

```
子任务 3/4 验收点(节录):
- 14 个 status 字符串字面量全部收敛到 enum(family scan 验证)
- pushRepairStatus 唯一调用入口
```

→ family scan 一级 + 私有方法唯一性 = BE 自检项(`fix-pattern-scan` rule) / 不是 QA / PM 可对照的验收门 / 下沉 self-review checklist。

**正模式参考:**

```
子任务 3/4 产出(修正):
- WechatSubscribeMessageService.java — 14 个 exec* 方法 + processOrder 6 分支改造
  (commit: <hash>)
- SalesForceService.java — 2 处调用方适配(commit: <hash>)

子任务 3/4 验收点(修正):
- execOrderStatusChangeNotification 的 remark 入参写入 thing5
  (对照原 36c5663 commit 丢失语义已回填)
- mvn -pl backstage compile BUILD SUCCESS
- 14 状态字段映射与共识文档表格一一对应(对照 baozun-template-params-consensus.md §字段映射)
```

### 12.5 与 close 4 字段的协同

Ticket close 时(详见 `concepts/issue-handling.md` close 4 字段规约)/ 4 字段本身已经包含 commit hash + CHANGELOG + release-log + 关联 artifact / 即 ticket 字段不需要重复实现细节(close 时已经有正规通道指向代码 source of truth)。

**协同原则:** 创建时 ticket 字段含 artifact 级声明 + close 时 close 4 字段含 commit hash + PR link / 二者**互补不重叠** / 实现细节始终在代码层不在 ticket 层。

### 12.6 违规处置

§十二 铁律违规处置(append §八 通用违规处置):

- **轻度**(产出含 1-2 处方法签名 / 验收点含 1 处 self-review)→ comment 提示 + 自行下沉
- **中度**(产出大段实现细节 / 验收点全是 self-review)→ audit 起 finding + 走范式 ticket 复盘段
- **重度同模式复发 ≥ 2 次** → handoff PM/SA review 是否需要升级 ticket 模板硬约束(在 description / 产出 / 验收点 字段头部加 inline 提示)

### 12.7 累积 surface 触发(extension point evidence)

本节是 **standard 落地项目 → standard 主版本反哺**的第一个 case(2026-05-27 起累积)。后续累积 case 通过相同模式 append 到 §12.4 evidence 段。

累积阈值(`formalization-timing` 类型 A):
- 同模式 evidence ≥ 3 个落地项目 / ≥ 2 个 ticket 系统(TAPD + Jira / Linear / 等)
- → 抽象到跨 ticket 系统通用层(候选独立 protocol `ticket-field-granularity.md`)
- → 同时触发 standard extension point taxonomy ADR 讨论(候选 ADR-008)

**来源:** 2026-05-27 user × main:SA discussion / TAPD case 现象驱动 / 非顶层设计驱动。

---

## 修订日志

| 日期 | 修订 | 修订者 |
|---|---|---|
| 2026-05-25 | 初建(ADR-006 / Issue #12 / 通用层抽象 v1.5 §1 通用铁律 + 跨类型角色权限矩阵 + 跨类型 SOP + sub-protocol 索引) | standard EL via SA handoff |
| 2026-05-27 | §十二 字段内容颗粒度边界(起源 evidence workspace 37320255 / story 1047382 / 单人多角色场景判据补强) | standard EL via SA handoff |
