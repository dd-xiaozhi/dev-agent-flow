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

检查 `.chatlabs/spec/.scan.json` 是否存在：

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

从代码中提取正例，不编造。扫描样本：每个模块最多 5 个文件。

### 1.4 核心模块识别

扫描全部源码文件（排除 `node_modules/`、`__pycache__/`、`vendor/`、`dist/`），按以下标准识别核心模块：

1. **被依赖次数 ≥ 2**（全局 grep `from <module> import` / `require('./<module>')` / `import <module>`）
2. **包含入口逻辑**（含 `main` / `app` / `server` 关键词）
3. **代码量前 30%**（行数统计，排除空行和注释）

取并集，每条标准至少有一个模块。

### 1.5 模块依赖关系

对每个核心模块，用正则提取其 import/require 语句，建立有向关系：

```python
# 伪结构，存入 .scan.json
{
  "modules": {
    "module-a": {
      "files": ["src/a/foo.py", "src/a/bar.py"],
      "imports": ["module-b", "module-c"],
      "imported_by": ["module-b"]
    }
  }
}
```

提取规则（按语言）：
- **Python**: `^import |^from ` 后跟非 `\.` 开头的模块名
- **TypeScript/JavaScript**: `^import .+ from ['"]([^'"]+)['"]` 和 `require\(['"]([^'"]+)['"]\)`
- **Go**: `^\t?import \"?([a-zA-Z0-9_/]+)`（忽略标准库 `^std` / `^golang`）
- **Java**: `^import |^import static `

忽略测试文件（`*_test.*` / `*.test.*`）的依赖关系，避免 devDeps 污染。

### 1.6 功能→文件映射

对每个核心模块，列举其文件列表，手动标注主要功能（从文件名推断 + 扫描文件顶部的注释/docstring）。格式：

```
src/
├── module-auth/          # 认证授权
│   ├── auth.py           # 登录/登出/JWT 颁发
│   └── permissions.py    # RBAC 权限检查
```

### 1.7 扫描结果持久化

将 Phase 1 全部结果写入：

```
.chatlabs/spec/.scan.json
```

结构：
```json
{
  "version": 1,
  "scanned_at": "<ISO timestamp>",
  "project_root": "<绝对路径>",
  "tech_stack": { "language": "Python", "version": "3.11", "framework": "FastAPI" },
  "source_root": "src/",
  "modules": { /* 模块名 → {files, imports, imported_by, functions} */ },
  "naming_conventions": { /* 从代码归纳 */ },
  "import_order": [ /* 分组列表 */ ],
  "error_handling": { "style": "result-type", "examples": [] },
  "test_patterns": { "dir": "tests/", "naming": "test_*.py", "framework": "pytest" }
}
```

此文件不展示给用户，只做 diff 底稿。

---

## ===== 模式 A: 初始化流程 =====

### Phase 2: 生成 conventions.md（已废弃，改由 Phase 8 处理）

> ⚠️ 编码规范已统一由 Phase 8.2 生成到 `.chatlabs/spec/backend/coding-style.md`。
> `.claude/docs/` 目录仅存放 Flow 运行时文件，不存放项目特定文档。

### Phase 3: 生成模块文档（已废弃，改由 Phase 8 处理）

> ⚠️ 模块文档已统一由 Phase 8 生成到 `.chatlabs/spec/backend/` 目录。
> `.claude/docs/modules/` 目录不再使用。

### Phase 4: 生成 architecture.md（已废弃，改由 Phase 8 处理）

> ⚠️ 架构文档已统一由 Phase 8.3 生成到 `.chatlabs/spec/backend/architecture.md`。
> `.claude/docs/architecture.md` 不再使用。

### Phase 5: 生成 infra 文档（已废弃，改由 Phase 8 处理）

> ⚠️ 基础设施文档已统一由 Phase 8 生成到 `.chatlabs/spec/backend/` 目录。
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
├── module-a/    # 功能描述 → .chatlabs/spec/backend/modules/a.md
└── module-b/    # 功能描述 → .chatlabs/spec/backend/modules/b.md

## 规范文档 → .chatlabs/spec/INDEX.md

