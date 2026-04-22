---
name: self-reflect
description: AI 自审核心技能。在故事理解、QA 打回、工作流复盘、阻断点发生、用户手动触发等场景下，对 AI 自身行为进行结构化评估，产出 flow-log 条目，写入 .chatlabs/flow-logs/。触发关键词：自审、self-reflect、AI 反思、行为复盘、feedback-loop。
---

# Self-Reflect — AI 自审技能

## 职责

在关键触发点，AI 对自身行为进行结构化自审，量化评分 + 文字分析，产出标准化的 flow-log 条目。

## 四维评分标准（每维 0-10）

| 维度 | 含义 | 0 分 | 10 分 |
|------|------|------|-------|
| **理解（understanding）** | 对需求、边界、约束的把握 | 完全理解错误 | 准确无误 |
| **实现（implementation）** | 代码/文档与契约的一致性 | 与契约多处偏离 | 完全符合契约 |
| **遵守（compliance）** | 对 spec/流程规范的遵循程度 | 大幅跳过规范 | 严格遵守 |
| **流程（workflow）** | 流程关卡和质量门的执行质量 | 跳过关卡 | 完整执行每一步 |

## 触发类型与上下文要求

| trigger | 重点关注 | 必须填写 |
|---------|---------|---------|
| `story-start` | 理解维度 + spec 对照 | dimension_notes.understanding |
| `tapd-reopen` | 逃逸根因 + 哪个维度失守 | root_cause（必填）|
| `workflow-review` | 全维度 + 跨事件模式 | insights.tags |
| `manual` | 按用户指定的维度 | 无强制要求 |
| `blocker` | 阻断发生的根因 + 是否可预防 | root_cause（必填）|

## 行为

### 第一步：收集上下文

1. 根据 `trigger` 确定要读哪些文件：
   - `story-start` → 读 `contract.md`（若存在）
   - `tapd-reopen` → 读 `blockers.md` + `meta.json`
   - `workflow-review` → 读近期（近 30 天）所有 flow-log
   - `blocker` → 读当前 blockers.md
   - `manual` → 无特定要求

2. 根据 `context_ref` 定位 story/task：
   - `story_id` → 读 `.chatlabs/stories/<story_id>/contract.md`
   - `case_id` → 读 `.chatlabs/reports/tasks/<case_id>/`

### 第二步：AI 自审（结构化思考）

**每个维度输出：**
```
评分: X/10
分析: <文字说明，支持 10 分或 0 分的关键证据>
```

**整体输出：**
```
## 自审总结

### 各维度评分
- 理解: X/10 — <一句话>
- 实现: X/10 — <一句话>
- 遵守: X/10 — <一句话>
- 流程: X/10 — <一句话>

### 总体评估
<2-3 句话，总结这次行为的质量和主要问题>

### 根因分析（仅 tapd-reopen / blocker）
<若问题严重，分析根因：是因为理解偏差？规范缺失？还是流程没走完？>

### 改进建议
<1-3 条可执行的改进建议，越具体越好>

### Insight Tags
<识别出的洞察标签，用于后续模式归纳，格式如: api-design-ambiguous, boundary-condition-missed>
```

### 第三步：写入 flow-log

1. **获取序列号**：
   ```bash
   TODAY=$(date +%Y-%m-%d)
   LOG_DIR=".chatlabs/flow-logs/${TODAY:0:7}"  # YYYY-MM
   mkdir -p "$LOG_DIR"

   # 找当月当天已存在的序列号最大值
   MAX_SEQ=$(find "$LOG_DIR" -name "${TODAY}-*.json" 2>/dev/null \
     | sed 's/.*-0*\([0-9]*\)\.json/\1/' | sort -n | tail -1)

   NEXT_SEQ=$(printf "%03d" $((10#${MAX_SEQ:-0} + 1)))
   ```

2. **写入文件**（`.chatlabs/flow-logs/YYYY-MM/FL-YYYY-MM-DD-NNN.json`）：
   ```json
   {
     "id": "FL-YYYY-MM-DD-NNN",
     "type": "<reflection|escape-analysis|blocker|understanding>",
     "trigger": "<story-start|tapd-reopen|workflow-review|manual|blocker>",
     "context_ref": "<story_id 或 case_id>",
     "timestamp": "<ISO8601>",
     "dimensions": {
       "understanding": { "score": N, "notes": "..." },
       "implementation": { "score": N, "notes": "..." },
       "compliance": { "score": N, "notes": "..." },
       "workflow": { "score": N, "notes": "..." }
     },
     "summary": "<2-3句话总体评估>",
     "root_cause": "<根因，仅 tapd-reopen/blocker 填写>",
     "suggestion": "<改进建议>",
     "insight_tags": ["tag1", "tag2"]
   }
   ```

3. **幂等保证**：若当日已达 `999` 条，停止写入并告警。

### 第四步：输出

```
═══════════════════════════════════════
  🪞 AI 自审完成

  触发: {trigger}
  上下文: {context_ref}

  各维度评分：
    理解   {N}/10
    实现   {N}/10
    遵守   {N}/10
    流程   {N}/10

  {总体评估一句话}

  日志: .chatlabs/flow-logs/YYYY-MM/FL-YYYY-MM-DD-NNN.json
═══════════════════════════════════════
```

## 触发点集成指引

**集成到 story-start**：在 doc-librarian 路由前，若 contract.md 已生成或理解已整理，触发 self-reflect，trigger=`story-start`，context_ref=`STORY-NNN`。

**集成到 tapd-subtask-reopen**：第三步（本地状态回退）完成后，第四步（TAPD 更新）开始前，触发 self-reflect，trigger=`tapd-reopen`，context_ref=`case_id`。

**集成到 workflow-review**：在 Blocker 审查完成后，作为 workflow-review 的第三步，trigger=`workflow-review`，context_ref=`workflow`。

**集成到 blocker 场景**：任何时候发现阻断点（ctx-guard 阻断、超时、知识缺失等），立即触发 self-reflect，trigger=`blocker`，context_ref=`当前 task/session`。

**用户手动触发**：用户说"自审一下"、"复盘一下这个 story"时，trigger=`manual`，context_ref=用户提供。

## 错误处理

| 场景 | 处理 |
|------|------|
| 上下文文件不存在 | 跳过读文件，继续自审（评分会更保守） |
| 写入日志失败 | 输出大写警告 `⚠️ 自审日志写入失败`，不阻断主流程 |
| 序列号达到 999 | 输出 `🚫 今日自审日志已达上限`，停止写入 |

## 关联

- 洞察提炼：`.claude/skills/insight-extract/SKILL.md`
- 进化提案：`.claude/skills/evolution-propose/SKILL.md`
- 日志目录：`.chatlabs/flow-logs/`
