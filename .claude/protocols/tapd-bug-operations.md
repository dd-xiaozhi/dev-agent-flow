# TAPD Bug Operations Protocol — TAPD Bug 字段操作硬约束(类型 sub-protocol)

> **2026-05-25 重命名(ADR-006 / Issue #12):** 本文件原名 `tapd-mcp-operations.md` / 实际仅管 Bug 字段层 / 通用层规则迁移到 [`tapd-ticket-operations.md`](tapd-ticket-operations.md)(跨 ticket 类型通用铁律 + 角色权限矩阵)/ 本文件保留 Bug 类型 sub-protocol 角色。

> **定位:** TAPD Bug 模块(`tapd:create_bug` / `update_bug` / `get_bug`)的 MCP 调用硬约束规约。落地 PM 规范 v1.5 §7.4 流转规则到执行层 protocol / 配合 [`issue-handling.md`](../rules/core/issue-handling.md) 协作流纪律 / 不破坏现有 [`tapd-worktime-integration.md`](tapd-worktime-integration.md) 工时集成。
>
> **使能:** 项目 install 时通过 `## TAPD 配置` 段开启(`tapd_enabled: true` + workspace_id / project mapping)。未开启的项目走 GitHub-only 流程,零影响。
>
> **类型:** 节点配套类形式化(参考 `rules/core/formalization-timing.md` 类型 B)
>
> **关联:**
> - [`rules/core/issue-handling.md`](../rules/core/issue-handling.md) — Issue / Bug 5 场景协作流纪律(本 protocol 是其字段层执行规约)
> - [`docs/concepts/platform-mapping-tapd-bug.md`](../../docs/concepts/platform-mapping-tapd-bug.md) — TAPD 平台映射(本 protocol 7 硬约束来源)
> - [`tapd-worktime-integration.md`](tapd-worktime-integration.md) — TAPD 工时集成(本 protocol 与工时操作互补 / 不重叠)
> - **PM 规范 SSOT:** [`docs/requirements/2026-05-20-tapd-bug-handoff-flow/source/pm-tapd-ticket-spec-v1.5.md`](../../docs/requirements/2026-05-20-tapd-bug-handoff-flow/source/pm-tapd-ticket-spec-v1.5.md) §7

---

## 一、协议定位与边界

### 这个协议解决什么

TAPD Bug 字段操作(v_status / current_owner / fixer)在 PM 规范层有约束,但 AI / Dev 调用 MCP 时**容易凭直觉操作**(漏读现状 / 单字段更新 / 误推状态机 / 越权关闭)。本 protocol 把规范铁律落地为执行层硬约束 / 配合 `issue-handling.md` 协作流纪律形成完整双层防御。

### 这个协议不做什么

- ❌ 不重制 PM 规范 v1.5(SSOT 在 docs 仓 / 本 protocol 引用并落地为执行层硬约束)
- ❌ 不接管协作流判定(S1-S5 场景判定走 `issue-handling.md` / 本 protocol 仅管字段层)
- ❌ 不接管工时操作(工时走 `tapd-worktime-integration.md` / 本 protocol 仅管 Bug 字段)
- ❌ 不实现 Webhook / 双向同步(同 worktime-integration 边界)

### 与现有机制的协同

| 机制 | 关系 |
|------|------|
| Layer 1 `issue-handoff-flow.md` | 概念层 / 本 protocol 是其 TAPD 字段层落地 |
| Layer 2 `platform-mapping-tapd-bug.md` | 字段映射文档 / 本 protocol 是其 §五.2 7 硬约束的展开 |
| `issue-handling.md`(rule) | 协作流纪律 / 本 protocol 是字段操作纪律 / 两者协同(协作流先,字段操作后) |
| `tapd-worktime-integration.md` | 工时操作 / 互补不重叠(本 protocol 不动工时 / 仅 §七引用提醒) |
| `skills/core/issue/SKILL.md` | 执行层 skill / 本 protocol 是其 TAPD 分支段的硬约束源 |

---

## §A · API 层强制 vs 协议层 self-discipline 边界(2026-05-20 加 / dogfood 6 Obs 回流)

**重要边界声明:** 本 protocol 7 硬约束中,**仅 IC-5 / IC-6 / IC-7 部分在 API 层有客观约束**,其余 **IC-1 / IC-2 / IC-3 / IC-4 在 TAPD API 层零强制 / 100% 协议层 self-discipline**。

### 7 IC 分层表(实测 standard-dog-food workspace 65099424 / 2026-05-20)

| IC | API 层行为 | 协议层强制 |
|----|---|---|
| **IC-1** 双字段同传 | ❌ **零强制** — API 接受单字段 update / 不返 422 / `v_status` 改 + owner 不动 / 静默成功 | ✅ 协议层强制(唯一防线)|
| **IC-2** get_bug 前置 | ❌ **零强制** — API 无状态调用 / 漏 get_bug 直接 update + 虚构 user 名都接受 | ✅ 协议层强制 |
| **IC-3** 追加 vs 替换 | ❌ **零强制** — API 接受任何 current_owner 值 / **fixer 字段不自动 populate**(Obs-39) | ✅ 协议层强制(唯一保留 Dev 名手段)|
| **IC-4** Dev v_status 上限 | ❌ **零强制** — **API 完全放行 Dev 推 `测试完成`/`已上线`/`已关闭`**(Obs-37 / AP-1 实测调用成功) | ✅ 协议层强制(唯一防线 / 违反代价高:状态机被错误更新需 QA 回退)|
| **IC-5** resolved 解读 | ⚠️ **MCP server 实际返回中文字面值**(Obs-40 / 当前 MCP 返回 `status: "待测试"` 直接 / 不是 `resolved`)| 协议层认知校准 |
| **IC-6** 字段+comment | API 不联动(comment 独立 API)| ✅ 协议层强制 |
| **IC-7** 工时时点 | API 接受任何时点 add_timesheets | ✅ 协议层强制 |

**含义:**

1. AI / Dev 违反 IC-1 ~ IC-4 时 **MCP 调用不会报错** / 必须 AI / Dev 自律 / 协议层 self-check 是唯一防线
2. 违反 IC-4(Dev 越权)代价最高 — 字段已被错误更新 / 需 QA 重新打开纠正 / 不是"调用失败"的可恢复错误
3. **错误处理表 §四 多处与实际 API 行为不符** — 详见 §四 修订说明
4. Audit 5 维(§六)= 协议层 self-check 校验路径 / 是唯一可机器检测的合规路径

**反推:** 任何 protocol IC 写"API 必须 X"前 **must** 实测 API 行为 / 否则文档可能美好但虚假(本节是元层教训实例)。

---

## 二、7 硬约束(Iron Constraints)

### IC-1 · `update_bug` 必须同时传 `v_status` + `current_owner`

**铁律:** 每次 `tapd:update_bug` 调用 **must** 同时传 `v_status` + `current_owner`,**must not** 只传单字段。

**例外(2026-05-20 扩展 / Obs-36):** **跨人指派场景(S2 / S3 / S4)或 PM 路由场景**(只改处理人不改状态)允许只传 `current_owner` / **但必须在 comment 显式说明**"本次只改 owner 不改 status"。原措辞仅限"PM 路由" / 实际 Layer 2 §2.3 已隐式扩展到 S2/S3/S4 全部 / 本次澄清。

**违规后果:** 字段不一致 / 状态机镜像失真 / audit 链断裂。

**API 层行为(Obs-38 实测 / AP-3):** TAPD API 在 update_bug **缺 current_owner 时不会返回 422** / 调用成功 / `v_status` 被更新 / `current_owner` 静默不动 / `participator` 自动设。本 IC 是**协议层强制**(唯一防线) / API 不联动校验。

**来源:** PM 规范 v1.5 §7.4 MCP 状态更新模板铁律。

### IC-2 · `update_bug` 前 **must** 先 `get_bug`

**铁律:** 任何 `tapd:update_bug` 之前 **must** 调用 `tapd:get_bug` 读取当前 `current_owner` / `reporter` / `fixer` / `status`,基于现有值改 / **must not** 凭记忆或上次对话上下文猜。

**get_bug 必读字段清单:**
```
fields: "id,status,current_owner,reporter,fixer"
```

**违规后果:** `current_owner` 错误覆盖(漏读其他追加人) / `fixer` 漏识别(QA 重新打开时无法回退给原 Dev)。

**来源:** PM 规范 v1.5 §7.4 + Layer 2 `platform-mapping-tapd-bug.md` §二.3。

### IC-3 · `current_owner` 追加 vs 替换模式分场景

**铁律:**

| 场景(Layer 1 S 编号)| `current_owner` 操作模式 |
|---|---|
| S1 修完 → QA / S5 不需修 → QA | **追加** `{当前 owner};{reporter}`(分号分隔 / 保留 Dev 名) |
| S2 转 FE / S3 转 PM / S4 转 PM | **替换** 为新单值(因为是跨人指派 / current_owner 单点转移) |
| QA 测试不通过退回 Dev(非本 protocol 触发场景,但需识别)| **替换** 为 `{fixer}`(上次修复的 Dev) |

**违规后果:**
- S1 / S5 用替换 → Dev 名丢失 / QA 重新打开无法回溯
- S2 / S3 / S4 用追加 → current_owner 列表无限增长 / 责任不清

**API 层行为(Obs-39 实测 / AP-4):** TAPD 工作流**不自动 populate `fixer` 字段**(`fixer` 是手工字段 / 不随 update_bug 自动 inherit current_owner)。这意味着:

- QA 重新打开 Bug 退回 Dev 时 / 如 IC-3 追加模式失守(S1/S5 用替换)→ **`fixer` 也无值**(workflow 不自动设)→ QA 没有任何字段层可回溯原 Dev → 唯一线索是 comment 历史 grep
- 因此 IC-3 追加模式的重要性比原描述更高 — **是唯一保留 Dev 名的字段层手段**

**修正后约定:** S1 / S5 **must** 用追加模式(分号分隔 / 保留 Dev 名)/ 不仅是"便于 QA 重新打开" / 更是"防止 Dev 名永久丢失"。

**来源:** PM 规范 v1.5 §7.4 + 追加模式说明段。

### IC-4 · Dev 角色 v_status 推进上限

**铁律:** Dev 角色(BE / FE)调用 `update_bug` **must not** 传以下 v_status 值:

- ❌ `测试中` — QA 操作
- ❌ `测试完成` — QA / PM 操作
- ❌ `已上线` — PM 操作
- ❌ `已关闭` — QA / PO 操作

**Dev 允许传的 v_status 值:**
- ✅ `进行中` — Dev 开始修复
- ✅ `待测试` — Dev 修完提测(Dev 最远到这里)
- ✅ 不传 v_status(只改 current_owner)/ 即 S2 / S3 / S4 场景

**API 层行为(Obs-37 实测 / AP-1):** TAPD API 对 Dev 角色越权推 v_status(`测试中` / `测试完成` / `已上线` / `已关闭`)**完全放行**(MCP server 不基于 user 角色拒绝调用 / 调用返回 `status: 1` success / v_status 真的被改)。

**违规后果(严重度高):** 本 IC 是**协议层强制 / 唯一防线** — 违反后 v_status **真的会被错误更新** / 需 QA 重新打开纠正(comment 说明误操作 + 记 problem-registry)/ 不是"调用失败"可恢复 / 代价高于其他 IC。

**QA 路径备注(2026-05-25 加 / Issue #12 G6):** v1.5 §7.4 明确"测试中"状态可选 / **推荐 QA 直接推 `待测试 → 测试完成`**(跳过"测试中"不违规)。Dev 仍受本 IC 约束(`测试中` 仍是 Dev 禁推 / 即使 QA 可跳过)。

**来源:** PM 规范 v1.5 §7.4 Dev 角色铁律。

### IC-5 · `resolved` ≠ "已解决"

**铁律:** `get_bug` API 返回 `status: "resolved"` 对应 `v_status` = **`待测试`**,**不是"已解决"**。

AI / Dev **must not** 看到 `resolved` 字面值就解读为"Bug 已完成"/ 必须以 `v_status` 字段为准。

**例:**
```
get_bug 返回:
{
  "id": "1234",
  "status": "resolved",        # ← 不是"已解决"
  "v_status": "待测试",         # ← 真实状态
  ...
}
```

**违规后果:** 误解状态机 / 漏 QA 验证 / 误以为可以关闭。

**MCP server 实际行为(Obs-40 实测 / 2026-05-20 standard-dog-food workspace 65099424):** 当前 MCP 工具调用 `tapd:get_bug` 返回 **直接是 `status: "待测试"`**(中文 v_status 字面值 / `resolved` 字段独立 null)/ 不是 `status: "resolved"` 英文 API key。

**可能原因:** MCP server 已做 v_status 映射 / 或 TAPD workspace 配置差异。**Dev 应同时核查 `status` 和 `v_status` 字段** / 不假设 `status` 一定是英文 API key。原 IC-5 描述基于 raw TAPD API(从 PM 规范 §7.4 引用)/ 与当前 MCP server 行为不完全对齐。

**来源:** PM 规范 v1.5 §7.4 警示段。

### IC-6 · 字段改动 must 有 comment 留痕

**铁律:** 任何 `update_bug` 调用 **must** 配套写 comment(`v_status` 改动 / `current_owner` 改动 / `fixer` 改动均触发)。

**Comment 内容必含:**
- 场景标识(`[S{N}] xxx` / 引用 [`issue-handling.md`](../rules/core/issue-handling.md) §三.1 通用 4 字段)
- 字段操作摘要(`v_status: X → Y` / `current_owner: A → B`)
- 与字段改动同源的事实(修复范围 / 决策选项 / 等)

**违规后果:** 字段镜像失去事实底料 / 后续审查无法回溯改动理由。

**来源:** Layer 1 `issue-handoff-flow.md` §1.2 核心洞察(comment 是底料 / 字段是镜像)+ `issue-handling.md` Iron Law COMMENT FIRST。

### IC-7 · 工时填写时点

**铁律:** Dev 推进到 `待测试` 时(即 S1 / S5 场景)**must** 同步填写工时;S2 / S3 / S4 场景(v_status 不变)**must not** 填工时。

**调用工具:** 详见 [`tapd-worktime-integration.md`](tapd-worktime-integration.md) `add_timesheets` / `update_timesheets` 模式。

**违规后果:** PM 规范 §7.6 违反 / 工时缺失或失真。

**来源:** PM 规范 v1.5 §7.6。

---

## 三、标准调用顺序模板

### S1 / S5 — 推进到「待测试」(完整调用序列)

```
# 1. 读现状
tapd:get_bug
  workspace_id: "{项目ID}"
  options:
    id: "{bug_id}"
    fields: "id,status,current_owner,reporter,fixer"

# 2. 写 comment(场景标识 + 修复范围 + 关键证据 + 下一步)
# (使用 TAPD comment 字段 / 富文本格式 / 引用 platform-mapping-tapd-bug.md §三 模板)

# 3. 更新字段
tapd:update_bug
  workspace_id: "{项目ID}"
  options:
    id: "{bug_id}"
    v_status: "待测试"
    current_owner: "{从 get_bug 读的 current_owner};{reporter}"

# 4. 填工时(参考 tapd-worktime-integration.md)
tapd:get_timesheets  # 先查是否已有当天工时
tapd:add_timesheets 或 update_timesheets  # 新增或覆盖
```

### S2 / S3 / S4 — 跨人指派(v_status 不变)

```
# 1. 读现状
tapd:get_bug
  workspace_id: "{项目ID}"
  options:
    id: "{bug_id}"
    fields: "id,status,current_owner,reporter,fixer"

# 2. 写 comment(BE 边界 + 接手边界 / 决策选项 / 等)

# 3. 更新字段(只改 current_owner / v_status 保持)
tapd:update_bug
  workspace_id: "{项目ID}"
  options:
    id: "{bug_id}"
    current_owner: "{下游 Dev / PM 中文名}"
# 4. 工时不填(v_status 未推到「待测试」)
```

---

## 四、错误处理

> **本表 2026-05-20 修订(dogfood 6 Obs 回流):** 原表多处假设 API 层强制 / 实测发现 IC-1/IC-2/IC-3/IC-4 在 API 层零强制(详 §A 边界声明)/ 因此本表去除"API 报错"误导 / 改为"客户端 self-check 失败时如何识别 + 处理"。

| 现象 / self-check 触发 | 原因 | 处理 |
|---|---|---|
| `update_bug` API 成功但 owner 未追加(漏 reporter / fixer 也 null)| IC-1 违反单字段 update(实测 Obs-38 / API 不返 422 / 静默成功)/ 或 IC-3 替换覆盖 | **重 get_bug 读现状 + 重 update_bug 双字段同传(追加模式 S1/S5)** / 写 comment 说明误操作 / 不依赖 API 报错信号 |
| QA 反馈"无法重新打开退回 Dev" / fixer 为 null / current_owner 不含 Dev 名 | IC-3 替换覆盖了 Dev 名 + `fixer` 字段从未自动 populate(Obs-39)/ TAPD 工作流不自动设 fixer | 优先**查 comment 历史 grep Dev 名**(唯一 audit trail)/ 然后 update_bug 把 Dev 名追加回 current_owner / 必要时手工 set fixer |
| `get_bug` 返回 `status: "待测试"`(中文)/ `resolved: null` | **MCP server 当前行为**(Obs-40)/ 不是 raw API `status: "resolved"` | 不是错误 / 不要误读为"已解决" / 以 `v_status` / `status` 中文值为准 |
| Dev 调用 `update_bug` v_status 传 `测试完成` / `已上线` / `已关闭` 调用**成功** | IC-4 违反 / Dev 越权(实测 Obs-37 / AP-1 / **API 永远成功** / 不会拒绝)/ v_status **已被错误更新** | 严重:重 update_bug 回退到正确 v_status + comment 详细说明误操作 + 记 problem-registry / 通知 QA 协调实际状态 / 是协议层 self-discipline 违反代价最高的场景 |
| comment 写完但 grep 无法识别 `commit:` | comment 反引号转义错误(GitHub 平台)| 用 `--body-file` 重写(参考 issue SKILL.md grep 自检段)/ TAPD 富文本走纯文本不加反引号 |
| `current_owner` 传含角色后缀(如 `顾尚荣(FE)`)/ 字段被截断 | TAPD `current_owner` 字段静默截断角色注解后缀(Obs-35 / IC-8 候选)| `current_owner` 传纯中文名(workspace 内合法 user)/ 角色识别走 comment `@{名}(FE)` 文本 |
| `current_owner` 传虚构 user 名 / 调用成功 | IC-2 漏 get_bug + API 不校验 user 存在性(Obs-35 / AP-2 / IC-8 候选)| 必先 get_bug 看现 owner / current_owner 必从 get_bug 读的合法 user 列表选 / 不凭记忆构造 |

---

## 五、与 issue-handling.md 协作流的执行顺序

```
1. 协作流层(issue-handling.md):
   - Step 0 自检表 → 判定场景 S1-S5(必须显式标 S 编号)

2. 字段层(本 protocol):
   - get_bug 读现状
   - 写 comment(场景标识 + 4 字段)
   - update_bug(按场景 + IC 7 硬约束)
   - 工时(S1 / S5 时填)

3. 审查层:
   - issue-process.md(协议) 状态机审查
   - 本 protocol 7 硬约束 audit
```

**关键约束:** 协作流判定优先 / 字段操作随后。**不允许跳过场景判定直接调 update_bug**(违反 `issue-handling.md` Iron Law)。

---

## 六、Audit 路径(节点配套审查)

本 protocol 字段层有 5 个 audit 维度:

| # | 维度 | 检查方法 |
|---|---|---|
| 1 | `update_bug` 双字段同时传 | grep `update_bug.*v_status` 不命中 `current_owner` = 违 IC-1 |
| 2 | `get_bug` 前置 | 历史 MCP 调用日志 / `update_bug` 前缺 `get_bug` = 违 IC-2 |
| 3 | `current_owner` 模式匹配场景 | comment 含 S 编号 + 对照 IC-3 表 = 检查模式正确性 |
| 4 | Dev 越权 v_status | grep update_bug v_status ∈ {测试中 / 测试完成 / 已上线 / 已关闭} = 违 IC-4 |
| 5 | 字段改动有 comment | 字段改动数 vs comment 数(handoff 类 / 同时间窗内) = 失同检测 |

---

## 七、与工时集成的边界

工时操作走 [`tapd-worktime-integration.md`](tapd-worktime-integration.md) / 本 protocol **only** 在 IC-7 引用工时填写时点 / **不重制**工时 MCP 调用模板。

- ✅ 本 protocol 管:Bug 状态 / 处理人 / 修复人字段
- ❌ 本 protocol 不管:工时记录 / 时间累计 / 工时 comment 模板

两 protocol 协同时序:
```
issue-handling.md(协作流) → 本 protocol(字段) → tapd-worktime-integration.md(工时,仅 S1/S5)
```

---

## 八、形式化时序

**类型:** 节点配套类(参考 `formalization-timing.md` 类型 B)

**4 触发条件核实:**

| # | 条件 | 自检 |
|---|---|---|
| 1 | 流程结构化 | ✅ TAPD MCP 调用是 Bug 处理流程节点 / 字段操作有规范定义 |
| 2 | 流程反复发生 | ✅ 每个 TAPD Bug 处理都触发 |
| 3 | 已有规则约束但缺审查路径 | ✅ PM 规范 §7.4 有约束 / MCP 调用层无 audit 路径 / 违规无人扫 |
| 4 | 违规会沉底 | ✅ 直觉操作 / 漏 get_bug / 单字段 update / 越权推 v_status 等模式高频出现(framing 来源 PM 何 jerry 反馈即证据)|

四条全满足 → 节点配套合法形式化 / 首次实践即基线。

---

## 九、起源与演进

- **2026-05-20** Proposed(本 protocol 初版)— 配合 TAPD Bug Handoff Flow 实施 handoff 的 P5 产物 / 7 硬约束首次形式化 / 落地 PM 规范 v1.5 §7.4 铁律
- 后续演进追加于此(PM 规范升级 / 新 MCP 工具变更 / 新约束识别 etc)
