# Case 任务 md 模板

> 本模板供 **planner** 填充，每个 case 一个文件，置于 `.chatlabs/stories/<story-id>/cases/NNN-<slug>.md`。
>
> **设计原则**：
> 1. **不复述契约内容**（用 `links` 指回 contract.md / openapi.yaml）
> 2. **验收标准必须引用 AC-NNN**（便于 Evaluator 自动映射测试覆盖）
> 3. **禁止事项**防止 Generator 过度发挥
> 4. **`kind: feature` case 必须原子**（单一模块、单一职责、可独立测试）；`kind: setup` 仅用于搭骨架，每个 story 至多 1 个

---

## 模板

```markdown
---
case_id: STORY-XXX/CASE-NN       # 格式严格：Story ID / CASE-两位数
story_id: STORY-XXX
title: 一句话目标（≤20 字，勿加项目/角色前缀，前缀在派发时自动注入）
kind: feature                     # feature | setup（详见下方"kind 分类"）
type: backend                     # backend | frontend | infra | doc
phase: pending                    # pending | in_progress | done
blocked_by: []                    # 依赖的其他 case_id
acceptance_criteria:              # 引用 contract.md 中的 AC 编号
  - AC-001
  - AC-002
affected_files:                   # 必填:本 case 预计影响的文件路径(estimator 工时估算依据)
  primary:                        # 主责文件:工时全归属本 case
    - src/main/java/com/chatlabs/xxx/XxxController.java
    - src/test/java/com/chatlabs/xxx/XxxControllerTest.java
  touched:                        # 仅小幅修改:工时按本 case 实际 diff 行数实算,不参与共享分摊
    - src/main/java/com/chatlabs/xxx/XxxService.java
links:
  contract: ../contract.md#section-2
  openapi: ../openapi.yaml#/paths/~1api~1v1~1xxx/post
  adr: null                       # 若有架构决策记录
# estimate_hours: 1.5             # 可选;不写则由 estimator 自动估算,需人工覆盖时手动添加此字段
---

# 目标

<!-- ≤20 字的原子目标，例如： -->
实现 POST /api/v1/xxx 创建端点，含基本校验和持久化。

# 验收标准

<!-- 每条 AC 引用 contract.md 中的 AC-NNN，Generator 产出的测试必须带 `// covers: AC-NNN` 注释 -->

- [ ] **AC-001**（见 contract.md §5#AC-001）
  - 测试描述：POST 合法 body → 201 + 响应符合 schema + DB 有记录 `status=pending`
- [ ] **AC-002**（见 contract.md §5#AC-002）
  - 测试描述：POST 重复 name → 409 + 错误码 `ERR_NAME_DUPLICATED`

# 上下文指针

<!-- 不复述内容，只指向源头，避免上下文污染 -->

- **契约**：`contract.md` §2 数据模型 / §3 接口概览 / §5 AC-001, AC-002
- **接口定义**：`openapi.yaml` `/api/v1/xxx` POST 操作
- **状态机**：`contract.md` §4.1（本 case 只关心 `[*] → pending` 这条边）
- **代码位置**：`src/main/java/com/chatlabs/xxx/`（Planner 指定，Generator 遵循）
- **相关 ADR**：无（或指向 `docs/adr/ADR-017-state-machine.md`）

# 禁止事项

<!-- 防止 Generator 过度发挥，每个 case 都要明确 -->

- ❌ **不修改** `openapi.yaml` 中的字段命名（跨端契约）
- ❌ **不实现** 本 case 之外的 AC（即使相关，也交给其他 case）
- ❌ **不引入** 本 case 未在 `links` 中指向的外部依赖
- ❌ **不跳过** 单元测试，不用 mock 覆盖 AC（AC 必须由契约测试验证）
- ❌ **不修改** 测试骨架锁定后的测试结构（骨架锁定后只能改实现）

# 实现提示（可选）

<!-- Planner 在架构设计时留下的提示，Generator 参考但不必严格遵守 -->

- 推荐复用 `xxx-service` 中的已有 `XxxValidator`
- 数据库操作走 `XxxRepository`（参考 `yyy-service` 的模式）

# 变更历史

<!-- case 创建后若有重要变更（如被反馈影响），追加记录 -->

- 2026-04-19：初始创建（Planner）
<!-- - 2026-04-20：因 contract v0.2 变更，重新规划（Planner） -->
```

---

## 字段详解

### `case_id` 命名规则（严格）

格式：`<STORY-ID>/CASE-<NN>`，例如：`STORY-123/CASE-01`。

- Story ID 与契约文档 `story_id` 一致
- CASE 编号**两位数**，从 01 开始递增
- 编号一旦分配**不可重用**（即使 case 被删除）

### `phase` 状态机

```
pending ──▶ in_progress ──▶ done
                  ▲             │
                  └─── reopen ───┘   (QA 打回时 done → in_progress)
