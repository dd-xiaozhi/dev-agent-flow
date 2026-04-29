---
name: init-project
description: 扫描项目并生成/更新 Claude Code 项目文档体系（知识库 + 入口文档）。适用于首次接入、架构重构或文档过时场景。
model: opus
---

# /init-project

> 扫描项目代码并生成/更新知识库（`.chatlabs/knowledge/`）+ 项目根 `CLAUDE.md`。
>
> **用法**：`/init-project`

## 行为

### 第一步：判定模式
读 `.chatlabs/knowledge/.scan.json`：

| 状态 | 模式 | 含义 |
|------|------|------|
| 不存在 | A（首次接入） | 全量生成知识库骨架 + 根 CLAUDE.md |
| 存在 | B（增量更新） | 与旧扫描结果 diff，仅改有变化的文件 |

`.scan.json` 损坏视为模式 A 重新初始化，旧知识库文件保留并按模式 B 红线处理。

### 第二步：扫描建模
调用 init-project skill 对项目根做扫描，输出扫描底稿，包含：

- 技术栈与版本（语言 / 构建工具 / 容器基础镜像）
- 框架与架构（Web 框架、数据库、缓存、API 端点、领域模型、架构模式）
- 编码规范归纳（命名、import 顺序、注释、错误处理、测试）
- 模块清单 + 模块依赖关系 + 功能→文件映射

扫描实现细节由 skill 内部处理，command 不复述。

### 第三步:模式 A —— 全量生成
1. 按检测到的架构模式选择技术层目录（DDD / MVC / Clean / Next.js App Router / Rails / Feature-Sliced，默认 `tech/backend/`），创建 project / tech / asset 三层骨架。`asset/` 下强制创建 `contract/`、`frozen/`、`tech-proposals/`、`test-cases/`、`tech-debt/`。
2. 用 TaskCreate 并行 5 个子任务，每任务只写自己负责的文件，互不读写：
   - coding-style.md（命名 / import / 错误处理 / 测试规范）
   - project 层（overview.md 概述 + core-functions.md 核心功能流程）
   - architecture.md（模块依赖 + 领域模型）
   - fitness-rules.md（分层约束 / API 规范 / 存储层约束）
   - modules/*.md（每核心模块一份，固定段落见下方产出）
3. 所有任务完成后写 `knowledge/README.md`（渐进式披露索引），段落顺序：快速入口 → 项目层 → 技术层（含 Consumer 映射）→ 资产层 → Flow 元规范 → 使用模式（三条硬规则）。
4. 写 `.claude/.flow-source.json`（version / flow_repo / flow_version / last_commit / last_upgraded_at）。
5. 写项目根 `CLAUDE.md`（纯索引，见红线）。

### 第四步：模式 B —— 增量更新
1. **CLAUDE.md 兜底**（最先执行）：若根 CLAUDE.md 缺失或格式退化（内联了技术栈详情/集成列表/运行环境等本应在知识库的内容），按模式 A 第 5 步模板重新生成。
2. 与旧 `.scan.json` 逐项 diff：模块新增/删除/重命名、技术栈变化、编码规范新增模式、架构模式变化。
3. 输出变更摘要后定向更新：

| 变化 | 操作 |
|------|------|
| 新增模块 | 新建 `tech/backend/modules/<name>.md` 骨架 + 更新 README 目录树 |
| 删除模块 | 删除对应模块文档 + 从 README 移除引用 |
| 模块内部文件变化 | 仅更新对应模块文档的「文件路由表」段，其他段落保留 |
| 技术栈变化 | 更新 `project/overview.md` 技术栈行 + README 元信息 |
| 编码规范变化 | 在 `coding-style.md` 追加新模式，不删旧内容 |
| 架构模式变化 | 更新 `project/architecture.md` + README 架构模式行 |
| 构建/运行命令变化 | 更新 `project/overview.md` 构建段 |

4. 覆盖写 `.scan.json`（保持 version: 2）。无 diff 时仍执行 CLAUDE.md 兜底校验后退出。

## 输入

无参数。命令对当前 git 仓库根执行。

## 产出

- `CLAUDE.md`（项目根，纯索引）
- `.chatlabs/knowledge/README.md`（渐进式披露索引）
- `.chatlabs/knowledge/.scan.json`（扫描底稿，不展示给用户）
- `.chatlabs/knowledge/project/{overview,core-functions,architecture}.md`
- `.chatlabs/knowledge/tech/backend/{coding-style,fitness-rules}.md`
- `.chatlabs/knowledge/tech/backend/modules/<module>.md`（固定段落：Overview / API 端点 / 领域模型 / 存储层 / 依赖关系 / 文件路由）
- `.chatlabs/knowledge/asset/{contract,frozen,tech-proposals,test-cases,tech-debt}/`（空目录占位）
- `.claude/.flow-source.json`（仅模式 A 首次写入）

## CLAUDE.md 红线

- 必须是**纯索引**：项目一句话描述 + 知识库目录指向 + coding-style / fitness-rules 路径。不得内联技术栈详情、模块列表、集成说明、运行环境——这些归 `knowledge/project/overview.md`。
- 模式 B 重生成时，若 `knowledge/project/overview.md` 已存在，CLAUDE.md 完全不写技术栈详情。
- 团队手写段落绝对不覆盖：`asset/` 下全部、`modules/*.md` 的「注意事项」「设计决策」段、`project/core-functions.md` 的手动补充段、`coding-style.md` 与 `fitness-rules.md` 中团队补充的段落（仅允许追加新模式，不允许删除）。

## 失败处理

| 场景 | 行为 |
|------|------|
| 项目无构建文件，技术栈推断失败 | 写 Blocker（信息-外部依赖），coding-style/modules 跳过空骨架占位，仍生成 README + CLAUDE.md |
| 模式 A 检测到 `knowledge/` 已部分存在 | 视为模式 B：保留已有内容，按 diff 流程补齐缺失文件 |
| 模式 B 团队已自定义受保护段落 | 不覆盖；新归纳内容仅追加到允许追加段落 |
| 模式 B 无任何 diff | 仅执行 CLAUDE.md 兜底校验，通过后输出「文档与代码一致，无需更新」退出 |
| 单子任务失败（Phase 2 并行） | 该任务对应文件留 placeholder + Blocker，不阻塞其他任务和 README 生成 |

## 关联

- Skill: init-project（扫描器，承担所有 ripgrep / 框架检测 / API 端点扫描细节）
- 入口文档: `CLAUDE.md`、`.chatlabs/knowledge/README.md`
- 配置：`.claude/.flow-source.json`（Flow 来源版本追踪）
- 后续：`/start-dev-flow`（开始开发流）、`/tapd-init`（绑定 TAPD 项目，可选）
