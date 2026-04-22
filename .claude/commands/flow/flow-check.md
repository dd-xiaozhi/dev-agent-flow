# /flow-check

> Flow 健康检查工具。在任意时刻评估 Flow 配置、命令/Skill 可用性、运行时状态、架构合规性、会话上下文的健康状况。
>
> **触发关键词**：`flow-check`、`诊断`、`健康检查`、`flow 健康`、`检查 flow`

## 与其他自审机制的区别

| 机制 | 触发时机 | 特点 |
|------|---------|------|
| `/flow-check` | 任意时刻手动/自动 | **实时诊断**，检查当前状态 |
| `self-reflect` | story-start / blocker 等关键点 | 事后 AI 自审 |
| `/workflow-review` | 周期（周/月） | 聚合分析 |
| `/sprint-review` | task 结束后 | 即时复盘 |

## 用法

```
/flow-check [--check-type <full|config|runtime|session|health>] [--verbose]
```

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--check-type` | `full` | 检查范围 |
| `--verbose` | false | 输出详细 JSON 报告 |

### check-type 可选值

| 值 | 覆盖维度 | 适用场景 |
|----|---------|---------|
| `full` | 全部 5 个维度 | 全面体检（默认） |
| `config` | 配置健康度 + 命令/Skill 可用性 | 怀疑配置损坏时 |
| `runtime` | 运行时状态 + 架构合规性 | 任务卡住时 |
| `session` | 会话上下文分析 | 复盘、交接时 |
| `health` | 快速汇总 | 快速检查 |

## 检查维度

### 1. 配置健康度
- `.claude/settings.json` 存在性和必需字段
- `.claude/tapd-config.json` 存在性和有效性
- `.chatlabs/` 目录结构完整性
- `workflow-state.json` 状态一致性

### 2. 命令/Skill 可用性
- 关键命令存在性（story-start、tapd-subtask-emit 等）
- 关键 skill 存在性（self-reflect、fitness-run 等）
- hook 脚本完整性

### 3. 运行时状态
- 当前 phase 和 verdicts
- blocker 计数
- 未处理事件数量
- TAPD 同步状态

### 4. 架构合规性
- fitness 规则检查结果
- 报告新鲜度（>1h 提示重新运行）
- fitness 目录和规则脚本存在性

### 5. 会话上下文
- 当前 phase vs 预期 phase 偏差
- phase 跳跃检测
- contract 生成状态检查
- flow-log 评分趋势（下降时提示）

## 输出格式

```
═══════════════════════════════════════
  Flow 健康检查报告
  时间: {timestamp} | 范围: {check-type} | 版本: {flow-version}
═══════════════════════════════════════

## ✓ 配置健康度  [通过] 95/100
  ✓ 无问题

## ⚠ 架构合规性  [警告] 75/100
  - fitness 报告不存在

───────────────────────────────────────
  综合健康分: 93/100  ✓ 优秀

  📋 优先建议:
  1. [P1] fitness 目录不存在
═══════════════════════════════════════
```

## 报告存储

- JSON 格式报告写入：`.chatlabs/reports/flow-check/FC-YYYYMMDD-NNN.json`
- 报告 ID 格式：`FC-YYYYMMDD-NNN`（每日从 001 开始递增）

## 自动触发建议

在以下场景建议自动调用：
1. **session-start** 时发现 phase 异常
2. **任务长期无进展** 时诊断卡点
3. **/workflow-review** 前作为前置检查
4. **用户主动输入** `/flow-check` 时

## 依赖

- `.claude/scripts/workflow-state.py` — 读取运行时状态
- `.claude/scripts/paths.py` — 路径常量定义
- `.claude/MANIFEST.md` — 读取 flow 版本号
