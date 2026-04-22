# flow-push

推送 Flow 变更到 GitHub 仓库。

## 使用场景

- 在项目 A 开发时发现 Flow 需要改进
- 修改了 Flow 配置（如 hooks、agents、commands）
- 需要将改进分享给其他项目

## 命令

### 基本用法

```
/flow-push "feat: 添加新的 hook 类型"
```

### 带作者信息的推送

```
/flow-push --author "张三" --email "zhangsan@example.com" "fix: 修复 session-start bug"
```

## 行为说明

1. **读取配置**：从 `.chatlabs/flow/.flow-source.json` 获取 Flow 仓库信息
2. **检查变更**：确认有未提交的 Git 变更
3. **提交变更**：执行 `git add -A` + `git commit`
4. **推送变更**：执行 `git push origin master`
5. **更新配置**：更新 `last_commit` 和 `last_synced_at`

## 输出示例

成功：
```
🚀 Flow 变更已推送

Commit: abc1234
Message: feat: 添加新的 hook 类型
分支: master
URL: https://github.com/dd-xiaozhi/dev-agent-flow/commit/abc1234

其他项目可以使用 /flow-pull 同步此更新
```

失败（无变更）：
```
❌ 没有需要提交的变更
```

失败（有冲突）：
```
❌ 推送失败: src refspec master does not match any.
   请确保在 master 分支上推送
```

## 注意事项

- 提交消息建议使用语义化格式：`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
- 如果推送失败，检查 GitHub 权限和网络连接
- 推送前确保本地仓库是最新的（如果有冲突先拉取）

## 依赖

- `.chatlabs/flow/.flow-source.json` 配置文件（需要先运行 `/flow-link`）