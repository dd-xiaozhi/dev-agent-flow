---
name: jenkins-deploy
description: Jenkins 构建部署技能。触发 CI/CD 构建、轮询构建状态、发送结果通知。被 tapd-story-start 或 start-dev-flow 在开发完成后自动调用。
---

# Jenkins Deploy Skill

> 开发完成后自动触发 Jenkins 构建部署，基于构建结果通知相关人员。

## 项目配置

读取 `.claude/jenkins-config.json`：

```json
{
  "default_job": "bde-debeers-be-staging",
  "branch": "dev-cpwx-wecom-bot-test",
  "notify_on_success": true,
  "notify_on_failure": true,
  "poll_interval_seconds": 30,
  "timeout_minutes": 15
}
```

若配置文件不存在，使用默认值。

## 流程

```
1. 读取 jenkins-config.json
2. 触发构建: mcp__jenkins__build_item(fullname=<job>, build_type="build")
3. 记录 build_number
4. 轮询构建状态（poll_interval_seconds 间隔，最多 timeout_minutes）
5. 构建完成 → 获取控制台输出摘要
6. 发送企业微信通知（notify_on_success / notify_on_failure）
7. 更新 ticket.local_mapping.deploy_info
8. 返回构建结果
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
