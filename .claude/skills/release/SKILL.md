---
name: release
description: Trigger CI/CD build for deployment — select branch, trigger job, report status, post-process labels
disable-model-invocation: true
installed-from: agent-dev-standard@cf04193
installed-on: 2026-05-29
---

# /release — 触发构建发布

通过 CI/CD 系统（Jenkins / GitHub Actions / 其他）REST API 触发构建任务 + 后置处理（Issue label 切换 / 通知 / 历史记录）。

---

## 输入

- `$ARGUMENTS`：可选值：
  - `<branch>` — 指定分支触发构建（如 `dev` / `main` / `feature/xxx`）
  - 无参数时提示用户选择分支

---

## 项目配置

执行前读取项目 CLAUDE.md 中的 `## Release 配置` 段：

| 项 | 含义 |
|---|---|
| `ci_system` | jenkins / github-actions / circleci / 其他 |
| `ci_url` | CI 服务地址 |
| `job_name` | 构建任务名称 |
| `ci_user` / `ci_token` | 认证（敏感值，从 `.env` 加载）|
| `branch_param` | 分支参数名（如 `branch` / `BRANCH` / `ref`）|
| `default_branch` | 默认分支 |
| `release_history` | 历史文件路径（默认 `docs/release-history.md`）|
| `notify_webhook` | 通知 webhook（如有）|

---

## 执行逻辑

### Step 0 — 发布前检查

#### 0.1 Critical 问题核查
1. 检查 problem-registry 中是否有 `critical` + 未修复的条目
2. 有 → 警告，等用户确认是否继续
3. 没有 → 继续

#### 0.2 共享文档同步检查（硬门禁）
发布前必须验证本地 docs 与共享仓库同步——代码推了但文档没推是典型的"跨 repo 状态不一致"问题。

1. 比对代码仓库 `docs/` 最新 commit 时间 vs 共享文档仓库相应目录最新 commit 时间
2. **代码 docs 比共享更新** → 🛑 STOP，提示先推共享文档仓库
3. **一致或共享更新** → ✅ 通过

**豁免条件：** 本次 release 纯代码改动（grep 本次 commits 无 `docs/` 变更）/ 用户明确说"docs 不需要推"（带原因）

#### 0.3 技术债扫描 + tech-debt-index 自动生成

**扫描命令：**
```bash
# 1. grep 所有 TODO 注释
grep -rnE 'TODO\((.*?)\):' <src-dir>

# 2. 对每条用 git blame 取首次提交日期
# 3. aging = 今日 - 首次提交日期
```

**Aging 分级（核心原则：TODO 是短期临时标记，不该变成永久）：**

| Aging | 状态 | 动作 |
|-------|------|------|
| ≤ 7 天 | 正常 | 无动作 |
| 7~14 天 | LOW 提醒 | 建议评估能否清理 |
| 14~30 天 | MEDIUM | 下次 release 前建议拉清单讨论 |
| **> 30 天** | **HIGH — 必须处理** | 强制转移：① 转 Issue / ② 转 session-todos / ③ 直接实现 / ④ 接受为永久（从 TODO 改 NOTE 或移入 ADR）|

**净变化记录（不 STOP）：** 对比上次 release 的快照（新增 / 清除 / 净变化），记入 tech-debt-index 的"净变化历史"表。**不阻塞 release**（软记录），但如净增 > 0 在通知中注明。

#### 0.4 push 状态检查（硬门禁）

发布前**强制核查本地未 push commits**，避免 CI 拉到的 origin/<branch> 不含本地修改、build 跑历史代码：

```bash
git status -sb              # 显示 branch tracking + 工作区状态
git log @{u}..HEAD --oneline  # 列出本地领先 origin 的 commits
```

**判据：**
- `git log @{u}..HEAD` 输出**非空** → 🛑 STOP，提示先 push 再发布
- `git status` dirty 工作区（与本次 release 相关）→ 提示用户决定 stash / commit / 取消
- 全部 clean → 通过

