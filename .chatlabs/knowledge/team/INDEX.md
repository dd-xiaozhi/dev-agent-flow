# 团队层规范 — INDEX

> **定位**：跨项目通用、稳定演进的团队级约定。所有 agent / skill / command 启动前可按需读取这里。
> **与 tech/ 层的边界**：team/ 是"团队怎么协作"，tech/ 是"项目本身怎么实现"。

## 入口表

| 主题 | 文档 | 何时读 |
|------|------|--------|
| Git 分支与提交规范 | [git-brance-spec.md](git-brance-spec.md) | 创建分支、提交、合并、清理前 |
| 团队工作流总纲 | [team-workflow.md](team-workflow.md) | 接入工作流、流程改造、新人 onboarding |
| TAPD 工单操作规范 | [TAPD_Ticket_操作规范.md](TAPD_Ticket_操作规范.md) | 涉及 TAPD 工单状态、字段、subtask、工时回填 |
| 路径占位符词典 | [path-dictionary.md](path-dictionary.md) | 写新文档 / agent / skill / 模板时 |
| 业务命名规范 | [naming-conventions.md](naming-conventions.md) | doc-librarian 写 contract / planner 写 spec / arbiter 检测冲突 |

## Consumer 映射

| 角色 | 必读 |
|------|------|
| 所有 agent / skill / command 作者 | path-dictionary（写文档前） |
| `git` skill | git-brance-spec |
| `tapd` skill / `/tapd` command | TAPD_Ticket_操作规范 |
| `doc-librarian` / 新人 agent | team-workflow + naming-conventions |
| `planner` | naming-conventions |
| `arbiter` | naming-conventions（判定冲突基准） |
| `workflow-reviewer` / `sprint-review` skill | 全部 |

## 维护

- team/ 下文档**完全由人工维护**，`/init-project` 不会触碰。
- 新增团队级规范直接落到 team/，更新本 INDEX 入口表即可。
- 文档迁出 docs/ 后保留原文件名（避免引用面级联改动）。
