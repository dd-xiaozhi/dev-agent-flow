---
name: audit
description: Phased audit for spec-implementation alignment — spec / architecture / api / behavior / integration / issue-process / rule-coverage
disable-model-invocation: true
installed-from: agent-dev-standard@cf04193
installed-on: 2026-05-29
---

# /audit — 需求与实现的分阶段审查

按 audit phase 协议（参考 `protocols/issue-process.md` + `protocols/rule-coverage.md` + `rules/extension/audit-phases.md`）对项目进行分阶段审查。

---

## 输入

- `$ARGUMENTS`：审查阶段，可选值：
  - `prd` — PRD 对齐审查（原型 / PRD → 共识文档 → 实现，三层对齐）
  - `spec` — Spec 审查（共识文档 + 模块清单的完整性和追溯链）
  - `architecture` — 架构审查
  - `api` — 接口审查
  - `behavior` — 行为审查
  - `integration` — 集成审查
  - `issue-process` — Issue 处理流程合规审查
  - `rule-coverage` — 规则覆盖度审查（SA 月度跑）
  - `all` — 全部 phase 顺序执行
  - 可附加 `--module <name>` 指定模块范围
  - 可附加 `--window <N>d` 限定 issue-process 审查窗口（默认 30 天）
  - 无参数时提示用户选择

---

## 项目配置

执行前读取项目 CLAUDE.md 中的 `## Audit 输入映射` 段。

如果配置不存在，提示用户先运行 `/install` 配置审查输入映射。

配置格式：

```markdown
## Audit 输入映射

### prd
- PRD/原型项目: `<path>`
- 共识文档: `<path>`
- 实现基线: build #xxx 或 commit hash

### spec
- 共识文档: `<path>`
- 模块清单: `<path>`

### architecture
- 共识文档: `<path>`
- 架构设计: `<path>`
- ADR: `<path>`
- 第三方约束: <列表>

### api
- 设计文档: `<path>`
- 数据模型: `<path>`
- Controller: `<path>`
- DTO/Entity: `<path>`

### behavior
- Issue 仓库: `<owner/repo>`
- 状态机: `<path>`
- 业务代码: `<path>`

### integration
- ADR: `<path>`
- Client 代码: `<path>`

### issue-process
- Issue 仓库: `<owner/repo>`
- 默认窗口: `30d`
- /release 历史: `<path>`
- 共享文档仓库: `<path>`
- 项目特定规则补充: `<CLAUDE.md 段或 path>`
```

---

## 执行流程

所有阶段共享同一套执行骨架：

```
【前置门禁】创建任务清单 → 读取历史 → 确定范围 → 收集输入 → 正向比对 → 反向比对 → 安全语义升级 → Family-scan 合规 → 生成报告+日志 → 写入 Registry → 结束
```

### 前置门禁 — 创建任务清单（必须先于 Step 0 完成）

**这是硬性前置，不是可选步骤。任务清单文件不存在，禁止进入 Step 0。**

1. 检查 `<audit_dir>/task-YYYY-MM-DD-<phase>.md` 是否存在
   - **存在且状态为「进行中」** → 恢复上次中断的任务，从未完成的步骤继续
   - **不存在** → 立即创建，含执行清单 + 产出物验证 + 任务日志段

2. 任务清单创建完成后，进入 Step 0。
3. 每完成一个 Step，**立即**勾选对应项 + 追加任务日志，然后再进入下一步。

> **为什么是前置门禁而不是建议：** 没有任务清单，就没有 Check 步骤，就没有任何机制能拦截"审查过程中修复"的越界行为。清单是流程的骨架，不是事后的记录。

### Step 0 — 读取历史状态

1. 检查 `<audit_dir>/findings-registry.md` 是否存在
   - **存在** → 读取，已排除的跳过，已知未修的标注为"持续未修"
   - **不存在**（首次审查）→ 跳过

### Step 1 — 确定范围

1. 检查项目 CLAUDE.md 是否有 `## Audit 输入映射` 段
   - **没有** → 提示用户先运行 `/install`
