# 经验沉淀 — experience/

> **定位**：本项目特有的踩坑教训永久驻留位。每条经验回答一个问题——"下次遇到类似情况，怎么避免再犯"。
> **写入方**：`sprint-review` skill 自动判定 + 人工补充。
> **读取方**：所有 agent 启动前可按需读取；`sprint-review` 在分析新 blocker 时检索是否已有同类经验。

---

## 与 tech-debt-backlog 的边界

| 类型 | experience/ | docs/tech-debt-backlog.md |
|------|------------|---------------------------|
| 性质 | **已学会**——教训已总结，下次知道怎么做 | **待修复**——明确的工程债务，等待还债 |
| 例子 | "批量 MCP 调用必须分批，避免 TAPD 限流" | "TODO: 实现 flow_advance 的原子 retry" |
| 写完后 | 永久驻留，作为 agent 上下文 | 修完后从 backlog 移除 |
| 关闭条件 | 不关闭（除非证明不再适用） | 实现完成 → 关闭 |

**判断标准**（sprint-review 自动判定时用）：

```
是否模式性教训？
├─ 是 → 写 experience/（永久沉淀）
└─ 否 → 一次性 diff，不沉淀

是否有可操作的还债动作？
├─ 是 → 写 tech-debt-backlog（待修复）
└─ 否 → 不写
```

一条 blocker 可能**同时**产生 experience 和 tech-debt 条目（教训 + 还债动作分离）。

---

## 写入规范

### 文件命名

```
YYYY-MM-<kebab-case-slug>.md
例：
  2026-05-tapd-batch-create-rate-limit.md
  2026-05-flow-advance-idempotency.md
  2026-05-contract-tbd-bypass-via-frontmatter.md
```

按月归档，便于检索趋势。

### 文件骨架

```markdown
---
title: <一句话标题>
created: 2026-05-21
source_task: <task_id>          # 触发本经验的 task
related_blockers: [<blocker_id>] # 关联的 blocker（如有）
severity: high|medium|low        # 教训严重程度
tags: [tapd, flow-engine, ...]   # 检索标签
---

## 现象
（具体发生了什么——错误信息、表现）

## 根因
（为什么会这样——技术原因 + 流程原因）

## 教训
（一句话核心结论——下次怎么办）

## 适用场景
（什么时候这条经验会再次相关）

## 反例 / 边界
（什么时候**不**适用这条经验，避免过度泛化）

## 关联
- experience: [[other-experience-slug]]（如有）
- tech-debt: backlog#<id>（如有还债动作）
```

---

## 维护

- **新增**：sprint-review 自动写 + 人工补充
- **修订**：发现教训过时 → 在文件末尾加 `## 修订` 段，不删除原内容
- **检索**：agent 读取入口 = 本 INDEX.md；按 tag 或时间反查
- **归档**：经验确认不再适用 → 移到 `archive/` 子目录，frontmatter 加 `archived: true`

---

## 当前条目

> 待沉淀。首条经验由下次 `sprint-review` 自动判定产生，或人工手工写入。

| 创建日 | 标题 | severity | 标签 |
|-------|------|---------|------|
| — | — | — | — |
