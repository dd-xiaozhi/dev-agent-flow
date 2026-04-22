# <<PROJECT_NAME>> — 项目特定规范索引

> Agent 读这里获取整体结构，按需 Read 子文件。**这是规范的唯一入口**。
>
> 本项目技术栈：<<TECH_STACK>>

## 规范目录树

```
.chatlabs/knowledge/
├── backend/                    — 后端规范（<<TECH_STACK>>）
│   └── coding-style.md         编码风格、注释纪律、命名约定
├── frontend/                   — 前端规范（纯后端项目可删除此目录）
│   └── coding-style.md         前端编码风格、组件组织
├── product/                    — 产品规范
│   └── domain-terminology.md   领域术语表
└── contract/                   — 契约规范（补充 docs/contract-template.md）
    └── design-principles.md    契约设计原则
```

> **维护规则**：新增规范文件必须同步在上方树中加一行说明；目录树永远在本文件顶部。

## Consumer 映射（agent/skill 按角色读取）

| Agent / Skill  | 主要读取                           |
|----------------|----------------------------------|
| doc-librarian  | `contract/**`、`product/**`       |
| planner        | 全部（技术规划需全局）               |
| generator      | `backend/**`、`frontend/**`（按语言）|
| evaluator      | `contract/**`                     |
| fitness-run    | `<module>/fitness-rules.md`       |

## 使用模式（渐进式披露）

Agent 的标准读法：
1. **第一步**：Read `.chatlabs/knowledge/INDEX.md`（本文件）获取目录结构。
2. **第二步**：按 Consumer 映射 + 当前任务上下文，只 Read 相关模块的具体规范。
3. **禁止**：硬编码 `.chatlabs/knowledge/<module>/<file>.md` 路径，必须从本文件的目录树解析。

## 关联

- Flow 元规范（跨项目通用）：`.claude/docs/team-workflow.md`、`.claude/docs/task-directory-convention.md`
- 契约模板（跨项目通用）：`.claude/docs/contract-template.md`
- 技术债存储：`.claude/docs/tech-debt-backlog.md`
