# Flow Phase Reference — 阶段与门禁口径

> **定位**：本项目所有 flow 模板的**阶段语义单一真相源**。修改任何 phase 含义、新增 gate、调整门禁口径，都先改本文档，再去改 flow JSON / agent.md / start-dev-flow.md。
> **维护原则**：忠实反映现状。本项目当前**只有 1 个真 flow 门禁**（不是 4 个），强凑数量只会制造伪规范。

---

## 1. 7 个 Flow 模板全貌

```
tapd-full      doc-librarian → consensus-push → consensus-gate ⭐ → planner → generator → evaluator → git-push → merge → deploy → subtask-emit → done
local-spec     doc-librarian                                        → planner → generator → evaluator → git-push → merge → deploy                  → done
local-plan     todo-write → edit                                                                       → git-push → merge → deploy                  → done
local-vibe                  edit                                                                       → git-push → merge → deploy                  → done
bugfix-spec    doc-librarian                                        → planner → generator → evaluator → git-push → merge → deploy → tapd-close     → done
bugfix-plan    todo-write → edit                                                                       → git-push → merge → deploy → tapd-close     → done
bugfix-vibe                 edit                                                                       → git-push → merge → deploy → tapd-close     → done
                                                  ⭐ = 唯一真门禁
```

---

## 2. Phase 含义字典

| phase_id | kind | 触发方 | 完成事件 | 出现在哪些 flow |
|----------|------|--------|---------|----------------|
| `edit` | inline | 主 Claude（Read/Edit） | — | vibe/plan 系列 |
| `todo-write` | inline | 主 Claude（TaskCreate） | — | plan 系列 |
| `doc-librarian` | agent | 子 agent | `contract:frozen` | spec / tapd-full |
| `consensus-push` | command | `/tapd-consensus-push` | `tapd:consensus-pushed` | tapd-full |
| `consensus-gate` | **gate** | 事件驱动 | `tapd:consensus-approved` | tapd-full |
| `planner` | agent | 子 agent | `planner:all-cases-ready` | spec / tapd-full |
| `generator` | agent | 子 agent | `generator:all-done` | spec / tapd-full |
| `evaluator` | agent | 子 agent | `evaluator:done` | spec / tapd-full |
| `git-push` | skill | `git` skill | `git:pushed` | 全部 |
| `merge` | skill | `git` skill | `git:merged` | 全部 |
| `deploy` | skill | `jenkins-deploy` | `jenkins:deployed` | 全部 |
| `subtask-emit` | command | `/tapd-subtask-emit` | `tapd:subtask-emitted` | tapd-full |
| `tapd-close` | command | `/tapd close` | `tapd:closed` | bugfix 系列 |
| `done` | terminal | — | — | 全部 |

---

## 3. 真门禁（flow gate）— 仅 1 个

### 3.1 `consensus-gate`（tapd-full）

| 属性 | 值 |
|------|---|
| 位置 | `.claude/templates/flows/tapd-full.json` step #3 |
| kind | `gate`（流程编排引擎识别的特殊类型） |
| 通过事件 | `tapd:consensus-approved`（外部 emit） |
| 拒绝事件 | `tapd:consensus-rejected` → 跳回 `doc-librarian` |
| **preflight_check** | `contract_tbd_empty` — 推进前强制扫描 contract.md |
| 豁免标记 | frontmatter `tbd_allowed: true`（仅人工显式允许） |
| 单向性 | GAN 内任何阶段不可回退至此（evaluator FAIL 只回 generator） |

**preflight_check `contract_tbd_empty` 拒绝条件**（任一命中即阻塞）：
- §16 TBD 跟踪表数据行 > 0
- 正文残留 `TBD-\d+` 或 `TBD-(PM|BE|FE|QA)-\d+`
- 裸 `TBD` 字样

**人工流程**：
```
contract.md frozen
   ↓
/tapd-consensus-push           ── 推送到 TAPD wiki，等待评审
   ↓
人工 review wiki
   ↓
/tapd-consensus-fetch          ── 扫 wiki 评论
   ↓
   ├─ [CONSENSUS-APPROVED]     → emit tapd:consensus-approved → 前进到 planner
   └─ [CONSENSUS-REJECTED:<原因>] → emit tapd:consensus-rejected → 回 doc-librarian（版本号+1）
```

