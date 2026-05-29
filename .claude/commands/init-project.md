---
name: init-project
description: 扫描项目并生成/更新 Claude Code 项目文档体系（知识库 + 入口文档）。适用于首次接入、架构重构或文档过时场景。
model: opus
---

# /init-project

> 扫描项目，生成或增量更新知识库 + 入口文档 + 项目级配置骨架。

## 用法

```bash
/init-project    # 无参数，对当前 git 仓库根执行
```

## 触发

| 场景 | 行为 |
|------|------|
| 首次接入新项目 | 模式 A 全量生成 |
| 架构重构 / 文档过时 | 模式 B 按 diff 增量更新 |
| `.scan.json` 损坏 | 视为模式 A，旧文件按 B 红线保留 |

## 流程

```mermaid
flowchart TD
    A[读 .scan.json] --> B{是否存在}
    B -->|不存在| C[模式 A 全量]
    B -->|存在| D[模式 B 增量]
    C --> E[扫描建模<br/>技术栈/架构/模块]
    D --> E
    E --> F{模式}
    F -->|A| G[TaskCreate 并行 5 子任务<br/>coding-style / project / arch / fitness / modules]
    F -->|B| H[diff 后定向更新对应文件]
    G --> I[写 README + AGENTS.md + 软链 CLAUDE.md]
    H --> I
    I --> J[project-config.json 骨架兜底]
    J --> K1[git init-config<br/>总跑·幂等]
    K1 --> K2{team_roles 全空?}
    K2 -->|是| K3[AskUserQuestion 询问<br/>workspace_id + name<br/>→ tapd init.py setup]
    K2 -->|否| K4{envs[] 空?}
    K3 --> K4
    K4 -->|是| K5[AskUserQuestion 询问<br/>dev/uat envs → 写 jenkins.envs]
    K4 -->|否| K6
    K5 --> K6[覆盖写 .scan.json]
```

**模式 B 兜底**：AGENTS.md 缺失或格式退化 → 重新生成；CLAUDE.md 不是软链则补齐。

**模式 B 更新映射**：

| 变化 | 操作 |
|------|------|
| 新增/删除模块 | 创建/删除 `tech/backend/modules/<name>.md` + README 同步 |
| 模块内文件变化 | 仅更新对应模块的「文件路由表」段 |
| 技术栈变化 | 更新 `project/overview.md` + README 元信息 |
| 编码规范变化 | 追加到 `coding-style.md`（不删旧） |
| 架构模式变化 | 更新 `project/architecture.md` + README |
| `team/` 新增文档 | 更新 `knowledge/README.md` + `team/INDEX.md` |
| `experience/` | 不自动处理（由 sprint-review 人工写入） |

**project-config.json 骨架**（文件不存在才生成，存在则不动）：

```json
{
  "ssh_servers": [],
  "log": { "paths": [], "output_dir": ".chatlbs/logs_query/{env}" },
  "jenkins": {
    "notify_on_success": true, "notify_on_failure": true,
    "poll_interval_seconds": 30, "timeout_minutes": 15, "envs": []
  },
  "tapd": {
    "enabled": false, "workspace_id": null, "workspace_name": null, "last_sync_at": null,
    "status_enum": {
      "story": ["规划中", "To do", "实现中", "任务/测试完成", "已实现/上线", "关闭"],
      "task":  ["To do", "实现中", "任务/测试完成", "关闭"],
      "item":  ["To do", "进行中", "已完成"],
      "bug":   []
    },
    "status_map": {
      "story": { "to_dev": "To do", "to_review": "规划中", "to_test": "任务/测试完成", "done": "已实现/上线" },
      "task":  { "to_dev": "To do", "to_review": null,     "to_test": "任务/测试完成", "done": "关闭" },
      "item":  { "to_do":  "To do", "in_progress": "进行中", "done": "已完成" },
      "bug":   { "to_dev": null,    "to_review": null,     "to_test": null,            "done": null }
    },
    "comment_markers": {
      "consensus_approved": "[CONSENSUS-APPROVED]",
      "consensus_rejected": "[CONSENSUS-REJECTED:",
      "qa_passed": "[QA-PASSED]", "qa_rejected": "[QA-REJECTED:",
      "subtask_emitted": "[SUBTASK-EMITTED]"
    },
    "team_roles": { "pm": [], "be": [], "fe": [], "qa": [], "other": [] }
  },
  "git": {
    "branches": {
      "feature": { "prefix": "feature/", "source": "master",  "merge_targets": ["dev", "uat"] },
      "bugfix":  { "prefix": "bugfix/",  "source": "current", "merge_targets": ["current-feature"] },
      "hotfix":  { "prefix": "hotfix/",  "source": "master",  "merge_targets": ["dev", "uat"] },
      "release": { "prefix": "release/", "source": "develop", "merge_targets": ["main", "develop"] }
    },
    "merge": { "strategy": "chained", "no_ff": true, "pull_before_merge": true, "allow_force_push": false, "return_to_branch": "current" },
    "commit_push": { "conventional_zh": true, "allow_no_verify": false, "auto_set_upstream": true, "auto_add_all": false },
    "worktree": { "root": ".chatlabs/worktrees" },
    "cleanup": { "allowed_prefixes": ["bugfix/"], "require_merged_to": "current", "delete_remote": true }
  }
}
```

