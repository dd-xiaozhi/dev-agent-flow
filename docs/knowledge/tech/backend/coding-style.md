# 编码规范 — coding-style

> 项目类型：Claude Code 配置框架（Python hooks/scripts + Markdown agents/commands/skills/templates）。
> 无源码编译，纯配置驱动。Python 与 Markdown 各有规范，下面分述。

---

## 1. Python（hooks/ + scripts/）

### 1.1 文件头与文档

```python
#!/usr/bin/env python3
"""
<module-name> — <一句话定位>

事件：<触发时机>（仅 hook 文件需要）
行为：<核心动作>

降级（核心设计）：
  - <场景1> → <降级动作>
  - <场景2> → <降级动作>
"""
```

- 所有可执行脚本必须含 shebang `#!/usr/bin/env python3`。
- 模块 docstring 必写：第一行定位，后续列出**事件 / 行为 / 降级路径**。降级是 hook 的第一公民。

### 1.2 路径处理

- **唯一来源**：`.claude/scripts/paths.py`。Python 代码禁止硬编码路径字符串。

```python
import sys
sys.path.insert(0, ".claude/scripts")
from paths import REPORTS_DIR, STORIES_DIR
```

- 路径用 `pathlib.Path`，不要混用 `os.path`。
- `PROJECT_DIR` 优先读环境变量 `CLAUDE_PROJECT_DIR`，回退到 `Path(__file__).resolve().parents[N]`。

### 1.3 命名

| 对象 | 规范 | 示例 |
|------|------|------|
| 文件 | `kebab-case.py`（hook/skill）/ `snake_case.py`（被 import 的库） | `ctx-guard.py` / `paths.py` / `flow_advance.py` |
| 函数 | `snake_case` | `load_force_pct()` |
| 常量 | `UPPER_SNAKE_CASE` | `DEFAULT_FORCE_PCT` |
| 私有辅助 | 前缀下划线 `_helper()` | `_log_failure()` |

注：hook 文件名用 kebab-case 是历史约定（与 .claude/ 下 Markdown 命名风格统一），库文件用 snake_case 以便 Python `import`。

### 1.4 错误处理（hook 三层降级模式）

hook 是**辅助流程**，绝不能因自身失败阻断主流程。模板：

```python
def main():
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        sys.exit(0)              # 降级 0：输入坏 → 静默放行

    if not RESOURCE.exists():
        sys.exit(0)              # 降级 1：依赖缺失 → 静默放行

    try:
        result = run_probe()
    except Exception:
        log_failure(...)         # 降级 2：探针异常 → 写日志 + 静默放行
        sys.exit(0)

    if violation_detected(result):
        print(msg, file=sys.stderr)
        sys.exit(2)              # 唯一阻断：明确违规
```

唯一允许 `sys.exit(2)` 的场景：**确认违反规则**（如 context 超阈值、敏感文件访问、契约写入路径错误）。

### 1.5 失败日志

使用统一的 `log_failure()` 函数，写到 `docs/reports/hook-failures.log`：

```python
def log_failure(msg: str):
    try:
        FAILURE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(FAILURE_LOG, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass                      # 写日志也失败 → 完全吞掉
```

### 1.6 类型提示

- 公共函数签名带 type hints：`def load_force_pct() -> float:`
- 内部短函数（< 5 行）可省略。
- `from typing import Optional, Dict, List` 按需引入；Python 3.9+ 优先用内置泛型 `dict[str, int]`。

### 1.7 配置解析（YAML 三层降级）

```python
# 1. 优先 PyYAML
try:
    import yaml
    cfg = yaml.safe_load(text) or {}
except Exception:
    pass

# 2. 失败 → 朴素行解析
# 3. 再失败 → 默认值
```

体现 KISS：不要为了一个可选配置引入硬依赖。

### 1.8 注释语言

- **统一中文**（与项目其他文档一致）。
- 行内注释用中文，docstring 中文。
- 例外：API 名称、专有名词、shell 命令保留英文。

