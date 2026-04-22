---
name: tech-debt-backlog
description: 技术债/Blocker 本地持久化存储。Generator sprint-review 自动写入，供后续 AI 直接读取优化工作流。
type: backlog
---

# Tech Debt Backlog

> **定位**：技术债和 Blocker 的本地持久化存储。所有 AI agent 直接读取此文件优化工作流，**不写入 TAPD**（TAPD 仅处理业务相关事项）。
>
> **写入来源**：
> - Generator sprint-review 后自动追加
> - 每个 task 的 `.claude/reports/tasks/<task_id>/blockers.md` 合并
> - AI 在执行中发现工作流改进点时主动追加

## 格式规范

每条记录包含：

```markdown
### [{category}] {title}
- **发现时间**: {YYYY-MM-DD}
- **发现来源**: {task_id} / {hook-name} / manual
- **问题描述**: {what}
- **根因分析**: {why}
- **影响范围**: {which workflow/tool/language}
- **改进动作**: {what to do}（对应文件或约束）
- **状态**: open | in-progress | resolved
- **resolved_at**: {YYYY-MM-DD}（resolved 时填写）
```

## 分类标签

| Tag | 含义 |
|-----|------|
| `[环境-编译]` | 构建/编译失败 |
| `[环境-依赖]` | 依赖配置问题 |
| `[流程-规划]` | 规划阶段遗漏或不足 |
| `[流程-执行]` | 执行阶段走了弯路 |
| `[流程-验收]` | Evaluator 验收失败模式 |
| `[规范-代码]` | 代码规范问题（如注释混入流程信息） |
| `[规范-文档]` | 文档结构或内容问题 |
| `[规范-TAPD]` | TAPD 集成问题 |
| `[工具-hook]` | Hook 脚本问题 |
| `[信息-技术决策]` | 需要 Tech Lead 决策（但应在规划阶段确认） |

---

<!-- entries_start -->
<!-- 此行以上为 header，请在此行以下追加新条目 -->

<!-- entries_end -->
