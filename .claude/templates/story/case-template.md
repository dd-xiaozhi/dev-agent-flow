# Case 任务 md 模板

> 本模板供 **planner** 填充，每个 case 一个文件，置于 `.chatlabs/stories/<story-id>/cases/NNN-<slug>.md`。
>
> **设计原则**：
> 1. **不复述契约内容**（用 `links` 指回 contract.md / openapi.yaml）
> 2. **验收标准必须引用 AC-NNN**（便于 Evaluator 自动映射测试覆盖）
> 3. **禁止事项**防止 Generator 过度发挥
> 4. **每个 case 必须是"原子"的**——单一模块、单一职责、可独立测试

---

## 模板

```markdown
---
case_id: STORY-XXX/CASE-NN       # 格式严格：Story ID / CASE-两位数
story_id: STORY-XXX
title: 一句话目标（≤20 字）
type: backend                     # backend | doc | infra（仅后端流程使用 backend）
phase: pending                    # pending | understand | architect | plan | skeleton | code | integrate | review | done
blocked_by: []                    # 依赖的其他 case_id
gate_required: none               # none | qa-skeleton-sign | architect-confirm
acceptance_criteria:              # 引用 contract.md 中的 AC 编号
  - AC-001
  - AC-002
links:
  contract: ../contract.md#section-2
  openapi: ../openapi.yaml#/paths/~1api~1v1~1xxx/post
  adr: null                       # 若有架构决策记录
estimate_hours: null              # 由 Planner 估计，可留空
created_at: 2026-04-19
updated_at: 2026-04-19
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
pending ──▶ understand ──▶ architect ──▶ plan ──▶ skeleton ──▶ code ──▶ integrate ──▶ review ──▶ done
                                                       │
                                                       └──▶ [骨架锁定 gate]
```

- **pending**：已创建但未开始
- **understand**：Planner 理解中（步骤 1）
- **architect**：Planner 架构设计中（步骤 2）
- **plan**：Planner 实现计划中（步骤 3）
- **skeleton**：Generator 生成测试骨架中（步骤 5，**QA 关卡在此**）
- **code**：Generator 编码中（步骤 6）
- **integrate**：Generator 集成测试中（步骤 7）
- **review**：Evaluator 验收中（步骤 8）
- **done**：完成，verdict = PASS

### `gate_required` 质量关卡

当前 case 推进到某 phase 时需要的人工签字关卡：

- `none`：无需关卡
- `architect-confirm`：Planner 完成架构方案后，需 PM/Tech Lead 签字才能进入 plan
- `qa-skeleton-sign`：Generator 完成骨架后，需 QA 签字才能进入 code
- `pm-confirm-understand`：Planner 完成理解后，需 PM 确认才能进入 architect

关卡未签字前，`gate-enforcer.py` hook（第 3 期提供）会阻断相关文件的 Edit/Write 操作。

### `blocked_by` 依赖规则

- 只能依赖**同 story 内**的 case，不允许跨 story 依赖
- Planner 初始化时填充，Generator 不得修改
- 依赖关系不能形成环（生成时会校验）

### `acceptance_criteria` AC 编号

- 必须引用 `contract.md` 中已存在的 AC 编号
- 多个 AC 可以属于同一个 case，但一个 AC 原则上只属于一个 case（便于定位责任）
- 例外：跨模块的 AC（如"所有接口必须返回标准错误格式"），可在多个 case 中引用，但其中一个 case 为"主责"

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
- [ ] `acceptance_criteria` 中每个 AC 都能在 contract.md 找到
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

### ❌ 反模式 3：一个 case 塞多个模块

```yaml
title: 实现 XXX 增删改查 + 状态变更 + 审计日志
```
→ 应拆成 3-4 个独立 case，每个单一模块。

### ❌ 反模式 4：禁止事项为空

```markdown
# 禁止事项

<!-- 暂无 -->
```
→ 每个 case 必须有至少 3 条禁止事项，否则 Generator 会过度发挥。
