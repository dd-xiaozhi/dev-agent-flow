---
name: issue
description: Issue / Bug standard handling flow — dual platform (GitHub + TAPD) with 5-scenario handoff discipline, doc-first approach
disable-model-invocation: true
installed-from: agent-dev-standard@cf04193
installed-on: 2026-05-29
---

# /issue — Issue / Bug 标准处理流程（双平台 + 5 场景）

按 issue 处理协议（参考 `protocols/issue-process.md`）处理指定 issue / bug。本 skill 支持 GitHub Issue（原生）+ TAPD Bug（2026-05-20 加 / 见 §TAPD 平台分支段）双平台。

**协作流纪律:** 任何 handoff 必须显式判定 S1-S5 五场景之一(详见 `rules/core/issue-handling.md` Iron Law: `NO HANDOFF WITHOUT EXPLICIT SCENARIO + COMMENT FIRST`)。

---

## 输入

- `$ARGUMENTS`：issue 编号（如 `123`）或 `list`

---

## 项目配置

执行前读取项目 CLAUDE.md 中的 `## Issue 配置` 段，获取以下信息：

| 项 | 含义 |
|---|---|
| `issue_platform` | **平台维度**（`github` / `tapd` / 双平台项目可 `github+tapd` / 决定走哪条分支 / 默认 `github`） |
| `issue_repo` | GitHub 平台:Issue 仓库（owner/repo）|
| `tapd_workspace_id` | TAPD 平台:workspace 数字 ID |
| `tapd_ticket_prefix` | TAPD 平台:ticket URL 前缀（可选，用于 comment 渲染）|
| `doc_repo` | 共享文档仓库本地路径（用于文档同步）|
| `adr_path` | ADR 文件目录 |
| `code_path` | 代码根目录 |
| `compile_cmd` | 项目编译命令（如 `mvn compile -q` / `npm run build` 等）|
| `role` | 当前角色（默认 `be`，可为 `fe` / `qa` / `sa`）**必须 lowercase**(对齐 labels.yml / 见 §Step -1 normalize)|

如果配置不存在，提示用户先运行 `/install` 或手动指定。

---

## 执行逻辑

### 当参数为 `list` 时

1. 拉取 issue_repo 的全部 open issues
2. 按优先级排序展示（high > medium > 无；pm-reviewed > raised）
3. 等待用户选择，不执行任何操作

### 当参数为 issue 编号时

#### 阶段一：展示 + 意图回读 + 建议（不做任何修改）

1. 拉取 issue 原文 + 所有 comments
2. 完整展示 issue 内容
3. **S/M/L 分级（在填自检表前先判断，决定后续每步深度）：**

   | 级别 | 判定特征 |
   |------|---------|
   | **S** | 单文件改动 / 无接口变更 / 无状态机影响 / 无歧义，可直接修 |
   | **M** | 单模块改动 / 可能有接口变更 / 状态机简单涉及 / 基本明确 |
   | **L** | 跨模块 / 接口或数据模型变更 / 需求有歧义 / 架构决策或 Gap |

   输出格式：`分级：S / M / L，理由：<一句话>`

