# /init-project

> 扫描项目、生成/更新 Claude Code 项目文档体系（知识库 + 入口文档）。
>
> 典型触发场景：首次接入项目、代码架构大幅重构、现有文档过时。

**目录职责划分**：
- `.claude/` — Flow 运行时目录（commands / skills / hooks / settings.json）
- `.chatlabs/` — 项目特定目录（knowledge/ 知识库、stories/ 本地任务、state/ 状态）
- `README.md` — 项目根目录，入口文档

---

## Phase 0: 模式判断

检查 `.chatlabs/knowledge/.scan.json` 是否存在：

| 状态 | 模式 | 后续流程 |
|------|------|---------|
| 不存在 | **模式 A: 初始化** | Phase 1 → Phase 2 → Phase 3 |
| 存在 | **模式 B: 增量更新** | Phase 1 → Phase U |

---

## Phase 1: 扫描与建模（两种模式均执行）

### 1.1 目录结构

扫描项目根目录，记录：
- 源码根路径（如 `src/`、`app/`）
- 模块目录层级
- 测试目录位置（`test/` 或 `tests/`）
- 构建文件（package.json / pyproject.toml / Cargo.toml 等）
- 入口文件（main.ts / main.go / App.java 等）

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

### 1.4 框架与架构检测

- **1.4.1 检测框架**：识别 Web 框架（Spring Boot / Flask / Express / Next.js 等）、数据库、缓存
- **1.4.2 提取 API 端点**：按模块分组，提取 method / path / handler
- **1.4.3 提取存储层设计**：集合/表命名、索引、Key 模式、TTL
- **1.4.4 提取领域模型**：聚合根/实体/服务

### 1.5 核心模块识别

列出核心模块 + 关键文件 + 模块职责描述。

### 1.6 模块依赖关系

建立模块间的依赖关系图。

### 1.7 功能→文件映射

每个模块的关键文件及其职责。

### 1.8 扫描结果持久化

写入 `.chatlabs/knowledge/.scan.json`（version: 2），包含：
- tech_stack、frameworks、domain_models、api_conventions、databases
- modules、naming_conventions、import_order、error_handling、test_patterns

此文件不展示给用户，只做 diff 底稿。

---

## ===== 模式 A: 初始化流程 =====

模式 A 在 Phase 1 完成后继续执行 Phase 2 → Phase 3。

### Phase 2: 生成知识库文件（Task 并行）

Phase 2 包含 5 个独立子任务，**必须用 TaskCreate 创建并行任务**，避免上下文焦虑。

#### 2.1 创建目录骨架

根据 Phase 1.4.1 检测到的框架 + 1.4.4 架构模式，创建目录：

| 架构模式 | 规范目录 |
|---------|---------|
| DDD | `knowledge/ddd/` |
| MVC | `knowledge/mvc/` |
| Clean Architecture | `knowledge/clean/` |
| Next.js App Router | `knowledge/frontend/` |
| Rails | `knowledge/rails/` |
| Feature-Sliced | `knowledge/features/` |
| 其他后端 | `knowledge/tech/backend/`（默认） |

三层骨架目录：
```
knowledge/
├── project/                    ← 项目层
│   ├── overview.md             ← Phase 2.2
│   ├── core-functions.md       ← Phase 2.2
│   └── architecture.md         ← Phase 2.3
├── tech/backend/              ← 技术层（默认）
│   ├── coding-style.md         ← Phase 2.2
│   ├── fitness-rules.md        ← Phase 2.4
│   └── modules/               ← Phase 2.5
├── product/                   ← 产品层
└── asset/                    ← 资产层
    ├── contract/              ← 契约原则
    ├── frozen/                ← 归档 PRD
    ├── tech-proposals/        ← 技术方案
    ├── test-cases/           ← 归档测试用例
    └── tech-debt/            ← 技术债台账
```

**必须创建的目录**：`contract/`、`product/`

#### 2.2 并行任务分配

在 Phase 2.1 创建目录骨架后，**立即创建 5 个并行任务**：

| Task | 任务名 | 输入依赖 | 负责文件 |
|------|--------|---------|---------|
| Task-1 | 生成 coding-style.md | Phase 1.3 归纳结果 | `knowledge/tech/backend/coding-style.md` |
| Task-2 | 生成 project 层文件 | Phase 1.2 tech_stack + 1.4.1 frameworks + 1.5~1.6 功能流程 | `knowledge/project/overview.md`、`knowledge/project/core-functions.md` |
| Task-3 | 生成 architecture.md | Phase 1.6 模块依赖 + 1.4.4 领域模型 | `knowledge/project/architecture.md` |
| Task-4 | 生成 fitness-rules.md | Phase 1.4.1~1.4.3 归纳结果 | `knowledge/tech/backend/fitness-rules.md` |
| Task-5 | 生成模块规范文档 | Phase 1.5~1.7 核心模块信息 | `knowledge/tech/backend/modules/*.md`（每个模块一个文件） |

**并行执行要求**：
- 所有 Task **同时启动**，不等待其他 Task 完成
- 每个 Task **只负责自己的文件**，不读写其他 Task 的输出文件
- Phase 2.3（生成 README.md）等待所有 Task 完成后执行

#### 2.3 任务详细说明

