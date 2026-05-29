# TAPD Worktime Integration Protocol

> **定位：** standard 的可选扩展协议——为使用 TAPD 作为 PM 工具的团队提供 ticket ↔ Issue 关联 + 工时管理机制，**不破坏 standard 现有 issue-process 协议**。

> **使能：** 项目 install 时通过 `## TAPD 配置` 段开启（`tapd_enabled: true` + ticket prefix + 工时模板配置）。未开启的项目走 GitHub-only 流程，零影响。

---

## 一、协议定位与边界

### 这个协议解决什么

PM 需要按 ticket 跟踪员工工时和项目成本估算（合规 / 财务 / 资源调度）；Dev 需要在 GitHub Issue 集中执行（保留 standard issue-process）。两者诉求都成立，本协议负责**衔接**。

### 这个协议不做什么

- ❌ 不替代 standard 现有 `issue-process.md`（GitHub Issue 状态机不变）
- ❌ 不做 TAPD ticket 与 GitHub Issue 状态机双向同步（不上 webhook）
- ❌ 不接管所有工时管理场景（仅适用"按 ticket 跟踪"，不强制非项目类岗位用）

### 与现有机制的协同

| 机制 | 关系 |
|------|------|
| `protocols/issue-process.md` | 状态机不动，本协议加 TAPD ticket 关联段（轻量引用）|
| Monthly timesheet（角色级清单上报） | **互补不冲突**——管理协调岗用 monthly，执行岗用 ticket 工时（双模式见 §六）|
| `audit-phases.md` §阶段五 issue-process audit（如有）| 可加可选维度：工时记录覆盖度（§audit 段）|

---

## 二、双模式工时管理

```
场景 A — 管理协调岗（PM / SA / TL）          场景 B — 执行岗（BE / FE / QA）
────────────────────────────────────       ─────────────────────────────────
Monthly timesheet                            TAPD ticket 工时管理（本协议）
（清单式月度上报，不按 ticket）              （按 ticket 跟踪，PM 成本估算）

岗位天然不绑定 ticket 工作                   岗位天然按 PM 提的需求 ticket 工作
                                              ↓
                                          ① PM 创建 TAPD ticket → 关联 GitHub Issue
                                          ② 各角色在 Issue 用多 comment 记工时
                                          ③ Issue close 时汇总 → 写回 TAPD ticket
```

**两机制兼容 / 互不冲突 / 按岗位选用。** 项目 install 时通过 `## TAPD 配置` 段决定是否启用本协议。

---

## 三、关联机制

### 双向手动关联

| 端 | 关联载体 | 内容格式 |
|---|------|----|
| **TAPD 端** | TAPD ticket "描述" 或专用关联字段 | GitHub Issue URL（如 `https://github.com/<org>/<repo>/issues/123`）|
| **GitHub Issue 端** | Issue body 头部段（必含）| `**TAPD ticket:** #<ticket-id>`（建议 + 链接如 TAPD 有 web URL） |

**约定：**
- 关联是 **PM 创建 ticket 后手动建立**（不上自动化 webhook，避免基建依赖）
- 一个 TAPD ticket 可对应**多个 GitHub Issue**（多 issue 拆解一个需求）
- 一个 GitHub Issue 通常对应 **1 个 TAPD ticket**（避免工时分摊歧义）

### Issue body 关联段模板

```markdown
**TAPD ticket:** #12345 — <ticket 简短描述（可选）>

<Issue 正文>
```

或加 label `tapd:12345`（次选，避免 label 膨胀）。

### 关联段自动校验（v0.3 加 — Finding 3）

skill `/tapd-worktime-summary` **Step 1 启动时必须校验** Issue body 头部含合法关联段：

| 校验路径 | 期望 | 不满足时动作 |
|---------|------|--------|
| body 头部含 `**TAPD ticket:** #<id>` 模式（regex `\*\*TAPD ticket:\*\*\s*#\d+`）| 提取 ticket id 后续写回 | **WARN 但不中断** — 提示用户「Issue body 缺关联段，是否手动指定 ticket id?」交互补 |
| body 头部含 label `tapd:<id>`（次选）| 同上 | 同上 |
| 都没有 | — | **ERROR 中断** — 拒绝写回（避免误关联或脏数据写入 TAPD）|

**为什么不直接 ERROR：** Issue 可能合法不关联 TAPD（如纯文档 Issue），WARN + 交互补允许用户决策。

