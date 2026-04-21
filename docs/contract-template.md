# 产品契约文档模板

> 本模板由 **doc-librarian** agent 填充。完成后置于 `.claude/tasks/stories/<story-id>/contract.md`，接口部分单独存为同目录 `openapi.yaml`。
>
> **设计原则**：**字段越少越好，宁缺毋滥**。未明确的部分标 `TBD`，不要臆造。

---

## 使用说明

1. 复制本模板为 `.claude/tasks/stories/<story-id>/contract.md`
2. 按节填写，不确定的部分显式标注 `TBD`
3. `status` 从 `draft` → `review` → `frozen`，`frozen` 后修改必须 bump `version` 并写 `changelog.md`
4. 接口契约详细定义放 `openapi.yaml`，本文件只放概览

---

```markdown
---
story_id: STORY-XXX
title: 一句话描述（≤20 字）
version: 0.1.0
status: draft          # draft | review | frozen
owner_pm: pm@chatlabs.com
owner_backend: backend@chatlabs.com
tapd_story: https://tapd.cn/xxxxx   # 可选
created_at: 2026-04-19
updated_at: 2026-04-19
---

# 1. 页面结构拆解

> 前端消费用。只写有哪些页面、跳转关系。不写样式细节（Figma 有）。

- 页面 A（入口）
  - 触发跳转：XX 操作 → 页面 B
- 页面 B（结果页）
  - 返回入口：XX 操作 → 页面 A

## 跳转关系图（可选）

\`\`\`mermaid
stateDiagram-v2
  [*] --> 页面A
  页面A --> 页面B: 提交
  页面B --> [*]
\`\`\`

---

# 2. 数据模型

> 领域实体、字段、约束。不写存储选型（那是后端 Planner 的事）。

## 2.1 实体：XXX

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| id | string(UUID) | 是 | 主键 | — |
| name | string(64) | 是 | 非空 | — |
| status | enum | 是 | active/inactive/pending | 状态机见 §4.1 |
| created_at | datetime | 是 | ISO8601 | — |

## 2.2 枚举：Status

- `active`：正常
- `inactive`：停用
- `pending`：待审核

---

# 3. 接口契约

> **详细定义见同目录 openapi.yaml**。本节只列端点概览。

| 方法 | 路径 | 用途 | 消费方 |
|------|------|------|--------|
| POST | /api/v1/xxx | 创建 XXX | 前端 |
| GET | /api/v1/xxx/{id} | 查询详情 | 前端 |
| PATCH | /api/v1/xxx/{id}/status | 状态变更 | 前端/内部服务 |

**统一约定**（引用 `docs/api-conventions.md`）：
- 分页：`?page=1&size=20`，最大 size=100
- 时间：ISO8601 UTC，字段后缀 `_at`
- 金额：整数分（人民币），字段后缀 `_cents`
- 错误：`{ "code": "ERR_XXX", "message": "...", "detail": {} }`

---

# 4. 业务规则

## 4.1 状态机

\`\`\`mermaid
stateDiagram-v2
  [*] --> pending: 创建
  pending --> active: 审核通过
  pending --> inactive: 审核拒绝
  active --> inactive: 停用
  inactive --> active: 启用
\`\`\`

**转换规则**：
- `pending → active`：仅 admin 可触发
- `active ↔ inactive`：owner 或 admin 均可
- 其他转换一律拒绝

## 4.2 校验规则

- 创建时 `name` 在租户内唯一
- `status` 变更必须记录操作日志（who/when/from/to）
- 批量查询默认按 `created_at` DESC

## 4.3 数量/频率限制（如有）

- 单租户最多 1000 条
- 单用户每分钟最多创建 10 条

---

# 5. 验收条件

> **每条必须：可测试、可观测、与接口/状态机直接对应**。
> **编号规则：AC-001 起递增，一旦分配不可改**（Evaluator 依赖编号做 AC↔测试映射）。

## AC-001 {#AC-001}
**场景**：创建 XXX 正常路径
**触发**：POST /api/v1/xxx，body 合法
**期望**：
- 返回 201
- 响应体符合 openapi.yaml 中 `XxxCreated` schema
- 数据库中新增一条记录，`status=pending`
**对应接口**：POST /api/v1/xxx
**对应状态转换**：[*] → pending

## AC-002 {#AC-002}
**场景**：创建 XXX 时 name 重复
**触发**：POST /api/v1/xxx，name 已存在
**期望**：
- 返回 409
- 错误码 `ERR_NAME_DUPLICATED`
**对应接口**：POST /api/v1/xxx

## AC-003 {#AC-003}
**场景**：非 admin 尝试 pending→active
**触发**：PATCH /api/v1/xxx/{id}/status，body `{"status":"active"}`，当前用户非 admin
**期望**：
- 返回 403
- 错误码 `ERR_PERMISSION_DENIED`
**对应接口**：PATCH /api/v1/xxx/{id}/status
**对应状态转换**：pending → active（被拒）

<!-- AC 继续追加 -->

---

# 7. 可观测性要求

> **每个端点必须填写**。log/metric/trace 三者中，`log` 和 `trace` 为必填，`metric` 为推荐。
> 不可留空或填 `TBD`——可观测性是契约的强制部分，不是可选部分。

| 接口 | log 必须包含 | metric 指标 | trace 传播字段 | 告警阈值 |
|------|-------------|------------|--------------|---------|
| POST /api/v1/xxx | `action=create`, `entity_id`, `user_id`, `duration_ms` | 请求量 QPS、错误率 5xx | `trace_id`, `span_id`, `user_id` | 5xx 率 > 1% |
| GET /api/v1/xxx/{id} | `action=query`, `entity_id`, `hit/miss` | P99 延迟 | `trace_id`, `span_id` | P99 > 500ms |
| PATCH /api/v1/xxx/{id}/status | `action=status_change`, `entity_id`, `from`, `to`, `operator_id` | 状态变更次数 | `trace_id`, `span_id`, `operator_id` | 异常变更率 > 5% |

**通用约定**：
- 所有接口：`X-Request-ID` 或 `traceparent` header 透传
- 所有写操作（POST/PATCH/DELETE）：写入操作日志表（`xxx_audit_log`），字段：who/when/what/from/to/result
- 错误响应：同时写 error log（`level=ERROR`，包含 `trace_id` 和完整 error detail）
- metric 命名规范：`{service}.{endpoint}.{metric_type}`（如 `chatlabs.user.create.qps`）

<!-- 如有新增端点，在此表追加一行 -->

---

# 附录 A：变更回溯影响范围（由 contract-diff skill 自动写入）

<!-- 示例，当契约冻结后第一次变更开始追加 -->

## v0.2.0 (2026-04-20)
- [BREAKING] AC-001 响应字段 `name` → `display_name`，影响：xxx-service 模块所有测试
- [ADD] 新增 AC-004（状态查询去重）
- 影响范围：**中等**（接口字段变化）
- 回溯指令：
  - 后端：重新分析 → 架构 → 计划 → 骨架
  - 前端：重分析 + 重生成测试骨架 + 重实现受影响页面

<!-- 每次契约冻结后变更都追加一节 -->
```