**字段归集原则**：相关配置按职责对象聚合到同一对象下（`log.*` / `jenkins.*` / `tapd.*` / `git.*`），禁止顶层散落。`git.branches.<type>.source` 支持特殊值 `current`（当前分支）/ `current-feature`（最近活跃 feature 分支）。

## init 三件套（2026-05-29 新增）

骨架生成后，按以下顺序自动执行三个 init 入口。**幂等 + 仅配置缺失时引导**——已配过的项目重跑 /init-project 不会被打扰。

| 步骤 | 触发条件 | 执行命令 | 失败处理 |
|------|---------|---------|---------|
| **git init-config** | 总跑（init_config.py 内部幂等） | `python .claude/skills/git/scripts/init_config.py` | 写 Blocker，续跑 tapd + jenkins |
| **tapd init** | `tapd.team_roles` 各角色数组全为空（首次配 TAPD） | (1) AskUserQuestion 询问 `workspace_id` + `workspace_name` <br/> (2) `python .claude/skills/tapd/scripts/init.py setup --workspace-id <id> --workspace-name "<name>"` <br/> (3) 完成后 AskUserQuestion 引导用户复核 `other` 桶角色分类 | `$TAPD_TOKEN` 未设 / 脚本失败 → 写 Blocker 提示后续单跑 `/tapd init`，**不阻断** |
| **jenkins envs** | `jenkins.envs[]` 为空 | AskUserQuestion 询问环境清单（典型 dev/uat），每环境收集 `env / job / branch` 三字段后写入 `project-config.json.jenkins.envs` | 用户选跳过 → 写 Blocker "jenkins 未配置，部署相关流程将报 FATAL"，**不阻断** |

### 幂等判断细则

```python
config = read_project_config()

# 1. git: 永远跑(init_config.py 内部幂等)
run_git_init_config()

# 2. tapd: 检查 team_roles 是否全空
tapd_team = config.get("tapd", {}).get("team_roles", {})
all_empty = all(
    len(tapd_team.get(role, [])) == 0
    for role in ("pm", "be", "fe", "qa")
)
if all_empty:
    run_tapd_init_guided()   # AskUserQuestion + init.py setup
# 否则跳过(不打扰已配置的项目)

# 3. jenkins: 检查 envs[] 是否空
if not config.get("jenkins", {}).get("envs"):
    run_jenkins_envs_guided()   # AskUserQuestion + 写入 envs
# 否则跳过
```

### AskUserQuestion 文案模板

**TAPD（仅 team_roles 全空时）:**

第一问 — 是否现在初始化:
> 检测到 TAPD 尚未配置。是否现在初始化?（需要 `workspace_id` + `workspace_name`，且已 `export TAPD_TOKEN`）

选项: `现在初始化(推荐)` / `跳过，后续单跑 /tapd init`

