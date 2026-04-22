# /init-project

> 扫描项目、生成/更新 Claude Code 项目文档体系（知识库 + 入口文档）。
>
> 典型触发场景：首次接入项目、代码架构大幅重构、现有文档过时。
>
> **目录职责划分**：
> - `.claude/` — Flow 运行时目录（commands / skills / hooks / settings.json）
> - `.chatlabs/` — 项目特定目录（knowledge/ 知识库、stories/ 本地任务、state/ 状态）
> - `README.md` — 项目根目录，入口文档

## Phase 0: 模式判断

检查 `.chatlabs/knowledge/.scan.json` 是否存在：

- **不存在** → `[模式 A: 初始化]`，执行 Phase 1 → Phase 8
- **存在** → `[模式 B: 增量更新]`，执行 Phase 1 → Phase U

---

## Phase 1: 扫描与建模（两种模式均执行）

### 1.1 目录结构

记录：源码根路径、模块目录层级、测试目录位置。

### 1.2 技术栈推断

从构建文件推断（不存在的跳过）：

| 文件 | 推断内容 |
|------|---------|
| `package.json` | Node.js；取 `engines.node` 或默认 20 |
| `pyproject.toml` / `setup.py` | Python；取 `python-version` 或默认 3.11 |
| `go.mod` | Go；取 `go` 版本行 |
| `Cargo.toml` | Rust；取 `edition` |
| `pom.xml` / `build.gradle` | Java/JVM；取 `java.version` |
| `Dockerfile` | 容器化；记录 FROM 基础镜像 |

### 1.3 编码规范归纳

用 ripgrep 扫描全部源码，归纳以下模式：

- **命名风格**：变量（下划线/camelCase/PascalCase）、文件（kebab-case/snake_case）
- **import 顺序**：分组方式（stdlib → 第三方 → 本地）
- **注释风格**：docstring 语言（英文/中文）、`TODO` / `FIXME` 分布
- **错误处理**：主要异常类型、错误返回值约定
- **测试组织**：`test/` 下的命名、断言风格

### 1.3.8 检测框架

```json
{ "frameworks": [], "database": "<MongoDB/PostgreSQL...>", "architecture_pattern": "<DDD/MVC...>" }
```

### 1.3.9 提取 API 端点

按模块分组，提取 method / path / handler。

### 1.3.10 提取存储层设计

集合/表命名、索引、Key 模式、TTL。

### 1.4 核心模块识别

列出核心模块 + 关键文件 + 模块职责描述。

### 1.4.1 提取领域模型

聚合根/实体/服务。

### 1.5 模块依赖关系

建立模块间的依赖关系图。

### 1.6 功能→文件映射

每个模块的关键文件及其职责。

### 1.7 扫描结果持久化

写入 `.chatlabs/knowledge/.scan.json`（version: 2），包含：

- tech_stack、frameworks、domain_models、api_conventions、databases
- modules、naming_conventions、import_order、error_handling、test_patterns

---

## ===== 模式 A: 初始化流程 =====

### Phase 6: 记录 Flow 来源（首次执行时）

读取 Flow Repo 的 `.claude/MANIFEST.md`，提取 `flow_version`。

创建 `.claude/.flow-source.json`：

```json
{
  "version": 2,
  "flow_repo": "<Flow Repo 绝对路径>",
  "flow_version": "<版本号>",
  "last_commit": "<git HEAD commit hash>",
  "last_upgraded_at": "<ISO timestamp>"
}
```

### Phase 8: 生成 .chatlabs/knowledge/ 项目规范

检查 `.chatlabs/knowledge/README.md` 是否存在：
- **已存在** → 跳过，仅提示
- **不存在** → 执行 Phase 8.1 ~ 8.7

#### Phase 8.1: 确定规范目录结构（框架/架构自适应）

| 架构模式 | 规范目录 |
|---------|---------|
| DDD | `knowledge/ddd/` |
| MVC | `knowledge/mvc/` |
| Clean Architecture | `knowledge/clean/` |
| Next.js App Router | `knowledge/frontend/` |
| Rails | `knowledge/rails/` |
| Feature-Sliced | `knowledge/features/` |
| 其他后端 | `knowledge/tech/backend/`（默认） |

**检测优先级**：框架（Spring Boot / Flask / Express / Next.js） → 架构模式（DDD / MVC / Clean） → 最终目录

**必须创建的目录**：`contract/`、`product/`

#### Phase 8.2: 生成 coding-style.md

内容：Phase 1.3 归纳的编码规范（命名 / import 顺序 / 错误处理 / 测试规范）。

#### Phase 8.3: 生成 architecture.md

内容：Phase 1.5 模块依赖关系 + Phase 1.4.1 领域模型。

#### Phase 8.4: 生成 knowledge/README.md（渐进式披露索引）

结构：
- §0 快速入口
- §1 项目层（overview / core-functions / architecture）
- §2 技术层索引（含 Consumer 映射）
- §3 资产层索引
- §4 Flow 元规范（指向 docs/）
- §5 使用模式（三条硬规则）

#### Phase 8.5: 生成 fitness-rules.md

内容：Phase 1.3.8-10 归纳的架构规则（分层 / API / 领域 / 存储层约束）。

#### Phase 8.6: 生成模板目录清单

```
📋 Agent 模板（来自 Flow Repo）
├── .claude/templates/sprint-contract.md
├── .claude/templates/evaluator-rubric.md
└── .claude/templates/story/case-template.md
```

#### Phase 8.7: 生成模块规范文档

对每个核心模块，生成 `knowledge/tech/backend/modules/<module>.md`：

- Overview（模块职责）
- API 端点（若检测到 Web 框架）
- 领域模型、存储层、依赖关系、文件路由

**保留原则**：已存在的文件只更新可归纳部分，保留团队手写内容。

---

**模式 A 增量更新说明（已存在 knowledge/ 时）**：
- **不覆盖**：已存在的 md 文件
- **只更新**：README.md 的目录树部分
- **新增模块**：追加到 README.md 并新建骨架文件

## ===== 模式 B: 增量更新流程 =====

### Phase U: 差异对比与定向更新

#### U-1: 读取旧扫描结果

读取 `.chatlabs/knowledge/.scan.json`，与 Phase 1 新扫描结果逐项对比。

#### U-2: 输出变更摘要

```
## 变更检测结果
1. [变化类型]: [具体描述] → 影响文件: <路径> → 操作: [新建/更新/删除]
```

无任何变化 → `✅ 所有文档与当前代码一致，无需更新。`

#### U-3: 执行定向更新

| 变化类型 | 操作 |
|---------|------|
| 新增模块 | 新建 `knowledge/tech/backend/modules/<name>.md`，更新 README.md |
| 删除模块 | 删除对应模块文档，从 README.md 移除 |
| 模块内部文件变化 | 只更新对应模块文档的文件路由表 |
| 技术栈/编码规范变化 | 更新 README.md / coding-style.md |

---

## 输出规范

### 模式 A 结尾

```
📁 生成文件清单
├── README.md
├── .claude/.flow-source.json
└── .chatlabs/knowledge/
    ├── README.md（渐进式披露索引）
    ├── .scan.json（扫描底稿）
    ├── project/（overview / core-functions / architecture）
    ├── tech/backend/（coding-style / fitness-rules / modules/）
    └── asset/（contract / frozen / tech-proposals / test-cases / tech-debt/）
```

### 模式 B 结尾

```
📁 更新总结
├── ✏️ knowledge/tech/backend/modules/xxx.md
├── ➕ knowledge/tech/backend/modules/new.md
└── ✏️ knowledge/README.md
```
