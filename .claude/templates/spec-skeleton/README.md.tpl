# <<PROJECT_NAME>> — 知识库

> 知识库三层结构：项目层（做什么）→ 技术层（怎么做）→ 资产层（沉淀什么）。
> **Agent 标准读法**：先读本文件，按需深入子文档。

---

## §0 快速入口

| 场景 | 文档 |
|------|------|
| 写代码前必读 | [tech/backend/coding-style.md](tech/backend/coding-style.md) |
| 新增 API 端点 | [tech/backend/api-conventions.md](tech/backend/api-conventions.md) |
| 起草/评审契约 | [asset/contract/design-principles.md](asset/contract/design-principles.md) |
| 理解团队流程 | [docs/team-workflow.md](../../docs/team-workflow.md) |

---

## §1 项目层

> 回答"这个项目是做什么的"。

```
knowledge/project/
├── overview.md          # 项目概述（技术栈、团队、目标）
├── core-functions.md    # 核心功能逻辑流程图
└── architecture.md     # 系统架构图
```

- 技术栈：<<TECH_STACK>>
- [详细概述 →](project/overview.md)

---

## §2 技术层

> 回答"这个项目在技术层面有哪些约束和约定"。

```
knowledge/tech/
├── backend/             # 后端规范（<<TECH_STACK>>）
│   ├── coding-style.md  # 编码风格、注释纪律、命名约定
│   ├── api-conventions.md # API 响应格式、分页、错误码
│   ├── fitness-rules.md # 架构适应度函数
│   └── modules/         # 各模块规范
├── frontend/           # 前端规范（纯后端项目可删除此目录）
├── middleware.md        # 中间件配置
└── libs/               # 三方库文档
```

**Consumer 映射**：

| Agent / Skill | 必读文档 |
|--------------|---------|
| generator | tech/backend/coding-style.md + tech/backend/fitness-rules.md |
| planner | tech/backend/ + project/architecture.md |
| doc-librarian | asset/contract/design-principles.md |
| fitness-run | tech/backend/fitness-rules.md |

---

## §3 资产层

> 回答"这个项目积累了哪些历史决策和资产"。

```
knowledge/asset/
├── contract/             # 契约设计原则 + 冻结的 PRD
│   └── design-principles.md
├── frozen/              # 归档 PRD（冻结后的 contract.md）
├── tech-proposals/       # 技术方案（ADR 格式）
├── test-cases/          # 归档测试用例
├── function-design/      # 核心功能设计方案
└── tech-debt/           # 技术债台账
    └── backlog.md
```

---

## §4 Flow 元规范（跨项目通用）

| 文档 | 用途 |
|------|------|
| [docs/team-workflow.md](../../docs/team-workflow.md) | 团队协作流程 |
| [docs/task-directory-convention.md](../../docs/task-directory-convention.md) | Story/Case 目录约定 |
| [docs/contract-template.md](../../docs/contract-template.md) | 契约文档模板 |

---

## §5 使用模式（渐进式披露）

**Agent 的标准读法（三条硬规则）**：

1. **第一步**：Read `.chatlabs/knowledge/README.md`（本文件）获取三层结构和快速入口。
2. **第二步**：按 Consumer 映射表 + 当前任务上下文，只 Read 相关模块的具体规范。
3. **禁止**：硬编码 `.chatlabs/knowledge/<layer>/<module>/<file>.md` 路径，必须从本文件的目录树解析。

**Fallback**：若 `.chatlabs/knowledge/README.md` 不存在（项目未初始化），agent 输出 warning 并 Read `docs/` 下的元规范，同时提示团队运行 `/init-project`。

**TBD 容忍**：读到的文件含 TBD 占位符时，agent 输出 warning 但**不阻断**（骨架未填完是常态）。

---

## §6 三层结构说明

| 层级 | 回答问题 | 典型读者 | 更新频率 |
|------|---------|---------|---------|
| **项目层** project/ | 这个项目是什么、做什么 | 所有新人 + 全局规划 | 低（架构变更时） |
| **技术层** tech/ | 编码/配置/架构有哪些约束 | generator、planner | 中（规范迭代时） |
| **资产层** asset/ | 历史决策、归档文档在哪 | 所有人按需 | 高（持续积累） |

---

## §7 关联

- Flow 版本记录：`.claude/.flow-source.json`
- 项目扫描底稿：`.chatlabs/knowledge/.scan.json`（内部用）
- 团队元规范：`../docs/`
