# /init-project

> 扫描项目、生成/更新 Claude Code 项目文档体系（项目规范 + 入口文档）。
>
> 典型触发场景：首次接入项目、代码架构大幅重构、现有文档过时。
>
> **目录职责划分**：
> - `.claude/` — Flow 运行时目录（commands / skills / hooks / settings.json）
> - `.chatlabs/` — 项目特定目录（spec/ 项目规范、stories/ 本地任务、state/ 状态）
> - `CLAUDE.md` — 项目根目录，唯一入口路由表

## Phase 0: 模式判断

检查 `.chatlabs/knowledge/.scan.json` 是否存在：

- **不存在** → `[模式 A: 初始化]`，执行 Phase 1 → Phase 8
- **存在** → `[模式 B: 增量更新]`，执行 Phase 1 → Phase U

输出模式标识并以此为蓝本执行后续流程。

---

## Phase 1: 扫描与建模（两种模式均执行）

### 1.1 目录结构

```
<项目根目录>/
├── src/                      # 源码目录
├── test/ 或 tests/           # 测试目录
├── docs/                     # 文档目录
├── scripts/                  # 脚本
├── <构建文件>                # package.json / pyproject.toml / Cargo.toml / pom.xml / go.mod 等
└── <入口文件>                # main.ts / main.go / App.java 等
```

记录：源码根路径、模块目录层级、测试目录位置。

### 1.2 技术栈推断

从构建文件推断（不存在的跳过）：

| 文件 | 推断内容 |
|------|---------|
| `package.json` | Node.js；取 `engines.node` 或默认版本 |
| `pyproject.toml` / `setup.py` | Python；取 `python-version` 或默认 |
| `go.mod` | Go；取 `go` 版本行 |
| `Cargo.toml` | Rust；取 `edition` |
| `pom.xml` / `build.gradle` | Java/JVM；取 `java.version` 或 `sourceCompatibility` |
| `Dockerfile` | 容器化；记录 FROM 基础镜像 |
| `.python-version` / `.nvmrc` | 显式版本约束 |

语言版本默认值：`node` 取 20，`python` 取 3.11，`go` 取 1.21。

### 1.3 编码规范归纳

用 ripgrep 扫描全部源码，归纳以下模式：

- **命名风格**：变量（下划线/camelCase/PascalCase）、文件（kebab-case/snake_case）、目录
- **import 顺序**：分组方式（stdlib → 第三方 → 本地）、相对路径 vs 绝对路径
- **注释风格**：docstring 语言（英文/中文）、行注释密度、`TODO` / `FIXME` 分布
- **错误处理**：主要异常类型、错误返回值约定（error as return value / exception / Result type）
- **测试组织**：`test/` 下的命名（`*_test.go` / `test_*.py` / `*.spec.ts`）、断言风格（assert / expect / require）

从代码中提取正例，不编造。

### 1.3.8 检测项目使用的框架

目标：识别项目使用的 Web 框架、数据库、架构模式。

结果格式：
```json
{
  "frameworks": ["Spring Boot", "Redis", "MongoDB"],
  "database": "MongoDB",
  "architecture_pattern": "DDD"
}
```

### 1.3.9 提取 API 端点

目标：提取项目中所有 API 端点，按模块分组。

结果格式：
```json
{
  "endpoints": [
    {
      "module": "sales",
      "method": "POST",
      "path": "/api/sales/orders",
      "handler": "createOrder",
      "param_type": "CreateOrderCmd"
    }
  ]
}
```

### 1.3.10 提取数据库/缓存设计

目标：提取集合/表命名、索引、Key 模式、TTL 等存储层约定。

结果格式：
```json
{
  "databases": {
    "mongodb": {
      "collection_naming": "全小写下划线复数",
      "collections": [{"name": "orders", "indexes": ["customerId"]}]
    },
    "redis": {
      "key_pattern": "{prefix}:{module}:{entity}:{id}",
      "ttl": {"cache": "30min", "lock": "10s"}
    }
  }
}
```

### 1.4 核心模块识别

目标：识别项目中核心业务模块。

结果：列出核心模块 + 每个模块的关键文件 + 模块职责描述。