2. 确定审查范围：
   - **全局**（默认）：所有模块，广而浅（多 phase 对齐检查）
   - **模块级**（`--module <name>`）：只查指定模块，**窄而深** —— 除对齐检查外，自动叠加业务逻辑审查（场景树：正常 → 异常 → 边界 → 压力）
   - **变更级**（事件驱动触发时）：只查本次变更涉及的模块

### Step 2 — 收集输入

从两侧收集，以模块清单追溯链为导航：

- **Spec 侧**：读取配置路径下的文档，列出"应该有什么"
- **实现侧**：扫描代码，列出"实际有什么"

模块级范围时，追溯链限定扫描边界 —— 只查关联的 API / 数据模型 / ADR，不全量扫描。

### Step 2.5 — 豁免段识别（单人多角色场景判定 / 2026-05-25 加 / Issue #10）

**定位:** 在 Step 3 / 4 通道合规检查(problem-registry 是否存在 / handoff/pending 是否有内容 / 任务清单文件是否存在等)之前必做。识别项目是否声明"单人多角色豁免"+ 验证豁免有效性。

**适用规则:** `rules/core/problem-handling-pattern.md` / `rules/core/artifact-based-handoff.md` / `rules/core/task-lifecycle.md` 各自 §单人多角色场景豁免 段。

**1. 识别豁免声明:**

```bash
grep -A 20 "单人多角色豁免\|PM = EL = QA" <project>/CLAUDE.md
```

**2. 若无豁免段** → 跳过本 Step / 按 standard 默认通道 audit。

**3. 若有豁免段** → 验证 6 条触发条件:

- **条件 1 显式声明:** 豁免段标题 / 内容显式提到 PM = EL = QA(或类似组合)同体
- **条件 2 等价载体清单:** 豁免段列每通道 → 等价载体映射
- **条件 3 载体活跃度(关键 / 防"挂羊头卖狗肉"):**
  ```bash
  # 对每个等价载体路径:
  ls -la <equivalent-carrier>                           # 文件 / 目录存在?
  wc -l <equivalent-carrier>                            # 非空?(> N 行)
  git log --since="30 days ago" -- <equivalent-carrier> # 近 30 天有改动?
  ```
- **条件 4 PP 落档:** `<project>/docs/problems/project-patterns.md` 含对应 PP-XXX 条目
- **条件 5 撤销触发显式:** 豁免段含"何时撤销"字段(如"团队加入第二人即失效")
- **条件 6 机器可验证:** 豁免段含具体载体映射(不是泛泛"我用别的")

**4. 判定:**

- 6 条全过 → 改判"豁免合规"/ 通道空 / 文件载体缺 不报违规
- 任一条不过 → **报豁免段声明无效**(违规 / 引用对应 rule §防滑坡机制)

**5. 反模式(audit 必报):**

- 豁免段声明但 条件 3 等价载体活跃度不达标 = "挂羊头卖狗肉" 豁免 → 报违规
- 豁免段不含撤销触发字段 = 长期豁免风险 → 报警告(MEDIUM)
- 豁免段引用 user ecosystem 私有路径(`/Users/.../` 等) = 违反 standard 输出自包含 → 报违规

**6. 不属豁免范围(即使 6 条全过仍按 standard 默认 audit):**

- HIGH 级别问题处置(不豁免)
- 安全 / 合规类问题(不豁免)
- 跨项目影响的决策(不豁免)
- 三契约语义(handoff)/ PDCA + 状态机 + 失败记录 + 迭代上限(task-lifecycle)— 仅载体形态豁免 / 语义仍按 standard 检查

### Step 3 — 正向比对

**Spec 有的，代码有没有？** 发现遗漏。

逐项检查 Spec 侧列出的每一项在实现侧是否存在、是否一致。

### Step 4 — 反向比对

**代码有的，Spec 有没有？** 发现多余或未管理的产物。

逐项检查实现侧列出的每一项在 Spec 侧是否有对应。

> 先正向再反向 —— 遗漏比多余更危险。

### Step 4.5 — 安全语义升级检查

比对完成后、生成报告前，执行两件事：

**A. 安全基线扫描（每次必做，3 项固定检查）：**

