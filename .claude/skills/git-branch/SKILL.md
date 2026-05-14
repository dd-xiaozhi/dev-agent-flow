---
name: git-branch
description: Git 分支生命周期管理。按 docs/git-brance-spec.md 规范创建/合并/清理分支（feature/bugfix/hotfix/release + 自定义前缀），半自动合并到 dev → uat。触发关键词：创建分支、新建分支、切分支、合并到 dev、合并到 uat、git branch、git merge、删除分支、清理分支。
model: sonnet
---

# Git Branch Skill

> 落地 `docs/git-brance-spec.md` 规范：管理分支的创建、合并、清理。与 `git-commit-push` 职责互补——本 skill 管分支生命周期，git-commit-push 管提交推送。
>
> **不做的事**：不写 commit、不发起 PR、不调外部服务、不强推、不自动 rebase。

## 分支命名规范

| 分支类型 | 前缀 | 创建来源 | 合并目标 |
|---------|------|---------|---------|
| 功能分支 | `feature/` | `master` | `dev` → `uat` |
| 修复分支 | `bugfix/` | 当前 `feature/` | 当前 `feature/`（或 `dev` → `uat`） |
| 紧急修复 | `hotfix/` | `master` | `dev` → `uat` |
| 发布分支 | `release/` | `develop` | `main` 和 `develop` |
| 自定义 | `<type>/` | 当前分支 | 由调用者显式指定 |

### 命名约束

- **小写 + 连字符**：仅 `[a-z0-9-]`，单词用 `-` 分隔
- **长度**：建议 30-50 字符，硬上限 50（超长截断），下限不强制
- **可选 ticket 前缀**：`{type}/{ticket_id}-{description}`（推荐）
- 反模式：`feature/UserLogin`、`feature/user_login`、`bugfix/fix`、`bugfix/update`

## 动作 1：create

**输入**：
- `type`（必填）：`feature` / `bugfix` / `hotfix` / `release` / 自定义前缀
- `description`（必填）：自然语言描述，自动转 slug
- `ticket_id`（可选）：TAPD 工单号或本地 story id
- `source_branch`（可选）：覆盖默认 source

**流程**：

```
1. 解析 ticket_id（若未提供）：
   - 读 .chatlabs/state/current_task → 拿到 task_id
   - 从 _index.jsonl 找 task_id 对应的 story_id
   - 读 .chatlabs/task/store/<story_id>/task.json 的 tapd.ticket_id 字段
   - （bug-fix 任务读 .chatlabs/task/bug-fix/<bug_id>/task.json）
   - 找不到则跳过（不阻塞）

2. 生成分支名：
   - desc_slug = description 转小写 + 空格/下划线转 -
   - 若 ticket_id 存在：branch = "<type>/<ticket_id>-<desc_slug>"
   - 否则：             branch = "<type>/<desc_slug>"
   - 截断到 50 字符（含前缀），尾部不留 -

3. 确定 source（若未显式指定 source_branch）：
   - feature / hotfix      → master
   - release               → develop
   - bugfix                → 当前分支（应为 feature/，否则告警）
   - 自定义前缀            → 当前分支

4. 前置检查：
   - git status --porcelain → 非空则报错"工作区有未提交变更"
   - git rev-parse --verify <branch> → 存在则报错"分支已存在"
   - git ls-remote --heads origin <source> → 不存在则报错"source 不存在"

5. 执行：
   git fetch origin
   git checkout -b <branch> origin/<source>

6. 输出 JSON
```

**错误处理**：

| 场景 | 行为 |
|------|------|
| 工作区有未提交变更 | 报错并提示先 commit / stash，**不**自动 stash |
| 目标分支已存在 | 报错并提示是否切换（让人决定） |
| source 分支不存在 | 报错让人介入 |
| 名字校验失败（含大写/下划线） | 自动 normalize 并提示最终用了什么名字 |

## 动作 2：merge

**输入**：
- `source_branch`（可选，默认当前分支）
- `targets`（可选，默认按 type 推断）

**按 type 推断 targets**：

| 前缀 | 默认 targets |
|------|-------------|
| `feature/` / `bugfix/` / `hotfix/` | `["dev", "uat"]` |
| `release/` | `["main", "develop"]` |
| 自定义 | 必须显式传 `targets`，否则报错 |

**流程（半自动）**：

> **链式合并**：按规范 `feature → dev → uat`，第 N 个 target 合并的是**第 N-1 个 target**（不是 source）。
> 即：dev 合并 source；uat 合并 dev；以此类推。

```
1. 记录 original_branch = git rev-parse --abbrev-ref HEAD
2. 前置检查：
   - git status --porcelain → 非空报错
3. git fetch origin
4. prev = source_branch
   for target in targets:
     git checkout <target>
     git pull --ff-only origin <target>   # 仅 fast-forward，远端领先非 ff 则报错
     git merge --no-ff <prev>             # 链式：第一轮合 source，后续合上一个 target
     # 冲突 → 立即终止，输出冲突文件清单，不 abort 让人介入
     git push origin <target>             # push 被拒则终止，禁止 --force
     prev = target
5. git checkout <original_branch>          # 切回原分支
6. 输出 JSON
```

**示例**：`source=feature/login`, `targets=["dev", "uat"]`
1. checkout dev → merge `feature/login` → push dev
2. checkout uat → merge `dev`（**不是** feature/login） → push uat
3. checkout feature/login

**错误处理**：

| 场景 | 行为 |
|------|------|
| 任一 target merge 冲突 | 立即终止后续 targets，保留中间状态（不 `git merge --abort`），输出冲突文件列表让人介入 |
| `git pull --ff-only` 失败 | 报错"远端 `<target>` 领先，需要先同步"，**不**自动 rebase |
| `git push` 被拒 | 终止流程，**禁止** `--force` / `--force-with-lease` |
| targets 为空（自定义前缀未传） | 报错要求显式传 `targets` |

