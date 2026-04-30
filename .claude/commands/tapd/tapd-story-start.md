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

1. 生成 `story_id = {MM-dd}-{title-slug}`：
   - 取 `ticket.name` → LLM 翻译为英文 → 转小写 → 空格转 `-` → 仅保留 `[a-z0-9-]` → 截断 30 字符
   - 翻译失败或为空 → `untitled`
   - 同名冲突时追加后缀 `-2`、`-3`
   - 例：ticket.name = "用户登录支持微信扫码" → `story_id = 04-30-wechat-login`
2. 把 `ticket_id` 写入 `local_mapping.tapd_ticket_id`，`local_mapping.story_id = <new_story_id>`（外部关联键保留）
3. 把 `fields_cache.description` 与元信息归档到 `.chatlabs/stories/<story_id>/source/tapd-ticket-<ticket_id>-<ts>.md` 和 `tapd-meta-<ts>.md`（强制带时间戳，不覆盖历史）
4. 调 `/task-new <story_id> --trigger first-start` 分配 task_id（如 `TASK-04-30-wechat-login-01`）
5. 调 `python .claude/scripts/flow_advance.py --story-id <story_id> init --flow-id tapd-full --task-id <task_id>` 实例化 flow 子对象
6. 路由 `doc-librarian`，传 `story_id / task_id / contract_path / source_dir`（不传 TAPD 上下文，agent 自行从 source/ 读）

> **稳定性**：首次生成的 slug 写入 `meta.json.title_slug`，后续重入操作只读不重译。

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
- first-start：新建 `.chatlabs/stories/<story_id>/`（story_id = `{MM-dd}-{title-slug}`）、`source/*.md`、TASK 记录、初始化 flow、启动 doc-librarian
- re-entry：按 flow 状态委派 `/task-resume` 或归档新 source 后路由 doc-librarian

## 失败处理

| 场景 | 行为 |
|------|------|
| 入参格式无法识别 | 输出用法提示，退出 |
| TAPD 拉取失败（404/权限/网络） | 输出错误原因，退出；不创建本地记录 |
| `entity_type` 非 stories | 拒绝，输出 hint |
| `/task-new` 失败 | 回滚 `local_mapping.story_id` 写入；保留已归档 source |
| LLM 翻译失败 | 兜底用 `untitled` 作为 title-slug |
| contract.md frontmatter 损坏 | 输出错误 + 提示手动修复，退出 |

## 关联

- Skill：`.claude/skills/tapd-pull/SKILL.md`
- 下游：`/task-new`、`/task-resume`、`/tapd-consensus-fetch`、`doc-librarian` agent
- 配置：`.chatlabs/project-config.json`