4. **问题定性自检表（硬门禁，不得跳过）**

   **执行硬约束：**
   - **必须**先在 Issue 贴 comment 含完整自检表 4 维（下列），用户确认后才能进入意图回读 + 后续步骤
   - **不得**只在对话回复中展示——必须落到 Issue comment 形成永久追溯
   - **不得**隐式判断 / 直接动手——AI 跳过自检表 = 违规
   - **规模豁免**满足全部条件时（跨文件 ≤ 1 / 不涉接口 / 不涉数据模型 / 不涉安全 / 改动类型限定 typo / log 级别 / comment / 私有作用域重命名 / 格式化），架构师 3 维段标"⚪ 规模豁免（XXX 原因）"，**仍必须发 comment**——豁免是答案不是省略

   **Comment template（depth 按 S/M/L 调整内容详尽度）：**

   ````markdown
   ## Step 0 — 问题定性自检表

   **分级：** S / M / L
   **理由：** <一句话>

   ### 需求前提
   - [ ] 共识文档有明确定义 → 引用章节号
   - [ ] 共识文档有提及但模糊 → 引用 + 标注模糊点
   - [ ] 共识文档未提及 → 标注 **"需求空白"**

   ### 影响范围
   - [ ] 只影响当前接口 → 列出接口
   - [ ] 影响同模块其他接口 → 列出关联接口
   - [ ] 跨模块 → 列出受影响模块

   ### 修复前提
   - [ ] 不需要需求决策，代码逻辑明确有错 → 可直接修
   - [ ] 存在 ≥ 2 种合理实现 → 列出选项，等用户拍板
   - [ ] 需求本身未定义 → 标注 **"需 PM 确认"**，先建 Gap Issue

   ### 架构师视角 3 维

   **架构影响：**
   - [ ] 无影响（纯实现细节）
   - [ ] 消除约束（改善）：<一句话>
   - [ ] 新增约束（需评估）：<一句话>

   **技术债维度：**
   - [ ] 消除债：<具体哪条>
   - [ ] 无关
   - [ ] 新增债（需标注）：<什么债 / 为什么接受>

   **长期演化：**
   - [ ] 让未来简单（复用性增）
   - [ ] 无影响
   - [ ] 让未来复杂：<为什么接受 / 是否走 LMP>

   ### LMP 升级判定
   任一维度勾"新增约束 / 新增债 / 让未来复杂" → **强制升级 LMP**（即使代码改动小）

   ### 场景判定（S1-S5 / 2026-05-20 加 / 详见 `rules/core/issue-handling.md`）

   按 `rules/core/issue-handling.md` §二.2 算法判定本次处理对应场景:

   - [ ] **S1 修完→回测**(BE 完整修复 / 推 QA / pending-verify)
   - [ ] **S2 部分修→转 FE**(BE 完成本端 / 需 FE 继续 / pending-collaboration)
   - [ ] **S3 修前需 PM**(评估发现需 PM 拍板才能动 / pending-decision)
   - [ ] **S4 部分修后需 PM**(BE 修一部分 / 剩余需 PM 拍板 / pending-decision)
   - [ ] **S5 不需修→回 QA**(判定非 bug / 不修 / closed-no-action)

   **判定结果显式标记:** comment 第一行标 `[S{N}] <场景中文标识>`,后续 §3.1 4 字段 + §3.2 场景特定字段均按场景填写。

   **平台映射:** S1-S5 在 GitHub 上的字段表达见 `docs/concepts/platform-mapping-github-issue.md`;在 TAPD 上的字段表达见 `docs/concepts/platform-mapping-tapd-bug.md`(+ MCP 操作规约 `protocols/tapd-bug-operations.md`)。

   **场景 → 阶段二分支映射(2026-05-20 加 / F-3 + F-4 follow-up):**
   - S1 修完→QA / 纯实现 → `pm-reviewed` 分支
   - S2 部分修→FE / 跨端协作 → `cross-role-handoff` 分支(新增 / 见阶段二)
   - S3 修前需 PM → `raised` 或 `pm-reviewed`(取决于是否已有 PM 决策 / 通常 `raised` 等 PM 回复)
   - S4 部分修后需 PM → `raised`(写 BE 部分实施 + 剩余决策选项 / 等 PM 回复)
   - S5 判定不修 → `纯文档类` 分支(comment 含判定理由 + 切 confirmed / 见阶段二)
   ````

   **执行步骤：**
   1. AI 用 `gh issue comment <N> -F <tmpfile>` 贴上述 template comment（占位符填好）
   2. 在对话同步展示完整内容给用户
   3. 等用户在 Issue 下追评 / 在对话显式确认 → 进入下一步

5. **意图回读** — 用自己的话复述理解：
   ```
   【我理解的目标】…
   【我理解的约束】…
   【我不确定的地方】…
   ```
6. 判断当前状态，给出执行层处理建议：
   - 是否需要 PM 回复？是否可直接行动？
   - 技术影响范围
   - 推荐方案（如有多个选择逐一列出，触发 Large Module Protocol 时按 L1/L2/L3 呈现）
   - 需确认的设计决策（如有）
   - 补充验收条件（issue 中未明确的，主动提出）
