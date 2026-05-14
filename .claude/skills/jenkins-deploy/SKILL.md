---
name: jenkins-deploy
description: Jenkins 构建部署技能。触发 CI/CD 构建、轮询构建状态、发送企业微信通知。被 /tapd start 或 start-dev-flow 在开发完成后自动调用。触发关键词：jenkins、构建部署、CI/CD、发布、deploy、构建。
model: haiku
---

# Jenkins Deploy Skill

> 开发完成后自动触发 Jenkins 构建部署，基于构建结果通知相关人员。

## 项目配置

读取 `.chatlabs/project-config.json`：

```json
{
  "jenkins": {
    "default_job": "bde-debeers-be-staging",
    "branch": "dev-cpwx-wecom-bot-test",
    "notify_on_success": true,
    "notify_on_failure": true,
    "poll_interval_seconds": 30,
    "timeout_minutes": 15
  }
}
```

若配置文件不存在，使用默认值。

## 部署分支决策（动态化）

不再写死部署分支。**优先级**：

1. 读 `.chatlabs/state/current_task` → 拿到 task_id
2. 根据 task_id 找到 task.json（`.chatlabs/task/store/<story_id>/task.json` 或 `.chatlabs/task/bug-fix/<bug_id>/task.json`）
3. 读 `task.json.git.branch` → 作为本次部署的实际分支
4. **fallback**：task.json 缺失或 `git.branch` 为空 → 用 `project-config.json.jenkins.branch`（兼容模式）
5. 若 `task.json.git.branch` 与 `project-config.json.jenkins.branch` 不一致：
   - 输出 WARN 提示用户确认（task 分支与项目默认分支不一致，按 task 分支部署）

## 流程

```
1. 读取 project-config.json.jenkins 配置（job/notify 选项）
2. 决议部署分支：
     branch = task.json.git.branch  (优先)
            或 project-config.json.jenkins.branch  (fallback)
3. 触发构建: mcp__jenkins__build_item(
     fullname=<job>,
     build_type="buildWithParameters",
     data={"BRANCH": branch}    # 若 Jenkins job 接受 BRANCH 参数
   )
   （若 job 不支持参数化，仍用 build_type="build" + 提示用户该 job 跑的是固定分支）
4. 记录 build_number
5. 轮询构建状态（poll_interval_seconds 间隔，最多 timeout_minutes）
6. 构建完成 → 获取控制台输出摘要
7. 发送企业微信通知（notify_on_success / notify_on_failure），消息含部署分支
8. 把构建信息写回 task.json：
     TaskJsonStore.update_git({last_build_number, last_build_status, last_deployed_at})
9. 返回构建结果
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

```json
{
  "job": "bde-debeers-be-staging",
  "build_number": 42,
  "status": "SUCCESS",
  "duration_seconds": 180,
  "console_summary": "...",
  "deployed_at": "2026-04-22T19:00:00+08:00"
}
```