## 关键规则（DO NOT 清单）
从 coding-style.md 提取最重要的 3-5 条禁止事项。
```

篇幅：40-80 行。不写成详细文档，只做速查索引。

### Phase 7: 生成子目录 CLAUDE.md（已废弃）

> ⚠️ 子模块约束已移至 `.chatlabs/spec/backend/` 对应模块文档中。

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

### Phase 8: 生成 .chatlabs/spec/ 项目规范（从扫描结果生成）

检查 `.chatlabs/spec/INDEX.md` 是否存在：
- **已存在**（模式 A 二次初始化）→ 跳过，仅在结尾提示"spec 目录已存在，跳过"
- **不存在** → 执行 Phase 8.1 ~ 8.4

#### Phase 8.1: 确定模块目录

根据 Phase 1 的技术栈扫描结果推断模块目录：

| 检测到 | 创建目录 | 说明 |
|--------|---------|------|
| `pom.xml` / `build.gradle` | `backend/` | Java / JVM 后端 |
| `go.mod` | `backend/` | Go 后端 |
| `pyproject.toml` / `setup.py` | `backend/` | Python 后端 |
| `package.json` + `src/` + React/Vue | `frontend/` | 前端 |
| TypeScript（无框架）| `frontend/` | 前端 |
| 任何后端 | `backend/` | 必须 |
| 任何前端 | `frontend/` | 可选 |
| — | `contract/` | 默认，契约原则 |
| — | `product/` | 默认，产品术语 |

#### Phase 8.2: 生成 backend/coding-style.md（从扫描结果）

**从 Phase 1.3 归纳结果生成，不是 TBD 骨架**：

```markdown
# 后端编码风格

> **项目**: <<PROJECT_NAME>>
> **技术栈**: <<TECH_STACK>>
> **最后更新**: <<TODAY>>

## 1. 命名规范

### 1.1 类/类型命名
| 类型 | 规范 | 示例 |
|------|------|------|
<<CLASS_NAMING_ENTRIES>>
```

**命名规范从 Phase 1.3 提取**：
- 扫描样本代码，提取变量/函数/类/文件/目录的命名模式
- 区分正面示例（代码中高频出现的模式）和反面示例（罕见的反模式）
- 每个模式标注"从代码归纳"而非"编造"

**Import 顺序从 Phase 1.3 提取**：
- 列出代码中的 import 分组顺序
- 标注 stdlib → 第三方 → 本地的分组

**错误处理从 Phase 1.3 提取**：
- 列出代码中的异常类型和错误返回值模式
- 提取实际的错误码/错误消息示例

#### Phase 8.3: 生成 backend/architecture.md（从扫描结果）

**从 Phase 1.5 依赖关系 + Phase 1.6 功能映射生成**：

```markdown
# 架构总览与依赖关系

> **项目**: <<PROJECT_NAME>>
> **技术栈**: <<TECH_STACK>>

## 1. 整体架构

<<ARCHITECTURE_OVERVIEW>>

## 2. 模块依赖关系图

```mermaid
graph TB
<<MERMAID_DEPENDENCY_GRAPH>>
```

## 3. 模块职责

| 模块 | 职责 | 关键依赖 |
|------|------|---------|
<<MODULE_MATRIX_ENTRIES>>
```

#### Phase 8.4: 生成 INDEX.md（渐进式披露入口）

```markdown
# <<PROJECT_NAME>> — 项目规范索引

> **技术栈**: <<TECH_STACK>>
> Agent 读这里获取整体结构，按需 Read 子文件。

## 规范目录树

```
.chatlabs/spec/
├── backend/                    # 后端规范（<<TECH_STACK>>）
│   ├── coding-style.md         # 编码风格（从代码归纳）
│   ├── fitness-rules.md        # 架构适应度函数清单
│   └── architecture.md         # 架构总览、模块依赖
├── frontend/                   # 前端规范（若无前端代码则删除）
├── product/                    # 产品规范
│   └── domain-terminology.md   # 领域术语（TBD）
└── contract/                   # 契约规范
    └── design-principles.md    # 契约设计原则（TBD）
```

## Consumer 映射（Agent 按角色读取）

| Agent | 主要读取 |
|-------|----------|
| doc-librarian | `contract/**`、`product/**` |
| planner | `backend/architecture.md` |
| generator | `backend/coding-style.md`、`backend/fitness-rules.md` |
| evaluator | `contract/**` |

## 使用模式（渐进式披露）

1. Read `.chatlabs/spec/INDEX.md` 获取目录结构
2. 按 Agent 角色 + 当前任务上下文，只 Read 相关模块
3. **禁止**硬编码路径，必须从 INDEX.md 解析
```

---

### Phase 8.5: 生成 fitness-rules.md 骨架（如后端项目）

若检测到后端技术栈（Java/Go/Python/Node.js），生成 `.chatlabs/spec/backend/fitness-rules.md`：

```markdown
# 后端架构适应度函数