**Task-1: coding-style.md**
- 内容来源：Phase 1.3 归纳结果（命名规范 / import 顺序 / 错误处理 / 测试规范）

**Task-2: project/ 层的两个文件**
- `overview.md`：从 Phase 1.2 tech_stack + 1.4.1 frameworks 生成项目概述
- `core-functions.md`：从 Phase 1.5~1.6 生成核心功能流程图

**Task-3: architecture.md**
- 内容来源：Phase 1.6 模块依赖关系 + Phase 1.4.4 领域模型

**Task-4: fitness-rules.md**
- 内容来源：Phase 1.4.1~1.4.3 归纳结果（分层约束 / API 规范 / 存储层约束）

**Task-5: modules/*.md**
- 对每个核心模块生成一个文件
- 包含：Overview（模块职责）、API 端点（若检测到 Web 框架）、领域模型、存储层、依赖关系、文件路由
- **保留原则**：已存在的文件只更新可归纳部分，保留团队手写内容

#### 2.4 生成 knowledge/README.md（所有任务完成后）

等待所有 Task 完成后，生成渐进式披露索引：

结构：
- §0 快速入口
- §1 项目层（overview / core-functions / architecture）
- §2 技术层索引（含 Consumer 映射：谁该读什么）
- §3 资产层索引
- §4 Flow 元规范（指向 docs/）
- §5 使用模式（三条硬规则）

---

### Phase 3: 记录 Flow 来源（模式 A 首次执行）

**仅在 `.claude/.flow-source.json` 不存在时写入**：

1. 读取 Flow Repo 的 `.claude/MANIFEST.md`，提取 `flow_version`（不存在则默认 "1.0"）
2. 创建 `.claude/.flow-source.json`：

```json
{
  "version": 2,
  "flow_repo": "<Flow Repo 绝对路径>",
  "flow_version": "<版本号>",
  "last_commit": "<git HEAD commit hash>",
  "last_upgraded_at": "<ISO timestamp>"
}
```

---

## ===== 模式 B: 增量更新流程 =====

模式 B 在 Phase 1 完成后执行 Phase U（**不是 Phase 2**）。

### Phase U: 差异对比与定向更新

#### U-1: 读取旧扫描结果

读取 `.chatlabs/knowledge/.scan.json`（Phase 0 已确认存在），与 Phase 1 新结果逐项对比：

- 模块列表 diff（新增 / 删除 / 重命名）
- 技术栈 diff（语言 / 框架 / 数据库变化）
- 编码规范 diff（新增模式 / 命名风格变化）

同时读取现有知识库文件，确认哪些是**团队手写内容**（不得覆盖）：

```
knowledge/
├── README.md                 ← 必读，检查目录树部分
├── project/                  ← 检查已有哪些骨架文件
├── tech/backend/
│   ├── coding-style.md      ← 只追加，不覆盖团队补充
│   ├── fitness-rules.md      ← 只追加，不覆盖团队补充
│   └── modules/             ← 逐文件对比文件路由表
└── asset/                   ← 团队内容优先
```

#### U-2: 输出变更摘要

```
## 变更检测结果

### 检测到以下变化：
1. [变化类型]: [具体描述]
   → 影响文件: <路径>
   → 操作: [新建 / 更新 / 删除]

### 无变化（确认以下文档仍然准确）：
- ✅ <文件路径>
```

**无任何变化时**：`✅ 所有文档与当前代码一致，无需更新。` 直接结束。

#### U-3: 执行定向更新

**严格只改有变化的部分**，不重写无变化的文件。

| 变化类型 | 具体操作 |
|---------|---------|
| 新增模块 | 读取 `knowledge/tech/backend/modules/` 是否存在同名文件；不存在则新建骨架 + 更新 README.md 目录树 |
| 删除模块 | 删除对应模块文档 + 从 README.md 移除引用 |
| 模块内部文件变化 | 只更新对应模块文档的**文件路由表**段落，其他段落保留 |
| 技术栈变化 | 更新 `project/overview.md` 技术栈行 + README.md 元信息 |
| 编码规范变化 | 在 `coding-style.md` 中**追加**新模式示例，不删除旧内容 |
| 架构模式变化 | 更新 `project/architecture.md` + README.md 架构模式行 |
| 构建/运行命令变化 | 更新 `project/overview.md` 的构建 section |

**覆盖红线**：团队在以下文件中的手写段落**绝对不得覆盖**：
- `asset/` 下所有内容（PRD / 技术方案 / 设计决策）
- `tech/backend/modules/*.md` 中的「注意事项」和「设计决策」段落
- `project/core-functions.md` 中的手动补充内容

#### U-4: 更新扫描底稿

将 Phase 1 的新扫描结果**覆盖写入** `.chatlabs/knowledge/.scan.json`（保持 version: 2）。

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
├── ✏️ knowledge/tech/backend/modules/xxx.md  - 更新了文件路由表
├── ➕ knowledge/tech/backend/modules/new.md   - 新增模块文档
├── ✏️ knowledge/README.md                    - 更新了目录树
└── ✏️ .chatlabs/knowledge/.scan.json        - 更新了扫描底稿

未变更（确认仍然准确）：
├── ✅ knowledge/tech/backend/coding-style.md（已存在，团队补充内容保留）
└── ✅ knowledge/project/architecture.md
```
