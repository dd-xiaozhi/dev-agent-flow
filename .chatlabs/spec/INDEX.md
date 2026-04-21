# ChatLabs Dev-Flow — 项目特定规范索引

> Agent 读这里获取整体结构，按需 Read 子文件。**这是规范的唯一入口**。
>
> 本项目技术栈：Java 17 + Spring Boot 3.x

## 规范目录树

```
.chatlabs/spec/
├── backend/                    — 后端（Java 17 + Spring Boot 3.x）
│   ├── coding-style.md         Java 编码风格、注释纪律、包结构
│   ├── api-conventions.md      API 响应格式、分页、错误码
│   └── fitness-rules.md        后端架构适应度函数清单
└── contract/                   — 契约（补充 docs/contract-template.md）
    └── design-principles.md    契约设计原则
```

> **维护规则**：新增规范文件必须同步在上方树中加一行说明；目录树永远在本文件顶部。

## Consumer 映射（agent/skill 按角色读取）

| Agent / Skill  | 主要读取                           |
|----------------|----------------------------------|
| doc-librarian  | `contract/**`（业务理解）          |
| planner        | 全部（技术规划需全局）               |
| generator      | `backend/**`（后端实现）           |
| evaluator      | `contract/**`（验收依据）          |
| fitness-run    | `backend/fitness-rules.md`       |

## 使用模式（渐进式披露）

**Agent 的标准读法（三条硬规则）**：

1. **第一步**：Read `.chatlabs/spec/INDEX.md`（本文件）获取目录结构。
2. **第二步**：按 Consumer 映射 + 当前任务上下文，只 Read 相关模块的具体规范。
3. **禁止**：硬编码 `.chatlabs/spec/<module>/<file>.md` 路径，必须从本文件的目录树解析。

**Fallback**：若 `.chatlabs/spec/INDEX.md` 不存在（项目未初始化），agent 输出 warning 并 Read `docs/` 下的元规范，同时提示团队运行 `/init-project`。

**TBD 容忍**：读到的文件含 TBD 占位符时，agent 输出 warning 但**不阻断**（骨架未填完是常态）。

## 关联

- Flow 元规范（跨项目通用）：`docs/team-workflow.md`、`docs/task-directory-convention.md`
- 契约模板（跨项目通用）：`docs/contract-template.md`
- 技术债存储：`docs/tech-debt-backlog.md`