| # | 检查项 | 方法 |
|---|--------|------|
| S1 | 裸接口扫描 | 所有 Controller 方法是否都有权限注解？无注解 = 未决策，标记为发现 |
| S2 | 凭证泄露扫描 | grep 代码中 key / secret / token / password / credential，是否有硬编码值或 URL 拼接？|
| S3 | OAuth 完整性 | 认证流程是否有 state / nonce 防 CSRF？token 是否有服务端失效机制？|

> 这三条是基线最小集。新增安全类问题时，项目可同步追加检查项到本地 SKILL 副本。

**B. 发现的安全语义升级：**

对 Step 3/4 的所有发现做安全语义扫描。涉及认证 / 授权 / 加密 / 凭证 / 输入校验的缺失或偏差，必须评估安全后果。安全后果非平凡的，升级为独立发现（严重度至少 Medium），不能淹没在聚合表格中。

### Step 4.6 — Family-scan 合规检查（常驻 Step）

**触发判据：** 任一发现命中 `rules/core/fix-pattern-scan.md` 触发场景 —— 状态转换 / 状态校验、参数校验 / 边界检查、异常处理 / 资源释放、一组同名方法、第三方 API 参数差异、身份隔离字段。命中即必做；未命中即跳过（task 日志注明"无 family-scan 命中场景"）。

**两层扫描（强制，参考 `rules/core/fix-pattern-scan.md` §扩展段 + §二级 pattern 元规则）：**

| 层 | 检查 | 输出格式 |
|----|------|---------|
| 一级 | 抽象搜索模式 → grep 直接特征 → 列出"已修 / 未修 / 合理差集"三类 | `**Family scan 一级：** grep <pattern> → N 处命中 → <清单>` |
| 二级（命中下表 8 类时强制）| 进入入口点实现内部 → 二次 grep 嵌套层 / fallback 层 / backstop 层 | `**Family scan 二级：** 进入 <入口> 实现 → grep <inner-pattern> → M 处命中 + 调用链` |

**二级触发的 8 类：**

异步 submission（lambda / closure 内）/ Backstop / Fallback（catch / orElse / recover）/ 嵌套 try-catch / 嵌套 Stream / Optional / 递归 / 回调 listener / Builder / Fluent / AOP / Interceptor。

**报告中必须分一级 / 二级两层呈现** —— 只写一级 = 等价于规则未升级 = 违规。

**FB 应用整改的家族扫描：** 当审查发现某 FB 触发场景已修时，必须同时验证家族覆盖率，分层呈现"FB-XXX 整改覆盖率：触发 100%，家族漏网：F-XX-NNN"。

### Step 5 — 生成报告 + 执行日志

**报告**保存到：`<audit_dir>/YYYY-MM-DD-<phase>.md`

格式遵循 audit 输出规范，每个发现分类为缺失 / 偏差 / 风险，按严重程度排序。

**执行日志**保存到：`<audit_dir>/YYYY-MM-DD-<phase>-log.md`

执行日志**边执行边写**（不是事后补），必须包含：
1. 每个 Step 实际读取了哪些文件
2. 正向比对：应查 N 项，实查 N 项，跳过 N 项（跳过必须注明原因）
3. 反向比对：同上
4. 覆盖率统计表
5. 每个 Phase 耗时

### Step 6 — 写入 Registry + 事件流追加

报告和日志全部完成后，**自动将所有发现批量写入 findings-registry 和 problem-registry**，状态统一为 `proposed`。

- 不做去向判断 —— 全部记录，对错留给事后处理
- 不等待用户确认 —— 审查过程零人工介入
- findings-registry 是审查专用详细视图，problem-registry 是全景索引，两者通过编号关联

**Step 6.5 — 事件流追加（按需）：**

如项目启用 jsonl 事件流（`<workspace>/.events/audit-finding/YYYY-MM.jsonl`），每条 finding INSERT 后同步 append 一行 jsonl 用于跨项目分析 / 趋势可视化。schema 见 `templates/archive-frontmatter.schema.yaml` 同源约定（项目可自定义 SCHEMA.md）。

