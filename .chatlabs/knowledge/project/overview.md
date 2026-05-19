# 项目概述 — overview

## 一句话定位

ChatLabs Dev-Flow：基于 Claude Code 的 **AI 驱动开发工作流配置框架**——把"产品需求 → 契约 → 实现 → 评估 → 部署"全链路编排为可配置的事件驱动流程。

本项目本身**不是业务系统**，而是 Claude Code 的 `.claude/` 配置 + 配套规范，用来驱动其他项目的 AI 开发流。

## 技术栈

| 维度 | 选型 |
|------|------|
| 语言 | Python 3.x（hooks / scripts），Markdown（agents / commands / skills / templates） |
| 运行平台 | Claude Code CLI / Desktop / Web / IDE 扩展 |
| 协议 | MCP（Model Context Protocol）连接外部工具 |
| 状态存储 | 纯文件：JSON / JSONL / Markdown，**无数据库** |
| 构建 | 无源码编译，纯配置——`git pull` 即生效 |
| 跨平台 | macOS / Linux / Windows（Windows 用 `python`，不用 `python3`） |

## 外部集成（MCP Servers）

定义于 `.mcp.json`：

| 服务器 | 用途 |
|--------|------|
| `chopard-tapd` | TAPD 工单读写（拉取需求、回写工时、子任务回填） |
| `jenkins` | CI/CD 触发与构建状态轮询 |
| `code-review-graph` | 代码评审图（实验性） |

⚠️ **凭据管理**：当前 `.mcp.json` 含明文 token，应迁移到环境变量（参见 `.env.example` 与 commit `43f3a71`）。

## 目录结构

```
chatlabs-dev-flow/
├── .claude/                  # Flow 配置（运行时被 Claude Code 加载）
│   ├── agents/               # 7 个 AI 子代理（doc-librarian / planner / generator / ...）
│   ├── commands/             # 8 个斜杠命令（扁平化：bug-fix / tapd / init-project / ...）
│   ├── skills/               # 10 个技能（按需触发的能力）
│   ├── hooks/                # 7 个事件钩子（SessionStart / PreToolUse / PostToolUse / ...）
│   ├── scripts/              # 7 个 Python 工具脚本（paths SSOT / flow_advance / task / ...）
│   ├── templates/            # 模板（contract / spec / flows[7] / story / task-report）
│   ├── settings.json         # hook & permission 配置
│   └── artifacts-layout.md   # 产物目录布局 SSOT
│
├── .chatlabs/                # 运行时数据（部分 git 跟踪，部分 ignore）
│   ├── stories/              # Story 产物（contract/spec/cases/feedback）
│   ├── reports/              # 任务/sprint/fitness 报告
│   ├── tapd/                 # TAPD 工单缓存
│   ├── knowledge/            # 项目知识库（本目录）
│   └── state/                # 机器状态（current_task / gc_last_run；流程状态与事件已迁入 task.json）
│
├── docs/                     # 人工撰写的规范文档（team-workflow.md）
├── AGENTS.md                 # 项目根索引（agents.md 开放规范统一入口）
├── CLAUDE.md                 # → AGENTS.md 软链接（兼容 Claude Code）
├── README.md                 # 用户文档
└── .mcp.json                 # MCP 服务器配置
```

## 构建与运行

无构建步骤。使用方式：

```bash
# 1. 用 Claude Code 打开项目
cd chatlabs-dev-flow

# 2. 入口命令（Claude Code REPL 中）
/start-dev-flow            # 自动识别意图并路由
/tapd-story-start <id>     # TAPD 工单开工
/story-start <描述>         # 本地需求开工
/init-project              # 重新生成知识库

# 任务续接
python .claude/scripts/task.py resume <task_id>
```

依赖：

- Python 3.x 标准库（部分脚本用到 `pyyaml`，缺失时降级到朴素解析）
- `uvx`（运行 MCP 服务器）

## 凭据与配置

| 文件 | 提交策略 | 内容 |
|------|---------|------|
| `.env` | ❌ ignored | 真实凭据 |
| `.env.example` | ✅ committed | 凭据占位符 |
| `.mcp.json` | ✅ committed | MCP 服务器（**当前含明文 token，待治理**） |
| `.chatlabs/state/` | ❌ ignored | 用户本地状态 |
| `.chatlabs/tapd/tickets/` | ❌ ignored | 工单缓存 |
| `.chatlabs/stories/` | ✅ committed | 团队共享产物 |
| `.chatlabs/reports/` | ✅ committed | 团队复盘资料 |
| `.claude/settings.local.json` | ❌ ignored | 用户本地设置 |

## 入口文档

- 项目根：`AGENTS.md`（纯索引；`CLAUDE.md` 为软链接，兼容 Claude Code）
- 知识库：`.chatlabs/knowledge/README.md`（渐进式披露索引）
- 用户文档：`README.md`
- 团队工作流：`docs/team-workflow.md`
- 产物布局：`.claude/artifacts-layout.md`