7. **硬性停止 — 展示以上全部内容后，必须停下来等待用户确认。禁止自行进入阶段二。用户未回复 = 未确认。**

#### 阶段二：执行（用户确认后）

根据 issue 状态分支：

##### `raised`（产品经理尚未回复）
1. 写 BE/FE/QA 技术分析 comment（含影响范围、推荐方案、补充的验收条件）
2. 更新 label → `[role]-reviewed`
3. 如果 label 含 `needs-pm` → 同步录入 `<project>/docs/problems/needs-pm-queue.md` 的 Open 段
4. 停止，等待产品经理回复

##### `pm-reviewed`（执行层可实现）

按以下步骤顺序执行：

**Step -1 — role 字段大小写 normalize（2026-05-25 加 / Issue #11 KR-FB-002）**

CLAUDE.md `role:` 字段在 Step 1~6 多处用于 label 拼接（`[role]-in-progress` / `[role]-confirmed` 等）。labels.yml 定义的 state labels **全部 lowercase**（`be-in-progress` / `fe-confirmed` 等）。若 `role: BE`（大写）则拼出 `BE-in-progress` 在 `gh issue edit --add-label` 时失败（label 不存在）。

进入 Step 0 前**必须** normalize role:

```bash
# 从 CLAUDE.md 读 role 后立即 lowercase
role=$(echo "$role" | tr '[:upper:]' '[:lower:]')
```

**约束:** CLAUDE.md.template 已示例 `role: be`（lowercase）+ 加注释"必须 lowercase / 对齐 labels.yml"。如 role 仍出现大写 → 强制 normalize 后用 / 不报错。

**Step 0 — 在 Issue 贴执行清单 comment（硬性前置，不得跳过）**

用户确认方案后，**第一个动作**是在 Issue 贴一条清单 comment，作为本次执行的唯一追踪源：

```markdown
## 执行清单（[role]）

- [ ] 标 `[role]-in-progress` + comment "开始实现"
- [ ] 文档先行（标记待实现，同步共享仓库）
- [ ] Step 3.5 — 测试计划（产出物级 / 测试骨架 FAIL 锁定 / dogfood）
- [ ] 实现
- [ ] 编译门禁（项目 CLAUDE.md 指定的 compile_cmd）
- [ ] 测试
- [ ] 6a — 模块文档 / api-spec / 追溯链更新，同步共享仓库
- [ ] 6b — problem-registry 同步
- [ ] 6b — Issue comment（commit hash + 文档链接 + 摘要）
- [ ] 6b — label **保持 `[role]-in-progress`**（不在收尾时切），注明 "工作完成 — 等 /release 发版"
- [ ] 6b — 等 `/release` 发版成功后由 release skill 批量切 `[role]-in-progress` → `[role]-confirmed` + comment 嵌入「可关闭」
```

贴出后**每完成一步立即更新对应 checkbox**（`[ ]` → `[x]`）。清单是执行的唯一追踪源，不靠记忆。

1. **标 `[role]-in-progress`（硬门禁）**
   - 0a. 执行 `gh issue view <N> --json labels` 验证含 `[role]-in-progress` label
   - 0b. 无则立即补：`gh issue edit <N> --add-label [role]-in-progress` + comment "开始实现"（不填 ETA）
   - 0c. **未通过禁止进入 Step 2** —— 这是机器化门禁，不是建议
   - 背景：纯文字约束在违规率高的环境下需机器化校验
2. **文档先行** — 判断是否触发 ADR（架构调整 / 技术选型 / 明显取舍）；更新 / 创建相关文档，标记"待实现"，同步共享仓库并推送

   **文档先行豁免规则（2026-05-25 加 / Issue #11 KR-FB-003）:** 满足**全部**条件可豁免，需在 comment 明示理由 + 字段:
   - S 级改动（Step 0 自检表分级为 S）
   - 项目处 bootstrap / 早期阶段 / 尚无 spec / api / 共识文档可对齐
   - Issue body 自含 SSOT（背景 + 验收条件齐备 / 不依赖外部文档）
   - 不触发 ADR

   豁免 comment **必填字段:**
   - "**文档先行豁免**" 显式关键词（audit 维度 3 #14 识别用）
   - 豁免理由（具体条件命中：S 级 / bootstrap / Issue body SSOT / 非 ADR 触发）
   - 项目当前阶段（bootstrap / active / mature）
   - 后置承诺（项目 active 后补建文档时的追溯锚点 — 如"待项目 active phase 补建 spec 时回填本 Issue 验收依据"）