**subagent 模式（audit-agent）：** 如果 audit-agent 被平台层拦截写 .jsonl，改为在 proposals 文件中加一段 `## 事件流追加建议 (jsonl)`，由父会话代 append。

如有高优先级发现（HIGH / CRITICAL），**执行 `/notify audit`** 通知团队（如 notify skill 已装）。无高优先级发现则不通知。

**审查到此结束。** 后续由全局会话 review 报告 + 日志，再由 `/fix` 分拣决定每条发现的去向。

---

## 各阶段的比对内容

七步骨架不变，每个阶段的 Step 2~4 读取和比对的内容不同：

### prd
| 步骤 | Spec 侧 | 实现侧 |
|------|--------|--------|
| 收集 | 原型功能点清单（按页面 / 模块）| 共识文档 + 实现代码 / 接口 |
| 正向 | 每个原型功能点是否在共识文档覆盖？是否实现？| — |
| 反向 | — | 实现是否都能在原型找到对应？|

**状态标注四类：** ✅ 已实现 / 📋 共识文档已定义但延期 / 🔶 FE-only（不需后端接口）/ ❌ Gap（原型有，缺失）

### spec
| 步骤 | Spec 侧 | 实现侧 |
|------|--------|--------|
| 收集 | 共识文档功能章节列表 | 模块清单模块列表 |
| 正向 | 每个功能章节是否有模块承接 | — |
| 反向 | — | 每个模块是否有共识文档对应 |

额外检查：TBD 收敛情况、反哺标记覆盖率、追溯链完整性、状态时效性。

### architecture
| 步骤 | Spec 侧 | 实现侧 |
|------|--------|--------|
| 收集 | 共识文档 + 模块清单 + 约束 | 架构设计文档 + ADR |
| 正向 | 每个模块是否在架构中有对应 | — |
| 反向 | — | 架构中的选型是否都有约束支撑 |

额外检查：ADR 决策是否在架构中体现、第三方依赖使用方式是否符合文档约束。

### api
| 步骤 | Spec 侧 | 实现侧 |
|------|--------|--------|
| 收集 | 接口设计文档 + 数据模型文档 | Controller / DTO / Entity |
| 正向 | 每个设计接口是否有 Controller 实现 | — |
| 反向 | — | 每个 Controller 方法是否在设计文档中有定义 |

额外检查：字段一致性（名称 / 类型 / 必填性）、状态码 / 错误码对齐、数据模型字段一致。

**数据建模质量检查（每次 api 审查必做）：**

| # | 检查项 | 方法 |
|---|--------|------|
| D1 | 隔离维度独立性 | 用于区分角色 / 租户 / 模块的字段，是否独立于业务类型？用业务枚举做身份隔离 = 脆弱 |
| D2 | 同类操作一致性 | 同性质的耗时操作是否使用相同的执行模式（同步 / 异步、重试策略）？|
| D3 | 枚举演化安全性 | 枚举 / 状态字段将来跨角色或跨模块复用时，现有设计是否兼容？|

### behavior
| 步骤 | Spec 侧 | 实现侧 |
|------|--------|--------|
| 收集 | Issue 验收条件 + 状态机定义 | Service / Domain 代码 |
| 正向 | 每条验收条件是否有代码覆盖 | — |
| 反向 | — | 代码中的业务分支是否都有验收条件对应 |

额外检查：状态机完整性（合法转换 + 非法拦截）、边界条件处理。

### integration
| 步骤 | Spec 侧 | 实现侧 |
|------|--------|--------|
| 收集 | ADR + 第三方 API 文档 | Client 代码 + 配置 |
| 正向 | ADR 决策是否在代码中落地 | — |
| 反向 | — | 代码中的集成方式是否都有 ADR 覆盖 |

额外检查：错误处理覆盖（超时 / 限流 / 认证失败）、配置项硬编码风险、API 版本一致性。

### issue-process

参考 `protocols/issue-process.md` § 审查维度（5 维度）。

**输入获取：**
- `gh issue list --state closed --search "closed:>=$(date -v-30d +%Y-%m-%d)" --json number,title,labels,closedAt --limit 200`
- `gh issue list --state open --label [role]-in-progress,[role]-confirmed --json number,title,labels,updatedAt`
- 单 Issue events / comments / commit log / release-history

