# spec-skeleton — 项目规范骨架模板

`/init-project` 扫描项目技术栈后，从本目录拷贝对应骨架到 `.chatlabs/knowledge/`。

## 目录约定

| 模板文件 | 拷贝目标 | 何时拷贝 |
|---------|---------|---------|
| `README.md.tpl` | `.chatlabs/knowledge/README.md` | 必需，所有项目都拷 |
| `backend/*.md.tpl` | `.chatlabs/knowledge/tech/backend/*.md` | 检测到后端代码才拷 |
| `frontend/*.md.tpl` | `.chatlabs/knowledge/tech/frontend/*.md` | 检测到前端代码才拷 |
| `product/*.md.tpl` | `.chatlabs/knowledge/product/*.md` | 默认拷，不需要可删 |
| `contract/*.md.tpl` | `.chatlabs/knowledge/asset/contract/*.md` | 默认拷，补充 `docs/contract-template.md` |

## 占位符规则

模板中有 3 类占位符：

- `<<PROJECT_NAME>>` — 项目名（从 package.json / pom.xml 等推断）
- `<<TECH_STACK>>` — 技术栈描述（如 "Java 17 + Spring Boot 3.2"）
- `TBD: <简述需填什么>` — 团队手动填充的段落

`/init-project` 自动替换前两类，TBD 留给团队。

## 知识库三层结构

```
knowledge/
├── README.md                 # 渐进式披露索引（§0-§6）
├── project/                  # 项目层（做什么）
│   ├── overview.md          # 项目概述
│   ├── core-functions.md    # 核心功能流程图
│   └── architecture.md      # 系统架构图
├── tech/                    # 技术层（怎么做）
│   ├── backend/             # 后端规范
│   ├── frontend/            # 前端规范
│   ├── middleware.md        # 中间件配置
│   └── libs/                # 三方库文档
└── asset/                   # 资产层（沉淀什么）
    ├── contract/           # 契约设计原则
    ├── frozen/             # 归档 PRD
    └── tech-debt/          # 技术债台账
```

## 与 `docs/` 的分工

| 类别 | 路径 | 举例 |
|------|------|------|
| Flow 元规范（跨项目通用） | `docs/` | team-workflow、task-directory-convention、contract-template |
| 项目特定规范 | `.chatlabs/knowledge/` | coding-style、api-conventions、domain-terminology |

谁属于哪边？看"换一个项目还能不能直接用"——能用就是元规范。
