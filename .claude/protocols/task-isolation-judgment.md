# Task Isolation Judgment — 多任务并发隔离判据

**定位：** 横向元规则，**正交于纵向组织协议**（主-分双实例 SA / SA + 项目 EL / 未来 monitor + EL 等）。任何纵向组织的任务在并发执行时，都用本规则判定是否需要 sandbox。

**类型：** 节点配套类形式化（参考 `rules/core/formalization-timing.md` 类型 B 路径）—— 节点客观存在（多任务并发）+ 规则配套缺位（隐式分散在协议外用法）+ 违规会沉底（无规则各自直接落，冲突累积无监控）+ 首次实践即基线。

---

## 核心元规则（一条）

**任务启动时问 1 个问题：**

> 这个任务和当前进行中的其他任务**有资源重叠吗**？
> - **无重叠** → 天然隔离，直接落地（修改正式文件 / commit / push）
> - **有重叠** → 人为隔离，临时产出落 sandbox，完成后 review + merge

**保守原则：** 不确定时按"有重叠"处理（沙箱不会出错，直接落可能冲突）。

---

## 资源重叠的判据清单

满足以下**任一**即视为"有重叠"：

| 类型 | 判据 |
|------|------|
| **完全重叠** | 同一文件被多任务修改（如多任务都改同一规则文件）|
| **概念重叠** | 任务主题高度相关，并发会产生重复发现 / 竞争结论 |
| **编号空间重叠** | 多任务都起 FB / GR / ADR / problem-registry 条目，需要分配编号 |
| **配套资源重叠** | 共享 rubric / 模板 / 元规则（且可能修订之）|
| **决策带宽重叠** | 多任务都有"待用户拍板"项，集中呈现会消耗用户带宽分配 |

**不重叠的典型场景：**

- 不同项目工作区（项目 A 代码 vs 项目 B 代码）
- 不同 artifact 类（项目代码 vs 协议层规则修订）
- 已切分的载体（主会话日志 vs 分身日志）

---

## Sandbox 机制（最简形式）

**Sandbox 不是顶级目录，是 task 文件下的子目录或 frontmatter 字段。**

### 目录结构

```
<task-root>/task-<id>/
├── task-<id>.md           ← 主 task 文件（含 frontmatter / PDCA / 任务日志）
└── staging/               ← sandbox（仅"有重叠"时启用）
    ├── proposed-changes.md  ← 建议改动（diff 格式或完整内容）
    ├── rationale.md         ← 改动理由
    └── artifacts/           ← 产出物草案（如新规则 draft / 新 FB 文本）
```

### Sandbox 生命周期

```
任务启动（隔离判定 = 有重叠）
  ↓
建 staging/ 目录 + frontmatter status: "draft"
  ↓
产出物落 staging/artifacts/
  ↓
任务完成 → status: "ready-for-review"
  ↓
review 责任方（按纵向组织协议决定，通常主会话）扫到
  ↓
按 confirm 流程呈现给用户（如需）
  ↓
用户 approve → review 责任方 merge 到落地文件 + status: "merged"
  ↓
归档：staging 目录可删除或保留至 task 归档（按项目惯例）
```

### Merge 时的冲突解决

- **同落地文件多 sandbox 改动** → review 责任方综合 merge（参考 git merge 心智模型）
- **编号空间冲突**（如 FB-NNN）→ merge 时主会话分配实际编号
- **概念冲突**（如两 task 提议矛盾的规则修订）→ 升级到用户拍板

> **多 dev 并发场景边界(ADR-008 / 2026-05-25 起):** 本协议主要处理**单人多 session 并发**编号空间重叠 / **多 dev 并发**(如 ADS v0.1 试装 / 多 BE feature branch)走 ADR-008 新编号格式(`<prefix>-YYYYMMDD-{hash}`)/ 详见 `docs/docs/adr/ADR-008-multi-dev-concurrent-id-schema.md`。两协议互补 — task-isolation-judgment 管单人并发 / ADR-008 管多 dev 并发。

---

## 与纵向组织协议的协同

本规则**不替代**任何纵向组织协议：

| 纵向组织 | 协议位置 | 本规则的角色 |
|---------|---------|------------|
| 用户 = SA / AI = sa-el（单实例）| `roles/` + 用户工作模式 | 不影响——SA 单干时仍按隔离判据决定是否 sandbox |
| sa-el 多实例（主-分身）| 协议层（待落地）| 分身工作时同样适用——分身遇有重叠任务也走 sandbox |
| SA + 项目 EL | handoff 协议 | EL 工作时同样适用——EL 遇跨 repo 有重叠也走 sandbox |
| 未来组织 | 待起草 | 共用本横向规则 |

**协同原则：**
- 纵向组织定义"**谁参与 + 谁做什么职责**"
- 本规则定义"**任务执行时如何处理资源**"
- 两者正交，不冲突

---

## 反模式

| 反模式 | 修正 |
|------|-----|
| 不确定是否重叠时偷懒选"无重叠"直接落 | 保守原则——不确定按"有重叠"处理 |
| 任何小改动都走 sandbox | 仅在"已识别有重叠"时启用——单 task 单干仍直接落地 |
| Sandbox 长期不 merge 沉淀 | review 责任方定期扫描（如主会话启动时扫 staging/）+ stale 报警（≥ 1 周）|
| 用 sandbox 替代纵向组织协议 | 本规则不替代职责切分——分身仍遵循纵向职责矩阵 |
| 把"美感"作为 sandbox 的理由 | 沙箱有成本（双向同步 + review 工作量），仅按事实判据使用 |

---

## 关联

- `roles/` — 纵向角色定义
- `protocols/role-taxonomy.md` — Agent 角色 + 团队角色双层规范
- `rules/core/artifact-based-handoff.md` — 文件长存基础原则（sandbox 机制的载体协议）
- `rules/core/task-lifecycle.md` — 任务内部 PDCA 流程（sandbox 不影响内部 task-life）
- `rules/core/formalization-timing.md` — 元规则形式化判据