**豁免 comment 识别（2026-05-25 加 / Issue #11 FB-006）:**

维度 3 #14（文档先行 commit）/ 维度 #16（测试覆盖）等结构化检查**必须先扫 Issue comment 语义豁免**，命中则标 ✅（豁免）而非 🟡（偏差）/ 不机械化报违规。

```bash
# 维度 3 #14 文档先行检查前 — 先扫豁免 comment
gh issue view <N> --comments | grep -E "文档先行豁免|S 级豁免|bootstrap 豁免" && {
    # 命中豁免关键词 → 验证豁免 comment 必填字段（豁免理由 / 项目阶段 / 后置承诺）
    # 字段齐全 = 标 ✅（豁免合规）/ 不报违规
    # 字段缺失 = 标 🟡（豁免依据不完整 / 不是不识别豁免）
}

# 维度 #16 测试覆盖检查前 — 同理扫 "测试豁免" 关键词
```

**豁免关键词清单（与 issue SKILL §pm-reviewed Step 2 §文档先行豁免规则对齐）:**
- `文档先行豁免` / `S 级豁免` / `bootstrap 豁免`(文档先行)
- `测试豁免`(测试覆盖)
- 项目根据自身 PP-NNN 扩展(audit 读 project-patterns.md 时扩展白名单)

**配套规则:** issue SKILL Step 2 §文档先行豁免规则定义"豁免 comment 必填字段" / audit 验证字段齐全性而非语义合理性(语义合理性需 review 人工判定)。

**反向漏切检测（维度 1 #5c 关键）：**

```bash
# 1. 拉所有 open [role]-in-progress 的 Issue
# 2. 对每条：从 comment 提取 commit hash（`commit: \`<hash>\`` 格式）
# 3. cross-check：每个 hash 是否是 release-history 中某 build 的 head_commit 的祖先
#    git merge-base --is-ancestor <hash> <build-head-commit>
# 4. 退出码 0 = 已部署 → 但 events 无 labeled [role]-confirmed = 5c 反向违规
# 5. 持续时长 = build 部署时间 - issue 收尾 comment 时间
```

**Closed issue 4 字段关联验证（2026-05-25 加 / Issue close-association 范式 v0 §3.5）:**

适用于 standard 类项目(无 deploy 概念 / 用 CHANGELOG + release-log `[Unreleased]` 段累积 + SemVer cut)。**closed issue 的 close comment 必含 4 字段**(规约见 `rules/core/task-lifecycle.md` §/issue Step 6b)。

audit 维度 #N — Close comment 4 字段齐全度(语义层 LLM 必需 + 部分机器验证):

```bash
# 维度 1: commit hash 列表存在 + 真实
gh issue view <N> --json comments --jq '.comments[] | select(.body | contains("Issue closed")) | .body' \
  | grep -oE '(code|docs)@[a-f0-9]{7,40}' \
  | while IFS=@ read repo hash; do
      git -C <project>/$repo cat-file -e $hash 2>/dev/null || echo "WARN: $repo@$hash 不存在"
    done

# 维度 2: CHANGELOG `[Unreleased]` 段含对应 issue entry
sed -n '/^## \[Unreleased\]/,/^## \[/p' code/CHANGELOG.md | grep -E "#$N\b" || echo "WARN: CHANGELOG 未含 #$N entry"

# 维度 3: release-log `[Unreleased]` 段含对应 issue entry(若 close comment 未显式标"不涉及")
sed -n '/^## \[Unreleased\]/,/^## \[/p' docs/docs/release-log.md | grep -E "#$N\b" || \
  gh issue view <N> --json comments --jq '.comments[].body' | grep -q "不涉及设计层" || \
  echo "WARN: release-log 既未含 entry 也未显式标'不涉及'"

# 维度 4: 关联 artifact 字段存在(ADR / FB / handoff / 关联 issue 或显式"无关联")
gh issue view <N> --json comments --jq '.comments[].body' \
  | grep -qE "关联 artifact|无关联|ADR-|FB-|handoff" \
  || echo "WARN: 关联 artifact 字段缺失"
