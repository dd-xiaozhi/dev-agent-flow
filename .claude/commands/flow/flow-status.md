# flow-status

查看 Flow 同步状态。

## 使用场景

- 查看当前项目与 Flow 仓库的同步状态
- 检查是否有可用的更新
- 查看未提交的变更

## 命令

```
/flow-status
```

## 输出说明

```
Flow 同步状态
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
仓库: https://github.com/dd-xiaozhi/dev-agent-flow.git
分支: master
版本: v2.4
本地: abc1234
远程: def5678
         ↑ 有更新可用
上次同步: 2026-04-22 10:00:00

变更状态:
  📝 .claude/hooks/session-start.py
  ✨ .claude/scripts/member-log-utils.py

提示: 运行 /flow-pull 获取最新版本
```

## 状态含义

| 状态 | 含义 | 操作建议 |
|------|------|---------|
| ✓ 已同步 | 本地和远程版本一致 | 无 |
| ↑ 有更新可用 | 远程有新版本 | 运行 /flow-pull |
| ⚠️ 有未提交的变更 | 本地有修改未推送 | 运行 /flow-push |
| ⚠️ 软链接无效 | 软链接断开 | 运行 /flow-link 修复 |

## 依赖

- `.chatlabs/flow/.flow-source.json` 配置文件