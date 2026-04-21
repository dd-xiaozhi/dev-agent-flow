---
name: frontend-coding-style
description: 前端编码风格、命名约定、组件组织。所有前端 agent 产出的代码必须遵循。
---

# 前端编码风格

> 技术栈：<<TECH_STACK>>

## 一、注释纪律

同后端：代码自解释，注释只补充 why，不重复 what。

**禁止**：
- 流程管理类（`// Step 1:` / `// CASE-xx:`）
- 人工标记（`// TODO` 写入 `docs/tech-debt-backlog.md`）
- 项目管理类（`@author` / `@since` 等）

**允许**：
- 业务规则（如 `// 防抖 300ms，产品决策`）
- 非常规选型（如 `// useLayoutEffect 避免闪烁`）
- 契约引用、兼容性声明

## 二、命名约定

TBD: 请团队填写。常见模式：

- 组件文件：`PascalCase.tsx`（`UserList.tsx`）
- Hook：`use` 前缀 + `camelCase`（`useAuth`）
- 工具函数：`camelCase`
- 类型 / 接口：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`
- CSS：`kebab-case` 或 CSS Module / styled-components

## 三、组件组织

TBD: 选择并填写：

- [ ] 按功能分目录（`features/auth/` / `features/order/`）
- [ ] 按类型分目录（`components/` / `hooks/` / `pages/`）
- [ ] 混合（顶层按功能，内部按类型）

## 四、状态管理

TBD: 选择本项目的方案：

- [ ] React Context
- [ ] Redux / Redux Toolkit
- [ ] Zustand
- [ ] Jotai / Recoil
- [ ] 其他：

**本地 vs 全局 state 的边界**：TBD

## 五、异步数据

TBD: 选择：

- [ ] React Query / SWR（推荐：声明式缓存）
- [ ] 手写 fetch + useEffect
- [ ] 其他

## 六、执行机制

| 阶段           | 检查点                                      |
|---------------|-------------------------------------------|
| 编码中         | 对照"禁止列表"自检                          |
| Fitness hook  | eslint / 自定义 fitness 规则                |
| Sprint review | 违规入 `docs/tech-debt-backlog.md`          |

## 关联

- 架构检查：`frontend/fitness-rules.md`（若存在）
- 契约：`docs/contract-template.md`