**skill 实现位置：** `skills/global/tapd-worktime/SKILL.md` Step 1（详见该 SKILL 文档）。

---

## 四、工时记录格式（半结构化）

### 在 GitHub Issue 用专门 comment 记录

每条工时 comment 用以下格式（半结构化便于 audit 扫描）：

```markdown
### 工时记录

- 2026-05-09 14:00-15:30 / @ssguren / be / 1.5h / 排查 X bug
- 2026-05-09 16:00-17:30 / @colleague / be / 1.5h / 修复 + 单测
```

**字段约定：**

| 字段 | 含义 | 必填 |
|------|----|----|
| 日期 | YYYY-MM-DD | ✅ |
| 时段 | HH:MM-HH:MM（可选，如不精确可写"上午"等粗粒度）| 推荐 |
| @author | GitHub 用户名 | ✅ |
| role | be / fe / qa / pm / tl / sa 之一 | ✅ |
| 时长 | 数字 + h（如 1.5h / 3h）| ✅ |
| 任务描述 | 一句话 | ✅ |

### 粒度约定（按 session）

- **按 session 记**（每天 1-2 条），不按 commit 级（太碎）
- 同一 session 内的多个微任务合并为一条
- 中断重启视为新 session
- 跨多天的连续工作每天独立条目

### 多条 comment 累计

一个 Issue 跑两周可能有多条工时 comment（不同时期）—— **不需要在同一 comment 里追加**，开新 comment 即可。close 时汇总扫所有"### 工时记录"段。

### TAPD 系统约束（v0.2 加 — Finding 8）

TAPD 后端强制：**同一 owner / 同一 spentdate / 同一 ticket = 仅允许 1 条 timesheet**。试图同日对同 ticket 第二次 `add_timesheets` 会触发 422 ParamError。

**对工时记录格式的影响：**
- Issue 内**同日多段**工时 comment 在写回 TAPD 时**必须聚合**为单条 timesheet
- 跨日的工时段保持独立 timesheet（不合并）
- 同日已写回的 timesheet，再次出现新工时段 / 修订 → 走 `update_timesheets`（不能再 `add`）

**聚合规则（写回时执行）：**

| TAPD 字段 | 聚合方式 |
|----------|--------|
| `timespent` | 同 owner / 同日 / 同 ticket 的所有工时段累加 |
| `memo` | 多段拼接，每段格式 `段号. HH:MM-HH:MM / Xh / 任务描述`，换行分隔 |

> 详细写回逻辑见 §五"写回 TAPD"段。

### 多 Issue ↔ 单 ticket 的 SSoT 语义（v0.3 加 — Finding 22）

§三 协议允许"一个 TAPD ticket 可对应多个 GitHub Issue"（多 Issue 拆解一个需求）。叠加上面 TAPD 系统约束"1 owner / 1 day / 1 ticket = 1 timesheet"，必须明确**多 Issue 工时如何聚合到单 timesheet**——否则各 Issue 独立写回会触发 422，或互相覆盖。

**SSoT 语义：** TAPD timesheet = N 个 Issue 当日同 owner 同 ticket 的工时**累加 mirror**，不按 Issue 拆分。

**聚合规则：**

| 维度 | 规则 |
|------|----|
| 工时段来源 | 所有关联同 ticket 的 Issue 当日"### 工时记录"段（不只是触发 skill 的那个 Issue）|
| `timespent` | sum(各 Issue 当日同 owner 工时段) |
| `memo` | 各 Issue 工时段按 Issue 编号分组拼接：`[#101] 1. HH:MM-HH:MM / Xh / 描述\n[#101] 2. ...\n[#102] 1. ...` |
| 写回触发 | 任一 Issue 触发 `/tapd-worktime-summary <N>` 时，**skill 必须先扫所有同 ticket Issue 当日工时**再聚合写回 |
| `update_timesheets` 时机 | 第 N+1 个 Issue 当日触发时，必走 update（首个 Issue 已 add）|

**skill 跨 Issue 扫描算法（详见 SKILL.md Step 4b.0）：**

```
ticket_id = Issue body 关联段提取（见 §三 关联段自动校验）
related_issues = gh issue list --search "in:body \"**TAPD ticket:** #<ticket_id>\"" \
                                --state all --json number
for each issue in related_issues:
    扫该 issue 的 "### 工时记录" 段，过滤当日（spentdate == today）
    按 owner 累加
聚合 → mcp__tapd__add_timesheets / update_timesheets（按 §五 双路径）
```