### 1.4.1 提取领域模型

目标：识别聚合根/实体/服务等核心领域对象。

结果格式：
```json
{
  "domain_models": {
    "pattern": "DDD",
    "aggregates": [
      {"name": "SalesOrderAgg", "module": "sales", "methods": ["create", "confirmPayment"]}
    ]
  }
}
```

### 1.5 模块依赖关系

目标：建立模块间的依赖关系图。

### 1.6 功能→文件映射

目标：列出每个模块的关键文件及其职责。

### 1.7 扫描结果持久化

将以上结果写入 `.chatlabs/knowledge/.scan.json`（version: 2）。

**完整结构**：
```json
{
  "version": 2,
  "scanned_at": "<ISO timestamp>",
  "project_root": "<绝对路径>",
  "source_root": "<src/> 或项目源码根目录",

  "tech_stack": {
    "language": "<Python / Java / TypeScript / Go ...>",
    "version": "<版本号>",
    "build": "<Maven / Gradle / npm / go ...>",
    "database": "<MongoDB / PostgreSQL / MySQL ...>",
    "cache": "<Redis / Memcached ...>"
  },

  "frameworks": ["<检测到的框架列表>"],
  "domain_models": {
    "pattern": "<DDD / MVC / Clean Architecture / Next.js / Feature-Sliced>",
    "aggregates": [ /* DDD 聚合根 */ ],
    "entities": [ /* MVC 实体 */ ],
    "controllers": [ /* MVC Controller */ ]
  },
  "api_conventions": {
    "framework": "<Spring Boot / Flask / Express ...>",
    "routing_style": "<annotation / file-based / decorator>",
    "dto_pattern": "<请求模型命名模式>",
    "vo_pattern": "<响应模型命名模式>",
    "pagination": "<分页参数模式>",
    "endpoints": [ /* 端点列表 */ ],
    "error_response": "<错误响应格式>"
  },
  "databases": {
    "<mongodb/postgresql/redis/s3>": { /* 存储层规范 */ }
  },
  "modules": {
    "<module-name>": {
      "files": [ /* 文件列表 */ ],
      "imports": [ /* 依赖的模块 */ ],
      "imported_by": [ /* 被哪些模块依赖 */ ],
      "description": "<模块职责描述>"
    }
  },
  "naming_conventions": {
    "class": "<PascalCase / camelCase>",
    "function": "<camelCase / snake_case>",
    "variable": "<camelCase / snake_case>",
    "file": "<PascalCase / kebab-case / snake_case>",
    "class_suffixes": { /* 后缀约定 */ }
  },
  "import_order": [ /* 分组列表 */ ],
  "error_handling": {
    "style": "<exception / result-type / error-as-value>",
    "exceptions": [ /* 异常类型 */ ],
    "error_codes": [ /* 错误码模式 */ ]
  },
  "test_patterns": {
    "dir": "<test 目录>",
    "naming": "<*Test.py / test_*.py / *.spec.ts>",
    "framework": "<pytest / JUnit / Jest>"
  }
}
```

**version 2 说明**：新增 `frameworks`、`domain_models`、`api_conventions`、`databases` 字段，从 Phase 1.3.8-10 和 1.4.1 的扫描结果填充。

此文件不展示给用户，只做 diff 底稿。

---

## ===== 模式 A: 初始化流程 =====

### Phase 2: 生成 conventions.md（已废弃，改由 Phase 8 处理）

> ⚠️ 编码规范已统一由 Phase 8.2 生成到 `.chatlabs/knowledge/backend/coding-style.md`。
> `.claude/docs/` 目录仅存放 Flow 运行时文件，不存放项目特定文档。

### Phase 3: 生成模块文档（已废弃，改由 Phase 8 处理）

> ⚠️ 模块文档已统一由 Phase 8 生成到 `.chatlabs/knowledge/backend/` 目录。
> `.claude/docs/modules/` 目录不再使用。

### Phase 4: 生成 architecture.md（已废弃，改由 Phase 8 处理）

> ⚠️ 架构文档已统一由 Phase 8.3 生成到 `.chatlabs/knowledge/backend/architecture.md`。
> `.claude/docs/architecture.md` 不再使用。