**为什么独立硬门禁：** push 状态检查在所有触发动作之前，避免后续 Step（特别是 Step 2 触发构建）在错误前提下推进。实证：未 push 的 commit 导致 build 跑空 + 错误前提扩散到下游。

### Step 1 — 确认分支

1. 用户指定 → 用指定值
2. 未指定 → 用 default_branch
3. 展示即将触发的信息 + 等用户确认

### Step 2 — 触发构建

> **⚠️ install 时必须根据 ci_system 类型调整命令模板，不保留占位符。**

**Jenkins 例：**
```bash
curl -sk -w "\nHTTP_CODE:%{http_code}" -X POST \
  "<ci_url>/job/<job_name>/buildWithParameters?<branch_param>=<branch>" \
  --user "<ci_user>:<ci_token>"
```

- HTTP 201 → 触发成功
- HTTP 400 → 检查分支参数格式（部分 CI 需要 `origin/` 前缀）
- 其他状态码 → 报错，展示响应

### Step 3 — 获取提交清单

触发成功后查询本次构建包含的 commits（CI API 返回的 changeSet）。以表格展示提交清单（commit hash / 时间 / 作者 / 说明）。changeSet 为空时说明并告知用户。

### Step 4 — 查询状态（可选）

询问用户是否需要轮询构建结果。

#### 轮询频率规则

**目标：每次发布控制在约 4 次轮询。**

1. 读取 `release_history` 取最近 10 次成功构建的平均耗时
2. 轮询间隔 = 平均耗时 ÷ 4（向上取整到 10 秒倍数）
3. 最小间隔 20 秒，最大间隔 120 秒
4. 无历史数据时使用默认 30 秒

> **Claude Code 环境限制：** `sleep N`（N≥2）作为 Bash 首条命令会被工具层阻断。**使用 `python3 time.sleep()` 替代 shell sleep。** 单条命令把 sleep 和查询写在一起，不分开。

### Step 5 — 上线验证（建议）

构建成功后，通过 `/log`（如已装）验证服务正常启动：
- 检查关键日志（如 `Started Application`、无 ERROR 级日志）
- 如有异常，立即告知用户

### Step 6 — 后置处理

#### 6.1 同步 problem-registry
标注本次发布修复了哪些 P-xxx（从提交清单的 Issue 编号反查）。

#### 6.2 Issue comment 通知
如有相关 open Issue，在 comment 中注明"已发布到 <环境>"。

#### 6.3 发版后 label 批量切换（强制）

`protocols/issue-process.md` 状态机规定 `[role]-confirmed` 由 `/release` 切（dev 部署后 = 下游可回测 / 对接）——本步骤**就是该承诺的实施载体**。跳过 = `[role]-in-progress` Issue 沉底，下游收不到"可回测"信号。

**算法（V2，从 Issue → commit → build 正查，不再从 build → Issue 反查）：**

核心思路：发布有节奏，不是每次 release 都对应"刚收尾的 Issue"。可能多个 Issue 完成后一起发，也可能某次 release 漏切。所以正确的判断不是"本次 build 涉及哪些 Issue"，而是"每个 in-progress Issue 的 commit 是否已经部署"——后者天然覆盖"本次 + 历史漏切"两种场景。

**⚠️ 注意 — GitHub label-based search 索引延迟（2026-05-25 加 / Issue #11 KR-FB-004）:** 新建 label 后 `--label X` search 索引有约 5-15 min 延迟。`09-github-labels.sh` 同步完 label + 创建 issue + 加 label 后立刻跑此 list 可能扑空（已实证 kingdom-rush 2026-05-15）。若返回 `[]` 但 `gh issue view <N> --json labels` 确认 label 存在 → 触发下方 fallback。

