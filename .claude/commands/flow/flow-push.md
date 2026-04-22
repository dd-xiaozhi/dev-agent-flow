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

## 行为说明

1. **读取配置**：从 `.claude/.flow-source.json` 获取 Flow 仓库信息
2. **克隆/更新**：在临时目录克隆 Flow Repo
3. **同步变更**：将项目的 `.claude/` 内容同步到临时目录
4. **提交变更**：执行 `git add` + `git commit`
5. **推送变更**：执行 `git push`
6. **更新配置**：更新 `last_commit` 和 `last_synced_at`

## 实现逻辑

```bash
# 1. 读取配置
FLOW_REPO=$(cat .claude/.flow-source.json | jq -r '.flow_repo')
FLOW_BRANCH=$(cat .claude/.flow-source.json | jq -r '.flow_branch // "master"')

# 2. 临时目录操作
TEMP_DIR=$(mktemp -d)
git clone --branch $FLOW_BRANCH $FLOW_REPO $TEMP_DIR

# 3. 同步 .claude/ 内容（排除敏感文件）
rsync -av --delete \
  --exclude='settings.json' \
  --exclude='settings.local.json' \
  --exclude='tapd/' \
  --exclude='__pycache__' \
  .claude/ $TEMP_DIR/.claude/

# 4. 提交并推送
cd $TEMP_DIR
git add -A
git commit -m "$COMMIT_MSG"
git push origin $FLOW_BRANCH

# 5. 更新本地配置
cd $PROJECT_DIR
jq ".last_commit = \"$(git -C $TEMP_DIR rev-parse HEAD)\" | .last_upgraded_at = \"$(date -Iseconds)\"" \
  .claude/.flow-source.json > tmp.json && mv tmp.json .claude/.flow-source.json

# 6. 清理
rm -rf $TEMP_DIR
```

## 输出示例

成功：
```
🚀 Flow 变更已推送

Commit: abc1234
Message: feat: 添加新的 hook 类型
分支: master
URL: https://github.com/dd-xiaozhi/dev-agent-flow/commit/abc1234

其他项目可以使用 /flow-upgrade 同步此更新
```

失败（无变更）：
```
❌ 没有需要提交的变更
```

## 注意事项

- 提交消息建议使用语义化格式：`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`
- 敏感文件（settings.json、tapd/）不会被同步
- 如果推送失败，检查 GitHub 权限和网络连接