### Phase 5: 生成 infra 文档（已废弃，改由 Phase 8 处理）

> ⚠️ 基础设施文档已统一由 Phase 8 生成到 `.chatlabs/knowledge/backend/` 目录。
> `.claude/docs/infra/` 目录不再使用。

### Phase 6: 生成 CLAUDE.md（入口路由表，最后执行）

路径：`CLAUDE.md`（项目根目录）

**这是每次对话的入口文件，必须精炼。**

标准结构：
```markdown
# <项目名> - 一句话描述

## 技术栈
<语言> / <框架版本> / <数据库> / <其他核心依赖>

## 构建与运行
\`\`\`bash
<构建命令>
<运行命令>
<测试命令>
\`\`\`

## 项目结构
src/
├── module-a/    # 功能描述 → .chatlabs/knowledge/backend/modules/a.md
└── module-b/    # 功能描述 → .chatlabs/knowledge/backend/modules/b.md

## 规范文档 → .chatlabs/knowledge/INDEX.md

## 关键规则（DO NOT 清单）
从 coding-style.md 提取最重要的 3-5 条禁止事项。
```

篇幅：40-80 行。不写成详细文档，只做速查索引。

### Phase 7: 生成子目录 CLAUDE.md（已废弃）

> ⚠️ 子模块约束已移至 `.chatlabs/knowledge/backend/` 对应模块文档中。

### Phase 7.5: 记录 Flow 来源（模式 A 首次初始化）

**仅在模式 A 首次执行时写入**（`.claude/.flow-source.json` 已存在则跳过）：

读取 Flow Repo 的 `.claude/MANIFEST.md`，从中提取 `flow_version`（若不存在则默认 "1.0"）。

在项目根目录创建 `.claude/.flow-source.json`：

```json
{
  "version": 2,
  "flow_repo": "<当前 Flow Repo 的绝对路径>",
  "flow_version": "<从 MANIFEST.md 提取的版本号>",
  "last_commit": "<当前 git HEAD commit hash>",
  "last_upgraded_at": "<ISO timestamp>",
  "note": "flow_version 是 Flow 的大版本号，跨版本升级走迁移流程（Phase M）。/flow-upgrade 依赖此文件定位 Flow Repo。"
}
```

用途：
- `/flow-upgrade` 依赖此文件定位 flow-repo 并判断是否跨版本
- `flow_version` 决定走增量升级（相同版本）还是迁移升级（版本不同）
- 可手动修改 `flow_repo` 指向新的 Flow Repo（项目换分支 / fork 时）
- 可手动修改 `flow_version` 以跳过迁移（仅当你确定不需要迁移步骤时）

### Phase 8: 生成 .chatlabs/knowledge/ 项目规范（从扫描结果生成）

检查 `.chatlabs/knowledge/README.md` 是否存在：
- **已存在**（模式 A 二次初始化）→ 跳过，仅在结尾提示"knowledge 目录已存在，跳过"
- **不存在** → 执行 Phase 8.1 ~ 8.9

#### Phase 8.1: 确定规范目录结构（知识库三层架构）

**知识库采用三层结构**：

| 层级 | 目录 | 回答问题 |
|------|------|---------|
| 项目层 | `knowledge/project/` | 这个项目是什么、做什么 |
| 技术层 | `knowledge/tech/` | 编码/配置/架构有哪些约束 |
| 资产层 | `knowledge/asset/` | 历史决策、归档文档在哪 |

**技术层子目录（框架/架构自适应）**：

| 检测到的架构模式 | 技术层子目录 | 说明 |
|----------------|-------------|------|
| DDD | `knowledge/tech/ddd/` | 聚合根、领域事件、限界上下文 |
| MVC | `knowledge/tech/mvc/` | Controller、Service、Repository |
| Clean Architecture | `knowledge/tech/clean/` | domain、application、infrastructure |
| Next.js App Router | `knowledge/tech/frontend/` | app/, components/, hooks/ |
| Rails | `knowledge/tech/rails/` | models/, controllers/, views/ |
| Feature-Sliced | `knowledge/tech/features/` | entities/, features/, shared/ |
| 其他后端模式 | `knowledge/tech/backend/` | 默认后端目录 |

