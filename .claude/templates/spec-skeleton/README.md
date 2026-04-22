# spec-skeleton — 项目规范骨架模板

`/init-project` 扫描项目技术栈后，从本目录拷贝对应骨架到 `.chatlabs/knowledge/`。
骨架里满是 TBD 占位符，**请团队手动填充**才能投入使用。

## 目录约定

| 模板文件 | 拷贝目标 | 何时拷贝 |
|---------|---------|---------|
| `INDEX.md.tpl` | `.chatlabs/knowledge/INDEX.md` | 必需，所有项目都拷 |
| `backend/*.md.tpl` | `.chatlabs/knowledge/backend/*.md` | 检测到后端代码才拷 |
| `frontend/*.md.tpl` | `.chatlabs/knowledge/frontend/*.md` | 检测到前端代码才拷 |
| `product/*.md.tpl` | `.chatlabs/knowledge/product/*.md` | 默认拷，不需要可删 |
| `contract/*.md.tpl` | `.chatlabs/knowledge/contract/*.md` | 默认拷，补充 `docs/contract-template.md` |

## 占位符规则

模板中有 3 类占位符：

- `<<PROJECT_NAME>>` — 项目名（从 package.json / pom.xml 等推断）
- `<<TECH_STACK>>` — 技术栈描述（如 "Java 17 + Spring Boot 3.2"）
- `TBD: <简述需填什么>` — 团队手动填充的段落

`/init-project` 自动替换前两类，TBD 留给团队。

## 模块目录名不固定

骨架用 `backend/`、`frontend/` 只是默认值。团队可改成 `api/`、`mobile/`、`sre/` 等，
**只要 INDEX.md 里的目录树同步更新**即可。

## 文件命名建议

- `coding-style.md` — 编码风格、注释纪律、命名约定
- `api-conventions.md` — API 响应格式、分页、错误码（后端）
- `component-rules.md` — 组件设计、状态管理（前端）
- `fitness-rules.md` — 架构适应度函数（各端均可）
- `design-principles.md` — 契约设计原则
- `domain-terminology.md` — 领域术语表（产品侧）

不强制，团队自由命名，只要 INDEX.md 能找到即可。

## 与 `docs/` 的分工

| 类别 | 路径 | 举例 |
|------|------|------|
| Flow 元规范（跨项目通用） | `docs/` | team-workflow、task-directory-convention、contract-template |
| 项目特定规范 | `.chatlabs/knowledge/` | coding-style、api-conventions、domain-terminology |

谁属于哪边？看"换一个项目还能不能直接用"——能用就是元规范。
