# Issue Process Protocol — Issue 处理流程协议

**定位：** Issue 处理流程的合规协议 + 审查路径。Issue 处理流程是 spec-to-code-flow 的核心节点之一；规则齐备但缺审查路径会导致违规沉底。本协议定义流程契约 + 审查维度。

**类型：** 节点配套类形式化首例（参考 `rules/core/formalization-timing.md` 类型 B 路径）—— 节点客观存在（Issue 处理流程是必经路径）+ 规则齐备但缺审查（task-lifecycle / issue-handling / fix-pattern-scan 等规则有，但执行违规无人扫）+ 违规会沉底 + 首次实践即基线。

---

## 流程契约

### Issue 状态机（Gap / Bug 通用）

```
raised → [role]-reviewed → pm-reviewed → [role]-in-progress → [role]-confirmed → closed
```

`[role]` 是承担实施的角色（如 BE / FE / QA）。状态切换的关键约束：

| 状态 | 何时打 | 何时切走 |
|------|----|----|
| `raised` | Issue 创建时 | review 流程开始 |
| `[role]-reviewed` | 角色 review 后（确认是否本角色范围）| PM review 阶段 |
| `pm-reviewed` | PM 决策后（确认产品意图）| 进入实施 |
| `[role]-in-progress` | 方案 approve 后 + 动手前打 | 实施完成 / dev 部署后 |
| `[role]-confirmed` | **由 `/release` 切**（不在 /issue 收尾时切；过早 = 违规）| 关闭 |
| `closed` | dev 已发版 + QA 可回测 | — |

### 关键约束

1. **`[role]-in-progress` 必须在方案 approve 后打** —— 不能从 `pm-reviewed` 直接跳到 `[role]-confirmed`
2. **`[role]-confirmed` 由 /release 切** —— 不在 /issue 收尾时切（dev 没部署就标 confirmed = 语义错）
3. **「可关闭」标注由 /release 切 label 时同步嵌入 comment** —— BE 收尾不再标"可关闭"，避免 dev 没发版下游就以为可关
4. **持续 `[role]-in-progress` 但 commit 已在某 build 中 = /release Step 6b.1 漏跑**（反向漏切检测必须做）

---

## 收尾 comment 完整性约束

Issue 收尾 comment 必含：

| 字段 | 要求 |
|------|----|
| commit hash | 文档 + 代码 commit 的 short hash 列表 |
| 文档链接 | 指向**共享文档仓库**（不是代码仓库）|
| 状态注明 | "BE 工作完成 — 等 /release 发版"（**不再标「可关闭」**——由 /release Step 6b.1 切 label 时同步嵌入）|
| 文档同步声明 | 每份文档对应 commit hash，可 cross-check |

`/release` 切 `[role]-confirmed` 后，附加 comment：
- `已发布到 dev — build #N — 可关闭`
- 此时下游（QA / FE）可回测对接

---

## 与其他规则的协同

| 规则 | 关系 |
|------|----|
| `rules/core/task-lifecycle.md` | /issue 模板的 PDCA 框架 |
| `rules/extension/issue-handling.md`（按需）| Gap / Bug 状态机 + 收尾详细 step |
| `rules/core/fix-pattern-scan.md` | Bug 修复时家族扫描触发条件 |
| `rules/extension/audit-fix-dispatch.md`（按需）| audit 产出 finding 后 fix dispatch handoff 触发 |
| `rules/core/architecture-constraints.md` | 代码实现的架构纪律 |
| **`protocols/tapd-worktime-integration.md`**（按需）| **如启用 TAPD 工时集成 — 加 ticket 关联 + 工时 comment + close 时汇总流程**（详见下段）|

### TAPD ticket 关联（如启用）

如项目 install 时启用 `protocols/tapd-worktime-integration.md`：

1. **PM 创建 TAPD ticket → 关联 GitHub Issue**：手动双向关联（TAPD 描述贴 Issue URL + Issue body 头部段标 `**TAPD ticket:** #<ticket-id>`）
2. **各角色用半结构化 comment 记工时**（按 session 粒度，详见 tapd-worktime-integration.md §四）
3. **close 时调 `/tapd-worktime-summary <issue-N>` 汇总**，关闭者手动粘贴回 TAPD ticket 工时栏
4. **本 issue-process 状态机不变** — TAPD ticket 工时管理是**附加层**，不参与 raised → reviewed → in-progress → confirmed → closed 流转决策