**检测优先级**：
1. 先检测框架（Spring Boot / Flask / Express / Next.js）
2. 再检测架构模式（DDD / MVC / Clean Architecture）
3. 框架 + 架构模式决定最终目录

**必须创建的目录骨架**：

```
knowledge/
├── project/                   # 项目层
│   └── overview.md           # 项目概述（TBD 占位）
├── tech/                      # 技术层
│   ├── <pattern>/            # 框架对应目录（backend/frontend/ddd/...）
│   ├── middleware.md         # 中间件配置（TBD 占位）
│   ├── coding-conventions.md # 全栈规范（TBD 占位）
│   ├── libs/                 # 三方库文档目录
│   └── internal-systems.md     # 内部系统文档（TBD 占位）
└── asset/                     # 资产层
    ├── contract/             # 契约设计原则
    ├── frozen/              # 归档 PRD 目录
    ├── tech-proposals/       # 技术方案目录
    ├── test-cases/          # 归档测试用例目录
    ├── function-design/      # 核心功能设计方案目录
    └── tech-debt/           # 技术债台账
        └── backlog.md        # 技术债台账
```

#### Phase 8.2: 生成 coding-style.md

内容：Phase 1.3 归纳的编码规范。

输出路径：`.chatlabs/knowledge/tech/<pattern>/coding-style.md`

结构示例（实际结构根据检测到的框架调整）：
```
- 命名规范（类/函数/变量/文件）
- Import 顺序
- 错误处理模式
- API 层规范（若检测到 Web 框架）
- 测试规范
```

#### Phase 8.3: 生成 architecture.md

内容：Phase 1.5 的模块依赖关系 + Phase 1.4.1 的领域模型。

输出路径：`.chatlabs/knowledge/project/architecture.md`

结构示例：
```
- 整体架构描述（根据检测到的架构模式）
- 模块依赖关系图（Mermaid）
- 领域模型（聚合根/实体/服务）
- 模块职责表
```

#### Phase 8.4: 生成 README.md（渐进式披露索引）

内容：知识库三层结构的渐进式披露索引。

输出路径：`.chatlabs/knowledge/README.md`

结构：
```
- §0 快速入口（最常用链接）
- §1 项目层概览
- §2 技术层索引（含 Consumer 映射）
- §3 资产层索引
- §4 Flow 元规范（指向 docs/）
- §5 使用模式（渐进式披露三条规则）
- §6 三层结构说明
```

#### Phase 8.5: 生成 fitness-rules.md

内容：Phase 1.3.8-10 归纳的架构规则。

结构（根据检测到的内容动态构建）：
```
- 架构分层规则（禁止逆向依赖）
- API 层规范（若检测到）
- 领域模型规范（若检测到）
- 存储层规范（MongoDB/SQL/Redis）
- 模块依赖约束
```

#### Phase 8.6: 生成模板目录清单

输出 Agent 模板位置说明：
```
📋 Agent 模板（来自 Flow Repo）
├── .claude/templates/sprint-contract.md
├── .claude/templates/evaluator-rubric.md
└── .claude/templates/story/case-template.md
```

---

### Phase 8.7: 生成模块规范文档

对每个核心模块，生成 `.chatlabs/knowledge/tech/<pattern>/modules/<module>.md`。

内容（根据 Phase 1 扫描结果选择性填充）：
```
- Overview（模块职责描述）
- API 端点（若检测到 Web 框架）
- 领域模型（聚合根/实体）
- 存储层（集合/表/缓存）
- 依赖关系
- 文件路由
- 设计决策（保留已存在的内容）
```

生成规则：
- 每个核心模块生成一个文件
- 已存在的文件只更新可归纳的部分，保留团队手写内容
- 目录结构根据检测到的架构模式决定

---

**模式 A 增量更新说明（已存在 .chatlabs/knowledge/ 时）**：
- **不覆盖**：已存在的 md 文件（保留团队的手工填充内容）
- **只更新**：README.md 的目录树部分（替换 Phase 8.1/8.3 推断出的新模块目录，保持团队段落不变）
- **新增模块检测**：若 Phase 1 扫描发现新模块，追加到 README.md 目录树并新建骨架文件（不覆盖旧文件）

