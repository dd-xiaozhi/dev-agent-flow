# 适应度规则 — fitness-rules

> 这是项目的**架构红线**。违反任意一条都会被 hook / `/fitness-run` skill 拦截。
> 规则按"分层 / 路径 / 编码 / Markdown / Git"分组。

---

## 1. 分层与依赖方向

### 1.1 单向依赖

```
入口（commands/）→ 编排（scripts/flow_advance）→ 执行（agents/ skills/）→ 持久化（state/ stories/ reports/）
```

| 规则 | 检查方式 |
|------|---------|
| ❌ agent 不得 import scripts/flow_advance（agent 是被调度方） | grep audit |
| ❌ skill 不得引用其他 skill | AGENTS.md 明令 + 人工 review |
| ❌ scripts/ 工具不得依赖具体 agent / skill | grep audit |
| ✅ command 可调用 agent / skill / script | 默认允许 |
| ✅ hook 可读所有产物，但只能写 reports/ 与 state/ | fitness-run skill |

### 1.2 三层目录边界

| 目录 | 写入权限 | 强制方 |
|------|---------|--------|
| `.claude/` | Flow 维护者（开发者） | git review |
| `.chatlabs/stories/<id>/source/` | **只读**（doc-librarian 也禁写） | doc-librarian.md 声明 |
| `.chatlabs/stories/<id>/contract.md` & `openapi.yaml` | doc-librarian 专属 | doc-librarian.md 声明 |
| `.chatlabs/stories/<id>/spec.md` & `cases/` | planner 专属 | （建议加 hook） |
| `.chatlabs/state/` | 系统脚本 + agent | gitignore（不进版本库） |

---

## 2. 路径规则

### 2.1 Python 必须用 paths.py

```python
# ✅ 正确
from paths import REPORTS_DIR, STORIES_DIR
report_dir = REPORTS_DIR / "fitness" / "fitness-run.json"

# ❌ 错误：硬编码
report_dir = ".chatlabs/reports/fitness/fitness-run.json"
```

| 规则 | 强度 |
|------|------|
| Python 文件硬编码 `.chatlabs/...` 字符串 | ❌ block by code review |
| Python 文件硬编码 `.claude/...` 字符串 | ⚠️ warn（除非是 Flow 自检脚本） |
| Markdown 文件硬编码路径 | ✅ allow（自然语言指令） |

### 2.2 sys.path 注入位置

每个用 paths.py 的脚本顶部：

```python
import sys
sys.path.insert(0, ".claude/scripts")
from paths import ...
```

不要把这块抽到工具函数——会被多次执行污染 sys.path。

---

## 3. Hook 规则

### 3.1 必须三层降级

任何 hook 必须能在依赖缺失时静默放行：

| 阶段 | 失败行为 |
|------|---------|
| stdin 解析失败 | `sys.exit(0)` |
| 配置文件缺失 | 用默认值 |
| 探针/外部进程失败 | 写 hook-failures.log + `sys.exit(0)` |
| 确认违规 | `sys.exit(2)` + stderr 提示 |

### 3.2 唯一阻断条件

只有以下场景 hook 才允许 `sys.exit(2)`：

- `ctx-guard.py`：context 占用 > force_pct
- `block-sensitive-files.py`：访问 `.env` / `.mcp.json` 中含 token 的字段
- `contract-path-guard.py`：已移除，改由 doc-librarian.md 声明产物位置

新增 hook 想加阻断必须 PR review。

### 3.3 失败日志统一

写到 `.chatlabs/reports/hook-failures.log`，不写其他地方。

---

## 4. Skill 规则

### 4.1 单一职责

| ✅ | ❌ |
|----|----|
| `git`：仅做 git 分支/worktree/commit-push | 复合 skill：commit + push + 更新 README + 通知群 |
| `jenkins-deploy`：仅触发构建 + 轮询 | 兼差 deploy + qa 通知 + 工时回填 |
| `tapd-pull`：仅拉取工单 | 拉取 + 同步 wiki + 起 task |

### 4.2 不引用其他 skill

AGENTS.md 明令。skill 之间通过**事件总线**协作：

```
skill-A 写 events.jsonl: {"type":"a:done"}
skill-B 启动时读 events.jsonl，按事件触发
```

### 4.3 SKILL.md 必须有

- frontmatter 含 `name` + `description`
- description 用"何时触发"句式（不是"我能做什么"）
- 触发关键词清单（中文，覆盖用户口语）

---

## 5. Agent 规则

### 5.1 职责边界明确

每个 agent 文档必含：

- **核心铁律**：一条不可违反的禁令
- **职责边界**：✅ 做什么 / ❌ 不做什么
- **输出物**：精确路径
- **不臆造**：不确定的标 `TBD`，不自编

### 5.2 单向流动

agent 链路：doc-librarian → planner → generator → evaluator。**禁止反向**：

- ❌ planner 改 contract.md
- ❌ generator 改 spec.md
- ❌ evaluator 读 generator 自评（避免污染）

---

## 6. Markdown 规则

### 6.1 frontmatter 必填

```markdown
---
name: <唯一标识>
description: <触发判断句>
---
```

缺 frontmatter 的 agent/skill/command 会被 Claude Code 忽略。

### 6.2 description 写法

- ✅ "用户说 X 时调用"
- ✅ "本地需求开工时触发"
- ❌ "强大的 XX 工具"
- ❌ "支持各种场景"

description 是 AI 触发判断的唯一依据，要写**触发条件**。

### 6.3 禁止内容

- ❌ 版本变更记录（"v2.0 改造"、"近期增加 XX"）
- ❌ 跨 skill 引用
- ❌ 内联实现细节（让 skill 内部说明）

---

## 7. Git 规则

### 7.1 Conventional Commits（中文）

```
feat(scope): 描述
fix(hook): 描述
refactor(flow): 描述
docs: 描述
chore: 描述
```

### 7.2 凭据保护

| 文件 | 规则 |
|------|------|
| `.env` | 永远 ignore |
| `.mcp.json` | committed，但**不得含明文 token**（应用环境变量替换） |
| `*.log` | ignore |
| `.chatlabs/state/` | ignore |

⚠️ 当前 `.mcp.json` 仍含明文 token（commit `09a5c3b` 引入），**待治理**。

### 7.3 危险操作需确认

`git reset --hard` / `git push --force` / `git branch -D` / `git clean -f` —— 必须用户明确同意。

---

## 8. 跨平台

- shebang 用 `#!/usr/bin/env python3`
- settings.json 中 hook 命令用 `python "..."`，**不写 `python3`**（Windows 不识别）
- 路径用 `pathlib.Path`，不写硬编码 `/`

---

## 9. 自检命令

```bash
/fitness-run              # 运行所有 fitness rule
```

输出到 `.chatlabs/reports/fitness/fitness-run.json`，由 self-reflect 消费。
