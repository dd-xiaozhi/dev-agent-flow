---
name: tapd-story-start
description: 主流程入口命令——从 TAPD 工单（URL 或 ID）一键开工或重入。解析入参、拉取/刷新缓存、归档 description 版本、分配 story/task、路由 doc-librarian。
model: opus
---

# /tapd-story-start

> 从 TAPD 工单（URL 或 ID）一键开工或重入。
>
> **用法**：`/tapd-story-start <ticket_id | tapd_url>`

## 行为

### 第一步：入参解析

1. 入参含 `tapd.cn` 或 `http(s)://` → 用正则 `(\d{10,})` 从路径提取 ticket_id
2. 入参为纯数字 → 直接作为 ticket_id
3. 其它格式 → 输出用法，退出

### 第二步：刷新本地缓存

委派给 `tapd-pull` skill 拉 `<ticket_id>` 最新工单数据，写 `.chatlabs/tapd/tickets/<ticket_id>.json`（保留 `local_mapping` / `subtasks` / `comments_cache`）。校验 `entity_type == "stories"`。

### 第三步：分支判断

读 `ticket.local_mapping.story_id`：

| 情形 | story_id | 分支 |
|------|----------|------|
| 未关联 | null | first-start |
| 已关联 | 非 null | re-entry |

**编排层不做 description 语义对比**，由 doc-librarian 在重入路径自行判断变更。

### 第四步：first-start

1. 用 `ticket_id` 作为 `story_id`，派生 `store_name = <ticket_id>-<name slug 前 30 字>`
2. 把 `fields_cache.description` 与元信息归档到 `.chatlabs/stories/<ticket_id>/source/tapd-ticket-<ticket_id>-<ts>.md` 和 `tapd-meta-<ts>.md`（强制带时间戳，不覆盖历史）
3. 调 `/task-new <ticket_id> --trigger first-start` 分配 task_id
4. 调 `python .claude/scripts/flow_advance.py --story-id <ticket_id> init --flow-id tapd-full --task-id <task_id>` 实例化 flow 子对象
5. 路由 `doc-librarian`，传 `story_id / task_id / contract_path / source_dir`（不传 TAPD 上下文，agent 自行从 source/ 读）

### 第五步：re-entry

委派给 `python .claude/scripts/flow_advance.py --story-id <story_id> check` 读 flow 状态：

- `is_terminal == true` → 输出 "已完成"，提示 `--force` 重启
- `is_terminal == false` → 调 `/task-resume <最近 task_id>`，由其按 `flow.current_step` 路由
- TAPD description 修改时间晚于本地 source 最新文件 → 走变更检查：归档新 source、`/task-new --trigger requirement-change-check`、创建 checklog（trigger=requirement_change）、路由 doc-librarian
- 以上都不命中 → 输出诊断信息（最近 task / phase / verdict / contract version）+ 候选操作清单

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<ticket_id \| tapd_url>` | 是 | TAPD 工单 ID（纯数字）或工单 URL |

## 产出

- 更新 `.chatlabs/tapd/tickets/<ticket_id>.json`
- first-start：新建 `.chatlabs/stories/<ticket_id>/`、`source/*.md`、TASK 记录、初始化 flow、启动 doc-librarian
- re-entry：按 flow 状态委派 `/task-resume` 或归档新 source 后路由 doc-librarian

## 失败处理

| 场景 | 行为 |
|------|------|
| 入参格式无法识别 | 输出用法提示，退出 |
| TAPD 拉取失败（404/权限/网络） | 输出错误原因，退出；不创建本地记录 |
| `entity_type` 非 stories | 拒绝，输出 hint |
| `/task-new` 失败 | 回滚 `local_mapping.story_id` 写入；保留已归档 source |
| contract.md frontmatter 损坏 | 输出错误 + 提示手动修复，退出 |

## 关联

- Skill：`.claude/skills/tapd-pull/SKILL.md`
- 下游：`/task-new`、`/task-resume`、`/tapd-consensus-fetch`、`doc-librarian` agent
- 配置：`.chatlabs/project-config.json`