3. **实现** — 确认分支状态（工作区干净、基准分支正确）；实现代码 / 文档改动；遵循 `rules/core/research-first.md` 和 `rules/core/incremental-verification.md`

   **commit message 关键词禁用清单（硬门禁 / 2026-05-25 加 / Issue #11 KR-FB-005）:**

   GitHub 默认行为:含以下关键词 + `#N` 的 commit push 到 default branch 时 **auto-close** issue #N。agent 写出 `closes #N` → push → GitHub 替 agent 关 issue = **agent 间接 close** / 违反 SKILL.md 约束(`closed` 只由人工触发)。

   ❌ **禁用** commit message 含(case-insensitive):
   ```
   closes / close / closed / closing
   fixes / fix / fixed / fixing
   resolves / resolve / resolved / resolving
   ```

   ✅ **推荐** commit message 引用 Issue:
   ```
   <type>: <subject>

   refs #<N>    # 或 related #<N> / see #<N> / cf #<N>
   ```

   **真实影响:** auto-close 会让 `/release` Step 6.3 (V2 算法 list `--state open`)扑空 / `[role]-confirmed` label 切换跳过 / 需 `gh issue reopen <N>` 恢复 / 与 `/release` 核心承诺("`[role]-confirmed` 由 release 切")矛盾。

   **机器化辅助(可选 / 推荐):** install/modules/05-core-hooks.sh 可注入 commit-msg hook 拦截 auto-close 关键词 + #N 引用组合。

4. **编译门禁（硬门禁）** — 跑 `<compile_cmd>`（项目 CLAUDE.md 指定），失败 → 修 → retry（max 2 次），仍失败 → 停下来上报用户
5. **测试** — 按改动类型执行最低测试要求
6. **收尾 6a** —
   - 更新文档状态为"已实现"，同步共享仓库并推送
   - 更新模块清单追溯链：补充本次新增 / 变更的 API、数据模型、ADR、Issue 关联