**为什么不内嵌进本协议主体：** 保持 issue-process 协议的纯净性 + TAPD 集成是按需启用的扩展（不强制）。详见 `protocols/tapd-worktime-integration.md` §一 协议定位与边界。

---

## 审查维度（issue-process audit phase）

完整审查应覆盖 5 维度：

### 维度 1 — Label 状态机合规性（structural）
1. 状态流转是否合法
2. 是否跳过中间态（典型：直接 pm-reviewed → [role]-confirmed）
3. 是否有未授权回退（如 [role]-confirmed → [role]-in-progress）
4. closed 是否在 [role]-confirmed 之后
5. 三角度切换时点验证：
   - **5a 正向（防缺失）**：`[role]-in-progress` 应在方案 approve 后打
   - **5b 正向（防过早切）**：`[role]-confirmed` 应由 /release 切
   - **5c 反向（防漏切）**：已发版的 `[role]-in-progress` Issue 应被 /release 及时切到 `[role]-confirmed`；漏切 = 违规

### 维度 2 — 收尾 comment 完整性（content）
6. commit hash 是否齐
7. 文档链接是否指向共享文档仓库
8. 状态注明是否合规
9. /release 切 label 后 comment 是否含「可关闭」标注
10. 文档同步每份是否有对应 commit hash

### 维度 3 — /issue Step 触发完整性（procedural）
11. Step 0 问题定性自检表是否贴出（**语义层 LLM 必需**）
12. Step 0 架构师视角 3 维（架构 / 技术债 / 演化）是否填，或标"规模豁免"（**语义层 LLM 必需**）
13. 方案确认（LMP）—— 中大改动是否有方案呈现 comment（**语义层 LLM 必需**）
14. 文档先行 —— 是否有标"待实现"的文档 commit 在代码 commit 之前（**结构化**）
15. 编译门禁 —— 编译失败 retry 是否超上限（**结构化**）
16. 测试 —— 收尾是否提及测试通过 / 新增测试用例（**语义层 LLM 必需**）
17. 6a 文档同步 / 6b Issue comment / be-in-progress label 标注（与维度 1/2 交叉）

### 维度 4 — 跨规则交叉验证（cross-validation）
18. `[role]-confirmed` 是否对应 dev build（由 /release 切换的 label 必须有 build 关联）
19. 修复涉及的 commit 在 build 号之前（时间 / 拓扑顺序）
20. fix-pattern-scan 适用类型的 Issue —— 是否有家族扫描证据
21. ADR 关联 —— Issue 触发或确认 ADR，ADR header 是否记录了 Issue 编号
22. tech-debt —— Issue 引入新 `TODO(reason)`，是否同时记 problem-registry / 共识文档

### 维度 5 — 趋势 / 模式（aggregate）
23. 违规率（合规 / 总 Issue）
24. 高频违规 step（作为规则改进信号）
25. 时间趋势（**prerequisite：累计 ≥ 3 次审查数据**）
26. 类型分布差异（Gap vs Bug vs 纯文档类违规率差异）
27. 责任人 / 来源差异（events.actor 字段）

---

## finding 编号约定

- `IPR-NNN` — 单 Issue 违规
- `IPR-T-NNN` — 趋势 / 模式发现

---

## 形式化路径（节点配套类 Type B 第 1 例）

| 触发条件 | 满足情况 |
|------|------|
| 节点客观存在 | Issue 处理流程是 spec-to-code-flow 必经路径 |
| 规则齐备但缺审查 | task-lifecycle / issue-handling / fix-pattern-scan 等规则有，但违规无人扫 |
| 违规会沉底 | 不审查 → 违规累积 → 流程信任崩塌 |
| 首次实践即基线 | 第一次跑产出违规率作基线，后续按趋势对比 |

**特殊执行约束：**
- **不主动修 label / 补 comment** —— 审查只记录，修复由 /fix 分拣
- **历史窗口外的 Issue 不重算** —— 已关闭 Issue 的违规如不在审查窗口内，不重新打开评判
- **历史漂移合并到趋势 finding** —— 大批量同模式违规（如 N 条跳过中间态）不创建 N 条单 finding，合并为一条 IPR-T-* 趋势 finding

---

## 关联

- `rules/core/spec-to-code-flow.md` — 主流程图，本协议覆盖其代码实现节点
- `rules/extension/issue-handling.md` — Gap / Bug 状态机详细 step
- `skills/core/issue/SKILL.md` — Issue 处理 skill 实施
- `skills/core/audit/SKILL.md` § issue-process phase — 审查执行
