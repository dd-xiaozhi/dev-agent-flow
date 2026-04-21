# /init-project

> 扫描项目、生成/更新 Claude Code 项目文档体系（CLAUDE.md + 模块文档）。
>
> 典型触发场景：首次接入项目、代码架构大幅重构、现有文档过时。

## Phase 0: 模式判断

检查 `.claude/docs/.scan.json` 是否存在：

- **不存在** → `[模式 A: 初始化]`，执行 Phase 1 → Phase 7
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
.claude/docs/.scan.json
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

### Phase 2: 生成 conventions.md

路径：`.claude/docs/conventions.md`

内容顺序：
1. **命名规范**（变量/函数/文件/类/目录），每条附正例 + 反例
2. **目录组织规则**
3. **import 顺序**（附 import 分组示例）
4. **错误处理约定**
5. **注释与文档风格**
6. **测试规范**（无测试跳过）
7. **其他一致性模式**

多架构模式（monorepo 多子项目、DDD + MVC 混用）→ 分 section 分别说明。

篇幅：150-250 行。**所有示例从 Phase 1 扫描结果提取，不编造。**

### Phase 3: 生成模块文档

路径：`.claude/docs/modules/<模块名>.md`

为每个核心模块生成独立文档，标准结构：

```markdown
# <模块名>

## Overview
一句话说明模块职责。

## 文件路由
| 要修改的功能 | 主文件 | 关联文件 |
|---|---|---|
| 功能A | path/to/main.ext | path/to/related.ext |

## 依赖关系
- **依赖**：module-X（原因）、module-Y
- **被依赖**：module-Z、module-W
- **禁止依赖**：无（或明确列出）

## 注意事项
- 只写代码里看不出来的隐性约束和设计决策原因
- 不描述函数做了什么
```

每个模块文档：80-150 行。

### Phase 4: 生成 architecture.md

路径：`.claude/docs/architecture.md`

内容：
- 整体架构模式（分层 / 微服务 / monolith / monorepo）
- 模块依赖关系图（Mermaid，`phase 1` 扫描结果自动生成，不手工绘制）
- 请求处理链路（一个请求从入口到持久层的完整路径）
- 数据流向说明

篇幅：80-150 行。

依赖图自动生成示例：
```mermaid
graph LR
    module-auth --> module-db
    module-api --> module-auth
    module-api --> module-order
    module-order --> module-db
```

### Phase 5: 生成 infra 文档（条件执行）

路径：`.claude/docs/infra/`

如果存在以下文件才生成：
- `Dockerfile` / `docker-compose.yml` → 构建与容器化说明
- `.github/workflows/*.yml` / `.gitlab-ci.yml` / `Jenkinsfile` → CI/CD 流程说明
- `k8s/` / `kubernetes/` → K8s 部署说明
- `.env.example` / `*.env` → 环境变量说明

无上述文件则跳过。

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
├── module-a/    # 功能描述 → .claude/docs/modules/a.md
└── module-b/    # 功能描述 → .claude/docs/modules/b.md

## 编码规范 → .claude/docs/conventions.md
## 架构说明 → .claude/docs/architecture.md
## 模块文档 → .claude/docs/modules/

## 关键规则（DO NOT 清单）
从 conventions.md 提取最重要的 3-5 条禁止事项。
```

篇幅：40-80 行。不写成详细文档，只做速查索引。

### Phase 7: 生成子目录 CLAUDE.md（条件执行）

路径：`src/<模块>/CLAUDE.md`

只为**确实有独立且复杂的特殊约束**的模块生成（最多 2-3 个）。每个文件 10-20 行，只写该模块特有的 3-5 条注意事项。

通用模块不生成。

---

## ===== 模式 B: 增量更新流程 =====

### Phase U: 差异对比与定向更新

#### U-1: 读取旧扫描结果

读取 `.claude/docs/.scan.json`，与 Phase 1 新扫描结果逐项对比。

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
| 新增模块 | 新建 `.claude/docs/modules/<name>.md`，更新 CLAUDE.md 和 architecture.md |
| 删除模块 | 删除对应模块文档，从 CLAUDE.md 和 architecture.md 移除引用 |
| 模块内部文件变化 | 只更新对应模块文档的文件路由表 |
| 依赖关系变化 | 更新 architecture.md 依赖图 |
| 技术栈变化 | 更新 CLAUDE.md 技术栈行 |
| 编码规范变化 | 更新 conventions.md 对应 section，补充新模式示例 |
| 构建/运行命令变化 | 更新 CLAUDE.md 构建与运行 section |

**保留原则**：每个模块文档中人工积累的「注意事项」和「设计决策」必须保留，不能因更新而覆盖。

---

## 输出规范

### 模式 A 结尾输出文件清单

```
📁 生成文件清单（初始化）
├── .claude/docs/conventions.md           - 编码规范与命名约定
├── .claude/docs/modules/auth.md          - 模块：auth
├── .claude/docs/modules/order.md         - 模块：order
├── .claude/docs/architecture.md         - 架构总览与依赖图
├── .claude/docs/infra/ci.md             - CI/CD 流程（如有）
├── CLAUDE.md                            - 入口路由表
└── .claude/docs/.scan.json              - 扫描底稿（内部用）
```

### 模式 B 结尾输出更新总结

```
📁 更新总结
本次更新涉及 X 个文件：
├── ✏️ .claude/docs/modules/auth.md    - 更新了文件路由表
├── ➕ .claude/docs/modules/new.md      - 新增模块文档
├── ✏️ .claude/docs/architecture.md    - 更新了依赖关系图
└── ✏️ CLAUDE.md                       - 更新了项目结构

未变更（确认仍然准确）：
├── ✅ .claude/docs/conventions.md
└── ✅ .claude/docs/modules/order.md
```
