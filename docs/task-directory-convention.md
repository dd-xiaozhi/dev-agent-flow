# 任务目录约定

> ChatLabs 后端团队 Agent Flow 的任务系统目录结构与命名规范。
>
> 适用于：`.claude/tasks/stories/` 下所有 story 产物。

---

## 顶层结构

```
.claude/tasks/
├── _index.json                   # [第 2 期引入] 所有 active story 索引
└── stories/
    ├── _template/                # 模板目录（只读）
    │   ├── contract-template.md  -> 实际软链到 docs/contract-template.md
    │   └── case-template.md      # case 任务 md 模板
    ├── STORY-001/                # 一个 story 一个目录
    │   ├── contract.md           # doc-librarian 产出
    │   ├── openapi.yaml          # doc-librarian 产出
    │   ├── changelog.md          # doc-librarian 维护（冻结后）
    │   ├── state.json            # [第 2 期引入] 机器状态文件
    │   ├── spec.md               # planner 产出
    │   └── cases/
    │       ├── CASE-01-<slug>.md
    │       ├── CASE-02-<slug>.md
    │       └── ...
    └── STORY-002/
        └── ...
```

---

## Story 目录命名

### Story ID 格式

**推荐格式**：`STORY-NNN`（三位数字，从 `STORY-001` 起）

- 如接入 TAPD，使用 TAPD 的 Story ID（`1140062001234567` 这种长数字）
- 如未接入，团队内部连号分配，记录在 `.claude/tasks/_index.json`（第 2 期）

### Story 目录内 slug 命名

文件名可读、小写、连字符分隔：

```
✅ cases/CASE-01-create-user.md
✅ cases/CASE-02-query-user-list.md
✅ cases/CASE-03-change-user-status.md

❌ cases/CASE-01.md               # 无 slug，难定位
❌ cases/case01_createUser.md     # 驼峰 + 下划线，破坏约定
❌ cases/CASE-01-创建用户.md       # 中文文件名，部分工具不友好
```

---

## 文件职责矩阵

| 文件 | 产出方 | 消费方 | 可变性 | 生命周期 |
|------|-------|--------|--------|---------|
| `contract.md` | doc-librarian | 所有人 | frozen 后走变更流程 | 贯穿 story |
| `openapi.yaml` | doc-librarian | 前后端、QA | frozen 后走变更流程 | 贯穿 story |
| `changelog.md` | doc-librarian | 所有人 | 追加写 | frozen 后 |
| `state.json`（第 2 期） | Planner 初始化，各 agent 更新 | hook / skill / 脚本 | 持续变更 | 贯穿 story |
| `spec.md` | planner | generator | spec 冻结后不改 | Planner → Generator |
| `cases/CASE-NN-*.md` | planner | generator、Evaluator | 创建后冻结，变更走反馈 | 贯穿 case 生命周期 |

---

## 命名规范

### case_id

严格格式：`<STORY-ID>/CASE-<NN>`

- `<STORY-ID>`：与所在目录一致（如 `STORY-123`）
- `<NN>`：两位数字，从 `01` 起，**编号不可重用**

### AC 编号

格式：`AC-NNN`（三位数字，从 `AC-001` 起）

- 在 `contract.md` §5 中分配
- **一旦分配永不改变**（Evaluator 依赖它做测试映射）
- 删除 AC：标 `[DELETED]` 保留条目，不删除

### 版本号

契约文档 `version` 字段遵循 **semver**：

- `major`：breaking change（接口字段变更、状态机调整）
- `minor`：add（新增 AC、新增端点）
- `patch`：fix（文案/注释修正）

---

## 目录权限

| 目录/文件 | 人工编辑 | Agent 编辑 | Hook 读取 |
|-----------|----------|-----------|-----------|
| `_template/*` | ✅（维护模板） | ❌ | ❌ |
| `stories/<id>/contract.md` | ❌（必须走 doc-librarian） | ✅ doc-librarian | ✅ |
| `stories/<id>/openapi.yaml` | ❌（必须走 doc-librarian） | ✅ doc-librarian | ✅ |
| `stories/<id>/state.json` | ⚠️ 应急时可手改 | ✅ 各 agent | ✅ |
| `stories/<id>/spec.md` | ❌ | ✅ planner | ✅ |
| `stories/<id>/cases/*.md` | ❌ | ✅ planner | ✅ |

