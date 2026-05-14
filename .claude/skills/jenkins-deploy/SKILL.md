---
name: jenkins-deploy
description: Jenkins 构建部署技能。触发 CI/CD 构建、轮询构建状态、发送企业微信通知。被 /tapd start 或 start-dev-flow 在开发完成后自动调用。触发关键词：jenkins、构建部署、CI/CD、发布、deploy、构建。
model: haiku
---

# Jenkins Deploy Skill

> 开发完成后自动触发 Jenkins 构建部署，基于构建结果通知相关人员。

## 项目配置

读取 `.chatlabs/project-config.json`（多环境配置）：

```json
{
  "jenkins": {
    "notify_on_success": true,
    "notify_on_failure": true,
    "poll_interval_seconds": 30,
    "timeout_minutes": 15,
    "envs": [
      {
        "env": "dev",
        "job": "bde-debeers-be-dev",
        "branch": "dev"
      },
      {
        "env": "uat",
        "job": "bde-debeers-be-uat",
        "branch": "uat"
      }
    ]
  }
}
```

**字段语义**：
- `notify_on_success` / `notify_on_failure` / `poll_interval_seconds` / `timeout_minutes`：所有环境共享的行为参数；env 项可选覆盖（仅当该环境需求不同时）
- `envs[].env`：环境标识（dev/uat/prod），用于通知消息分组与日志匹配
- `envs[].job`：该环境对应的 Jenkins job fullname
- `envs[].branch`：该环境**默认部署分支**（如 dev 环境部署 dev 分支）

若配置文件不存在或 `envs` 为空 → FATAL（无可部署环境，提示先 `/init-project` 生成骨架并填值）。

## 部署模式

### 模式 A：全量多环境部署（默认）

遍历 `envs[]`，**对每个环境**并发触发 Jenkins build：
- 每环境的部署分支 = `envs[i].branch`
- 每环境独立记录 `build_number` / `status`
- 任一环境失败不阻断其他环境（独立 promise）

### 模式 B：开发期单环境快速验证（task 上下文）

当 `.chatlabs/state/current_task` 存在且对应 task.json.git.branch 非空时：
1. 读 task.json.git.branch → 临时部署分支
2. **默认部署到 envs[0]**（约定第一个环境为开发联调环境），分支用 task 分支覆盖该 env 的默认 branch
3. 若 `task.json.git.branch` 与 `envs[0].branch` 不一致 → 输出 WARN（按 task 分支部署到开发环境）
4. 其他环境**不动**（待 PR 合并到对应分支后由模式 A 触发）

调用方通过显式参数选择模式：`mode=full` (模式 A) | `mode=task` (模式 B，默认当 current_task 存在)。

## 流程

```
1. 读取 project-config.json.jenkins 配置
2. 决议部署目标列表：
     - 模式 A: targets = envs[]
     - 模式 B: targets = [envs[0] with branch = task.json.git.branch]
3. 对每个 target 并发执行：
     a) mcp__jenkins__build_item(
          fullname=target.job,
          build_type="buildWithParameters",
          data={"BRANCH": target.branch}    # job 不支持参数化时退回 build_type="build"
        )
     b) 记录 build_number
     c) 轮询构建状态（poll_interval_seconds，最多 timeout_minutes）
     d) 构建完成 → 获取控制台输出摘要
4. 汇总所有 target 结果
5. 发送企业微信通知（按 notify_on_success/failure），消息按 env 分组列出结果
6. 把构建信息按环境写回 task.json（聚合形式）：
     TaskJsonStore.update_git({
       "builds": {
         "dev": {"build_number": 42, "status": "SUCCESS", "deployed_at": "..."},
         "uat": {"build_number": 18, "status": "FAILURE", "deployed_at": "..."}
       }
     })
7. 返回构建结果数组
```

## Blocker 等级

| 等级 | 行为 |
|------|------|
| **FATAL** | Jenkins API 失败、构建超时 |
| **WARN** | 构建成功但有警告、无配置但有默认值 |

## 依赖 MCP 工具

- `mcp__jenkins__build_item` — 触发构建
- `mcp__jenkins__get_build` — 获取构建状态
- `mcp__jenkins__get_build_console_output` — 获取构建日志摘要
- `mcp__chopard-tapd__send_qiwei_message` — 发送结果通知

## 输出

按环境聚合（targets 数组）：

```json
{
  "mode": "full",
  "targets": [
    {
      "env": "dev",
      "job": "bde-debeers-be-dev",
      "branch": "dev",
      "build_number": 42,
      "status": "SUCCESS",
      "duration_seconds": 180,
      "console_summary": "...",
      "deployed_at": "2026-04-22T19:00:00+08:00"
    },
    {
      "env": "uat",
      "job": "bde-debeers-be-uat",
      "branch": "uat",
      "build_number": 18,
      "status": "FAILURE",
      "duration_seconds": 95,
      "console_summary": "...",
      "deployed_at": "2026-04-22T19:01:30+08:00"
    }
  ],
  "summary": { "total": 2, "success": 1, "failure": 1 }
}
```