## 动作 3：cleanup

**输入**：
- `branch_name`（必填）
- `remote`（可选，默认 `true`）：是否同时删除远程分支

**流程**：

```
1. 校验已合并：
   git branch --merged dev | grep -F "<branch_name>"
   未合并 → 报错"分支未合并到 dev，拒绝删除"
2. 若当前在待删分支上 → git checkout master
3. git branch -d <branch_name>          # 用 -d 不用 -D，强制安全
4. 若 remote=true：
   git push origin --delete <branch_name>
5. 输出 JSON
```

**错误处理**：

| 场景 | 行为 |
|------|------|
| 未合并到 dev | 拒绝删除，提示"先调用 merge 动作或显式覆盖" |
| 本地分支不存在 | 视为已清理本地，继续删远程（若 remote=true） |
| 远程分支不存在 | 视为已清理远程，不报错 |

## 动作 4：worktree-create

> 在 `.chatlabs/worktrees/<branch_slug>/` 下创建 git worktree，用于多 bug 并行修复。

**输入**：
- `type`（必填）：通常是 `bugfix` / `hotfix`
- `description`（必填）：自然语言描述，自动转 slug
- `ticket_id`（可选）：TAPD bug ID
- `source_branch`（可选）：默认按 type 决定（hotfix → master；bugfix → 当前 feature 分支）

**流程**：

```
1. 解析 ticket_id（同 create 动作）
2. 生成分支名（同 create 动作）→ branch_name
3. 计算 worktree 路径：worktree_path = .chatlabs/worktrees/<branch_slug>
   slug 用 branch_name 末段或 ticket_id（无前缀斜杠，便于路径展示）
4. 前置检查：
   - git worktree list → branch_name 已被任意 worktree 占用则报错
   - <worktree_path> 已存在则报错
   - git rev-parse --verify <branch_name> 已存在（本地）→ 报错让人决定
5. 执行：
   git fetch origin
   mkdir -p .chatlabs/worktrees
   git worktree add <worktree_path> -b <branch_name> origin/<source>
6. 输出 JSON
```

**错误处理**：

| 场景 | 行为 |
|------|------|
| worktree 已存在同名分支 | 报错并提示"该 bug 似乎已存在工作树，使用 worktree-remove 清理或 cd 进入复用" |
| .chatlabs/worktrees/<slug> 已是目录 | 报错让人手工清理 |
| source 分支不存在 | 报错让人介入 |

**与 create 的区别**：
- `create` 在主工作树切分支（影响当前文件）
- `worktree-create` 在独立目录创建分支（**不**改变主工作树，可与其他任务并行）

## 动作 5：worktree-remove

> 清理已合并的 worktree 与分支（用于 bug 修复完成后）。

**输入**：
- `worktree_path`（必填）：要清理的 worktree 路径
- `branch_name`（可选）：缺省时从 worktree 内 `git rev-parse --abbrev-ref HEAD` 推断
- `remote`（可选，默认 `true`）：是否同时删远程分支

**流程**：

```
1. 校验 worktree_path 存在且在 git worktree list 里
2. 进入 worktree，校验工作区干净（status --porcelain 为空）
   不干净 → 报错让人介入，禁止 --force 移除
3. 校验 branch_name 已合并到 dev：
   git branch --merged dev | grep -F "<branch_name>"
   未合并 → 报错"分支未合并到 dev，拒绝清理"
4. 在主工作树执行：
   git worktree remove <worktree_path>   # 用普通 remove 不用 --force
5. 删除分支（复用 cleanup 逻辑）：
   git branch -d <branch_name>
   若 remote=true: git push origin --delete <branch_name>
6. 输出 JSON
```

**worktree-create 成功输出**：
```json
{
  "ok": true,
  "action": "worktree-create",
  "branch": "bugfix/67890-login-validation",
  "worktree_path": ".chatlabs/worktrees/67890-login-validation",
  "source": "master",
  "ticket_id": "67890"
}
```

**worktree-remove 成功输出**：
```json
{
  "ok": true,
  "action": "worktree-remove",
  "branch": "bugfix/67890-login-validation",
  "worktree_removed": true,
  "local_deleted": true,
  "remote_deleted": true
}
```

## 何时调用

- 开始新需求/修复 → `create`
- 并行修复多个 bug → `worktree-create`（每个 bug 一个工作树）
- 开发完成、`git-commit-push` 推完特性分支后 → `merge`
- merge 验证通过、要清理仓库 → `cleanup`（主工作树分支）或 `worktree-remove`（worktree + 分支）
- **不**进入任何 flow 模板，由用户/主 Claude 按需触发

## 输出 JSON

**create 成功**：
```json
{
  "ok": true,
  "action": "create",
  "branch": "feature/12345-user-login",
  "source": "master",
  "ticket_id": "12345",
  "switched_to": true
}
```

**merge 成功**：
```json
{
  "ok": true,
  "action": "merge",
  "source": "feature/12345-user-login",
  "merged_to": ["dev", "uat"],
  "returned_to": "feature/12345-user-login"
}
```

**merge 冲突**：
```json
{
  "ok": false,
  "action": "merge",
  "source": "feature/12345-user-login",
  "merged_to": ["dev"],
  "failed_at": "uat",
  "conflict_files": ["src/foo.py", "src/bar.py"],
  "current_branch": "uat",
  "next_step": "手动解决冲突 → git add → git commit → 重新调用 merge"
}
```

**cleanup 成功**：
```json
{
  "ok": true,
  "action": "cleanup",
  "branch": "feature/12345-user-login",
  "local_deleted": true,
  "remote_deleted": true
}
```