---

## 4. Agent 自检（不是 flow gate，但效果接近）

flow 模板没有的"门禁感"，由 4 个 agent 在各自 SKILL/agent.md 中以"质量门禁"小节自我 enforce：

| agent | 自检位置 | 自检要点 |
|-------|---------|---------|
| `doc-librarian` | doc-librarian.md `## 质量门禁` | TBD 角色化编号、AC 编号连续、frontmatter 字段齐全、来源标注 |
| `planner` | planner.md `## 质量门禁` | spec.md §7 三元组完整（AC ↔ 实现 ↔ 测试） |
| `generator` | generator.md（多处） | 自测通过、lint/compile 干净；**禁止以 PM/TBD 决议豁免单测** |
| `evaluator` | evaluator.md | 集成测试 PASS、AC 全覆盖 |

**与真门禁的差异**：
- 真门禁由 **flow-engine** 在 step 转换时强制（违反 → 流程卡住）
- agent 自检由 **agent 自己** 在产出前自查（违反 → agent 应自行拒绝输出 / 写 blocker）
- agent 自检的"绕过成本"更低（agent 可能放行不合规产物），所以这是**软约束**

---

## 5. 错误代价递增曲线（设计依据）

```
代价
 ▲
 │                                                  ╱ 已部署后回滚
 │                                              ╱
 │                                          ╱ deploy
 │                                       ╱ git-merge
 │                                   ╱ evaluator FAIL
 │                              ╱ generator 改代码
 │                         ╱ planner 改 spec
 │  ⭐ consensus-gate ──╱
 │         (改 contract)
 │ doc-librarian
 │    (改 source 理解)
 └─────────────────────────────────────────────────────▶ 时间
         门禁设在最便宜的拐点上（contract → planner 之前）
```

**为什么只在这一个点设真门禁**：
- contract 之前没有可机读的产物可校验（source 是任意素材）
- planner 之后产物是代码 + spec，回退代价已经显著上升
- evaluator 之后只能回 generator（重新生成），不能回评审（避免循环）

---

## 6. 与文章"4 道门禁"的对照（差异说明）

QQ 音乐 Harness Engineering 提出 4 个机读门禁，本项目实际只有 1 个。原因如下：

| QQ 音乐门禁 | 本项目对应位置 | 形态差异 |
|-----------|-------------|---------|
| 需求评审门禁（2.2） | `consensus-gate` + `preflight: contract_tbd_empty` | ✅ 形态相同（机读 + 事件驱动） |
| 设计门禁（3.3） | `planner` agent 自检 §7 三元组 | ⚠️ 软约束，非 flow gate |
| Dev 进入门禁（4.2） | `evaluator` 隐式检查（spec.md §7 引用） | ⚠️ 间接，无显式 gate |
| 服务仓库检查门禁（4.3） | N/A（单仓项目，无三仓联动） | — |

**判断**：本项目是单仓 + 流程编排框架，业务形态与 QQ 音乐 monorepo microservices 不同——**4 道门禁的具体形态不可照搬**。但"agent 自检 → 真门禁"的升级路径是清晰的，新增 gate 的判断标准见下节。

---

## 7. 何时把 agent 自检升级为 flow gate

升级标准（满足 2 条以上才考虑）：

- [ ] 该自检已经被绕过 ≥ 3 次，且每次都造成下游 blocker
- [ ] 检查项可纯机读判断（无需人工 review）
- [ ] 失败后的回退路径明确（不会形成循环）
- [ ] 检查耗时 < 5s（不影响 flow 体感速度）

满足后落地步骤：
1. 在对应 flow JSON 加 `{ "kind": "gate", "gate_event": "...", "preflight_check": "..." }`
2. 在 `flow-engine` skill 实现 preflight 检查函数
3. 本文档第 3 节登记新门禁
4. 在 sprint-review 中记录升级原因（沉淀为 experience）

---

## 8. 维护

- 新增/修改 phase → 改 flow JSON + 同步本文档第 2 节
- 新增门禁 → 改 flow JSON + 本文档第 3、6 节
- agent 自检收紧 → 改 agent.md + 本文档第 4 节
- 本文档是**人工维护**，`/init-project` 不会触碰