7. **收尾 6b** —
   - 同步 problem-registry（如有对应 P-xxx 条目，更新状态为 resolved）
   - **needs-pm-queue 状态同步**（如 Issue 曾入 Open 段）
   - 写 Issue comment（commit hash + 共享仓库文档链接 + 摘要）
   - **文档同步声明强制三选一**（防止 50% 缺失率）：
     - [ ] 列出每份已更新文档的 commit hash
     - [ ] 显式标 "无需更新（原因：<具体原因>）"
     - [ ] 标 "延后处理（追加 Issue ref：#NNN）"
     - **三选一缺失 = 收尾未完成**（不能切 confirmed 状态）
   - **commit hash 格式**：用 `` commit: `<hash>` `` 格式（前缀 `commit:` + 反引号包裹），机器可解析，供 `/release` 反查是否已部署
     - ✅ 正确：`` commit: `9818485` ``
     - ❌ 错误：heredoc 内 `commit: \\\`9818485\\\``（反斜杠转义后落库变字面量，regex 不命中）
     - 写法守则：heredoc / shell 字符串内**不要给反引号加反斜杠**。如有 shell 解析顾虑，用 `gh issue comment <N> --body-file <path>` 改走外部文件
   - **commit hash 动态捕获 + 占位禁止（硬门禁 / 2026-05-25 加 / Issue #8）**：
     - **必须**先 commit + push 拿到真实 hash / 再捕获 / 再贴 comment：
       ```bash
       # 1) 先 commit + push（不在此步嵌 hash）
       git commit -m "<message>"
       git push origin <branch>

       # 2) 捕获真实 hash（commit 完成后）
       ACTUAL_HASH=$(git rev-parse --short HEAD)

       # 3) 用变量插入 comment（heredoc 中用 ${ACTUAL_HASH}）
       gh issue comment <N> --body "$(cat <<INNER
       ...
       commit: \`${ACTUAL_HASH}\`
       ...
       INNER
       )"
       ```
     - **明文禁止：** comment 草稿预写占位 hash（如 `commit: \`a1b2c3d\`` / `commit: \`TODO\`` / `commit: \`<hash>\``）— 占位忘改 = 错误 hash 永久落库 = audit / `/release` 反查拿到无效 hash
     - **背景判据：** commit hash 是 commit 完成后才确定 / chicken-and-egg（comment 引用 commit / commit message 又可引用 Issue #）/ 唯一安全顺序 = commit → 捕获 → comment
     - **可选(self-check 升级)：** comment 前可加 `git cat-file -e ${ACTUAL_HASH} || { echo "hash invalid"; exit 1; }` 双保险存在性校验
     - **amend 场景：** commit 未 push 前发现 hash 错可 amend / 已 push 后**偏好新 commit**（与 standard 整体偏好一致 / 不 force push）
   - **comment 落库后自检（强制）**：写 comment 后立即 grep 验证可识别：
     ```bash
     gh issue view <N> --comments | grep -oE 'commit:\s*`[a-f0-9]{7,40}`'
     ```
     命中 = 合规（≥ 1 行输出）；空输出 = 格式不合规，**立即重写 comment**
   - **label 保持 `[role]-in-progress` 不变**（不在收尾时切；由 `/release` 发版成功后批量切 `[role]-confirmed`）
   - 注明 "工作完成 — 等 /release 发版"（6a 全部完成 + 三选一已填后；「可关闭」由 /release Step 6b.1 切 label 时同步嵌入）

   - **closed issue ↔ commit/release 关联 4 字段（硬约束 / 2026-05-25 加 / Issue close-association 范式 v0 §3.5）**:

     **适用:** Standard 项目无 deploy 概念但 closed issue 仍需可追溯 → Close comment **必含 4 字段**(D self-contained 快照层)+ CHANGELOG/release-log `[Unreleased]` 段累积(E 聚合层 SemVer)。

     **流程(close 前硬门禁):**

     1. **commit hash 列表** — 每改动文件对应 commit short hash(跨仓标 `code@<hash>` / `docs@<hash>`)
     2. **CHANGELOG entry** — 在 `code/CHANGELOG.md` `[Unreleased]` § Changed / Added / Fixed 段 append entry "YYYY-MM-DD — <总结> (#<N>) / commit: <hash>"
     3. **release-log entry** — 若涉及设计层(ADR / concept / overview)→ 在 `docs/docs/release-log.md` `[Unreleased]` 段 append / **若无设计层改动 → 显式标"不涉及"**(不能省略字段)
     4. **关联 artifact** — ADR / FB / 关联 issue / handoff 列出 / 无显式标"无关联"

     **helper 命令(可选 / 提示 EL 填):**

     ```bash
     # 1) 查最近 commit
     git log --oneline -- <file> | head -3

     # 2) grep CHANGELOG 当前 Unreleased entry
     sed -n '/^## \[Unreleased\]/,/^## \[/p' code/CHANGELOG.md | head -30

     # 3) grep release-log 当前 Unreleased entry
     sed -n '/^## \[Unreleased\]/,/^## \[/p' docs/docs/release-log.md | head -30
     ```

     **硬门禁:** 4 字段任一未填 / **不允许 close issue**。`closed` 由人工触发(agent 不主动 close)/ comment 中注明「可关闭」时必含 4 字段。

     **反模式:**

     - ❌ "下次发版补 CHANGELOG"(deferred 写不算合规)
     - ❌ release-log 字段省略不写(必须显式标"不涉及" / 不能空)
     - ❌ 多 commit 只列其中 1 个(必须全列 / 跨仓也要)
     - ❌ 关联 artifact 字段省略(必须显式标"无关联")

##### `cross-role-handoff`(S2 / 部分修 → 转 FE / 或反向 FE → BE 等 / 2026-05-20 加 / F-3 follow-up)

按 S2 场景处理跨端协作:

