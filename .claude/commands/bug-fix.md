---
name: bug-fix
description: Bug 修复统一入口。支持指定 TAPD bug URL 单独修复，或批量拉取所有未处理 bug。单 bug 走单分支（bugfix/hotfix），多 bug 用 worktree 并行隔离。按 bug 复杂度自动路由 vibe/plan/spec 三档。修复完合并到对应 store 分支或用户选定分支，调 jenkins-deploy 部署，TAPD 工时回填并转待测试。
model: sonnet
---

# /bug-fix

> Bug 修复统一入口。**用户只描述意图（指定 bug 或批量修复），路由层自动决定单/多分支、复杂度档位、合并目标、TAPD 回填。**

## 用法

```
/bug-fix <tapd_bug_url>           # 指定 TAPD bug 链接（单个修复）
/bug-fix --all                    # 拉取所有未处理 TAPD bug，批量修复
/bug-fix --local "<描述>"          # 本地 bug（无 TAPD 关联）
```

## 第一步：输入解析与 bug 集合获取

> **命名约定**：`bug_id == task_id == 目录名 == {MM}-{dd}-{slug}`（与 /tapd start、/story-start 同一套规则）。
> TAPD 的纯数字 ticket ID 不再作为目录名，而是单独存到 `task.json.tapd.ticket_id`。

| 形态 | 行为 |
|------|------|
| TAPD URL（含 `tapd.cn` 或 `http(s)://`） | 正则 `(\d{10,})` 提取 `tapd_ticket_id` → 调 tapd skill pull --type bug --id=<tapd_ticket_id> → 由 bug.title LLM 翻译生成 slug → 拼出 `bug_id = {MM}-{dd}-{slug}` |
| `--all` | 调 tapd skill pull --type bug --all（过滤 status != 完成） → 对每条 bug 重复上述 slug 生成 |
| `--local "<描述>"` | 不调 TAPD，从描述首行生成 slug → `bug_id = {MM}-{dd}-{slug}`（**无 `local-` 前缀**） |

**slug 生成规则**（与 /tapd start、/story-start 完全一致）：
1. 取 bug 标题或描述首行作为源
2. LLM 翻译为英文 → 转小写 → 空格转 `-` → 仅保留 `[a-z0-9-]` → 截断 30 字符
3. 翻译失败或为空 → 用 `bug-untitled`
4. 同名命中（扫描 `.chatlabs/task/bug-fix/`）→ 追加 `-2`、`-3` 后缀

每个 bug 拉取后写入 `.chatlabs/task/bug-fix/<bug_id>/`：
- `description.md`：bug 描述（TAPD 工单或用户输入）
- `task.json`：由 `python .claude/scripts/task.py new <bug_id> --name <slug>` 创建 task 骨架，再由 TaskJsonStore 补齐 `task_type="bug-fix"` + `bug_fix` section + `tapd.ticket_id`（数字）

**task.py new 调用**：
```bash
slug="${bug_id#??-??-}"
python .claude/scripts/task.py new "<bug_id>" --name "$slug" --trigger defect-fix
```
返回的 `task_id` 与 `bug_id` 完全一致（如 `05-21-login-redirect-fail`）。

## 第二步：bug 数量判定分支模式

```
count == 1 → 单分支模式
count >  1 → worktree 多分支模式（自动并行）
```

> 由用户用参数覆盖：传 `--worktree` 强制 worktree，传 `--single` 强制单分支；不传则按数量自动判定。

## 第三步：复杂度分级（每个 bug 独立判定）

主 Claude 读 bug 描述后判定档位：

| 档位 | 判定条件 | flow_id |
|------|--------|---------|
| **vibe** | 单点修改、常量/文案/明显笔误 | `bugfix-vibe` |
| **plan** | 多步骤逻辑、≤ 2 文件、有判断分支 | `bugfix-plan` |
| **spec** | 跨模块 / 涉及契约变更 / severity=critical | `bugfix-spec` |

判定不确定时 → AskUserQuestion 让用户选档位。

写回 `task.json.bug_fix.fix_mode` 与 `dev_mode`。

## 第四步：分支创建

> **配置驱动**：source 与 merge_targets 完全由 `.chatlabs/project-config.json.git.branches.<bugfix|hotfix>` 决定，命令只负责选 `branch-type`。

### 4.1 branch-type 选择

```
1. bug.severity == "critical" 或 标签含 "线上"/"production" → branch-type = "hotfix"
2. 其他情况 → branch-type = "bugfix"
```

写入 `task.json.bug_fix.branch_type`。

### 4.2 linked-story 反查（仅用于后续合并目标，不影响 source）

仅当 TAPD bug 含 `relate_story_id` 或本地传入 `--linked-story-id`：
- 调 `TaskJsonStore.find_by_story_id` 搜 store/ 与 bug-fix/，读 `task.json.git.branch`
- 找到 → 写入 `task.json.bug_fix.linked_story_id` 与 `linked_story_branch`（供第六步 merge_targets 决策）
- 找不到 → 字段留 null，不阻塞流程

### 4.3 单分支模式

调用 ensure-branch（**source 由 config 决定**，bugfix→`current`、hotfix→`master`）：

```bash
python .claude/skills/git/scripts/ensure_branch.py <branch-type>/<bug_id> --branch-type <bugfix|hotfix>
```

绑定到 task.json.git（`--source-branch` / `--merge-targets` 省略，task.py 走 config 读）：

```bash
python .claude/scripts/task.py bind-branch <task_id> \
  --branch <返回的 branch> \
  --branch-type <bugfix|hotfix>
```