```

**判定:** 任一字段缺失 → 标违规(轻度 LOW / 不阻塞 / 但应补)。`closed` 但 4 字段不全的 issue 在 `IPR-NNN` 编号 / 加 `close-association-incomplete` 子类。

**反模式(audit 必报):**

- ❌ Close comment 含"已修复"但无 commit hash(D 层 self-contained 失效)
- ❌ CHANGELOG `[Unreleased]` 缺对应 entry(E 聚合层断链)
- ❌ release-log 字段省略不写(应显式标"不涉及" / 不能空)
- ❌ commit hash 不真实(`git cat-file -e` 暴露)

**finding 编号：** `IPR-NNN` 单 Issue / `IPR-T-NNN` 趋势

> **多 dev 并发场景(ADR-008 / 2026-05-25 起):** 新 IPR / IPR-T entry 用 `IPR-YYYYMMDD-{hash}` / `IPR-T-YYYYMMDD-{hash}` 格式(通过 `code/scripts/generate-id.sh` 生成)。既有 `IPR-NNN` 保留 / 不迁移。同理 F-XXX-NNN / 详见 ADR-008。

### rule-coverage

参考 `protocols/rule-coverage.md` § 审查维度（6 维度）。

**执行者：** SA（不下推 EL）。
**节奏：** 每月初首工作日。
**finding 编号：** `RC-NNN` 单条 / `RC-T-NNN` 趋势

---

## 约束

**审查 = 自动化扫描 + 记录，不是工作流。** 审查的职责是发现和记录问题，不做任何处理动作。

- **审查过程零人工介入** —— 不询问、不确认、不等待用户输入。从 Step 0 到 Step 6 全自动执行
- **审查过程只记录，不修复** —— 不改代码、不改文档、不创建 Issue、不做任何修改动作
- **报告必须落文件** —— 保存到 `<audit_dir>/YYYY-MM-DD-<phase>.md`。未生成报告文件 = 审查未完成
- **执行日志必须落文件** —— 保存到 `<audit_dir>/YYYY-MM-DD-<phase>-log.md`。未生成日志 = 审查不可验证
- 每个阶段独立执行，可单独运行也可组合运行
- 所有发现统一写入 registry 状态为 `proposed`，去向由事后 `/fix` 决定
- **审查完成后 24h 内必须产出 fix dispatch handoff**（详见 `rules/extension/audit-fix-dispatch.md`）—— audit 自身不做 dispatch（保持"只记录不修"约束），但 SA 必须紧跟 dispatch handoff 显式处置每条 finding（5 选 1：resolve via fix / merge / dismiss / escalate / defer）。审查产出 ≠ 工作流结束，finding 不允许在 registry 沉底。

---

## FB 候选识别（审查完成后）

审查报告末尾的"系统性建议"专段是 FB 候选的天然来源。报告生成后，agent 应对每条系统性建议做一次判断：

**判断标准（满足以下三条则提示用户）：**
1. 跨项目普适 —— 不只在本项目发生
2. 根因在规范 / 流程 / 设计层面 —— 不是单条 bug
3. 改进规则后能降低此类问题发生概率

**判断为 FB 候选时，提示：**

> "系统性建议「[X]」可能具备跨项目普适性，建议上报为 FB 候选。运行 `/submit-fb` 完成提交（如已装）。"

**不做的事：**
- 不替用户判断"是否值得提交"
- 不自动提交，只提示

---

## 与协议层 / 规则层的关系

| 关联 | 关系 |
|------|----|
| `protocols/issue-process.md` | issue-process phase 实施 |
| `protocols/rule-coverage.md` | rule-coverage phase 实施 |
| `rules/core/fix-pattern-scan.md` | Step 4.6 family-scan 触发判据 + 二级 pattern 8 类 |
| `rules/extension/audit-phases.md`（按需）| 各 phase 详细 step 完整版 |
| `rules/extension/audit-fix-dispatch.md`（按需）| 24h SLA + dispatch handoff 5 选 1 决策 |
| `rules/core/artifact-based-handoff.md` | audit 报告 / 日志 immutable + registry living artifact |
