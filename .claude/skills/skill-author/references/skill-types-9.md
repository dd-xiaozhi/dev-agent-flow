# 9 类 Skill 全景图

Anthropic 内部把生产级 Skills 归纳为 9 类。新 skill 先定位类型，避开重复造轮子。

---

## 9 类对照

| # | 类型 | 核心作用 | 典型场景 | 本项目已有 |
|---|------|---------|---------|-----------|
| ① | **知识/参考** | 教 Claude 正确使用内部库/CLI,避坑 | 内部库 API、设计系统规范 | `java-testing` / `python-design` |
| ② | **验证** | 自动化测试代码是否正确 | 测试驱动、契约验证 | `integration-test` / `fitness-run` |
| ③ | **数据访问** | 连接数据与监控系统 | 日志查询、API 调用 | `remote-log-fetch` / `tapd` |
| ④ | **自动化** | 压缩重复操作为单命令 | 日报生成、批量工单 | `flow-engine` / `gc` |
| ⑤ | **脚手架** | 生成符合规范的代码框架 | 新服务模板、迁移脚本 | `skill-author`（本 skill）|
| ⑥ | **代码审查** | 执行代码质量与风格检查 | 对抗性审查、测试实践 | `evaluator` (agent) + `fitness-run` |
| ⑦ | **部署** | 自动化构建、发布与回滚 | CI/CD、灰度发布 | `jenkins-deploy` |
| ⑧ | **调试** | 根据症状输出排查报告 | 告警排查、日志关联 | (部分由 `remote-log-fetch` 覆盖) |
| ⑨ | **运维** | 带防护的破坏性操作 | 清理孤儿资源、成本调查 | `gc` / `context-reset` |

---

## 新 skill 定位决策树

```
你要做的事是什么？
├─ 让 Claude 学会正确用某 lib/工具 → ① 知识/参考
├─ 自动检查代码/契约是否符合规则 → ② 验证 (注意避开 fitness-run)
├─ 从外部系统拿数据 → ③ 数据访问
├─ 把多步操作压成单命令 → ④ 自动化
├─ 生成新文件/项目骨架 → ⑤ 脚手架 (注意避开 init-project / skill-author)
├─ 检查既有代码质量 → ⑥ 代码审查 (注意避开 evaluator)
├─ 触发构建/发布 → ⑦ 部署
├─ 给现象/告警 → 输出排查报告 → ⑧ 调试
└─ 清理/回收/迁移共享资源 → ⑨ 运维 (注意 dry-run 优先)
```

---

## 高价值但常被忽略的类型

### ⑧ 调试类（本项目盲区）

**为什么有价值**：
- 把"症状 → 根因"的排查经验固化
- 每次告警都靠人脑过一遍 → 浪费时间且经验不沉淀

**示例 idea**（不强求实现）：
- `incident-triage` — 输入告警关键字 → 输出"可能根因 + 关联日志查询 + 历史 incident"
- `slow-query-analyzer` — 输入慢日志 → 输出"索引建议 + 执行计划评估"

### ② 验证类（往往被低估）

**核心价值**：把"什么算对"从隐性变显性。
- 不是测试代码本身（那是 `fitness-run`），而是测试"业务/契约是否被遵守"
- 例如 `contract-validator` — 输入 spec.md + API 实现 → 输出"哪些 endpoint 缺失/类型不符"

---

## 不建议新增的类型（本项目已饱和）

| 类型 | 已有覆盖 | 新增风险 |
|------|---------|---------|
| ④ 自动化 | flow-engine（流程）/ gc（清理）/ tapd（工单）几乎覆盖所有 | 重复造轮子 |
| ⑤ 脚手架 | init-project + task.py create + skill-author 已覆盖 | 散乱 |
| ⑥ 代码审查 | evaluator agent Phase 1 + fitness-run rule | 维护成本高 |

---

## 命名建议

| 类型 | 推荐前缀 | 例子 |
|------|---------|------|
| 知识 | `<lib>-<topic>` | `python-design` / `java-testing` |
| 验证 | `<target>-verify` 或 `verify-<target>` | `integration-test` / `fitness-run` |
| 数据访问 | `<source>-<action>` | `remote-log-fetch` / `tapd` |
| 自动化 | 动词或动名词 | `flow-engine` / `gc` |
| 脚手架 | `<X>-author` 或 `<X>-init` | `skill-author` / `init-project` |
| 代码审查 | `<X>-review` | `code-review`（未建）|
| 部署 | `<target>-deploy` | `jenkins-deploy` |
| 调试 | `<X>-triage` 或 `<X>-analyzer` | （未建）|
| 运维 | `<X>` 动词 | `gc` / `context-reset` |

---

## 总结口诀

> **先看 9 类，再看本项目已有，最后才动手新建。**
> 强行造 skill 不如改造现有 skill。
