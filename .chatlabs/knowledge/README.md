# 知识库 — README

> **入口文档**：项目的"地图"。所有 agent / generator / planner / evaluator 启动前应先读这里定位上下文。
> **生成方式**：由 `/init-project` 扫描代码自动产出，团队手写补充段被严格保护（不会被覆盖）。

---

## 快速入口

| 你想知道 | 看哪 |
|---------|------|
| 项目是干什么的 | [project/overview.md](project/overview.md) |
| 核心业务流程 | [project/core-functions.md](project/core-functions.md) |
| 模块怎么互相依赖 | [project/architecture.md](project/architecture.md) |
| 怎么写 Python / Markdown | [tech/backend/coding-style.md](tech/backend/coding-style.md) |
| 架构红线（不准做什么） | [tech/backend/fitness-rules.md](tech/backend/fitness-rules.md) |
| 某个模块详情 | [tech/backend/modules/](tech/backend/modules/) |

---

## 项目层

```
project/
├── overview.md          技术栈 + 目录结构 + 构建运行
├── core-functions.md    核心流程（4 个 flow 模板 / Story 生命周期 / 事件总线）
└── architecture.md      模块依赖图 + 领域模型 + 状态机
```

| 你是谁 | 必读 |
|--------|------|
| 第一次接触本项目 | overview.md |
| PM / 决策者 | core-functions.md |
| 架构师 / 维护者 | architecture.md |
| AI agent（自动） | 三个全读 |

---

## 技术层

```
tech/backend/
├── coding-style.md       Python + Markdown 规范，含三层降级模板
├── fitness-rules.md      架构红线（路径 / 分层 / hook / skill / git）
└── modules/
    ├── agents.md         7 个 agent
    ├── commands.md       8 个 command（扁平化）
    ├── skills.md         10 个 skill
    ├── hooks.md          7 个 hook
    ├── scripts.md        7 个 script
    └── templates.md      产物模板 + 7 个 flow JSON
```

### Consumer 映射（哪个 AI 角色读哪份）

| 角色 | 必读 | 选读 |
|------|------|------|
| `doc-librarian` | overview / coding-style / contract 资产 | architecture / fitness-rules |
| `planner` | architecture / fitness-rules / coding-style | modules/* |
| `generator` | coding-style / fitness-rules / 相关 modules | architecture |
| `evaluator` | contract 资产 / fitness-rules | spec |
| `session-auditor` | fitness-rules / coding-style | 全部 |
| `workflow-reviewer` | architecture / 历史 reports | 全部 |

---

## 资产层

```
asset/
├── contract/           契约设计原则与最佳实践
├── frozen/             历史归档的 PRD / contract
├── tech-proposals/     待选技术方案
├── test-cases/         归档的用例
└── tech-debt/          技术债清单
```

资产层**完全由人工维护**，`/init-project` 不会触碰内容。

---

## Flow 元规范

本项目本身是 Claude Code 的 Flow 配置框架，存在两层规范：

| 层 | 文档 | 角色 |
|---|------|------|
| Flow 自身规范（如何写 hook / skill / agent） | 本知识库 | Flow 维护者 |
| 业务项目规范（用本 Flow 跑业务时） | 业务项目自己的 `.chatlabs/knowledge/` | 业务开发者 |

`/init-project` 命令对**业务项目**生成知识库；本项目自身的知识库是**示范+元规范**。

---

## 使用模式（三条硬规则）

1. **修改前先读**：动 `.claude/scripts/paths.py` 前必读 `tech/backend/coding-style.md` §1.2；动 hook 前必读 §1.4。
2. **AI 启动先扫**：任何 agent 启动前 by default 读 README.md → 按 Consumer 映射定位需要的子文档。
3. **手写段不动**：`asset/` 全部、`modules/*.md` 的「注意事项」「设计决策」段、`coding-style.md` / `fitness-rules.md` 的团队补充段——`/init-project` 增量更新时仅追加，不删除。

---

## 维护

```bash
/init-project              # 扫描项目并增量更新（mode B）
                           # 删除 .chatlabs/knowledge/.scan.json 触发全量重建（mode A）
```

变更日志：见 git history（不在文档内冗余记录）。
