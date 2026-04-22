---
name: contract-design-principles
description: 契约设计原则。doc-librarian 起草和修改契约时的决策依据，补充 docs/contract-template.md 的"为什么这么设计"。
---

# 契约设计原则

> `docs/contract-template.md` 讲契约**长什么样**（模板结构）；
> 本文件讲契约**为什么这么设计**（决策原则）。

---

## 一、契约 vs 代码 vs OpenAPI 的职责边界

| 文档           | 回答问题                                 | 谁负责    |
|---------------|----------------------------------------|----------|
| `contract.md`  | 业务做什么、为什么、AC 有哪些              | doc-librarian |
| `openapi.yaml` | 接口怎么调（字段、类型、状态码）             | doc-librarian |
| `spec.md`      | 技术怎么实现（库、架构、部署）               | planner |
| 代码本身       | 具体行为                                 | generator |

**三者必须一致**。contract.md §3（概览）↔ openapi.yaml 端点 ↔ spec.md 实现。

---

## 二、AC 设计原则

1. **编号不可变**：AC-001 一旦分配，永远占这个号。删除标 `[DELETED]` 不删编号（Evaluator 用 AC 编号做测试映射）。
2. **粒度原则**：一条 AC = 一个可测试的行为。"模块 A 正常工作"不可测，"用户登录后 session 有效期 2 小时"可测。
3. **写法**：Given-When-Then 或"当 X，应该 Y，并记录 Z"。
4. **幂等 AC**：`idempotent: true` 标注幂等操作。

---

## 三、版本化纪律

- `status: draft` 阶段允许任意修改，不要求 bump version。
- `status: frozen` 后修改：bump version + 写 changelog + 标注影响范围。
- Semver：breaking → major、add → minor、fix → patch。

---

## 四、禁止替下游决策

doc-librarian **不决定**：
- ❌ 用什么数据库（planner 的事）
- ❌ 分页用 offset 还是 cursor（planner 的事）
- ❌ 缓存 TTL 多少（planner 的事）

**必须写清业务侧精度 / 约束**：
- ✅ "金额字段精度到分，不接受浮点误差"
- ✅ "用户名长度 3-32，允许字母数字下划线"
- ✅ "脚本内容 base64 编码，单次上限 1MB"

---

## 五、TBD 的使用

- 信息不全时写 `[TBD: 请 PM 确认 X，YYYY-MM-DD 前]`
- **禁止臆造**：宁可 TBD 也不编业务规则。
- frozen 前必须清空所有 TBD。

---

## 六、禁止在契约中放代码

- ❌ `implementation: "java.util.HashMap"` → 那是 spec.md 的事
- ✅ `implementation_note: "实现需保证线程安全" → 这是业务约束
- ❌ 写出具体算法 → 那是在 spec.md
- ✅ `temporal_constraint: "AC-003 的执行必须在 AC-002 完成 5 分钟内" → 这是业务时序约束

---

## 关联

- 契约模板（结构说明）：`docs/contract-template.md`
- 领域术语：`product/domain-terminology.md`（若存在）
- 团队工作流：`docs/team-workflow.md`