```

- **pending**：已创建但未开始（Planner 拆完 case 的初始状态）
- **in_progress**：Generator 实现中 / Evaluator 验收中
- **done**：Evaluator verdict = PASS，且（接入 TAPD 时）subtask 已推到"待测试"

phase 由 agent / skill 隐式推进，Planner 写完 case 后**不要手填中间态**。
QA 打回（`/tapd-subtask-reopen`）会把 phase 从 `done` 拉回 `in_progress`。

### `blocked_by` 依赖规则

- 只能依赖**同 story 内**的 case，不允许跨 story 依赖
- Planner 初始化时填充，Generator 不得修改
- 依赖关系不能形成环（生成时会校验）

### `acceptance_criteria` AC 编号

- 必须引用 `contract.md` 中已存在的 AC 编号
- 多个 AC 可以属于同一个 case，但一个 AC 原则上只属于一个 case（便于定位责任）
- 例外：跨模块的 AC（如"所有接口必须返回标准错误格式"），可在多个 case 中引用，但其中一个 case 为"主责"

### `kind` 分类（必填）

| 取值 | 含义 | 是否强制原子 | acceptance_criteria |
|------|------|-------------|---------------------|
| `feature` | 增量功能 case，对应一组 AC | 是（单模块单职责） | 必填，至少 1 个 AC |
| `setup` | 框架搭建 case，为后续 feature case 立骨架（DTO/接口/工厂/控制器空壳） | 否（可包含整套骨架） | 必填，引用首个被支撑的 AC |

**拆 case 准则**：

- 同一 story **最多 1 个 setup case**，编号通常为 `CASE-01`
- 如果一个 case 不能独立跑通（必须依赖其他文件先建起来），是 setup 信号
- setup case 的 affected_files.primary 可以列 10+ 文件，但只能放"骨架级修改"（接口定义、空实现、DTO/VO）；具体业务逻辑必须留给 feature case
- 后续 feature case **禁止重复声明** setup 已建好的文件为 primary，可放 touched

### `affected_files` 影响文件映射（必填）

Planner 在拆 case 时**必须**填写本 case 预计影响的代码文件路径，分为 `primary` 和 `touched` 两类。这是部署后 `/tapd-subtask-emit` 调 estimator 估算工时的依据。

**`primary`（主责文件）**：本 case 主责实现，工时**全部归属本 case**。
- 包含本 case 新增的产出文件 + 对应单测文件
- 同一文件**最多只能在一个 case 的 primary 里出现**（避免工时重复计算）

**`touched`（顺手修改文件）**：本 case 仅做小幅修改的既有/共享文件，工时按**本 case 实际 diff 行数**实算，不参与共享分摊。
- 跨 case 共享的文件（如 ServiceImpl 被多个 case touched）放这里
- estimator 用 git blame / hunk 边界识别本 case 的实际增量

**填写规则**：

- 路径相对于仓库根（如 `src/main/java/.../XxxController.java`）
- `primary` 不能为空数组（至少 1 个文件）
- 拆 case 时还不确定路径？→ 先按现有架构规范预测；Generator 实现后 Planner 不再回填（估算误差由 estimator 调整因子吸收）

**反例**：
```yaml
affected_files:
  primary: []                     # ❌ 空数组等于放弃工时估算
  touched: [...]
affected_files:
  primary: ["src/"]               # ❌ 目录路径无法 diff
affected_files:
  - src/.../XxxController.java    # ❌ 老式平铺格式,不再支持
```

---

## 目录结构示例

```
.chatlabs/stories/STORY-123/
├── contract.md            # doc-librarian 产出
├── openapi.yaml           # doc-librarian 产出
├── changelog.md           # doc-librarian 维护
├── state.json             # Planner 初始化（第 2 期引入）
├── spec.md                # Planner 产出
└── cases/
    ├── CASE-01-create-xxx.md      # Planner 产出
    ├── CASE-02-query-xxx.md
    └── CASE-03-change-status.md
```

---

## 填写检查清单（Planner 自检）

- [ ] `case_id` 格式正确（`<STORY-ID>/CASE-NN`）
- [ ] `kind` 已声明（feature 或 setup），同一 story 至多 1 个 setup
- [ ] `acceptance_criteria` 中每个 AC 都能在 contract.md 找到
- [ ] **`affected_files.primary` 至少包含 1 个文件路径**（不能是空数组、不能是目录）
- [ ] 同一文件**未在多个 case 的 primary 里重复出现**（共享文件放 touched）
- [ ] `links.contract` 和 `links.openapi` 可访问（不是死链）
- [ ] 禁止事项明确列出（至少 3 条）
- [ ] `blocked_by` 不形成环
- [ ] 目标 ≤20 字
- [ ] 验收标准每条都有"测试描述"
- [ ] 实现提示不越界（不预先决定业务逻辑）

---

## 反模式（Planner 须避免）

### ❌ 反模式 1：在 case 里复述契约

```markdown
# 目标

创建 XXX。XXX 是一种 YYY，它有以下字段：id、name、status、created_at...
```
→ 应该用 `links.contract` 指回 §2 数据模型。

### ❌ 反模式 2：AC 模糊，没有对应编号

```markdown
- [ ] 功能正常
- [ ] 性能达标
```
→ 必须引用 `contract.md` 的 AC-NNN，或要求 doc-librarian 补充 AC。

### ❌ 反模式 3：一个 feature case 塞多个模块

```yaml
kind: feature
title: 实现 XXX 增删改查 + 状态变更 + 审计日志
```
→ 应拆成 3-4 个独立 feature case，每个单一模块。
→ 如果是为了让首条链路跑通而必须搭起整套骨架 → 用 `kind: setup` 显式声明。

### ❌ 反模式 4：禁止事项为空

```markdown
# 禁止事项

<!-- 暂无 -->
```
→ 每个 case 必须有至少 3 条禁止事项，否则 Generator 会过度发挥。

### ❌ 反模式 5：feature case 重复声明 setup 已建文件为 primary

```yaml
# CASE-01 是 setup,primary 已包含 SimplifiedReportApiController.java
# CASE-02 是 feature,又把同一文件放 primary
kind: feature
affected_files:
  primary:
    - .../SimplifiedReportApiController.java   # ❌ 重复,工时被双倍计算
```
→ feature case 在共享文件上做的小修改属于 `touched`，primary 仅放本 case 主责的新增文件。
