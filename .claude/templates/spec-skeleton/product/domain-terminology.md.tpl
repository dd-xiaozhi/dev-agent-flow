---
name: product-domain-terminology
description: 领域术语表。doc-librarian 在起草契约时需 Read 本文件保持术语一致。
---

# <<PROJECT_NAME>> 领域术语表

> 术语一致是跨端协作的地基。契约、代码、文档、UI 文案在此取齐。

## 使用规则

1. **doc-librarian 起草 contract.md 前**必须 Read 本文件，术语不一致要 ping 产品。
2. **新术语**：先在此登记，再出现在契约 / 代码 / UI 中。
3. **废弃术语**：标 `[DEPRECATED]` 保留一版，下次发布移除。

## 术语表

TBD: 请产品 / 业务填写。格式示例：

| 术语（中文） | 英文 / 代码标识     | 定义                            | 别名 / 禁用表达      |
|------------|-------------------|--------------------------------|-------------------|
| 订单        | `Order`            | 用户下单后形成的交易单据          | ❌ "单子"、"交易" |
| 脚本        | `Script`           | 用户创建的可执行 Groovy 代码片段   | ❌ "程序"、"代码片段" |
| 执行        | `Execution`        | 脚本的一次运行实例                | ❌ "跑"、"运行" |
| ...        | ...                | ...                            | ...                |

## 缩略语

TBD: 项目内使用的缩略语：

- `SLA` — Service Level Agreement
- `RBAC` — Role-Based Access Control
- ...

## 关联

- 契约模板：`docs/contract-template.md`
- 契约设计原则：`contract/design-principles.md`
