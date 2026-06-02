---
name: git
description: Git 操作统一入口。分支生命周期（create/merge/cleanup）、worktree（create/remove）、提交推送（commit-push）。按 docs/git-brance-spec.md + Conventional Commits 中文规范执行。触发关键词：创建分支、合并到 dev、合并到 uat、删除分支、清理分支、git push、commit、推送代码、worktree、提交代码。
model: sonnet
---

# Git Skill

> 项目内所有 git 写操作的单一入口,按 action 路由。

## 触发

创建分支 / 合并到 dev / 合并到 uat / 删除分支 / 清理分支 / commit / push / worktree / 提交代码。

## 边界

- ✅ 分支生命周期(create / merge / cleanup)
- ✅ worktree 隔离并行
- ✅ Conventional Commits 中文 commit message
- ✅ 配置驱动:行为先读 `.chatlabs/project-config.json` 的 `git` section
- ❌ 不发 PR / 不调外部服务 / 不更新 README
- ❌ 不强推 / 不自动 rebase
- ❌ 默认禁止删除 feature/hotfix/release/无前缀分支
- ❌ 禁止合并到 master / main

## Gotchas

1. 想合并到 `master` / `main` 直接被拒(默认禁止,见 `merge.merge_targets` 配置白名单)
2. `cleanup` 默认**总是删 worktree**(若 worktree_path 非空);**分支去留**由 `allowed_prefixes` 决定:在白名单内→删本地+远程,不在→保留分支(典型:bugfix 删/feature/hotfix 留)
3. merge 链式策略下第二步合的是**上一步 target** 不是原 source(如 dev→uat 合的是 dev 不是 feature)
4. pre-commit hook 失败时禁止 `--no-verify` 绕过(`commit_push.allow_no_verify=false`),应修底层问题
5. commit message 中文 Conventional 强制,反模式:英文描述 / emoji / 多行 body / 无 scope / Co-authored-by
6. 工作区有未提交变更时 create 直接报错,**不自动 stash**(避免误改丢失)
7. `worktree-create` 默认在 task 启动时被入口命令调起(`worktree.auto_create=true`),`vibe` 档默认豁免(`skip_for_complexity`),其他档强制开

## Action 总览

| action | 用途 |
|--------|------|
| `init-config` | 对齐本地仓库 git 配置(merge.ff / pull.rebase 等) |
| `ensure-branch` | 幂等保证分支存在并 checkout |
| `resolve` | 只读解析某 branch_type 的 prefix/source/merge_targets |
| `create` | 创建分支(feature/bugfix/hotfix/release) |
| `merge` | 链式合并 + push |
| `cleanup` | 完成时统一收尾:**删 worktree(如有)+ 按 `allowed_prefixes` 决定分支去留**(白名单内删,否则留) |
| `worktree-create` | 创建独立 worktree(task 启动时默认开,vibe 豁免);实现 = `scripts/worktree.py`(读 `git.worktree.{root,auto_create,skip_for_complexity}`,`resolve` 只读决策 / `create` 执行) |
| `worktree-remove` | (兼容)单独移除 worktree;**新流程下推荐用 `cleanup` 统一收尾** |
| `commit-push` | 中文 Conventional Commits 提交 + push |

## 配置驱动(project-config.json `git` section)

| 字段 | 用途 | 默认 |
|------|------|------|
| `branches.<type>.prefix` | 分支前缀 | feature/bugfix/hotfix/release |
| `branches.<type>.source` | 创建分支的 source | feature/hotfix→`master`、bugfix→`current`、release→`develop` |
| `branches.<type>.merge_targets` | merge 目标列表 | feature/hotfix→`["dev","uat"]`、bugfix→`["current-feature"]`、release→`["main","develop"]` |
| `merge.strategy` | `chained`(N 合 N-1) / `fanout`(都合 source) | `chained` |
| `merge.no_ff` | 是否带 `--no-ff` | `true` |
| `merge.pull_before_merge` | merge 前 `pull --ff-only` | `true` |
| `merge.allow_force_push` | 是否允许 `--force` | `false` |
| `merge.return_to_branch` | merge 完后切回:`source`/具体分支 | `source` |
| `commit_push.conventional_zh` | 强制中文 Conventional Commits | `true` |
| `commit_push.allow_no_verify` | 允许 `--no-verify` | `false` |
| `commit_push.auto_set_upstream` | 无 upstream 时 `push -u` | `true` |
| `commit_push.auto_add_all` | 允许 `git add -A` | `false` |
| `worktree.root` | worktree 根目录 | `.chatlabs/worktrees` |
| `worktree.auto_create` | task 启动时是否自动开 worktree | `true` |
| `worktree.skip_for_complexity` | 哪些复杂度档跳过 worktree | `["vibe"]` |
| `cleanup.allowed_prefixes` | 完成时**删分支**的前缀白名单(不在内的分支保留) | `["bugfix/"]` |
| `cleanup.require_merged_to` | 删分支前要求已合并到的分支 | `dev` |
| `cleanup.delete_remote` | 删分支时是否同时删远端 | `true` |

