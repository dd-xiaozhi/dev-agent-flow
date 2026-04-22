# flow-link

将当前项目关联到 Flow 仓库，通过软链接方式使用 Flow。

## 使用场景

- 新项目首次使用 Flow
- Flow 仓库位置变更后修复关联
- 强制重新关联（--force）

## 命令

### 基本用法

```
/flow-link
```

### 强制重新关联

```
/flow-link --force
```

## 行为说明

1. **检查本地 Flow 仓库**：如果 `~/.cache/chatlabs-flow/dev-agent-flow/` 不存在，从 GitHub 克隆
2. **创建配置**：在 `.chatlabs/flow/.flow-source.json` 创建来源配置
3. **创建软链接**：`.chatlabs/flow/.claude` → Flow 仓库的 `.claude` 目录
4. **仓库移动检测**：如果软链接失效，自动重新建立

## 输出示例

```
✅ Flow 关联成功

仓库: https://github.com/dd-xiaozhi/dev-agent-flow.git
版本: v2.4
分支: master
本地: ~/.cache/chatlabs-flow/dev-agent-flow
路径: .chatlabs/flow/.claude

软链接已创建 → ~/.cache/chatlabs-flow/dev-agent-flow/.claude

提示: 运行 /flow-status 查看同步状态
```

## 注意事项

- 只需要执行一次，后续 `/flow-pull` 和 `/flow-push` 会自动使用此配置
- 软链接指向固定的本地路径，**不要移动 Flow 仓库目录**
- 如果确实需要移动仓库，先运行 `/flow-unlink` 再重新 `/flow-link`

## 依赖

- Git
- 网络访问（首次关联时需要克隆仓库）