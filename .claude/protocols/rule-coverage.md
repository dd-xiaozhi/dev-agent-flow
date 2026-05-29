# Rule Coverage Protocol — 规则覆盖度审查协议

**定位：** 规则元层的覆盖度审查协议 + 审查路径。规则建立 / 修订是 SA 工作流的核心节点，但缺审查路径——违规可能沉底而无人察觉。本协议定义元规则审查的契约。

**类型：** 节点配套类形式化第 2 例（参考 `rules/core/formalization-timing.md` 类型 B 路径）—— 节点客观存在（规则建立 / 修订）+ 规则齐备但缺审查（① 全局规则覆盖度无人扫描 ② 项目级 CLAUDE.md 重复规则无人识别为"该提升至全局" ③ 用户头脑里的规则无主动迁移机制）+ 违规会沉底 + 首次实践即基线。

---

## 触发场景

每月初首工作日（与月度工时填报 / 节奏性 PM 任务合并 SA 启动动作）。

工时填报需扫上月 spool → rule-coverage 复用此扫描，不重复读取。遇月初长假顺延到节后首工作日，不强求月初 1 号。

**执行者：** SA（不是 EL）—— 本协议检查的是协议层 / 元层覆盖度，是 SA 视角任务，不下推 EL handoff。

---

## 审查对象

- 协议层规则（`protocols/`）+ 工程纪律规则（`rules/core/` + `rules/extension/`）+ feedback 索引（`fb-index.md`）
- 各项目级 CLAUDE.md
- 上月 spool（全局 + 各项目 spool 中用户对话）
- memory 文件
- 上月新增 GR / FB / problem 中标"载体覆盖率"类的 finding

**审查范围（默认）：** 滚动窗口 = 上一日历月的全部产出。

---

## 审查维度（6 维）

### 维度 1 — 跨项目 CLAUDE.md 重复模式（提升候选）

1. 同条规则在 ≥ 2 个项目级 CLAUDE.md 出现 → 提升至 standard 全局候选
2. 提升后是否有项目级保留必要（项目特有补充 vs 重复浪费）
3. 已提升至全局的规则，项目级 CLAUDE.md 是否需要简化（避免重复）

### 维度 2 — 全局规则占位项 vs 项目特定补充（覆盖度）

4. `rules/core/architecture-constraints.md` 等占位项（如"测试入口 module" / "MapStruct converter 路径" / "Gateway 接口示例"）在各项目 CLAUDE.md 是否被填充
5. 缺少占位项填充的项目 → flag 给 EL 补
6. 全局规则中描述模糊 / 抽象的规则段（如"按需" / "合理选择"）是否需要项目级具体化

### 维度 3 — 用户头脑→载体迁移漏网（最重要）

7. grep 上月 spool 用户对话中以下措辞：
   - "我之前说过 / 早就提过 / 早该有 / 我记得 X"
   - "为什么没补 / 怎么还没"
   - "这是我之前定的"
8. 每条命中 → 反查规则是否已落 ADR / standard rules / memory：
   - **已落** → 标注载体路径，确认无遗漏
   - **未落** → 立即补迁移（**不等下次审查**），并记 RC-finding
9. 同模式案例归集：判断是否需要起新 FB

### 维度 4 — FB observing → applied 状态推进

10. fb-index.md 中 status: observing 的条目，上月是否累积新实证
11. 达 ≥ 2 次实证 → 升 applied + 落入对应规则文件
12. 持续 observing > 2 个月无新实证 → 重新评估（降 dismissed 或保持 observing）
13. 新起 candidate 是否补全 fb-index 元数据

### 维度 5 — memory 应用痕迹（验证迁移有效性）

14. 上月新加的 memory 文件是否在 spool / handoff 中有引用
15. memory 命中预期触发时机
16. 无应用痕迹的 memory → 评估是否需调整描述（让 AI 更易识别相关场景）