**关键约束：**
- 单 Issue close 触发 skill 时，**不能只写自己的工时**——必须扫齐所有同 ticket Issue
- 跨日的工时段仍按"1 owner / 1 day / 1 ticket"独立 timesheet（不合并跨日）
- **memo Issue 编号前缀必填**（`[#NNN]`），便于回溯哪条工时来自哪个 Issue
- **PM 拆 Issue 时应避免跨日错乱**——同一天的工时跨 Issue 必须用 update 而非 add（否则 422）

**反模式（禁止）：**

- ❌ 单 Issue 关联多 ticket（除非业务确实跨 ticket，但 §三 已建议避免）
- ❌ skill 只看触发 Issue 不扫同 ticket 兄弟 Issue（漏聚合 → TAPD 工时少计）
- ❌ memo 不带 Issue 编号前缀（无法回溯审计链）

---

## 五、汇总 + 回写流程

### 主路径 — 用户触发 skill

**触发时机：** 关闭者（QA / PM / TL 等任意角色）在标 close 前**主动调** skill：

```
/tapd-worktime-summary <issue-number>
```

skill 输出：
- 扫该 issue 所有 "### 工时记录" 段
- 按角色（be / fe / qa / pm / tl / sa）汇总工时
- 输出 markdown 报告（在 issue 下加一条 summary comment）
- 同时给关闭者一份**可粘贴到 TAPD ticket 工时栏**的纯文本

### 兜底层 — 批量扫描

防主路径漏调（关闭者忘了 / 老 issue 历史欠账）：

```
/tapd-worktime-batch-scan
```

skill 行为：
- 扫所有 GitHub Issue 状态 = closed 但**没有 worktime-summary comment** 的
- 月度跑（与 monthly-timesheet 同期）
- 列出"待汇总"清单 + 给 SA / PM 主动调 summary

### 写回 TAPD（v0.2 起 — skill 经 TAPD MCP 自动写回）

> **v0.1 → v0.2 变更：** v0.1 设计为关闭者手动粘贴；dogfood 暴露这条假设不成立——手动易漏 / 易抄错 / 无法防 SSoT 违反，且 standard 本身已依赖 TAPD MCP 工具栈。v0.2 改为 skill 自动写回。原 v0.1 "为什么不自动" 推理在 §七 同步勘误。

#### SSoT 强制约束（v0.2 加 — Finding 10，CRITICAL）

> **GitHub Issue = Source of Truth；TAPD timesheet = mirror。**

任何 TAPD timesheet 的 `timespent` / `memo` 变更（无论 add 还是 update），**必须先**在对应 GitHub Issue 加工时段 comment（"### 工时记录"半结构化段），再触发 skill 汇总写回。

**禁止：** 直接调用 TAPD MCP 工具（`add_timesheets` / `update_timesheets`）修改 timesheet 而 Issue 无对应记录——这是 SSoT 违反，会让 Issue 与 TAPD 漂移、审计链断裂。

**skill 防御：** skill Step 4 写回前必须做 Issue↔TAPD 一致性校验（详见 `skills/global/tapd-worktime/SKILL.md` Step 4），三态对比：
- Issue 累加值 > TAPD 现有值 → `update_timesheets` 同步（合规）
- Issue 累加值 == TAPD 现有值 → 跳过（无变更）
- Issue 累加值 < TAPD 现有值 → 报错中断（违反 SSoT，TAPD 有但 Issue 无对应记录）

#### add / update 双路径（v0.2 加 — Finding 9）

由 §四 TAPD 系统约束（1 owner / 1 day / 1 ticket = 1 timesheet）推出，写回必有两条路径：

| 场景 | TAPD MCP 工具 | 触发 |
|------|--------------|----|
| 当日首次写回该 ticket 工时 | `mcp__tapd__add_timesheets` | Issue 当日首次 close + skill 触发 |
| 修订当日已写回工时（补录 / 矫正 / 多段累加）| `mcp__tapd__update_timesheets` | Issue 加新 comment（同日）或 re-open + close 再触发 skill |

**skill 自适应分支（详见 SKILL.md Step 4）：**

```
查 mcp__tapd__get_timesheets（owner / spentdate / ticket）
  ↓
无当日 timesheet → add_timesheets（首次）
有当日 timesheet → update_timesheets（同步 timespent + memo 聚合）
```