---

## 2. Markdown（agents/ + commands/ + skills/）

### 2.1 frontmatter（必须）

```markdown
---
name: <唯一标识>
description: <一句话，描述何时触发——AI 用它判断是否调用>
model: opus              # agent 专用，可选
---
```

- `description` 是 AI 触发判断的唯一依据。要写"什么场景调用"，不要写"我能做什么"。

### 2.2 文档骨架（agent / skill）

```markdown
# <Title>

> **产物路径**：详见 `.claude/artifacts-layout.md`

## 核心铁律
> **<一句话强禁令>**
> <展开说明，含理由>

## 职责边界
- ✅ <做什么>
- ❌ <不做什么>

## 输出物
<具体产物路径与内容>

## 关联
- 上游: <谁调用我>
- 下游: <我调用谁>
```

### 2.3 强调结构

- 用 `> **xxx**` 表示铁律或警示。
- 用表格表达：路径 → 作用 → 产出方 → 消费方。
- 决策树用 mermaid `flowchart TD`。
- ✅/❌ 用于职责边界正反对照。

### 2.4 禁止

- ❌ 不在 command/skill/agent/代码文件中声明"改造 xxx"或写版本变更记录（AGENTS.md 红线）。
- ❌ skill 是单一技能，**不在 skill 中关联或引用其他 skill**。
- ❌ 不在 agent/skill/command 中内联硬编码路径——引 `.claude/artifacts-layout.md`。

### 2.5 命名

- 文件名 = frontmatter 的 `name` = `kebab-case`，例：`tapd-story-start.md` ↔ `name: tapd-story-start`。
- 子目录用功能聚合：`commands/tapd/`、`commands/task/`、`commands/worktree/`。

---

## 3. 通用规则

### 3.1 SOLID / KISS / DRY / YAGNI 在本项目的体现

| 原则 | 体现 |
|------|------|
| **S** 单一职责 | 一个 hook 一个职责（ctx-guard / blocker-tracker / post-tool-linter-feedback 各管一事）；skill 不跨边界。 |
| **O** 开闭 | 流程模板用 JSON 数据化（`templates/flows/*.json`），改流程改数据不改代码。 |
| **L** 里氏替换 | hook 接口统一（stdin JSON in / exit code out），可热插拔。 |
| **I** 接口隔离 | agent description 精简到一句话，AI 不被噪音干扰。 |
| **D** 依赖倒置 | Python 依赖 paths.py 抽象，不依赖具体目录字符串。 |
| **KISS** | 没有 ORM / 没有数据库 / 没有 Web 框架——所有状态用 JSON / JSONL 文件。 |
| **DRY** | 路径 SSOT 在 paths.py；契约 SSOT 在 contract.md；流程 SSOT 在 templates/flows/*.json。 |
| **YAGNI** | 没用上的特性立刻删（参见近期 commits 删 `file_read_count` / 废弃 skill）。 |

### 3.2 Git commit 规范

参照 Conventional Commits（中文）：

- `feat:` 新功能
- `fix:` 修复 bug
- `refactor:` 重构（不变行为）
- `docs:` 文档
- `chore:` 构建/工具
- `test:` 测试

scope 用模块名：`feat(flow):` / `refactor(tapd):` / `fix(hook):`。

### 3.3 跨平台

Windows 环境 `python3` 命令不可用，统一用 `python`（参考 `fbcde6c` commit）。所有 hook 脚本头用 shebang，settings.json 中显式 `python "..."`。

---

## 4. 检查清单（写代码前对照）

- [ ] Python：用了 paths.py，没硬编码路径？
- [ ] hook：有三层降级，绝不阻断主流程？
- [ ] hook：唯一 `exit(2)` 是真正的违规？
- [ ] Markdown：frontmatter 完整，description 是触发判断而非自夸？
- [ ] skill：单一职责，没引用其他 skill？
- [ ] 文件：没有"改造记录"或版本变更说明？
- [ ] 注释：中文，与现有文档一致？
