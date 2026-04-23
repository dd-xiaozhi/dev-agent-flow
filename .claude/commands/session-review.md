# /session-review
> 实时审查当前会话的工作流执行情况，识别问题并自动更新 Flow。
>
> **使用**：`/session-review [--fix] [--since <time>]`
>
> - 无参数：审查当前会话全部历史
> - `--since 10m`：只审查最近 10 分钟
> - `--since 1h`：只审查最近 1 小时
> - `--fix`：发现问题后自动更新 Flow 配置

## 行为

### 第零步：需求预检（自动执行）

**在创建新功能前，先检查现有功能是否已覆盖需求。**

1. 搜索现有 agent/command/skill 是否覆盖类似场景
2. 若已有类似功能，输出提示并询问是否继续

```
⚠️ 检测到类似功能：
  - /existing-command — 已覆盖 "<场景描述>"

是否仍要继续创建新功能？
  y: 继续创建
  n: 使用现有功能（推荐）
```

### 第一步：收集会话上下文

1. **读取时间范围内的 conversation 历史**
   - 最近的 tool calls 和 results
   - 用户消息和 AI 响应摘要

2. **读取当前工作流状态**（若存在）
   ```
   .chatlabs/state/workflow-state.json
   .chatlabs/stories/<story_id>/contract.md（若有）
   ```

3. **读取最近的 flow-log**（近 24 小时）
   ```
   .chatlabs/flow-logs/YYYY-MM/*.json
   ```

### 第二步：启动 Session Auditor Agent

Agent 输入：
- `review_scope`: 审查范围（"full" | "recent_10m" | "recent_1h"）
- `auto_fix`: 是否自动修复（从 --fix 参数读取）
- `session_history`: 会话历史摘要
- `workflow_state`: 当前工作流状态
- `recent_flow_logs`: 最近的 flow-log 条目

### 第三步：Agent 分析与修复

Agent 产出：
- 审查报告（session 输出）
- 更新的文件列表（--fix 时）
- flow-log 条目

### 第四步：验证（--fix 时）

```
/fitness-run layer-boundary
```

确保更新没有引入架构违规。

## 输出格式

```
═══════════════════════════════════════
  🔍 Session Review 完成

  审查范围：<时间范围>
  发现问题：<N> 个
  已修复：<M> 个

  问题列表：
    🔴 <问题描述>
       建议：<修复方案>
       文件：<受影响的文件>

  修复详情：
    ✅ <文件> — 已更新

  日志：.chatlabs/flow-logs/YYYY-MM/FL-YYYY-MM-DD-NNN.json
═══════════════════════════════════════
```

## 错误处理

| 场景 | 处理 |
|------|------|
| 无会话历史 | 输出：`ℹ️ 暂无会话历史可审查` |
| 无需修复 | 输出：`✅ 当前会话无明显问题` |
| --fix 但无写权限 | 输出警告，跳过写入但继续分析 |

## 测试场景

创建新功能后，应该验证以下场景：

| 场景 | 预期行为 |
|------|---------|
| 无会话历史 | 输出 `ℹ️ 暂无会话历史可审查` |
| 正常审查 | 输出完整审查报告 |
| 检测到重复功能 | 提示已有类似功能 |
| --fix 执行修复 | 修改文件后验证 fitness-run |
| 边界：无 workflow-state | 跳过，使用默认状态继续分析 |

## 关联

- Agent：`.claude/agents/session-auditor.md`
- 自审：`.claude/skills/self-reflect/SKILL.md`
- 架构检查：`.claude/skills/fitness-run/SKILL.md`