> 架构规则是防止技术债积累的最后防线。每次引入违规前权衡，引入后立刻修复。

## 一、已实现的检查

| 规则名 | 检查内容 | 运行时机 |
|--------|---------|---------|
| `layer-boundary.sh` | Controller/Service/Repository 三层依赖方向正确 | 每次文件变更 |
| `openapi-lint.sh` | openapi.yaml 合法 + 与代码 endpoint 一致 | 修改 endpoint 后 |

## 二、Layer Boundary 规则

```
controller → service → repository → domain
                  ↕
              config / exception（允许）
```

## 三、TBD

- [ ] 根据项目实际情况补充 fitness 规则

## 关联
- Fitness 检查脚本：`.claude/fitness/*.sh`
```

---

### Phase 8.6: 生成模板目录清单（Agent 所需模板）

**不生成模板文件**（模板在 Flow Repo 的 `.claude/templates/` 中），但在 `init-project` 结尾输出模板位置说明：

```
📋 Agent 模板（来自 Flow Repo）
├── .claude/templates/sprint-contract.md        # Generator 收尾谈判用
├── .claude/templates/evaluator-rubric.md       # Evaluator 评分标准
└── .claude/templates/story/case-template.md    # Planner 生成 case 用
```

---

---

**模式 A 增量更新说明（已存在 .chatlabs/spec/ 时）**：
- **不覆盖**：已存在的 md 文件（保留团队的手工填充内容）
- **只更新**：INDEX.md 的目录树部分（替换 Phase 8.1/8.3 推断出的新模块目录，保持团队段落不变）
- **新增模块检测**：若 Phase 1 扫描发现新模块，追加到 INDEX.md 目录树并新建骨架文件（不覆盖旧文件）

## ===== 模式 B: 增量更新流程 =====

### Phase U: 差异对比与定向更新

#### U-1: 读取旧扫描结果

读取 `.chatlabs/spec/.scan.json`，与 Phase 1 新扫描结果逐项对比。

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
| 新增模块 | 新建 `.chatlabs/spec/backend/modules/<name>.md`，更新 CLAUDE.md 和 INDEX.md |
| 删除模块 | 删除对应模块文档，从 CLAUDE.md 和 INDEX.md 移除引用 |
| 模块内部文件变化 | 只更新对应模块文档的文件路由表 |
| 依赖关系变化 | 更新 INDEX.md 的模块依赖部分 |
| 技术栈变化 | 更新 CLAUDE.md 技术栈行 |
| 编码规范变化 | 更新 `.chatlabs/spec/backend/coding-style.md` 对应 section，补充新模式示例 |
| 构建/运行命令变化 | 更新 CLAUDE.md 构建与运行 section |

**保留原则**：每个模块文档中人工积累的「注意事项」和「设计决策」必须保留，不能因更新而覆盖。

---

## 输出规范

### 模式 A 结尾输出文件清单

```
📁 生成文件清单（初始化）
├── CLAUDE.md                            - 入口路由表
├── .claude/.flow-source.json            - Flow 来源记录
└── .chatlabs/spec/                     - 项目特定规范（从扫描结果生成）
    ├── .scan.json                       - 扫描底稿（内部用）
    ├── INDEX.md                         - 规范入口（渐进式披露）
    ├── backend/
    │   ├── coding-style.md             - 编码风格（从代码归纳）
    │   ├── architecture.md              - 架构文档（从扫描生成）
    │   └── modules/
    │       └── <module>.md             - 各模块文档（如有）
    ├── contract/
    │   └── design-principles.md         - 契约原则（模板）
    └── product/
        └── domain-terminology.md        - 领域术语（模板）
```

> **注意**：`.claude/docs/` 目录不再用于存放项目文档，仅存放 Flow 运行时配置。
> 如需清理旧 `.claude/docs/` 目录，可手动删除。
```
```

### 模式 B 结尾输出更新总结

```
📁 更新总结
本次更新涉及 X 个文件：
├── ✏️ .chatlabs/spec/backend/modules/auth.md  - 更新了文件路由表
├── ➕ .chatlabs/spec/backend/modules/new.md   - 新增模块文档
├── ✏️ .chatlabs/spec/INDEX.md                 - 更新了规范目录树（新增模块已加入）
└── ✏️ CLAUDE.md                               - 更新了项目结构

未变更（确认仍然准确）：
├── ✅ .chatlabs/spec/backend/coding-style.md（已存在，手工内容保留）
└── ✅ .chatlabs/spec/backend/modules/order.md
```
