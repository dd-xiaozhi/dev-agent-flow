# 模块：skills/

## Overview

10 个原子能力，按"按需触发"语义存在。skill 与 command 的区别：command 是显式入口，skill 是 Claude 在合适时机自主调用的能力。

## API 端点

不适用。

## 领域模型

| Skill | 触发场景 | 输入 | 输出 |
|-------|---------|------|------|
| `context-reset` | context > 60% 时 | 当前 transcript | handoff 工件（reports/handoffs/） |
| `fitness-run` | 改完代码 / 主动触发 | fitness 规则 + 代码 | reports/fitness/fitness-run.json |
| `gc` | 每日 3:00 或手动 | 全 .chatlabs/ 目录 | 清理 stale 缓存 |
| `git-commit-push` | flow 模板 git-push step | 当前 diff | git commit + push |
| `jenkins-deploy` | flow 模板 deploy step | 构建参数 | 部署状态 + events.jsonl |
| `tapd-init` | 首次配置 TAPD | 用户答题 | .chatlabs/project-config.json |
| `tapd-pull` | 同步工单 | TAPD ID | 工单 JSON 缓存 |
| `tapd-consensus` | 契约评审 | contract.md | TAPD Wiki + 双向同步 |
| `tapd-subtask` | 部署后 / QA 状态变更 | cases + verdict | TAPD subtask 操作 |
| `tapd-sync` | events.jsonl 监听 | contract:frozen 事件 | 自动推 TAPD |

## 存储层

- skill 自身：`.claude/skills/<name>/SKILL.md`（提交到 git）
- skill 输出：因 skill 而异，多写到 `.chatlabs/reports/` 或 `.chatlabs/state/events.jsonl`

## 依赖关系

skill 的核心约束：**不互相引用**（CLAUDE.md 明令）。skill 间协作通过：

1. **events.jsonl** 事件总线
2. **共用产物路径**（一个 skill 写 contract.md，另一个读）
3. **scripts/paths.py** 路径常量

```
skill-A 完成 → 写 events.jsonl{type:"a:done"}
                              ↓
                       skill-B 启动时检查事件 → 触发执行
```

## 文件路由

```
skills/
├── context-reset/SKILL.md
├── fitness-run/SKILL.md
├── gc/SKILL.md
├── git-commit-push/SKILL.md
├── jenkins-deploy/SKILL.md
├── tapd-consensus/SKILL.md
├── tapd-init/SKILL.md
├── tapd-pull/SKILL.md
├── tapd-subtask/SKILL.md
└── tapd-sync/SKILL.md
```

## 注意事项（团队手写段，禁止自动覆盖）

- **单一职责**：skill 不做兼差。`git-commit-push` 不更新 README、不通知群——这些是其他 skill / 流程的事
- **不引用其他 skill**：CLAUDE.md 红线
- skill description 要写"何时触发"，含中文关键词覆盖用户口语（"提交代码"、"推到远程"等）
