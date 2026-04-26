---
name: fitness-run
description: 运行架构适应度函数（fitness functions），检查代码结构、契约、依赖方向。在每次代码修改前后使用，确保不引入架构违规。触发关键词：fitness、架构检查、适应度、lint、代码质量检查。
---

# Fitness Run — 架构适应度函数执行

## 使用场景

1. **编码前**：确认基线状态（跑全量）
2. **编码后**：每修改结构/新增文件，跑相关 rule
3. **PreToolUse**：Edit/Write 文件后，跑对应 fitness rule（由 `post-tool-linter-feedback.py` hook 触发）

## 使用方式

### 独立脚本（任何时候可跑）
```bash
# 跑全量
python scripts/fitness-run.py

# 只跑指定 rule
python scripts/fitness-run.py layer-boundary
python scripts/fitness-run.py openapi-lint
python scripts/fitness-run.py layer-boundary openapi-lint
```

### Claude Code 中召唤
```
/fitness-run [rule-name]
```

## 规则清单（阶段 3 已实现）

| Rule | 目的 | 退出码 |
|------|------|--------|
| `layer-boundary` | 目录依赖方向校验 | 0=pass, 1=fail |
| `openapi-lint` | OpenAPI spec 合法性 | 0=pass, 1=error |
| `handoff-lint` | handoff 工件完整性 | 0=pass, 1=fail |
| `dep-scan` | 依赖漏洞 + 过期 | 0=pass, 1=高危, 2=中危 |
| `contract-diff` | OpenAPI 破坏性变更 | 0=无破坏, 1=有破坏 |

## 报告

- 全量报告：`reports/fitness/fitness-run.json`
- 单规则日志：`reports/fitness/<rule>.log`
- **任意 rule 红 → 整体红**（`fail_fast: true` 由 config/fitness.yaml 控制）

## 与 hook 的关系

`hooks/post-tool-linter-feedback.py` 在 Edit/Write 后自动触发：
- 根据文件路径推断相关 rule
- 失败时追加候选规则到 `docs/fitness-backlog.md`

## 与 Evaluator 的边界

- **Fitness**：确定性、毫秒-秒级、结构性检查
- **Evaluator**：行为契约、端到端、分钟级测试

两者不重叠，不互相替代。

## 关联

- 脚本：`fitness/*.py`
- 项目特定规范（渐进式披露入口）：`.chatlabs/knowledge/README.md`（获取 `<module>/fitness-rules.md` 路径）
- 架构检查规则：`.chatlabs/knowledge/tech/backend/fitness-rules.md`（或其他对应模块的 fitness-rules.md）