**第 3 期引入 hook 后**：`gate-enforcer.py` 会对 `contract.md` 和 `openapi.yaml` 的编辑做门禁（必须是 doc-librarian 身份）。

---

## 生命周期示例

### 1. Story 启动（doc-librarian 阶段）

```bash
STORY_ID=STORY-123

mkdir -p .claude/tasks/stories/$STORY_ID/cases

# doc-librarian 产出 contract.md + openapi.yaml
# status: draft → review → frozen
```

### 2. Story 规划（planner 阶段）

```
.claude/tasks/stories/STORY-123/
├── contract.md              # status: frozen
├── openapi.yaml
├── spec.md                  # planner 产出
└── cases/
    ├── CASE-01-create.md    # planner 按 AC 拆分产出
    ├── CASE-02-query.md
    └── CASE-03-update.md
```

### 3. Story 执行（generator 阶段）

Generator 按 `blocked_by` 顺序逐个处理 case，每完成一个：
- 更新 case 的 `phase` 字段
- 产出代码 + 测试（带 `// covers: AC-NNN`）
- 更新 `state.json`（第 2 期引入）

### 4. Story 验收（evaluator 阶段）

Evaluator 读 `openapi.yaml` 跑契约测试，产出 `reports/verdicts/<timestamp>.json`，结果写回 `state.json.last_verdict`。

### 5. Story 变更（冻结后反馈）

```bash
# 例如 PM 发现 AC-002 错了
/feedback design-gap STORY-123 "AC-002 错误，应改为..."

# doc-librarian 接手：
# 1. 更新 contract.md（bump version 0.1.0 → 0.2.0）
# 2. 追加 changelog.md（标注影响范围=中等）
# 3. 通知 Planner/Generator 按回溯指令重入
```

---

## 归档策略

Story 完成后（所有 case `phase: done` 且 `verdict: PASS`）：

```
.claude/tasks/stories/STORY-123/   # 保留原位
```

**不立即归档**，保留原位一个 sprint，方便：
- QA 回溯验收
- Evaluator 历史 verdict 对比
- 类似需求参考

**定期归档**（gc skill 执行）：
- 完成 ≥4 周的 story 移到 `.claude/tasks/archive/stories/`
- 归档前跑一次 `contract-diff` 比对，确认无"关闭但仍被引用"的情况

---

## 常见问题

### Q: 一个 story 下的 case 太多（>20 个），怎么办？

A: 说明 story 粒度太大，拆成 2-3 个子 story。doc-librarian 应在契约评审时识别出这种情况并拒绝。

### Q: 多个 story 共享一个契约（如"公共接口"）？

A: 创建 `stories/SHARED-xxx/` 目录（前缀 SHARED 而非 STORY），但尽量避免。共享契约维护成本高，建议：
- 小的共享（<3 个端点）：直接复制到各 story 的 openapi.yaml
- 大的共享：使用 OpenAPI `$ref` 引用 `docs/openapi-components.yaml`

### Q: TAPD 集成后目录结构变化吗？

A: 不变。TAPD 集成只影响 `state.json` 的元数据字段和外部通知，目录结构保持稳定。

### Q: case 能跨 story 依赖吗？

A: **不能**。case 的 `blocked_by` 只能引用同 story 的其他 case。跨 story 协作：
- 小依赖：在 case 的"实现提示"中标注"需等 STORY-XXX 交付"
- 大依赖：合并成一个 story，或拆成两阶段（先独立交付，再集成）

---

## 演进说明

本约定是**渐进的**：

- **第 1 期**：只用 `contract.md` / `openapi.yaml` / `cases/*.md` / `spec.md`
- **第 2 期**：引入 `state.json` 和 `_index.json`
- **第 3 期**：引入 hook 对文件编辑做门禁
- **第 4 期**：引入 `feedback/` 子目录和自动化 triage
- **第 5 期**：无目录变化（只是 ctx-guard 调整）

不要一上来就搞全套。**先手工后自动化**。