```bash
# 1. 列所有 open [role]-in-progress Issue
issues=$(gh issue list --repo <owner/repo> --label [role]-in-progress --state open \
  --json number,title,comments)

# 1-fallback. 如果 search index 未就绪（命中 KR-FB-004 模式 / 返回 []）→ 二次过滤
if [ "$issues" = "[]" ]; then
    issues=$(gh issue list --repo <owner/repo> --state open \
             --json number,title,comments,labels \
             | jq '[.[] | select(.labels[]?.name == "[role]-in-progress")]')
fi

# 2. 对每个 Issue：从 comment 提取 commit hash
#    EL 在 /issue Step 6b 收尾时按 issue-handling 三选一格式写入：
#      commit: `<hash>`  （前缀 commit: + 反引号包裹 hash，机器可解析）
gh issue view <N> --comments | grep -oE 'commit:\s*`[a-f0-9]{7,40}`' | sed -E 's/.*`([a-f0-9]+)`/\1/'

# 3. 对每个 hash：判断是否已部署
#    依据：merge-base 检查 hash 是否是 release-history 最新成功 build 的 head_commit 的祖先
git merge-base --is-ancestor <hash> <last-build-head-commit>
# 退出码 0 = 是祖先（已部署）/ 1 = 不是（未部署）

# 4. 已部署 → 切 [role]-confirmed + comment "已发布到 <env> — build #<N> — 可关闭"
gh issue edit <N> --remove-label [role]-in-progress --add-label [role]-confirmed
gh issue comment <N> --body "已发布到 dev — build #<N> — **可关闭**"
# 「可关闭」标注由本步骤同步嵌入 (dev 已发版下游可回测 = 真"可关闭"语义)

# 5. 未部署 → 保持 in-progress（不动作）
```

**依赖：** `release_history` 必须记录每次 build 的 **head_commit**（HEAD commit hash），否则 merge-base 无法判断（见 §release-history 格式）。

**fallback（comment 缺 commit hash）：** 如果 Issue comment 没按格式写 commit hash，**不要回退到事件 referenced commit_id**——而是在本步骤末尾产出"格式不合规 Issue 清单"，由 SA 起 corrections handoff 推 EL 补 comment。**单一数据源更清晰**，不留兜底分支。

**预期触发频率：** `/issue` Step 6b 已要求执行层写 comment 后立即 grep 自检。机器化自检部署后，本 fallback 触发频率应降至接近 0；持续触发 ≥ 2 次 → 升级排查（自检步骤是否被跳过 / regex 是否需放宽）。

#### 6.4 通知
执行 `/notify release`（如已装）—— 向团队 IM 发送发布通知（构建号 + 提交清单 + 修复的 Issue）。

#### 6.5 记录发布耗时
追加到 `release_history`，**含 head_commit 字段**，仅保留最近 10 条。

---

## release-history 格式

存放位置：`docs/release-history.md`（项目级）

```markdown
# Release History

| 构建号 | 日期 | 分支 | 耗时(秒) | head_commit | 结果 |
|-------|------|------|---------|-------------|------|
| #N | YYYY-MM-DD | dev | NNN | `<short-hash>` | SUCCESS |
| ... | ... | ... | ... | ... | ... |
```

`head_commit` 取 build 触发时分支的 HEAD commit hash（短 7 位足够），用于 Step 6.3 的 merge-base 判断"某 commit 是否已部署"。仅记录成功构建，保留最近 10 条，超出删除最旧的。

---

## 约束

- 触发前必须经用户确认，不自动触发
- 认证信息不在日志或 comment 中输出
- 构建失败时展示失败原因，不自动重试
- curl 使用 `-sk` 跳过 SSL 验证（内网 CI 证书可能不受信）
- Step 6.3 是强制步骤（不可跳过）—— `[role]-confirmed` 状态切换是 issue-process 协议承诺的兑现

---

## 与协议层 / 规则层的关系

| 关联 | 关系 |
|------|----|
| `protocols/issue-process.md` | Step 6.3 实施 issue-process 协议中的 `[role]-confirmed` 切换 |
| `rules/core/tech-debt.md` | Step 0.3 技术债扫描的元规则依据 |
| `rules/core/artifact-based-handoff.md` | release-history 是 living artifact，按 append 模式维护 |
