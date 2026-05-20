---
name: git
description: Git 操作统一入口。分支生命周期（create/merge/cleanup）、worktree（create/remove）、提交推送（commit-push）。按 docs/git-brance-spec.md + Conventional Commits 中文规范执行。触发关键词：创建分支、合并到 dev、合并到 uat、删除分支、清理分支、git push、commit、推送代码、worktree、提交代码。
model: sonnet
---

# Git Skill

> 把项目内所有 git 写操作收敛为单一 skill，按 action 路由。
>
> **不做的事**：
> - 不更新 README、不调外部服务、不发起 PR、不强推、不自动 rebase
> - 默认禁止删除 feature/hotfix/release/无前缀分支（由 `git.cleanup.allowed_prefixes` 配置覆盖）
> - 提交流程不绕过 pre-commit hook（除非 `git.commit_push.allow_no_verify=true`）
> - 禁止合并到 master、main 分支

## 配置驱动（project-config.json `git` section）

所有 action 的行为都先读 `.chatlabs/project-config.json` 的 `git` section，缺省字段才落回本 SKILL 描述的默认值。**任何项目都可在 `git` section 覆盖**：

| 字段 | 用途 | 默认 |
|------|------|------|
| `branches.<type>.prefix` | 分支前缀（生成分支名时用） | `feature/`、`bugfix/`、`hotfix/`、`release/` |
| `branches.<type>.source` | 创建分支时的 source 来源；可填具体分支名 / `current`（当前分支）/ `current-feature`（最近一个 feature/* 分支） | feature→`master`、bugfix→`current`、hotfix→`master`、release→`develop` |
| `branches.<type>.merge_targets` | merge action 的目标列表（按顺序）；`current-feature` 表示关联的 feature 分支 | feature/hotfix→`["dev","uat"]`、bugfix→`["current-feature"]`、release→`["main","develop"]` |
| `merge.strategy` | `chained`（链式：第 N 个 target 合 N-1 个 target）/`fanout`（每个 target 都合 source） | `chained` |
| `merge.no_ff` | merge 时是否带 `--no-ff` | `true` |
| `merge.pull_before_merge` | merge 前是否对 target 跑 `git pull --ff-only` | `true` |
| `merge.allow_force_push` | 是否允许 `--force` push | `false`（强禁） |
| `merge.return_to_branch` | merge 完成后切回哪条分支：`source`（原分支）/`master`/具体分支名 | `source` |
| `commit_push.conventional_zh` | 强制 Conventional Commits 中文 commit message | `true` |
| `commit_push.allow_no_verify` | 是否允许 `--no-verify` 绕过 pre-commit hook | `false` |
| `commit_push.auto_set_upstream` | 当前分支无 upstream 时是否自动 `git push -u` | `true` |
| `commit_push.auto_add_all` | 是否允许 `git add -A`（默认手工挑文件） | `false` |
| `worktree.root` | worktree 创建根目录 | `.chatlabs/worktrees` |
| `cleanup.allowed_prefixes` | cleanup 允许删除的分支前缀白名单 | `["bugfix/"]` |
| `cleanup.require_merged_to` | cleanup 前要求已合并到的分支 | `dev` |
| `cleanup.delete_remote` | cleanup 默认是否同时删远端 | `true` |

**特殊取值**：
- `source: "current"` → 创建分支时以 `HEAD` 为 source（不切换工作树场景外通常等于当前分支）
- `source: "current-feature"` / `merge_targets: ["current-feature"]` → 沿 git log 找最近一个 `feature/*` 分支；找不到则报错让人介入
- `return_to_branch: "source"` → merge 完成后切回调用 merge 时所在分支

**读取优先级**：调用方显式参数 > `project-config.json.git` > 本 SKILL 默认值。

## Action 总览

| action | 用途 | 简述 |
|--------|------|------|
| `init-config` | 初始化仓库配置 | 设置本地仓库 merge.ff=false / pull.rebase=true 等符合规范的配置 |
| `ensure-branch` | 确保分支存在 | 幂等：分支已存在则切过去，不存在则从 source 创建 |
| `create` | 创建分支 | `feature/bugfix/hotfix/release + 自定义前缀`，从指定 source 切出 |
| `merge` | 链式合并 | 半自动按 `feature → dev → uat` 链式合并并 push |
| `cleanup` | 清理分支 | 删除本地 + 远端的 bugfix 分支（仅 bugfix） |
| `worktree-create` | 创建 worktree | 多 bug 并行隔离，分支落在独立工作树 |
| `worktree-remove` | 清理 worktree | 已合并的 worktree + 分支一并删除 |
| `commit-push` | 提交并推送 | 按 Conventional Commits 中文格式 commit 后 push |

---

## Action 0a：init-config

> 把当前仓库的本地 git 配置对齐 `docs/git-brance-spec.md`。**只动 `.git/config`（本地）**，不修改 user / global 配置。同时将 merge 相关配置写入 `project-config.json` 的 `git.merge` section。

**入口**：`python .claude/skills/git/scripts/init_config.py`

**写入**：
- `.git/config`（本地仓库配置）：
  - `merge.ff = false`（强制 merge commit）
  - `merge.noff = true`（默认带 --no-ff）
  - `pull.rebase = true`（pull 自动 rebase）
  - `branch.autosetuprebase = always`
  - `push.default = current`
- `project-config.json`（`git.merge` section）：
  - `no_ff = true`
  - `pull_before_merge = true`
  - `allow_force_push = false`
  - `return_to_branch = "source"`

**输出**：
```json
{
  "ok": true,
  "action": "init-config",
  "applied": {"merge.ff": {"old": null, "new": "false"}},
  "skipped": ["pull.rebase"],
  "errors": [],
  "project_config": {
    "ok": true,
    "applied": {"no_ff": {"old": null, "new": true}},
    "skipped": ["pull_before_merge", "allow_force_push", "return_to_branch"]
  }
}
```

**何时调用**：
- 项目首次接入 Claude flow（`/init-project` 之后）
- 本地仓库克隆后第一次跑（手动 `python .claude/skills/git/scripts/init_config.py`）

---

## Action 0b：ensure-branch

> 幂等地确保某条分支存在且当前 checkout 在它上面。**`/tapd start` 等流程在 `task.py new` 之后调用，把分支信息回写到 `task.json.git`**。

**入口**：`python .claude/skills/git/scripts/ensure_branch.py <branch_name> --from <source_branch> [--allow-dirty]`

**行为**：
1. 工作区有未提交变更 → 报错（除非 `--allow-dirty`）
2. `<branch_name>` 已是当前分支 → noop 成功
3. `<branch_name>` 本地已存在 → `git checkout <branch_name>`
4. 不存在 → `git fetch origin <source_branch>`：
   - 远端有 `origin/<source_branch>` → `git checkout -b <branch_name> origin/<source_branch>`
   - 否则用本地 `<source_branch>` 作起点
   - 都没有 → 报错

**输出**：
```json
{
  "ok": true,
  "action": "ensure-branch",
  "branch": "feature/05-20-sf-account-merge",
  "source_branch": "dev",
  "start_point": "origin/dev",
  "from_remote": true,
  "created": true,
  "switched": true,
  "previous_branch": "dev"
}
```

**与 `create` 的区别**：
- `create` 是新建分支的标准入口，会校验前缀、命名规则、ticket_id 解析
- `ensure-branch` 是底层幂等原语，**接收完整分支名**，不做命名规范校验；适合脚本编排（如 `/tapd start` 已经在上层算好分支名）

---

## 一、分支命名规范（create / worktree-create）

> 下表为**未配置 `project-config.json.git.branches` 时**的内置默认值。任何项目都可在 `git.branches.<type>` 覆盖前缀 / source / merge_targets。

| 分支类型 | 前缀 | 创建来源 | 合并目标 |
|---------|------|---------|---------|
| 功能分支 | `feature/` | `master` | `dev` → `uat` |
| 修复分支 | `bugfix/` | 当前分支 | 关联的 `feature/*` 分支 |
| 紧急修复 | `hotfix/` | `master` | `dev` → `uat` |
| 发布分支 | `release/` | `develop` | `main` 和 `develop` |
| 自定义 | `<type>/` | 当前分支 | 由调用者显式指定 |

### 命名约束

- **小写 + 连字符**：仅 `[a-z0-9-]`，单词用 `-` 分隔
- **长度**：建议 30-50 字符，硬上限 50（超长截断），下限不强制
- **可选 ticket 前缀**：`{type}/{ticket_id}-{description}`（推荐）
- 反模式：`feature/UserLogin`、`feature/user_login`、`bugfix/fix`、`bugfix/update`

---

## Action 1：create

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

3. 确定 source（按 `git.branches.<type>.source` 取值；未配置时走默认）：
   - feature / hotfix      → `master`
   - release               → `develop`
   - bugfix                → `current`（当前分支，应为 feature/，否则告警）
   - 自定义前缀            → `current`（当前分支）
   - 取值可为：具体分支名 / `current` / `current-feature`（沿 git log 找最近 feature/*）

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

**成功输出**：

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

---

## Action 2：merge

**输入**：
- `source_branch`（可选，默认当前分支）
- `targets`（可选，默认按 type 推断）

**按 type 推断 targets**（受 `git.branches.<type>.merge_targets` 配置覆盖；下表为缺省值）：

| 前缀 | 默认 targets |
|------|-------------|
| `feature/` / `hotfix/` | `["dev", "uat"]` |
| `bugfix/` | `["current-feature"]`（合回关联的 feature 分支） |
| `release/` | `["main", "develop"]` |
| 自定义 | 必须显式传 `targets` 或在配置里定义，否则报错 |

`merge_targets` 元素的特殊取值：`current-feature` 表示沿 git log 找到最近一个 `feature/*` 分支；找不到则报错让人介入。

**流程（半自动，受 `git.merge.*` 配置控制）**：

> **strategy=`chained`（默认）**：按规范 `feature → dev → uat`，第 N 个 target 合并的是**第 N-1 个 target**（不是 source）。即 dev 合并 source；uat 合并 dev；以此类推。
>
> **strategy=`fanout`**：每个 target 都直接合并 source（不链式）。

```
1. 记录 original_branch = git rev-parse --abbrev-ref HEAD
2. 前置检查：
   - git status --porcelain → 非空报错
3. git fetch origin
4. prev = source_branch
   for target in targets:
     git checkout <target>
     if git.merge.pull_before_merge: git pull --ff-only origin <target>   # 仅 fast-forward
     git merge [<--no-ff if git.merge.no_ff>] <prev if strategy=chained else source_branch>
     # 冲突 → 立即终止，输出冲突文件清单，不 abort 让人介入
     git push origin <target>             # push 被拒则终止；除非 git.merge.allow_force_push=true 否则不带 --force
     if strategy=chained: prev = target
5. 按 git.merge.return_to_branch 切回：
   - "source"     → original_branch（默认）
   - "master" / 具体分支名 → git checkout <那个分支>
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

**成功输出**：

```json
{
  "ok": true,
  "action": "merge",
  "source": "feature/12345-user-login",
  "merged_to": ["dev", "uat"],
  "returned_to": "feature/12345-user-login"
}
```

**冲突输出**：

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

---

## Action 3：cleanup

**输入**：
- `branch_name`（必填）
- `remote`（可选，默认走 `git.cleanup.delete_remote`）：是否同时删除远程分支

**流程**：

```
1. 校验前缀白名单：
   分支名前缀 ∉ git.cleanup.allowed_prefixes → 报错"该前缀不在白名单内，拒绝删除"
2. 校验已合并（target = git.cleanup.require_merged_to）：
   git branch --merged <target> | grep -F "<branch_name>"
   未合并 → 报错"分支未合并到 <target>，拒绝删除"
3. 若当前在待删分支上 → git checkout master
4. git branch -d <branch_name>          # 用 -d 不用 -D，强制安全
5. 若 remote=true：
   git push origin --delete <branch_name>
6. 输出 JSON
```

**错误处理**：

| 场景 | 行为 |
|------|------|
| 未合并到 dev | 拒绝删除，提示"先调用 merge 动作或显式覆盖" |
| 本地分支不存在 | 视为已清理本地，继续删远程（若 remote=true） |
| 远程分支不存在 | 视为已清理远程，不报错 |

**成功输出**：

```json
{
  "ok": true,
  "action": "cleanup",
  "branch": "feature/12345-user-login",
  "local_deleted": true,
  "remote_deleted": true
}
```

---

## Action 4：worktree-create

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
3. 计算 worktree 路径：worktree_path = <git.worktree.root>/<branch_slug>
   slug 用 branch_name 末段或 ticket_id（无前缀斜杠，便于路径展示）；root 默认 `.chatlabs/worktrees`
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

**成功输出**：

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

---

## Action 5：worktree-remove

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

**成功输出**：

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

---

## Action 6：commit-push

> 把本地变更 commit 并 push 到远程。纯粹的 git commit + push，不更新 README、不调外部服务、不判断仓库结构变化。

### Commit Message 规范

git log 风格（Conventional Commits 中文版）：

```
<type>(<scope>): <中文描述>
```

#### type 取值

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `refactor` | 重构（不改外部行为） |
| `perf` | 性能优化 |
| `chore` | 杂项（构建、依赖、配置） |
| `config` | 配置文件变更 |
| `docs` | 文档变更 |
| `test` | 测试相关 |
| `style` | 代码格式（不影响逻辑） |

#### scope

模块名/目录名，简短小写，可用 `-` 连接。例：`dao`、`callback`、`data-sync`、`auth`、`cls`、`config`、`entity`、`logging`

#### 描述

- **中文**，动词开头
- 简洁，一行讲清楚做了什么
- 不带句号

#### 反模式

- ❌ 英文描述（`feat(api): add login`）
- ❌ 带 emoji（`✨ feat(api): 新增登录`）
- ❌ 多行 body（项目风格不用）
- ❌ 无 scope（`feat: 新增登录`）
- ❌ 带 Co-authored-by 等 footer

#### 例子

```
feat(callback): 新增手机号更新和 SF 数据操作功能
fix(callback): 修复渠道账号取消事件的条件判断逻辑
refactor(dao): 移除数据删除记录相关组件
chore(config): 更新阿里云 OSS 访问密钥配置
perf(sync): 优化订单同步服务超时配置
config(auth): 更新认证排除路径配置
```

### 流程

```
1. git status                   # 检查是否有变更，无变更则 skip 整个流程
2. git diff --stat              # 看变更范围，判定 type + scope
3. git diff                     # 看具体内容，生成中文描述
4. 主 Claude 综合 1-3 输出     生成 commit message（单行）
5. git add <相关文件>           # 不用 git add -A，避免误加 .env / 大文件
6. git commit -m "<message>"    # 走预提交 hook，不加 --no-verify
7. git push                     # push 到当前分支对应的 remote
8. 输出 commit hash + push 结果摘要
```

### 错误处理

| 场景 | 行为 |
|------|------|
| 无变更可提交 | 输出 `noop: no changes to commit`，直接成功（不阻塞 flow advance） |
| pre-commit hook 失败 | 输出 hook 错误，默认禁止 `--no-verify` 绕过（受 `git.commit_push.allow_no_verify` 配置覆盖） |
| push 冲突（remote 有新提交） | 输出冲突信息，**不自动 git pull --rebase**，要求人工介入 |
| 当前分支无 upstream | 若 `git.commit_push.auto_set_upstream=true`（默认）则用 `git push -u origin <branch>` 建立追踪；否则报错 |
| `git.commit_push.auto_add_all=false`（默认） | 不允许 `git add -A`；调用方须传具体文件列表 |

**成功输出**：

```json
{
  "ok": true,
  "action": "commit-push",
  "noop": false,
  "commit_hash": "a1b2c3d",
  "commit_message": "feat(callback): 新增手机号更新功能",
  "branch": "dev-cpwx-wecom-bot-test",
  "pushed_to": "origin/dev-cpwx-wecom-bot-test",
  "files_changed": 5
}
```

noop 情形：
```json
{
  "ok": true,
  "action": "commit-push",
  "noop": true,
  "reason": "no changes to commit"
}
```

---

## 何时调用

- 开始新需求/修复 → `action=create`
- 并行修复多个 bug → `action=worktree-create`（每个 bug 一个工作树）
- 开发完成、变更要入仓 → `action=commit-push`
- 推完特性分支后 → `action=merge`
- merge 验证通过、要清理仓库 → `action=cleanup`（主工作树分支）或 `action=worktree-remove`（worktree + 分支）

flow 模板的 `git-push` step（kind=skill, target=git, action=commit-push）在 deploy 前调用 commit-push；`merge` step（kind=skill, target=git, action=merge）紧随其后。
