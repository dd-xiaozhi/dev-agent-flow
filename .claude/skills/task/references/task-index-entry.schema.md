# Task Index Entry Schema

> `.chatlabs/task/_index.jsonl` 与 `.chatlabs/task/archive/<YYYY-QN>/_index.jsonl` 的单行 entry 契约。
>
> **写者**：
> - `task.py new` → 初始 entry（仅 required 字段）
> - `task.py finalize` → 任务完成时回填全部字段
> - `blocker-tracker` hook → 仅更新 `blocker_count` / `updated_at`
> - `gc --archive` → 搬运 entry 到归档 jsonl
>
> **读者**：
> - `task.py search` → AI 检索接口
> - `session-start` hook → 加载当前 task 上下文
> - gc skill → orphan 清理
>
> **演进原则**：新字段一律 optional；不允许删除已存在字段；类型变更需先 deprecate 一个周期。

---

## 字段定义

| 字段 | 类型 | required | 来源 | 说明 |
|------|------|---------|------|------|
| `task_id` | str | ✅ | task.py new | 格式 `<MM-dd>-<description>`（branch 才用 ticket-short,见 git-brance-spec） |
| `story_id` | str | ✅ | task.py new | 任务目录名（可与 task_id 一致） |
| `task_type` | `"store"`\|`"bug-fix"` | ✅ | task.json 顶层 | 业务需求 / 缺陷修复 |
| `phase` | str | ✅ | task.json.workflow.phase | 当前阶段（created/doc/plan/dev/eval/done 等） |
| `complexity` | `"vibe"`\|`"plan"`\|`"spec"` | ⭕ | flow_id 反推 | 复杂度档位 |
| `flow_id` | str | ⭕ | task.json.workflow.flow.flow_id | 用了哪个 flow 模板 |
| `title` | str | ⭕ | contract.md / patch.md frontmatter | 一句话标题 |
| `one_liner` | str | ⭕ | task.json.workflow.summary.acceptance 首句 | 简短摘要 |
| `modules` | list[str] | ⭕ | task.json.workflow.summary.touched_modules | 涉及模块（粗粒度，不是文件名） |
| `contracts` | list[str] | ⭕ | spec.md / contract.md §接口段粗匹配 | 涉及 API 端点 |
| `tags` | list[str] | ⭕ | task.json.tags 或 finalize 时主 Claude 填 | 自由标签 |
| `keywords` | list[str] | ⭕ | 同上 | 自由关键词 |
| `key_decisions` | list[str] | ⭕ | task.json.workflow.summary.key_decisions | 关键决策摘要 |
| `commit_hashes` | list[str] | ⭕ | `git log --grep=<task_id> --format=%h` | 关联 commit |
| `blocker_count` | int | ✅ | blocker-tracker 维护 | 当前 blocker 数 |
| `verdict` | `"PASS"`\|`"FAIL"`\|`"ERROR"`\|`null` | ✅ | task.json.workflow.verdict | 最终验收结论 |
| `created_at` | ISO8601 | ✅ | task.py new | 创建时间 |
| `updated_at` | ISO8601 | ✅ | 任何写者 | 最后更新时间 |
| `completed_at` | ISO8601 | ⭕ | task.json.workflow.summary.completed_at | 完成时间（归档判定依据） |

---

## 示例 entry（finalize 后的完整形态）

```json
{
  "task_id": "05-20-sf-token-retry",
  "story_id": "05-20-sf-token-retry",
  "task_type": "bug-fix",
  "phase": "done",
  "complexity": "plan",
  "flow_id": "bugfix-plan",
  "title": "SF Token 限流重试机制",
  "one_liner": "PASS: 限流时退避 + 失败转人工，覆盖 3 个失败场景",
  "modules": ["account", "salesforce-gateway"],
  "contracts": ["POST /api/v1/sf/sync"],
  "tags": ["retry", "third-party"],
  "keywords": ["salesforce", "rate-limit"],
  "key_decisions": [
    "选指数退避而非固定窗口",
    "失败 3 次转人工而非永久 retry"
  ],
  "commit_hashes": ["a1b2c3d", "e4f5g6h"],
  "blocker_count": 0,
  "verdict": "PASS",
  "created_at": "2026-05-19T10:00:00+08:00",
  "updated_at": "2026-05-20T16:30:00+08:00",
  "completed_at": "2026-05-20T16:30:00+08:00"
}
```

---

## 旧 entry 兼容（task.py new 当前写入）

历史 entry 只含 `task_id / story_id / phase / keywords / created_at / updated_at / blocker_count / verdict / tags`，缺失的新字段一律视为 `null` / `[]`。`task.py search` 在过滤时跳过未填字段（不当作匹配失败）。

---

## 归档路径约定

| 状态 | 路径 |
|------|------|
| 活跃任务 entry | `.chatlabs/task/_index.jsonl` |
| 季度归档 entry | `.chatlabs/task/archive/<YYYY-QN>/_index.jsonl` |
| 跨季度归档总索引 | `.chatlabs/task/archive/_index.jsonl`（cat 各季度索引重建） |

> 注意：当前 `task.py` 仍读写 `.chatlabs/reports/tasks/_index.jsonl`（TASK_INDEX），新 entry schema 兼容该位置。后续如要迁移到 `TASK_LAYER_INDEX`（`.chatlabs/task/_index.jsonl`）需走 ADR。
