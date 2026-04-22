# flow-pull

从 Flow 仓库拉取最新版本。

## 使用场景

- 项目 B 需要同步最新 Flow
- 获取其他项目推送的 Flow 更新
- 回滚到指定版本

## 命令

### 拉取最新版本

```
/flow-pull
```

### 切换到指定版本

```
/flow-pull --version v2.3
```

### 强制拉取（覆盖本地修改）

```
/flow-pull --force
```

## 行为说明

1. **检查配置**：确认项目已关联 Flow
2. **验证软链接**：检查 `.claude` 软链接是否有效
3. **拉取更新**：执行 `git fetch` + `git pull`
4. **版本切换**（可选）：如果指定 `--version`，切换到指定 tag/commit
5. **更新配置**：更新 `last_commit` 和 `last_synced_at`

## 输出示例

成功（正常拉取）：
```
📥 Flow 已更新
  版本: v2.5
  Commit: def5678
  更新内容:
    - feat: 新增成员活动日志
    - fix: session-start 修复
    - docs: 更新 README

请重启 session 使变更生效
```

成功（版本切换）：
```
📥 Flow 已切换版本
  从 v2.4 → v2.3
  Commit: abc1234

请重启 session 使变更生效
```

失败（未关联）：
```
❌ 项目未关联 Flow，请先运行 /flow-link
```

## 注意事项

- 拉取后需要**重启 Claude Code session** 才能使变更生效
- 如果有未提交的本地修改，需要先提交或使用 `--force`
- 切换版本会改变 Flow 的功能，谨慎操作

## 依赖

- `.chatlabs/flow/.flow-source.json` 配置文件（需要先运行 `/flow-link`）
- 网络访问