1. **完成本端修复**(确保 BE 端可独立工作 / commit + push)
2. **comment 含 S2 模板**(引用 `docs/concepts/platform-mapping-github-issue.md` §3.3 / `docs/concepts/platform-mapping-tapd-bug.md` §3.4):
   - BE 完成范围 + commit hash
   - FE 接手边界(具体什么 / 哪些接口已就绪 / 哪些约束)
   - 接口契约变更(如有 / 含兼容性说明)
   - 文档同步三选一
3. **字段操作:**
   - **GitHub:** label 加 `needs-fe`(对称 `needs-pm`)+ `assignee` 转 FE 负责人 / `[role]-in-progress` 保持(反映 BE 端完成 + FE 待接手)
   - **TAPD:** `current_owner` 单值替换为 FE Dev / `v_status` 不变(参考 `protocols/tapd-bug-operations.md` IC-3 替换模式)
4. **显式 @ 下游**(comment 含 `@<FE-user>` 请按 FE 接手边界继续 / TAPD 用 `@{中文名}(FE)` 文字标识)
5. **不切 in-progress / confirmed**(state 保持开启 / 反映"BE 完成本端 + FE 待接手"协作中状态)

##### 纯文档类(含 S5 判定不需修场景 / 2026-05-20 显式标注 / F-4 follow-up)

适用以下 2 种场景:
- **纯文档变更**(updates to docs only / 无代码改动)
- **S5 判定不需修**(BE 评估 issue 后认定非 bug / 不修 / 走此路径写 comment + 切 confirmed)

1. 更新文档 + 同步共享仓库(仅纯文档场景 / S5 不需要)
2. 更新模块清单追溯链(如影响模块关联产物 / S5 通常不影响)
3. 同步 problem-registry(如有对应 P-xxx 条目 / **S5 必填**:在 comment 显式标"是否记入 problem-registry"二选一)
4. 写 comment + 更新 label → `[role]-confirmed` + comment 嵌入「可关闭」
   - **S5 comment 必含**:判定理由(非 bug / 重复 / 不修原因)+ §3.7 S5 模板所有字段(引用 platform-mapping-github-issue.md / platform-mapping-tapd-bug.md)

---

## Stage Gate × 3 (G1 / G2 / G3) — feature 级消费方门禁(dogfood)

