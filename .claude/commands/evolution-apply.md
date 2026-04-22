# /evolution-apply

> 应用用户确认的 spec 进化提案。从 `.chatlabs/flow-logs/evolution-proposals/_pending.jsonl` 中读取指定提案，执行 spec 文件变更，更新提案状态。

## 行为

### 第一步：解析参数

```
/evolution-apply --all          # 应用全部 pending 提案
/evolution-apply EP-2026040101  # 应用指定提案（逗号分隔）
/evolution-apply --discard      # 丢弃全部 pending 提案
/evolution-apply --dry-run      # 预览变更，不执行
```

### 第二步：读取提案

1. 读取 `evolution-proposals/_pending.jsonl`
2. 根据参数过滤提案
3. 若提案文件不存在或为空 → 输出 `ℹ️ 无待处理提案`，退出

### 第三步：预览变更（所有模式）

无论哪种模式，先展示变更预览：

```
═══════════════════════════════════════
  📋 提案预览

  [{id}] → {target_file}
    {action}: {变更摘要}
    风险: {risk} · 可回滚: {revertible}
    ────
    {content_after 全文（若 add/modify）}
    ────
```

### 第四步：分支处理

**`--dry-run`**：输出预览后退出，不修改任何文件。

**`--discard`**：
1. 清空 `_pending.jsonl`
2. 对应洞察的 `proposal_id` 置为 `discarded`

**`--all` 或指定 ID**：
1. **执行变更**：对每个 `action`：
   - `add`：读取 target_file，在 location 位置插入 content_after
   - `modify`：用 content_after 替换 content_before
   - `delete`：删除 content_before
2. **更新提案状态**：写入 `evolution-proposals/_applied.jsonl`（从 pending 移入）
3. **备份回滚信息**：在提案条目中添加 `applied_at` + `rollback_patch`

### 第五步：输出

```
═══════════════════════════════════════
  ✅ 进化提案已应用

  已应用：{N} 条
  变更文件：{file1, file2, ...}

  变更摘要：
  [{id}] [{action}] {target_file}

  📁 回滚备份：evolution-proposals/_applied.jsonl
═══════════════════════════════════════
```

## 输入参数

| 参数 | 说明 |
|------|------|
| `--all` | 应用所有 pending 提案 |
| `<id1>,<id2>,...` | 应用指定的提案 ID（逗号分隔） |
| `--discard` | 丢弃所有 pending 提案 |
| `--dry-run` | 预览变更，不执行 |

## 产出

- spec 文件被修改（apply 模式）
- `evolution-proposals/_pending.jsonl` 变更（pending→applied）
- `evolution-proposals/_applied.jsonl` 追加记录

## 关联

- 进化提案生成：`.claude/skills/evolution-propose/SKILL.md`
- 自审日志：`.claude/skills/self-reflect/SKILL.md`
- 洞察提炼：`.claude/skills/insight-extract/SKILL.md`
