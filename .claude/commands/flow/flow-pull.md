# flow-pull

从 Flow 仓库拉取最新版本到本地。

## 使用场景

- 项目需要同步最新 Flow
- 获取其他项目推送的 Flow 更新
- 回滚到指定版本

## 命令

### 拉取最新版本

```
/flow-pull
```

### 强制拉取（覆盖本地修改）

```
/flow-pull --force
```

## 行为说明

1. **读取配置**：从 `.claude/.flow-source.json` 获取 Flow Repo 信息
2. **克隆/更新**：在临时目录克隆或更新 Flow Repo
3. **同步变更**：将 Flow Repo 的 `.claude/` 内容同步到项目
4. **更新配置**：更新 `last_commit` 和 `last_synced_at`

## 实现逻辑

```bash
# 1. 读取配置
FLOW_REPO=$(cat .claude/.flow-source.json | jq -r '.flow_repo')
FLOW_BRANCH=$(cat .claude/.flow-source.json | jq -r '.flow_branch // "master"')

# 2. 临时目录操作
TEMP_DIR=$(mktemp -d)
if [ -d "$FLOW_REPO" ]; then
  git -C $FLOW_REPO pull origin $FLOW_BRANCH
  cp -r $FLOW_REPO/.claude $TEMP_DIR/
else
  git clone --branch $FLOW_BRANCH $FLOW_REPO $TEMP_DIR
fi

# 3. 同步到项目（排除敏感文件）
rsync -av --delete \
  --exclude='settings.json' \
  --exclude='settings.local.json' \
  --exclude='tapd/' \
  --exclude='__pycache__' \
  $TEMP_DIR/.claude/ .claude/

# 4. 更新配置
jq ".last_commit = \"$(git -C $TEMP_DIR rev-parse HEAD)\" | .last_synced_at = \"$(date -Iseconds)\"" \
  .claude/.flow-source.json > tmp.json && mv tmp.json .claude/.flow-source.json

# 5. 清理
rm -rf $TEMP_DIR
```

## 输出示例

成功：
```
📥 Flow 已更新
  版本: v2.5
  Commit: 5be5c1e
  时间: 2026-04-22T11:35:00+08:00

请重启 session 使变更生效
```

## 注意事项

- 拉取后需要**重启 Claude Code session** 才能使变更生效
- 敏感文件（settings.json、tapd/）不会被覆盖
- 如果推送失败，检查 GitHub 权限和网络连接