#### 写回字段映射表（v0.3 完整化 — Finding 7）

> **本表是 skill 写回 TAPD timesheet 的权威字段推导规则。** skill Step 4 内的所有 `add_timesheets` / `update_timesheets` 调用都按此推导，不再硬编码。

| TAPD 字段 | 类型 | GitHub Issue 来源 | 推导规则 | 必填 | 示例 |
|----|----|----|----|---|----|
| `workspace_id` | string | CLAUDE.md `tapd_workspace` | 直接读项目配置 | ✅ | `12345` |
| `entity_id` | string | Issue body 关联段 `**TAPD ticket:** #<N>` | 拼 `<workspace_id><N>`（workspace + ticket 拼接成绝对 id）| ✅ | `1234500067890` |
| `entity_type` | enum | TAPD ticket 实际类型 | 调 `mcp__tapd__get_stories_or_tasks` / `mcp__tapd__get_bug` 探测：bug → `bug`，story → `story`，task → `task` | ✅ | `bug` |
| `owner` | string | comment author `@github_username` + 角色映射 | 通过 CLAUDE.md `## TAPD 配置 § 角色映射` 段查 github → TAPD 用户名（中文），多对一时按 role 字段区分 | ✅ | `张三` |
| `spentdate` | date | 工时段日期 `YYYY-MM-DD` | 直接取每条工时记录第 1 字段 | ✅ | `2026-05-13` |
| `timespent` | float | 当日 Issue 内同 owner / 同 ticket 工时段累加 | sum(时长字段 `Xh` / `X.Yh`)，单位小时 | ✅ | `3.5` |
| `memo` | string | 当日所有工时段拼接 | 多段格式 `1. HH:MM-HH:MM / Xh / 任务描述\n2. ...` | ✅ | 见下例 |

**memo 拼接示例：**

```
1. 09:30-11:00 / 1.5h / 修 NPE
2. 14:00-16:00 / 2h / 单测 + 自测
```

**多 Issue 关联同 ticket 的聚合（参考 §四 多 Issue ↔ 单 ticket SSoT 段，v0.3 Finding 22）：**
- `timespent` = sum(各 Issue 当日同 owner 工时)
- `memo` = 各 Issue 的工时段聚合 + 前缀标 Issue 编号（`[#101] 1. ... / [#102] 2. ...`）

**角色映射的具体配置位置：** `<project>/CLAUDE.md` § TAPD 配置 § 角色映射表（github username → TAPD 中文名）。skill Step 4b.2 读这张表做映射；未配置时报错"角色映射缺失"。

### v0.2 → v0.3 prior context

> v0.2 暂未规范全字段映射表（owner 中文映射 / entity_id workspace 拼装等），skill 内置硬编码处理 — v0.3 完整化后，skill Step 4b.2 改为读本表，不再硬编码。

### 流转角色

| 阶段 | 谁做 |
|------|----|
| 工时记录（多 comment）| 各角色（@author = role 自维护）|
| 触发汇总 skill | **关闭者**（QA / PM / TL 等，不一定是 BE）|
| 写回 TAPD | 关闭者 / PM（手动粘贴）|
| 兜底 batch-scan | SA（月度，与 monthly-timesheet 合并）|

---

## 六、Audit 维度（可选）

### issue-process audit 加可选第 7 维度

如项目启用本协议，audit phase `issue-process` 可加可选维度："**工时记录覆盖度**"：

| 检查项 | 判据 |
|------|----|
| 7.1 工时 comment 存在性 | 关联 TAPD ticket 的 closed Issue 是否含 "### 工时记录" 段 |
| 7.2 汇总 comment 存在性 | closed Issue 是否含 worktime-summary comment（skill 产出标识）|
| 7.3 工时格式合规性 | 半结构化字段是否齐全（日期 / role / 时长 / 任务描述）|
| 7.4 TAPD 写回追溯 | 关联 TAPD ticket 是否含工时记录（外部系统校验，可选 — 需 PM 反馈）|

**可选**——项目按需启用。

---

## 七、设计推理（Why this way）

> **本段记录"为什么是这样设计"的推理过程**——给后续维护者 / 试点小伙伴 / 跨项目 reviewer 理解决策逻辑，而非只看规则。
>
> **形成背景：** 2026-05-09 用户与 SA 讨论沉淀。原始对话：用户内部 BE 会议提出 TAPD ticket 工时跟踪需求 → SA-用户讨论流程层方案 → 拍板"保留现有 issue 流程 + TAPD 仅工时管理"。

