# /start-dev-flow

> **唯一入口命令**。用户只需描述意图，AI 自动识别并路由到对应流程。
> 其他 slash commands（如 `/story-start`、`/task-resume`）由 AI 根据意图自动调用，用户无需手动选择。

## 意图识别规则

### 用户输入 → 自动路由

| 识别条件 | 自动行为 |
|---------|---------|
| 包含 TAPD 工单 ID（纯数字/101xxxxxx 格式） | 拉取工单 → 进入需求处理 |
| 包含"tapd"关键词 | 检测 tapd-config.json → 按需初始化 → 拉取工单 |
| 描述功能/需求/bug（无工单 ID） | 进入需求处理流程（doc-librarian） |
| 包含"继续"/"恢复"/"上次的任务" | 读取 .current_task → 恢复任务 |
| 包含"复盘"/"review"/"迭代" | 调用 workflow-reviewer |
| 纯命令词（无具体内容） | 输出当前状态，等待补充 |

### TAPD 意图自动处理

当检测到 TAPD 意图时：

1. **无 tapd-config.json** → 自动调用 tapd-init skill
2. **有配置** → 解析工单 ID → 调用 tapd-pull skill → 进入 story-start 流程
3. **工单格式错误** → 反馈原因

### 需求意图自动处理

当用户直接描述需求时：

1. 调用 doc-librarian agent 生成 contract.md
2. 自动引导后续：冻结契约 → planner 拆分 case → **自动派发 TAPD Subtask** → generator 实现 → **自动 Jenkins 部署**

## 环境预检（静默，不主动输出）

```
tapd-config.json  →  存在/不存在
.current_task     →  有/无
git status        →  clean/有变更
```

只在用户询问"当前状态"或需要时展示。

## 设计原则

- **用户只需说"我要做 xxx"**，不需要知道具体命令
- AI 根据语义自动判断：TAPD 相关 → 走工单流程；直接需求 → 走本地流程
- 所有其他 commands 对用户透明，作为内部路由目标