---

## 填写检查清单

提交 `review` 前 doc-librarian 必须自检：

- [ ] 所有 `TBD` 已澄清或明确标注"需 PM 补充"
- [ ] §7 可观测性表格每行均已填写，无空值
- [ ] AC 编号连续、无跳号
- [ ] 每条 AC 都对应至少一个接口或状态转换
- [ ] openapi.yaml 中的 path 和第 3 节一致
- [ ] 状态机覆盖所有有效转换（非法转换不必画）
- [ ] `updated_at` 已更新
- [ ] 无未解释的术语（首次出现要写全称或加注释）

## 冻结后变更流程

1. `status: frozen` 后，contract.md 修改必须：
   - bump `version`（遵循 semver：breaking→major，add→minor，fix→patch）
   - 追加 `附录 A` 的变更记录
   - 触发 `contract-diff` skill 生成影响范围报告（第 4 期提供）
2. 影响范围判定：
   - **小**：文案/注释修正 → 通知即可
   - **中**：AC 增减、字段变化 → 后端重走"计划 → 骨架"
   - **大**：状态机/核心模型调整 → 后端重走完整九步

## 字段裁剪指南

**禁止添加未证实必要的字段**。以下是本模板为何不含某些字段的原因：

- ❌ 未加"优先级"字段：应由 TAPD Story 本身管理
- ❌ 未加"估时"字段：由 Planner 的实现计划填充
- ❌ 未加"部署环境"字段：由 CI/CD 流水线管理
- ❌ 未加"回归测试项"字段：由 Evaluator 自动生成

如果团队发现这些字段有需要，走"工作流改进"反馈流程（第 4 期），不直接加字段。
