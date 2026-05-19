---
name: story-start
description: 本地 Story 入口（spec 模式标准入口）。直接从本地 description 开工，走完整 contract → spec → cases → generator → evaluator 链路，跳过 TAPD 工作流（不同步 wiki、不回写工单）。
model: sonnet
---

# /story-start

> **本地 Story 入口命令**（spec 模式标准入口）。直接从本地 description 开工。
>
> **角色定位**：非 TAPD 需求中**复杂任务（spec 档）的标准入口**。走完整 `contract → spec → cases → generator → evaluator` 链路，但跳过 TAPD 工作流（不同步 wiki、不需产品评审、不回写工单）。
>
> 适用于：技术债 refactor、跨模块功能、多角色协同、对外 API 变更、数据迁移、需要正式契约归档的场景。
>
> 通常由 `/start-dev-flow` 的 spec 档位自动调用；用户也可直接调用。
>
> **编排层只做任务分配，不做语义理解。**

## 与 TAPD 流程的关键区别

| 环节 | /tapd start | /story-start（本地 spec） |
|------|-------------------|---------------------------|
| contract.md 生成 | ✅ doc-librarian | ✅ doc-librarian |
| spec.md / cases 生成 | ✅ planner | ✅ planner |
| 代码实现 | ✅ generator + evaluator | ✅ generator + evaluator |
| **TAPD wiki 同步** | ✅ /tapd push | ❌ **跳过** |
| **产品评审等待** | ✅ waiting-consensus | ❌ **跳过** |
| **TAPD subtask 派发** | ✅ /tapd emit | ❌ **跳过** |
| **TAPD 工单回写** | ✅ 状态推进 | ❌ **跳过** |

## 行为

### 第一步：解析 description

1. 入参为纯文本 description（可带换行）
2. description 为空 → 输出用法，退出
3. 用 `/story-start <description>` 或 heredoc 格式均可

### 第二步：分配 story_id（`{MM-dd}-{title-slug}` 格式）

**生成规则**：
1. 取 description 首行作为 title 源
2. 用 LLM 翻译为英文 → 转小写 → 空格转 `-` → 仅保留 `[a-z0-9-]` → 截断 30 字符
3. 翻译失败或为空 → `untitled`
4. 拼装：`story_id = {MM-dd}-{title-slug}`，例：`04-30-wechat-login`

**冲突解决**：
- 扫描 `.chatlabs/task/store/` 已有目录
- 同名命中 → 追加后缀 `-2`、`-3`，例：`04-30-wechat-login-2`

> **稳定性**：首次生成的 slug 是稳定 ID，写入 `meta.json.title_slug` 后续操作只读不重译。

### 第三步：归档 source

将 description 写到：
```
.chatlabs/task/store/<story_id>/source/local-description-<YYYYMMDD-HHMMSS>.md
```
文件内容格式：
```markdown
---
source: local
created_at: <timestamp>
---

<description>
```

### 第四步:创建任务记录

```bash
python .claude/scripts/task.py new <story_id> --trigger first-start
```

stdout 返回 JSON,取 `task_id`(如 `TASK-04-30-wechat-login-01`)。
若返回含 `todo_hint`,调用方可据此创建平台原生 todo。

### 第五步：创建并绑定 git 分支

调用 `git` skill 创建本 story 的特性分支，并把分支写回 `task.json.git`：

1. 前置检查：`git status --porcelain` 必须为空。脏工作区 → 阻塞流程，提示用户先 commit / stash 后重试。
2. 调 git skill：
   ```
   action: create
   type: feature
   description: <story_id>          # 用 story_id 作为分支描述（已是 slug）
   source_branch: master            # 默认值；可由用户参数覆盖
   ```
   输出形如 `{ok: true, branch: "feature/<story_id>", source: "master", switched_to: true}`。
3. 把分支结果回写 task.json：
   ```bash
   python .claude/scripts/task.py bind-branch <task_id> \
     --branch <返回的 branch> \
     --branch-type feature \
     --source-branch master \
     --merge-targets dev,uat
   ```

git skill create 失败（分支已存在 / source 不存在 / 工作区脏）→ 阻塞流程，不要继续到 flow 初始化。

### 第六步:实例化 flow 子对象(必做)

```bash
python .claude/skills/flow-engine/scripts/flow_advance.py --story-id <story_id> init \
  --flow-id local-spec \
  --task-id <task_id>
```

local-spec 模板的首步是 `doc-librarian`(无 tapd-pull),init 后 `flow.current_step.id == "doc-librarian"`,phase 自动双写为 `doc-librarian`。

### 第七步:路由 doc-librarian

- `story_id = <story_id>`（如 `04-30-wechat-login`）
- `task_id = <task_id>`（如 `TASK-04-30-wechat-login-01`）
- `contract_path: .chatlabs/task/store/<story_id>/contract.md`
- `source_dir: .chatlabs/task/store/<story_id>/source/`
- `tapd_ticket_id: null`(本地入口无 TAPD 关联)
- `tapd_ticket_url: null`
- `comments_ref: []`(无 TAPD 评论)

doc-librarian 完成后输出 `[FLOW-COMPLETE: doc-librarian]`,主 Claude 调 `/flow-advance doc-librarian` 推进到 planner。

> **不再手动写 phase**:flow_advance.py 已双写 phase / agent,/story-start 不需要再单独维护 meta.json.phase 字段。

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `<description>` | 是 | Story 描述（纯文本，可多行） |

## 产出

- 新建 `.chatlabs/task/store/<story_id>/`（story_id = `{MM-dd}-{title-slug}`）
- 归档 `source/local-description-*.md`
- 新建 TASK 记录（task.json 含 workflow / git 两个 section）
- 创建并切换到 `feature/<story_id>` 分支
- 启动 doc-librarian agent

## 与 /tapd start 的关系

| 维度 | /tapd start | /story-start |
|------|------------------|-------------|
| 来源 | TAPD 工单 | 本地 description |
| 入口 | URL / ticket_id | 纯文本 |
| TAPD 评论 | ✅ 拉取 | ❌ 无 |
| local_mapping | ticket→story | 无 TAPD 绑定 |
| 后续 PM 评审 | /tapd push | 手动方式或跳过 |

两者最终都路由到 **doc-librarian**，后续流程完全一致。

## 失败处理

| 场景 | 行为 |
|------|------|
| description 为空 | 输出用法，退出 |
| STORY 目录已存在 | 正常幂等（扫描逻辑保证不冲突） |
| `task.py new` 返回 `ok: false` | 回滚 story 目录写入 |
| git skill action=create 失败（工作区脏 / 分支已存在 / source 不存在） | 阻塞，提示用户处理后重试，**不**继续到 flow 初始化 |
| `task.py bind-branch` 失败 | 提示但不阻塞（分支已建好，task.json.git 缺失可后续补写） |
| contract.md frontmatter 损坏 | 输出错误，退出 |

## 第八步：AI 自审（理解阶段）

在 doc-librarian 阶段完成后，调用 `self-reflect` skill：

```
Skill: self-reflect
trigger: story-start
context_ref: <story_id>
```

**时机**：当 doc-librarian 输出了对需求的理解（无论是生成新契约还是修订），在路由到下一步前，自审理解质量。

**重点自审**：
- understanding 维度：边界条件、异常路径、数据约束是否已识别
- compliance 维度：是否参照了 spec/INDEX.md 的规范

## 关联

- 下游调用：`python .claude/scripts/task.py new`（分配 task_id）
- doc-librarian（生成契约，由 agent 自行判断 generate/revise 模式）
- 后续（可选）：`/tapd push`（若需 TAPD 评审，需手动绑定 ticket）