> **Status: dogfood (2026-05-26 起 / #17 接纳).** 详 [`rules/core/stage-gate.md`](../../../rules/core/stage-gate.md)。**G4 测试骨架 Gate 由下方 §Step 3.5 覆盖**。dogfood 期 LMP L 必走 / M 推荐 / S 豁免。跨家族 ≥ 2 项目实证后升 active。

**位置:** 介于 spec-to-code-flow 节点切换之间(feature 级,非 Issue 级)。`/issue` 触达单 Issue 时,若该 Issue 属于 feature 级开发流程,本 skill 须先确认上游 Gate 已 PASS。

| Gate | 触发位置 | 消费方动作 | 产出物 | 用户确认 |
|---|---|---|---|---|
| **G1 — 理解** | 共识文档 → 模块清单 之后 | 阅读共识文档 / 形成 AI 理解清单 / 用户确认 | AI 理解清单(复述 + 推断项)| `gh issue comment` "G1 PASS" + stage-state 记录 |
| **G2 — 架构** | 模块清单 → 架构 之后 | 阅读模块清单 / 形成架构视图 + 用例切片 / 用户确认 | 架构视图 + 用例切片 | 同上 "G2 PASS" |
| **G3 — 计划** | 架构 → 接口/数据模型 + 测试计划 之后 | 阅读架构 + AC / 形成依赖图 + AC 映射 + 风险标注 / 用户确认 | 用例依赖图 + AC 映射 + 风险标注 | 同上 "G3 PASS"(G3 之后立即触发下方 §Step 3.5 测试骨架生成 = G4)|

**Gate 顺序约束(硬):** G1 → G2 → G3 → G4(Step 3.5 骨架生成)→ /issue 主体(实现)。前一 Gate 未 PASS 不允许进下一 Gate。

**rule 对偶:** 本段是 [`rules/core/stage-gate.md`](../../../rules/core/stage-gate.md) 的 SKILL 落地。rule 定义"为什么 / 是什么 / 约束 / 风险点 v1 OPEN",SKILL 定义"怎么在 /issue 流程中执行"。

---

## Step 3.5 — 测试计划(产出物级)— dogfood

> **Status: dogfood (2026-05-26 起 / #15 接纳).** 详 [`rules/core/test-skeleton-lock.md`](../../../rules/core/test-skeleton-lock.md)。dogfood 期 LMP L 必走 / M 推荐 / S 豁免(详 rule §风险 15.1)。跨家族 ≥ 2 项目实证后升 active。

**位置:** 在 §执行清单 #2(文档先行)之后、#3(实现)之前触发。

**产出物:** 测试骨架文件集 + 覆盖率映射表

3.5.1 从本 Issue 的 AC 清单生成测试块(每 AC 一个,断言全 FAIL)
3.5.2 生成覆盖率映射表(AC ID ↔ 骨架文件 ↔ 测试块 ↔ 状态)
3.5.3 git commit 锁定(基线建立)
3.5.4 硬门禁:进入 Step 4(实现)前 git status 必须 clean;Step 4 完成时 `git diff <pre-implementation-commit> -- <skeleton-files>` 不能有命中

**rule 对偶:** 本 Step 是 [`rules/core/test-skeleton-lock.md`](../../../rules/core/test-skeleton-lock.md) 的 SKILL 落地。rule 定义"为什么 / 是什么 / 约束",SKILL 定义"怎么执行"。

---

## 约束

- 每一步完成后再进入下一步，不跳步
- Issue comment 中文档链接指向**共享文档仓库**，不使用代码仓库路径
- `closed` 只由人工触发，agent 不主动 close，完成后 comment 中注明「可关闭」
- 遵循 `rules/core/large-module.md`：涉及较大改动时先呈现方案，等用户确认
- 遵循 `rules/extension/adr-discipline.md`（按需启用）：架构级决策在编码前生成 ADR

---

## TAPD 平台分支(2026-05-20 加 / `issue_platform: tapd` 时走此路径)

### 平台分支总览

| 路径 | GitHub Issue(现行) | TAPD Bug(新加) |
|---|---|---|
| 拉取 issue | `gh issue view <N> --comments` | `tapd:get_bug` + comment 历史(workspace_id 必带)|
| Step 0 自检表 | 共用(平台无关 / S 场景判定 + LMP / 见上)| 共用 |
| 字段操作 | `gh issue edit` + label / assignee | `tapd:update_bug`(v_status + current_owner 双字段铁律)|
| 收尾 comment | markdown 格式 | TAPD 富文本(简化 / 详见 `docs/concepts/platform-mapping-tapd-bug.md` §三.1 格式差异表)|
| `/release` 联动切 `[role]-confirmed` | ✅(GitHub label)| ❌(TAPD 状态机不切 confirmed / Dev 最远到`待测试`/ 由 QA 接手) |

### TAPD 路径阶段二(对应现行 §阶段二)

进入实施前 / 已通过 Step 0 自检表 + 场景判定(S1-S5):

**Step 0 — TAPD MCP 调用强制前置(get_bug)**

任何 `update_bug` 之前 **must** 先 `get_bug` 读现状(`current_owner` / `reporter` / `fixer`):

```
tapd:get_bug
  workspace_id: "{tapd_workspace_id}"
  options:
    id: "{bug_id}"
    fields: "id,status,current_owner,reporter,fixer"
```

详见 `protocols/tapd-bug-operations.md` IC-2。

**Step 1 — 按场景执行字段操作 + comment**

按 `rules/core/issue-handling.md` §二.2 判定的场景,**comment 先,字段操作后**(COMMENT FIRST 铁律):

| 场景 | comment 模板 | 字段操作 | current_owner 模式 |
|---|---|---|---|
| S1 修完→QA | `platform-mapping-tapd-bug.md` §三.3 | `v_status: 待测试` + `current_owner` 追加 reporter | 追加(分号) |
| S2 部分修→FE | §三.4 | v_status 不变 + current_owner → FE Dev | 替换 |
| S3 修前需 PM | §三.5 | v_status 不变 + current_owner → PM | 替换 |
| S4 部分修后 PM | §三.6 | v_status 不变 + current_owner → PM | 替换 |
| S5 不需修→QA | §三.7 | `v_status: 待测试` + current_owner 追加 reporter | 追加(同 S1 / 区别在 comment 内容) |

**Step 2 — 7 硬约束 self-check**

`update_bug` 调用前后必跑(见 `protocols/tapd-bug-operations.md` §二):

- [ ] IC-1 双字段同时传(v_status + current_owner)/ 例外:只改 owner 时 comment 说明
- [ ] IC-2 `get_bug` 已前置
- [ ] IC-3 `current_owner` 追加 vs 替换正确(对照场景表)
- [ ] IC-4 Dev 不传 v_status ∈ {测试中 / 测试完成 / 已上线 / 已关闭}
- [ ] IC-5 不把 API 返回 `status: resolved` 解读为"已解决"
- [ ] IC-6 字段改动配 comment(已在 Step 1 / 但收尾再 verify)
- [ ] IC-7 工时填(仅 S1 / S5 / 推到`待测试`时 / 走 `protocols/tapd-worktime-integration.md`)

**Step 3 — TAPD 收尾(6a / 6b)**

- 6a — 同 GitHub 路径(模块文档 / api-spec / 追溯链 / 同步共享仓库)
- 6b — TAPD comment 含 commit hash + 文档链接 / 字段改动留痕完成(IC-6)/ **无 `[role]-confirmed` 切换概念**(TAPD 走自己的 v_status / 不复制 GitHub label 体系)
- 6b — 不主动关闭 Bug(Dev 铁律 / 关闭归 QA / PO)/ comment 写"工作完成 → 等 QA 验证"

### 平台中性化补丁:label 体系(GitHub 侧 / TAPD 不适用)

`rules/core/issue-handling.md` §二 5 场景在 GitHub 上需要扩展 label 体系覆盖 S2:

| label(GitHub 侧新增 / 待落地)| 用途 |
|---|---|
| `needs-fe` | S2 转 FE 标记(对称现有 `needs-pm`) |
| `needs-be` | 反向 / FE 转 BE 标记 |
| `needs-qa` | S1 / S5 推 QA 的辅助标记(可选 / 不强求) |

**当前状态:** label 仅在 SKILL.md / rule 描述层落地,**GitHub repo labels.yml 配置同步留后续**(`/install` skill 升级时同步 + 涉及 GitHub repo admin 操作)。

### 跨平台 comment 内容等价性

同一 Bug 在 GitHub Issue 和 TAPD Bug 上分别有 ticket 时:

- comment 内容(§3.1 4 字段)**must** 跨平台等价(只有格式差异)
- 平台字段表达可以不同(label vs v_status / assignee vs current_owner)
- comment 是事实底料 / 平台字段是镜像(Layer 1 核心洞察)

---

## 与新规约的关系(2026-05-20 加)

| 关联 | 关系 |
|---|---|
| Layer 1 `docs/concepts/issue-handoff-flow.md` | 5 场景概念层 / 本 skill 是其平台落地 |
| Layer 2 `docs/concepts/platform-mapping-github-issue.md` | GitHub 字段映射 / comment 模板源 |
| Layer 2 `docs/concepts/platform-mapping-tapd-bug.md` | TAPD 字段映射 / comment 模板源 |
| `rules/core/issue-handling.md` | 5 场景纪律(Iron Law + Red Flags + 借口对照)/ 本 skill 是其执行层落地 |
| `protocols/tapd-bug-operations.md` | TAPD 字段层 7 硬约束 / 本 skill TAPD 分支段直接引用 |
| `protocols/tapd-worktime-integration.md` | TAPD 工时集成 / 本 skill IC-7 引用工时填写时点 |
| **PM 规范 SSOT** `docs/requirements/2026-05-20-tapd-bug-handoff-flow/source/pm-tapd-ticket-spec-v1.5.md` | TAPD 字段规范权威源 / 通过 Layer 2 文档间接引用 |

---

## 与协议层的关系

参考 `protocols/issue-process.md` —— 本 skill 是 issue-process 协议的执行层 skill。状态机定义 / 5 维度审查由 protocol 描述，本 skill 实施 PDCA。

参考 `protocols/tapd-bug-operations.md` —— TAPD 平台分支段直接引用其 7 硬约束。