若选"现在初始化",再询问 `workspace_id`(数字) 和 `workspace_name`(自由文本)。跑完 `init.py setup` 后,根据脚本输出的成员列表询问 `other` 桶里哪些应该归到 PM / BE / FE / QA。

**Jenkins（仅 envs[] 空时）:**

第一问 — 是否现在配置:
> 检测到 Jenkins envs 尚未配置。是否现在引导填写?（典型有 dev + uat 两套环境）

选项: `现在配置(推荐)` / `跳过，后续手填 project-config.json`

若选"现在配置",依次问每个环境的 `env`(如 dev/uat) / `job`(jenkins job fullname) / `branch`(默认部署分支)。允许填多个,允许 0 个完成后退出。

## 输入参数

无参数。命令对当前 git 仓库根执行。

## 产出

- `AGENTS.md`（纯索引，统一入口）+ `CLAUDE.md`（软链）
- `.chatlabs/project-config.json`（缺失才生成空骨架；`git.merge` / `tapd.*` / `jenkins.envs` 段由 init 三件套填充）
- `.chatlabs/knowledge/README.md` + `.chatlabs/knowledge/.scan.json`
- `.chatlabs/knowledge/{team,project,tech/backend,asset}/`（含 `modules/`、`asset/{contract,frozen,tech-proposals,test-cases,tech-debt}/`）
- `.chatlabs/knowledge/project/experience/`（空目录占位，sprint-review 写入）
- 本地仓库 `.git/config`（git init-config 调整 merge.ff / pull.rebase / push.default 等）
- (可选) TAPD 工作流配置 + 团队成员角色分类（首次配 TAPD 时由用户引导写入）
- (可选) Jenkins envs 部署环境清单（首次配 Jenkins 时由用户引导写入）

## 失败处理

| 场景 | 行为 |
|------|------|
| 技术栈推断失败 | 写 Blocker，跳过空骨架占位，仍生成 README + AGENTS.md |
| 模式 A 检测到 `knowledge/` 已部分存在 | 视为模式 B 按 diff 补齐 |
| 模式 B 团队自定义受保护段落 | 不覆盖，仅追加新模式 |
| 模式 B 无 diff | 仅做 AGENTS.md 兜底校验后退出 + init 三件套常规检查 |
| 单子任务失败 | 该文件留 placeholder + Blocker，不阻塞其他 |
| `git init_config.py` 失败（非 git 仓库 / 配置只读） | 写 Blocker，续跑 tapd + jenkins |
| `$TAPD_TOKEN` 未设 或 tapd init 脚本失败 | 写 Blocker 提示后续单跑 `/tapd init`，续跑 jenkins |
| 用户对 tapd / jenkins 选"跳过" | 写 Blocker 记录"<X> 未配置，相关流程将报 FATAL"，续跑 |

## AGENTS.md 红线

- **必须是纯索引**：一句话项目描述 + 知识库目录指向 + coding-style / fitness-rules 路径。不得内联技术栈详情、模块列表、集成说明、运行环境（归 `knowledge/project/overview.md`）。
- `CLAUDE.md` 必须是指向 `AGENTS.md` 的相对软链接（`ln -s AGENTS.md CLAUDE.md`），不得是副本。
- 受保护段落不覆盖：`asset/` 全部、`modules/*.md` 的「注意事项」「设计决策」、`project/core-functions.md` 手动补充段、`coding-style.md` / `fitness-rules.md` 团队补充段（只允许追加）。

## 关联

- Skill: `init-project`（扫描器，承担所有 ripgrep / 框架检测细节）
- 入口文档: `AGENTS.md` / `.chatlabs/knowledge/README.md`
- init 三件套下游脚本:
  - `.claude/skills/git/scripts/init_config.py`（无参数，幂等）
  - `.claude/skills/tapd/scripts/init.py setup`（需 `$TAPD_TOKEN`）
  - jenkins envs 直接写 `.chatlabs/project-config.json.jenkins.envs[]`（无独立脚本）
- 后续: `/start-dev-flow`、`/tapd init`（如重新配置 TAPD）
