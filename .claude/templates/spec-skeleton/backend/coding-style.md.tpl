---
name: backend-coding-style
description: 后端编码风格、注释纪律、命名约定。所有后端 agent 产出的代码必须遵循。
---

# 后端编码风格

> **项目**: <<PROJECT_NAME>>
> **技术栈**: <<TECH_STACK>>
> **生成方式**: 从项目源码归纳生成，非模板填充

## 一、注释纪律

### 禁止出现的注释

| 类别         | 示例                                    | 正确做法                          |
|-------------|----------------------------------------|----------------------------------|
| 流程管理类   | `// CASE-02: xxx` / `// Step 1: xxx`    | 删除，流程信息在 `cases/*.md`     |
| 人工标记     | `// TODO` / `// FIXME` / `// HACK`      | 写入 `docs/tech-debt-backlog.md` |
| 项目管理类   | `@author` / `@since` / `@last-modified` | 删除，git log / blame 已记录      |
| 过度自述     | `// 循环处理每个用户`                     | 删除，代码本身即说明              |

### 允许出现的注释

只解释 **why**，不解释 what：

- **业务规则**：`// 折扣上限 20%，财务合规要求`
- **非常规选型**：`// 用 WeakHashMap 允许 GC 回收已完成记录`
- **契约引用**：`// 对应 contract.md §3.2 AC-005`
- **安全/合规**：`// 日志脱敏，PIPL §9`

## 二、命名约定

{{CLASS_NAMING_EXAMPLES: 从 Phase 1.3 扫描结果提取}}

{{METHOD_NAMING_EXAMPLES: 从 Phase 1.3 扫描结果提取}}

## 三、分层 / 包结构

{{DIRECTORY_STRUCTURE: 从 Phase 1 扫描结果提取}}

## 四、错误处理

{{ERROR_HANDLING_EXAMPLES: 从 Phase 1.3 扫描结果提取}}

## 五、测试规范

{{TEST_PATTERNS: 从 Phase 1.3 扫描结果提取}}

## 关联

- 架构文档：`.chatlabs/knowledge/project/architecture.md`
- 领域术语：`.chatlabs/knowledge/product/domain-terminology.md`
- 契约原则：`.chatlabs/knowledge/asset/contract/design-principles.md`