### 为什么用 GitHub Issue comment 记工时（而不是实时更新 TAPD）

**用户原话洞察：**
> "我考虑整个流转都在 issue，把信息放置在这里更方便 review 或者是审查（比如 pm 可能会做个人绩效审查）。"

**核心权衡：信息密度 vs 信息分散**

| 方案 | 信息密度 | review 难度 |
|------|------|----|
| 实时更新 TAPD（每次干活先开 TAPD 写工时）| 工时与执行细节割裂（TAPD 是工时摘要 / Issue 是执行细节）| 难——审查需要切两个工具拼 |
| **GitHub Issue 多 comment + close 时汇总（本方案）** | 高——所有上下文 + 工时 + 决策都在 Issue 单一载体 | 易——单 issue 浏览即可重建工作过程 |

**结论：选信息密度高的载体（Issue）作 SSoT，TAPD 仅汇总 sink。**

### 为什么 PM 创建 ticket 而非 BE 创建（关联方向）

**PM 是需求 / 成本视角入口** —— TAPD ticket 自然由 PM 在 TAPD 提需求时创建。BE 不该被强制创建 ticket（增加流程负担 + 不符合 PM 工具的使用习惯）。

**单向关联** = 简化心智模型：先有 ticket，后有 issue。Issue 是 ticket 的实现载体之一。

### 为什么手动关联（不上 webhook）

**用户原话约束（多次出现）：** 不要垃圾 / 专业 / 大胆。

**评估：**
- Webhook = 重型基建依赖（公司 GitHub 是否支持 / 鉴权 / 失败重试 / 跨 repo 配置）
- 手动 = PM 创建 ticket 时贴 Issue URL（30 秒动作，发生频次低）
- ROI：Webhook 节省的 30 秒 ≪ 维护成本

**结论：** 手动关联的轻量优势远超自动化收益（在当前规模下）。

### 为什么 close 时汇总（而不是实时算）

**SA 之前误读：** "close 时一次性算" → 担心 2 周后回头算不准。

**用户校准：** 多 comment 实时记 + close 时仅"汇总动作"。

**关键洞察：** **多 comment 实时记 = 实时记账，汇总只是动作 = 累加，不算估算**。两者解耦：
- 实时记 = 准确度保证（工程师每天 / 每 session 记，不靠估）
- 汇总 = 触发动作（一次性把多 comment 加起来 → 不引入估算误差）

**类比 standard 的 spool 4 层兜底原则**——实时落地不靠记忆。

### 为什么用户触发 skill + 兜底 batch-scan（不上事件驱动）

**用户校准 D3：** "目前 closed 都不是 BE 做的，应该是其他岗位处理"

**含义：** 关闭动作和工时记录者解耦——BE 记工时，QA / PM / TL close。如果 close 时自动触发汇总，**关闭者需要执行 BE 的产出**（不友好）。

**SA 推荐双层：**
- **主路径**：用户主动调 skill（关闭者 / 任意角色都可，自然衔接 close 动作）
- **兜底层**：月度 batch-scan（与 monthly-timesheet 同期）catch 漏调的

不上事件驱动（GitHub Actions / Webhook），**理由同 §为什么手动关联** —— 重型基建成本超过收益（在当前规模下）。

### ~~为什么写回 TAPD 用手动粘贴（不上 TAPD MCP / API）~~ — v0.2 反转

> **v0.1 假设：** 手动粘贴 = 30 秒，不依赖 TAPD MCP / API（基建 / 鉴权 / 失败重试成本高）。
>
> **v0.2 反转（2026-05-09 dogfood 验证）：**
> - dogfood 暴露手动模式无法防 SSoT 违反 — Issue 与 TAPD 易漂移、抄错、漏录（Finding 10 CRITICAL）
> - standard 本身已依赖 TAPD MCP 工具栈（`mcp__tapd__add_timesheets` / `update_timesheets` / `get_timesheets` / `get_bug`），"基建 / 鉴权"成本已经付过
> - 30 秒手动粘贴 × N 个 ticket / 月 = 实际成本 + 错误率显著高于自动写回
>
> **v0.2 设计：** skill 经 TAPD MCP 自动写回 + SSoT 一致性校验（详见 §五 写回段）。手动粘贴作为 MCP 工具不可用时的降级兜底。