## ===== 模式 B: 增量更新流程 =====

### Phase U: 差异对比与定向更新

#### U-1: 读取旧扫描结果

读取 `.chatlabs/knowledge/.scan.json`，与 Phase 1 新扫描结果逐项对比。

#### U-2: 输出变更摘要

```
## 变更检测结果

### 检测到以下变化：
1. [变化类型]: [具体描述]
   → 影响文件: <路径>
   → 操作: [新建 / 更新 / 删除]

### 无变化（确认以下文档仍然准确）：
- <文件路径>: 内容与代码一致
```

如果无任何变化：
```
✅ 所有文档与当前代码一致，无需更新。
```
直接结束。

#### U-3: 执行定向更新

**严格只改有变化的部分**，不重写无变化的文件。

| 变化类型 | 操作 |
|---------|------|
| 新增模块 | 新建 `.chatlabs/knowledge/tech/backend/modules/<name>.md`，更新 CLAUDE.md 和 README.md |
| 删除模块 | 删除对应模块文档，从 CLAUDE.md 和 README.md 移除引用 |
| 模块内部文件变化 | 只更新对应模块文档的文件路由表 |
| 依赖关系变化 | 更新 README.md 的模块依赖部分 |
| 技术栈变化 | 更新 CLAUDE.md 技术栈行 |
| 编码规范变化 | 更新 `.chatlabs/knowledge/tech/backend/coding-style.md` 对应 section，补充新模式示例 |
| 构建/运行命令变化 | 更新 CLAUDE.md 构建与运行 section |

**保留原则**：每个模块文档中人工积累的「注意事项」和「设计决策」必须保留，不能因更新而覆盖。

---

## 输出规范

### 模式 A 结尾输出文件清单

```
📁 生成文件清单（初始化）
├── CLAUDE.md                            - 入口路由表
├── .claude/.flow-source.json            - Flow 来源记录
└── .chatlabs/knowledge/                 - 知识库（三层结构）
    ├── README.md                        - 渐进式披露索引
    ├── .scan.json                      - 扫描底稿（内部用）
    ├── project/                        - 项目层
    │   ├── overview.md                 - 项目概述
    │   ├── core-functions.md           - 核心功能流程图
    │   └── architecture.md            - 系统架构图
    ├── tech/                          - 技术层
    │   ├── backend/                   - 后端规范
    │   │   ├── coding-style.md        - 编码风格（从代码归纳）
    │   │   ├── fitness-rules.md       - 适应度函数
    │   │   └── modules/
    │   │       └── <module>.md        - 各模块文档（如有）
    │   ├── middleware.md              - 中间件配置
    │   └── coding-conventions.md       - 全栈编码规范
    └── asset/                         - 资产层
        ├── contract/
        │   └── design-principles.md    - 契约原则（模板）
        ├── frozen/                    - 归档 PRD
        ├── tech-proposals/            - 技术方案
        ├── test-cases/               - 归档测试用例
        └── tech-debt/
            └── backlog.md             - 技术债台账
```

> **注意**：`.claude/docs/` 目录不再用于存放项目文档，仅存放 Flow 运行时配置。
> 如需清理旧 `.claude/docs/` 目录，可手动删除。
```
```

### 模式 B 结尾输出更新总结

```
📁 更新总结
本次更新涉及 X 个文件：
├── ✏️ .chatlabs/knowledge/tech/backend/modules/auth.md  - 更新了文件路由表
├── ➕ .chatlabs/knowledge/tech/backend/modules/new.md   - 新增模块文档
├── ✏️ .chatlabs/knowledge/README.md                    - 更新了规范目录树（新增模块已加入）
└── ✏️ CLAUDE.md                                      - 更新了项目结构

未变更（确认仍然准确）：
├── ✅ .chatlabs/knowledge/tech/backend/coding-style.md（已存在，手工内容保留）
└── ✅ .chatlabs/knowledge/tech/backend/modules/order.md
```
