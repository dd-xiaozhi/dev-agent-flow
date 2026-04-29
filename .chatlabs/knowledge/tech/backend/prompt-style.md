# Prompt 写作规范

> Agent / Command / Skill 提示词的最小骨架与反模式清单。所有新写或重写的提示词必须按此规范。

## 共同原则

1. **YAGNI**：只写当下用得到的字段、约束、边界。不预留「未来可能」的扩展点。
2. **信任模型**：Claude 已具备通用编程、流程、决策能力。不需要被教「什么是好代码」「先思考再动手」「if/else 分支」。
3. **声明 > 程序化**：写 WHAT（输入契约、输出契约、边界、失败语义），不写 HOW（步骤 1→2→3 伪代码、ASCII 流程图、Python 函数体）。
4. **单一职责**：一个文件只承担一个能力。skill 不引用其它 skill；command/agent 不复述被调用方的内部行为。
5. **零变更日志**：禁止出现 `v1`、`v2 改造`、`新版`、`已废弃`、`向后兼容` 等字样。变更走 git history，不污染提示词。
6. **零装饰**：不堆 ASCII 框（`═══`、`┌─┐`）、不滥用 emoji 横线、不为只承载 1-2 行的内容套表格或多级标题。

## Agent 骨架

```markdown
---
name: <agent-name>
description: <一句话定位 + 核心副作用边界>
model: sonnet|haiku|opus
---

# <Agent Name>

## 核心铁律
≤3 条。每条一句话，写"必须 / 禁止"边界，不解释为什么。

## 职责边界
- 应做（≤4 条）
- 禁止（≤4 条）

## 输入契约
| 字段 | 含义 |

## 输出契约
严格 JSON 或固定 markdown 段落 schema。给最小可执行示例。

## 失败处理
| 场景 | 行为 |
```

**禁止段落**：「工作流程」「步骤 1→2→3」「与 X agent 的关系」「触发方式」「关联」。这些由调用方决定，被调用 agent 不自报家门。

## Command 骨架

```markdown
---
name: <command-name>
description: <一句话作用 + 用法签名>
---

# /<command-name>

> <一句话作用>
>
> **用法**：`/cmd [args]`

## 行为
按调用顺序的 1-3 个高层节拍。每个节拍一行，写做什么、不写怎么做。
重逻辑必须在被调 skill/agent 中，command 自己只是入口路由。

## 输入
| 参数 | 必填 | 说明 |

## 产出
- 文件路径 / 状态变更 / 副作用

## 失败处理
| 场景 | 行为 |
```

**禁止段落**：「v1 vs v2 对比」「与 X 命令的区别」「设计原则」「使用示例」（写在 README）、内嵌 Python/MCP 调用伪代码。

## Skill 骨架

```markdown
---
name: <skill-name>
description: <精准触发说明 + 触发关键词。不含版本号。说清楚 WHEN trigger / WHEN skip>
model: haiku|sonnet
---

# <Skill Name>

## 职责
一段话：做什么（不写为什么、不对比其它 skill）。

## 输入 / 输出契约
表格或最小代码块。

## 关键约束
≤6 条列表。

## 失败处理
| 场景 | 行为 |

## 关联
- 脚本 / 配置 / 报告路径（路径项，不展开行为）
```

**禁止段落**：「与 X skill 的区别」「v1 vs v2 变更」、引用其它 skill 名、嵌入完整 Python 实现、嵌入 markdown 输出模板（模板放 templates/）。

## 反模式清单（写完自检）

| 反模式 | 示例 | 应改为 |
|---|---|---|
| 步骤伪代码 | "第一步：读 X，第二步：判断 Y..." | 输入契约 + 输出契约 |
| ASCII 流程图 | `读 → 判断 → 写` 框图 | 删除，由调用方决定 |
| 跨模块描述 | "与 sync-github 不同的是..." | 删除整段 |
| 变更日志 | "v2 改为事件驱动" | 删除，走 git log |
| 装饰边框 | `═══════` 包裹输出格式 | 删除，模型不需要 |
| 教学列表 | "Conventional Commits 9 种 type 是..." | 删除，模型已知 |
| 内嵌 Python 函数体 | `def auto_judge(): ...` 完整实现 | 移到 .claude/scripts/ |
| 内嵌 markdown 模板 | 完整 review.md 30 行模板 | 移到 templates/ |
| 单行表格 | 只有 1-2 行的表格 | 改为段落 |
| 重复纪律 | 同一条规则换标题写 3 遍 | 合并为一条 |
| frontmatter description 含版本 | `description: ... (v2)` | 删除版本号 |

## 标杆参考

按本规范已经写对的范例：

- Agent：`.claude/agents/estimator.md`
- Command：`.claude/commands/tapd/tapd-ticket-sync.md`
- Skill：`.claude/skills/gc/SKILL.md`

新写或重写时优先参考这三份。

## 篇幅基线

| 类型 | 推荐行数 | 上限 |
|---|---|---|
| Agent | 60-100 | 120 |
| Command | 40-80 | 100 |
| Skill | 40-70 | 90 |

超出上限 = 几乎必然违反某条原则，需重审。