### 维度 6 — 跨载体一致性 sweep（已 applied FB 的整改有效性）

> applied 状态不等于根治。**已 applied FB**（如跨载体一致性类）的持续高频复发说明规则覆盖与执行间有 gap。

17. **已识别同源条目状态核查**：
    - 拉取上月所有 audit 报告中标"跨载体一致性"类的 finding
    - 核查每条修复状态（resolved / fixing / dismissed / proposed 沉底）
    - **沉底 ≥ 7 天的同源 finding** → 升级到本月度处置清单
18. **主动 grep 寻找未识别同源**：
    - 字段 javadoc / @Schema annotation / api-spec docs 三方一致性
    - registry 状态字段 / Issue label / commit message 类别一致性
    - ADR 引用 / 代码注释 / module doc 引用一致性
19. **趋势统计**（当月）：新增同源 finding 数 / 上月遗留处置率 / 累计趋势曲线
20. **整治建议产出**（≤ 3 条 actionable）：高频复发载体 / 整改方向 / 是否起新 FB

**与维度 4 的差异：**
- 维度 4 关注 FB 编号的状态流转（candidate → observing → applied）
- 维度 6 关注**已 applied FB** 的整改有效性 —— applied 不等于根治

---

## 输出

- **单条 finding**（`RC-NNN` 编号）：每条规则覆盖度问题作为可修复入口
- **趋势 finding**（`RC-T-NNN` 编号）：跨项目规则模式 / 用户对话措辞频率 / FB 状态推进健康度
- **系统性建议**（≤ 3 条 actionable）：规则修订 / 新建 / 提升至全局 / 补 memory 等方向建议

**月度处置：**
- 规则提升 / 简化 → SA 直接落地（standard rules + 项目级 CLAUDE.md commit）
- FB 状态推进 → fb-index 更新
- 用户头脑→载体迁移 → memory / ADR / standard rules append（**审查中即落地**，不等月底）

---

## 特殊执行约束

- **维度 3（用户头脑迁移漏网）允许审查中即落地** —— 这是与项目代码 audit 的关键差异。代码 audit 严格"只记录不修"防止越界，但规则元层"发现规则缺失立即补"是合理的（不补 = 下次还会撞）；前提是不涉及业务方案选项 / 不涉及 PM 决策（这两类仍立 RC-finding 等用户拍板）
- **不审查具体项目代码** —— 本协议不涉及代码层；那是 architecture / behavior 等 audit phase 职责
- **首次跑作为基线** —— 首次产出覆盖率指标作为基线，后续按趋势对比
- **pilot 节奏建议** —— 节点配套类形式化首次设计后，建议跑 ≥ 3 次确认维度合理性

---

## 报告位置

`<sa-workspace>/reviews/rule-coverage-YYYY-MM-DD.md`

---

## 形式化路径（节点配套类 Type B 第 2 例）

| 触发条件 | 满足情况 |
|------|------|
| 节点客观存在 | 规则建立 / 修订是 SA 工作流核心节点 |
| 规则齐备但缺审查 | 多条规则齐备，但全局覆盖度 / 跨项目重复 / 用户头脑迁移**无审查机制** |
| 违规会沉底 | 不审查 → 用户决策带宽浪费 + 规则信任损耗长期累积 |
| 首次实践即基线 | 第一次跑产出覆盖率指标作基线，后续按趋势对比 |

---

## 关联

- `rules/core/formalization-timing.md` — 元规则形式化判据 + 类型 A/B 区分
- `rules/core/problem-handling-pattern.md` § 项目级质量模式记忆 — PP 升级路径
- `protocols/issue-process.md` — 节点配套类 Type B 第 1 例（同源协议层方法）
- `protocols/task-isolation-judgment.md` — 节点配套类 Type B 第 3 例（横向元规则）
- `skills/core/audit/SKILL.md` § rule-coverage phase — 审查执行细节