补全 `task.json.bug_fix`：
- `branch_type`：`"bugfix" | "hotfix"`（来自 4.1）
- `linked_story_id` / `linked_story_branch`：来自 4.2（无关联留 null）
- `source_branch_decision`：`"config:<branch_type>"`（语义化决策已下沉至 config，此字段仅记录"由 config 解析"）

ensure-branch 失败：
- 工作区脏 / 分支冲突 → 阻塞
- `source unresolved`（config 缺 git section） → `AskUserQuestion` 让用户在 `candidates` 中选一个 → `--from <选择>` 显式调用

### worktree 多分支模式

对每个 bug 调用 git skill：
```
action: worktree-create
type: bugfix（或 hotfix，按 severity）
description: <bug_id>          # 已是 {MM}-{dd}-{slug} 格式
ticket_id: <tapd_ticket_id>    # TAPD 数字 ID；本地 bug 留空
```

输出含 `worktree_path` → 写回 `task.json.git.worktree_path`，便于主流程进入隔离工作树执行修复。

## 第五步：实例化 flow + 实施修复

为每个 bug 调用：
```bash
python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <bug_id> init \
  --flow-id <bugfix-{mode}> \
  --task-id <task_id>
```

然后按 dev_mode 行动：
- **vibe**：直接 Read 受影响文件 → Edit 改修 → 完成调 `/flow-advance edit`
- **plan**：TaskCreate 拆分修复步骤 → Edit 各步骤 → 完成调 `/flow-advance edit`
- **spec**：路由到 doc-librarian（更新契约，标注本次修复点）→ 后续 planner/generator/evaluator 链路

worktree 模式下，每个 bug 在自己的 worktree 路径下执行（主 Claude 切 cwd 或并发触发多个隔离 session）。

## 第六步：合并目标决策

修复实施完毕、git-push 步骤完成后，进入 merge step。先决定合并目标：

```
1. 读 task.json.bug_fix.linked_story_id
2. 若非空：
   - 查 .chatlabs/task/store/<linked_story_id>/task.json.git.branch → 作为合并目标
3. 若为空：
   - 列出所有活跃 feature/* 分支（git branch --list 'feature/*' --no-merged dev）
   - AskUserQuestion 让用户从候选中选择，或选 "直接合 dev"
4. hotfix 类型特例：默认目标 = ["master", "dev"]（不再询问），完成后 master → dev 回流
```

把决策结果写回 `task.json.bug_fix.target_branch` 与 `task.json.git.merge_targets`。

## 第七步：合并 → 部署 → TAPD 回填

flow 步骤会自动顺序触发：

1. **merge**：调 git skill `action=merge source=<分支> targets=<决策结果>`
2. **deploy**：调 jenkins-deploy（读 `task.json.git.branch` 作为部署分支）
3. **tapd-close**（仅有 TAPD 关联时）：
   - 调 tapd skill `subtask emit`（如未派发）+ `subtask close`（推到待测试）
   - 工时回填：主流程模型按 task.json 的 audit 时间窗 + git diff 自评耗时

worktree 模式收尾：调 git skill `action=worktree-remove worktree_path=<worktree_path>` 清理。

## 输入参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `<tapd_bug_url>` | 三选一 | 单个 TAPD bug 链接或纯数字 ID |
| `--all` | 三选一 | 拉取所有未处理 bug，批量修复 |
| `--local "<描述>"` | 三选一 | 本地 bug，无 TAPD 关联 |
| `--worktree` | 否 | 强制 worktree 模式（即使只有 1 个 bug） |
| `--single` | 否 | 强制单分支模式（即使有多个 bug，串行处理） |
| `--mode` | 否 | 强制档位 `vibe`/`plan`/`spec`（绕过自动判定） |

## 产出

- `.chatlabs/task/bug-fix/<bug_id>/task.json`（bug_id = `{MM}-{dd}-{slug}`，每个 bug 一份，4 个 section 都填充；`task.json.tapd.ticket_id` 存 TAPD 数字 ID）
- `.chatlabs/task/bug-fix/<bug_id>/description.md`
- `bugfix/<bug_id>` 或 `hotfix/<bug_id>` 分支（单分支模式，bug_id 本身已含日期+slug）
- `.chatlabs/worktrees/<bug_id>/` git worktree（多分支模式）
- TAPD bug 状态推到"待测试"（仅有 TAPD 关联）
- TAPD 工时回填

## 失败处理

| 场景 | 行为 |
|------|------|
| TAPD bug URL 无效 / 无权限 | 报错退出，不创建 task 目录 |
| `--all` 无未处理 bug | 输出"无可处理 bug"，正常退出 |
| git skill create 失败（工作区脏 / 分支已存在） | 阻塞，提示用户处理 |
| worktree 路径冲突 | 报错，提示先用 worktree-remove 清理或换 slug |
| 修复实施过程出错 | 保留 task.json 与分支/worktree，写入 blockers，flow 停在当前 step；用户解决后调 `/flow-advance` 继续 |
| merge 冲突 | git skill action=merge 会保留冲突现场，提示用户手工解决 → 重新 merge |
| jenkins 构建失败 | 写 blockers，flow 停在 deploy step；用户排查后调 `/flow-advance deploy` 续推 |
| tapd-close 失败（状态机不允许） | WARN 输出，flow 仍标 done；用户人工去 TAPD 操作 |

## 关联

- 上游：`/start-dev-flow` 识别到 bug 关键词后路由到本命令
- 下游 skill：`tapd`（pull bug + close subtask）、`git`（create / merge / cleanup / worktree-create / worktree-remove / commit-push）、`jenkins-deploy`
- 下游 agent（仅 spec 档）：`doc-librarian` / `planner` / `generator` / `evaluator`
- 状态：`.chatlabs/task/bug-fix/<bug_id>/task.json`