### 为什么 v0.2 仍保留 "Issue=SoT, TAPD=mirror" 而非"双向同步"

**单向防漂移 + 审计链清晰。** 双向同步在 SSoT 违反时无法判定哪一侧是真值；单向（Issue → TAPD）让所有变更必经 Issue comment，审计完整。手工修 TAPD（如 PM 直接在 TAPD UI 改 timespent）由 skill SSoT 校验拦下，强制经 Issue 走变更流程。

### 为什么双模式（管理岗 monthly + 执行岗 ticket）

**用户原话：**
> "对于像我这种不需要独立工时的岗位，需要有 monthly 的清单式的工时上报；而对于其他小伙伴，他们有 ticket 工时考量，是需要这个东西的。"

**岗位天然不同：**
- 管理协调岗（PM / SA / TL）= 协调 / 决策 / 跨任务，**不绑定 ticket**——按 monthly 清单上报合规
- 执行岗（BE / FE / QA）= 按需求 ticket 干活，**天然绑定 ticket**——按 ticket 跟踪工时

**两机制不冲突 / 互补 / 按岗位选用** —— 项目 install 时按团队成员构成决定启用哪种 / 哪些。

### 为什么 v0.3 把字段映射从 skill 提到 protocol（Finding 7）

**v0.2 做法：** skill SKILL.md Step 4b.2 内嵌字段推导表（owner / spentdate / entity_id 等）。
**v0.3 改：** protocol §五 维护权威映射表，skill 仅引用，不再硬编码字段规则。

**驱动：** Finding 7 dogfood 实测 owner 中文映射 + entity_id workspace 拼接细节散落 skill 各处，未来跨 skill / 跨项目复用易漂移。protocol 是上层契约，"字段权威推导"是契约的一部分，本就该属 protocol；skill 是执行者，按契约执行。

**风险（已接受）：** protocol 表更新时需同步 skill 引用，存在双载体漂移可能 —— 但相比"字段规则散落 skill 多处"的漂移成本，集中维护反而更稳。

### 为什么 v0.3 把 "Issue body 关联段校验" 设三态而不是二态（Finding 3）

**初版设想：** 有 = 继续 / 无 = 拒绝（二态）。
**v0.3 改：** 标准 body 头 / label fallback / 交互补 / ERROR 拒绝（三态 + 交互兜底）。

**驱动：** Issue 可能合法不关联 TAPD（如纯文档 Issue / 元 Issue / 历史欠账 Issue）。二态会让这些 Issue 无法用 skill；三态允许 WARN + 交互补，保留人工裁量空间，但禁止"无 ticket id 而写回 TAPD"（避免脏数据）。

### 为什么 v0.3 强制 skill 跨 Issue 扫同 ticket 兄弟 Issue（Finding 22）

**初版设想（v0.1/v0.2）：** skill 只扫触发 Issue 自己的工时。
**v0.3 改：** skill 必须扫所有关联同 ticket 的 Issue 当日工时再聚合。

**驱动：** §三 协议明示"一个 TAPD ticket 可对应多个 GitHub Issue"，但 §四"1 owner/day/ticket = 1 timesheet"约束意味着多 Issue 必须聚合到单 timesheet。如果 skill 只看触发 Issue，第 N+1 个 Issue 当日 add 会触发 422，或更糟——靠 update 但不知道兄弟 Issue 工时 → TAPD 工时少计。**正确语义是 TAPD = 跨 Issue 累加 mirror**。

**实现成本：** skill 需多调一次 `gh issue list --search`（in:body 模式匹配 ticket_id）。代价小，收益是写回正确性 + 审计链完整（memo `[#NNN]` 前缀回溯）。

---

## 八、试点期约束

本协议是 **5-09 起新建（v0.1）**，进入 standard `protocols/extension layer`（虽然 standard 当前 protocols 都是核心 — 本协议作为可选启用 protocol 进入 protocols/ 顶层）。

### 试点期注意

- 1-2 个团队 / 项目先试装（Phase 6 试点同期）
- 收 1-2 周反馈
- 反馈分类：bug / 体验 / 内容缺漏 / 个人偏好不通用
- ~~反馈触发 v0.2 修订~~ — v0.2 已落地（2026-05-09 dogfood 暴露 4 findings → 修订）
- v1.0 触发条件：≥ 2 项目稳定运行 ≥ 2 周

### v0.2 已知遗留 → v0.3 闭环（历史 — 现已闭环）

