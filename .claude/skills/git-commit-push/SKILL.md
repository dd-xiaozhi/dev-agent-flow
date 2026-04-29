---
name: git-commit-push
description: 单独的 git commit + push,不做其他副作用（不更新 README、不调外部 API）。按 Conventional Commits 中文规范生成 commit message。flow 模板的 git-push step 调用此 skill。触发关键词:commit push、提交代码、推送代码、git push。
model: sonnet
---

# Git Commit + Push Skill

> 部署前最后一步：把本地变更 commit 并 push 到远程。纯粹的 git commit + push,不更新 README、不调外部服务、不判断仓库结构变化。

## Commit Message 规范

参考项目 `chatlabs-cdev-chopard-bde` 的 git log 风格(Conventional Commits 中文版):

```
<type>(<scope>): <中文描述>
```

### type 取值

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

### scope

模块名/目录名,简短小写,可用 `-` 连接。例：
- `dao`、`callback`、`data-sync`、`auth`、`cls`、`config`、`entity`、`logging`

### 描述

- **中文**,动词开头
- 简洁,一行讲清楚做了什么
- 不带句号

### 反模式

- ❌ 英文描述(`feat(api): add login`)
- ❌ 带 emoji(`✨ feat(api): 新增登录`)
- ❌ 多行 body(项目风格不用)
- ❌ 无 scope(`feat: 新增登录`)
- ❌ 带 Co-authored-by 等 footer

### 例子

```
feat(callback): 新增手机号更新和 SF 数据操作功能
fix(callback): 修复渠道账号取消事件的条件判断逻辑
refactor(dao): 移除数据删除记录相关组件
chore(config): 更新阿里云 OSS 访问密钥配置
perf(sync): 优化订单同步服务超时配置
config(auth): 更新认证排除路径配置
```

## 流程

```
1. git status                   # 检查是否有变更,无变更则 skip 整个流程
2. git diff --stat              # 看变更范围,判定 type + scope
3. git diff                     # 看具体内容,生成中文描述
4. 主 Claude 综合 1-3 输出    生成 commit message(单行)
5. git add <相关文件>           # 不用 git add -A,避免误加 .env / 大文件
6. git commit -m "<message>"    # 走预提交 hook,不加 --no-verify
7. git push                     # push 到当前分支对应的 remote
8. 输出 commit hash + push 结果摘要
```

### 错误处理

| 场景 | 行为 |
|------|------|
| 无变更可提交 | 输出 `noop: no changes to commit`,直接成功(不阻塞 flow advance) |
| pre-commit hook 失败 | 输出 hook 错误,**禁止 --no-verify 绕过**,要求修复后重跑 |
| push 冲突(remote 有新提交) | 输出冲突信息,**不自动 git pull --rebase**,要求人工介入 |
| 当前分支无 upstream | 用 `git push -u origin <branch>` 建立追踪 |

## 输出

```json
{
  "ok": true,
  "noop": false,
  "commit_hash": "a1b2c3d",
  "commit_message": "feat(callback): 新增手机号更新功能",
  "branch": "dev-cpwx-wecom-bot-test",
  "pushed_to": "origin/dev-cpwx-wecom-bot-test",
  "files_changed": 5
}
```

noop 情形:
```json
{
  "ok": true,
  "noop": true,
  "reason": "no changes to commit"
}
```

## 何时调用

由 flow 模板的 `git-push` step(kind=skill, target=git-commit-push)在 deploy 前调用。
完成后主 Claude 调 `/flow-advance git-push` 推进到 deploy。
