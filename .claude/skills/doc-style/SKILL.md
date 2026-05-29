---
name: doc-style
tier: extension
status: Proposed
proposed-by: ddxu
accepted: 2026-05-28
description: Apply agent-dev-standard writing style when authoring or editing project markdown (rules / protocols / skills / docs / CHANGELOG / ADR / handoff / spec). Triggers when user writes / edits / drafts .md files, creates new rule or protocol or skill docs, writes ADR or CHANGELOG entries, or asks how to write project docs. Enforces section markers, table-first organization, Chinese-English mixed convention, bold-only-for-discipline, and anti-pattern checklist.
related-doc: docs/writing-style-analysis.md(完整版风格分析 / 13 段详尽规约)
---

# /doc-style — 项目文档书写风格规约

> **完整版:** [`docs/writing-style-analysis.md`](../../../docs/writing-style-analysis.md) (13 段 / 反模式速查 / 自检清单)
> **本 skill = 精简版:** 12 条铁律 + 速查表 + 模板骨架

---

## § Iron Rules(12 条铁律)

1. **标题用 `X — Y` 形式** —— 主标题 + 中文破折号 + 副标题定位 (例: `# Role Taxonomy — Agent 角色 + 团队角色双层规范`)
2. **顶部 blockquote 含元信息** —— 定位 / 类型 / 关联 / status,不是引文
3. **用 `## §一` 而非 `## 1`** —— 中文圆点 + 中文数字防被读成顺序步骤
4. **表格优先于列表** —— 信息有 ≥ 2 维度立刻用表格
5. **技术术语保留英文,语境用中文** —— spec / handoff / artifact 不译,共识文档 / 反哺 / 沉底用中文
6. **半角标点为主** —— 半角逗号 `,` + 半角斜杠 `/`(并列)+ 中文句号「。」(陈述句末),禁用全角逗号 `,`
7. **粗体只锚定铁律 / 概念** —— 不用粗体做美观,只用于 **must / must not**、**铁律**、关键名词锚点
8. **emoji 仅导航场景用** —— README / 受众入口可用 (📚 ⏳ ✅ ⚠️),技术 rule / protocol / skill 零 emoji
9. **每条规则附"为什么 / 失败模式"段** —— 不带 why 的规则在边界 case 无法判断
10. **改动声明必含 commit hash + 日期 + 来源** —— `(2026-05-28 加 / Issue #N)` + `commit: code@<hash>`
11. **文末必有"与其他规则的关系" + "修订日志"** —— 孤立文档无追溯链 = 失联
12. **反模式段用 `❌ / ✅` 对照表** —— 不口语化描述,直接对照

---

## § 反模式速查(10 条)

| ❌ 反模式 | ✅ 正确做法 |
|---|---|
| 长篇散文叙事 | 短句 + 表格 + 列表 |
| 全角逗号 `,` | 半角逗号 `,` |
| emoji 装饰技术内容 | 仅导航 / 状态标记用 |
| 粗体用于美观 | 粗体仅锚定铁律 / 概念 |
| 规则不带"为什么" | 必附动机段 + 失败模式 |
| 改动声明无 commit hash | `commit: code@<hash>` 必含 |
| 隐式判定 / 不留痕 | 显式 S 编号 + comment first |
| 散文式 CHANGELOG | 单条 entry 含文件路径 + 动作 + 内容 + refs + commit |
| 孤立文档(无追溯链) | 文末必有"与其他规则的关系" |
| H 标题用纯数字 (`## 1` / `## 2`) | 用 `## §一` 防顺序误读 |

---

## § 模板骨架

### Rule / Protocol 文档骨架

```markdown
# <标题> — <一句话定位>

> **定位:** <用途>
> **类型:** <节点配套 / 异象探索 / discipline-enforcing>
> **关联:** <相关 rule / protocol / skill 路径>

---

## §一 · <核心概念定义>

## §二 · <算法 / 流程>

## §三 · <硬约束(must / must not)>

## §四 · 反模式

| ❌ | ✅ |
|---|---|

## §五 · 与其他规则的关系

| 规则 | 关系 |
|---|---|

## §六 · 形式化时序 / 起源

## §修订日志

| 日期 | 修订 | 责任人 |
|---|---|---|
```

### CHANGELOG entry 模板(7 字段)

```
- YYYY-MM-DD — `<file-path>` <动作: 新建 / 加 / 改> <内容详述>(refs #N) / commit: code@<hash> [+ docs@<hash>]
```

字段:**日期 + 文件路径 + 动作 + 内容 + 关联 issue + commit + (可选)reporter / source / dogfood-status**

---

## § 自检清单(写完前过一遍)

- [ ] 标题 `X — Y` 形式
- [ ] 顶部 blockquote 元信息齐(定位 / 类型 / 关联)
- [ ] 段标用 `## §一` 而非 `## 1`
- [ ] ≥ 2 维度信息用了表格(不堆列表)
- [ ] 技术术语保留英文,解释用中文
- [ ] 半角逗号 / 半角斜杠 / 中文句号(无全角逗号)
- [ ] 粗体只锚定铁律 / 概念(不做美观)
- [ ] 技术文档零 emoji(导航 / 状态标记除外)
- [ ] 规则附"为什么"+ "失败模式"段
- [ ] 改动有 commit hash + 日期 + 来源
- [ ] 文末"与其他规则的关系"段齐
- [ ] 反模式用 `❌ / ✅` 对照表

---

## § 调用方式

| 触发方式 | 场景 |
|---|---|
| **自动加载** | 用户说"写 / 改 / 起草 / 新建 .md 文档"时 Claude 自动加载本 skill |
| **显式调用** `/doc-style` | 想强制对照规约 / 想看完整自检清单时手动调用 |
| **完整版参考** | 边界 case 不确定时读 [`docs/writing-style-analysis.md`](../../../docs/writing-style-analysis.md) |

---

## § 修订日志

| 日期 | 修订 | 责任人 |
|---|---|---|
| 2026-05-28 | 初建 / 精简版 / 派生自 `docs/writing-style-analysis.md` 13 段规约 | ddxu |