dogfood standard self-application 暴露 + v0.3 修订闭环：

- ~~Finding 1~~ → install/modules/09-github-labels.sh + templates/labels.yml.template（v0.3 Phase A1）
- ~~Finding 4~~ → templates/CLAUDE.md.template TAPD 6 字段必填性标注（v0.3 Phase B2）
- ~~Finding 7~~ → §五 写回字段映射表（7 字段 × 5 列权威推导）（v0.3 Phase B3）
- ~~Finding 11~16~~ → 大部分在 v0.3 闭环（详见 v0.3 commit history）
- ~~Finding 17~~ → 改编号 17/17a/b/c 留 v0.4 ADR-001 决策 5（curl|bash 分发）
- ~~Finding 18~~ → 改编号 22 → §四 加 "多 Issue ↔ 单 ticket 的 SSoT 语义" 段（v0.3 Phase B4）

### v0.3 已知遗留（v0.4 ADR 实施）

v0.3 dogfood 后续 + v0.4 范围（ADR-001 决策）：

- Finding 17 / 17a/b/c — curl | bash 分发机制（ADR-001 决策 5）
- Finding 18 — L0/L1/L2 分层（ADR-001 决策 1）
- Finding 20 — sa-el finding registry（ADR-001 决策 4）
- Finding 21 — 双仓库职责分工 / 过程透明性（ADR-001 决策 2/3）

### v0.3 试点反馈期（2026-05-13 起）

v0.3 修订后试点反馈期延续：
- 实际 TAPD MCP 端到端验证（B1 三态校验、B3 字段映射、B4 多 Issue 聚合）— v0.3.1 范围
- 跨日 / 跨 Issue / 多 owner 复杂场景验证
- 期间发现的新 finding 进入 v0.3.x 修订或 v0.4 ADR 实施

### 期间观察指标

| 指标 | 期望 |
|------|----|
| 工时 comment 记录率（应有 / 实际）| ≥ 80% |
| close 时调 summary skill 比例（自然触发率）| ≥ 60% |
| batch-scan 兜底捕获 % | < 40%（说明主路径有效）|
| 工时格式合规率（半结构化字段全） | ≥ 90% |

试点期数据**反哺本协议 v0.2**。

---

## 九、关联

- `protocols/issue-process.md`（本协议加 TAPD 关联段引用）
- `skills/global/tapd-worktime/`（本协议的执行 skill — 5-09 同期落地）
- `templates/CLAUDE.md.template` `## TAPD 配置` 段（本协议的 install 入口）
- 上游讨论沉淀：用户 5-09 内部 BE 会议提出 → SA-用户对话设计 → 本协议成型
- 类比参考：`adobe-embed/CLAUDE.md` Gap Registry 协议（GitHub-based 同模式）

---

## 十、变更记录

| 日期 | 版本 | 变更 |
|------|----|----|
| 2026-05-09 | v0.1 | 初建。双模式 + 双向手动关联 + 半结构化工时 comment + skill 触发 + 月度 batch-scan 兜底 + 手动写回 TAPD + §设计推理段（含用户原话洞察）|
| 2026-05-09 | v0.2 | dogfood 修订。范围 4 findings (6/8/9/10)：§四 加 TAPD 系统约束段（1 owner/day/ticket=1 timesheet + 聚合规则）；§五 重写"写回 TAPD"段（手动 → MCP 自动 + SSoT 强制约束 + add/update 双路径）；§七 反转"为什么手动粘贴"推理；§八 加 v0.3 候选清单。Finding 1/4/7/11~16 + dogfood 新发现 Finding 17/18 留 v0.3。|
| 2026-05-13 | v0.3 | install + protocol/skill/template 双批次修订。范围 10 findings (1/2/3/4/5/7/13/16/19/22)。Phase A — install bug fix（6 findings）：labels.yml 同步模块（24 labels）/ .gh-account 自动写（Layout A 无条件）/ hub .gitignore 模板 / install resume / CLAUDE.md 三选一交互 / .gitignore 细粒度。Phase B — protocol/skill/template（4 findings）：§三 关联段自动校验三态 / §四 多 Issue ↔ 单 ticket SSoT 段 / §五 写回字段映射表完整化 7 字段 / template TAPD 6 字段必填性标注。skill Step 1 + 4b.0 + 4b.2 同步 protocol 表。commit Phase A=bebf37e + Phase B=0e2fab7。|