**特殊 source 取值**:
- `"current"` — `HEAD`
- `"current-feature"` — 沿 git log 找最近的 `feature/*`(找不到报错)

**优先级**:调用方显式参数 > `project-config.json.git` > 内置默认值。

## 分支命名规范

| 类型 | 前缀 | 创建来源 | 合并目标 |
|------|------|---------|---------|
| 功能 | `feature/` | `master` | `dev → uat` |
| 修复 | `bugfix/` | 当前分支 | 关联 `feature/*` |
| 紧急 | `hotfix/` | `master` | `dev → uat` |
| 发布 | `release/` | `develop` | `main` + `develop` |

**命名**(2026-05-29 更新,详见 `docs/git-brance-spec.md`):
- 仅 `[a-z0-9-]`
- 格式:`<type>/{<ticket-short>-}<description>`
  - 无 ticket(本地任务):`<type>/<description>`,如 `feature/ec-user-exists-api`
  - 有 ticket(TAPD):`<type>/<ticket-short>-<description>`,如 `feature/1000123-add-payment`
- ticket 短 id 取 TAPD 工单 ID 后 7 位(如 `1152676229001000123` → `1000123`)
- 硬上限 50 字符
- **不再含 MM-dd 日期前缀**(已废弃)
- **注**:以上为 git 分支命名(按工单关联);task / story_id 是另一维度(`<MM-dd>-<description>`,按时间组织),勿混用,详见 docs/git-brance-spec.md

## 流程(典型 feature 全链路)

```mermaid
flowchart LR
  A[ensure-branch<br/>feature/...] --> A2[worktree-create<br/>.chatlabs/worktrees/...]
  A2 --> B[开发 + commit-push]
  B --> C[merge<br/>chained dev→uat]
  C --> D{冲突?}
  D -->|是| E[人工解决<br/>重新 merge]
  D -->|否| F[切回 source<br/>验证通过]
  F --> G[cleanup<br/>删 worktree + 按 prefix 决定分支去留]
```

## cleanup 行为详解(新流程)

```
输入: branch / branch_type / worktree_path

步骤:
  1. worktree_path 非空 → git worktree remove <path>(总是执行)
  2. branch_type 在 allowed_prefixes 内?
     是 → 删本地分支 + 远端(if delete_remote=true)
     否 → 跳过,分支保留(典型:feature/hotfix 留作记录)
  3. require_merged_to 校验:目标分支未合并到时拒绝删分支(仅删 worktree)
```

**示例**:
- `bugfix/fix-token` + worktree=`.chatlabs/worktrees/fix-token/`
  - → 删 worktree + 删 bugfix 分支(在白名单)
- `feature/new-pay` + worktree=`.chatlabs/worktrees/new-pay/`
  - → 删 worktree,**保留 feature 分支**(不在白名单)
- `hotfix/...` 同 feature:删 worktree,保留分支

## merge 链式策略示例

`source=feature/login, targets=["dev","uat"], strategy=chained`:
1. checkout dev → merge `feature/login` → push
2. checkout uat → merge **`dev`**(不是 feature/login)→ push
3. checkout feature/login(`return_to_branch=source`)

## commit-push:Conventional Commits 中文

格式:`<type>(<scope>): <中文描述>`

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修 bug |
| `refactor` | 重构 |
| `perf` | 性能 |
| `chore` | 杂项 |
| `config` | 配置 |
| `docs` | 文档 |
| `test` | 测试 |
| `style` | 格式 |

示例:`feat(callback): 新增手机号更新和 SF 数据操作功能`

**反模式**:英文描述 / emoji / 多行 body / 无 scope / Co-authored-by footer。

## 错误处理(通用)

| 场景 | 行为 |
|------|------|
| 工作区有未提交变更 | 报错,不自动 stash |
| 目标分支已存在(create) | 报错让人决定 |
| merge 冲突 | 立即终止后续 targets,保留中间状态,输出冲突清单 |
| `pull --ff-only` 失败 | 报错"远端领先,需先同步",不自动 rebase |
| `push` 被拒 | 终止,禁止 `--force`(除非配置允许) |
| cleanup 前缀不在白名单 | 拒绝删除 |
| cleanup 未合并到 target | 拒绝删除 |
| commit-push 无变更 | noop 成功(不阻塞 flow advance) |
| pre-commit hook 失败 | 输出错误,禁止 `--no-verify`(除非配置允许) |

## 入口脚本

```bash
python .claude/skills/git/scripts/init_config.py
python .claude/skills/git/scripts/ensure_branch.py <branch> [--branch-type ...] [--from ...]
python .claude/skills/git/scripts/git_config.py resolve --branch-type <type>
```

各 action 详细输入输出 schema 见 `.claude/skills/git/scripts/*.py` 顶部 docstring。

## 关联

- 配置:`.chatlabs/project-config.json` `git` section
- 脚本目录:`.claude/skills/git/scripts/`
- 规范:`docs/git-brance-spec.md`
- 调用方:flow 模板的 `git-push` / `merge` step、`/tapd start`、`/bug-fix`
