# TAPD API 常量速查

> 本文件是 tapd skill 调用 MCP 时所有"可写死"参数的唯一引用源。
> 完整业务规范见 `.chatlabs/knowledge/team/TAPD_Ticket_操作规范.md`（v1.0+）。
> 本文件只摘录 AI 调用 MCP 时必须严格遵守的常量与陷阱。

---

## 1. 铁律（违反即报错）

| 编号 | 铁律 | 错误后果 |
|------|------|---------|
| R-01 | 状态更新只能用 `v_status`（中文显示名），禁止用 `status`（API key） | 跨项目状态 key 不一致，必报错 |
| R-02 | 创建 ticket 用两步法：`get_workitem_types` 查 ID → 传 `workitem_type_id`；**禁止传 `workitem_type_name`** | MCP 会触发交互式列表，无法自动匹配 |
| R-03 | 优先级用 `priority_label`（`High`/`Middle`/`Low`/`Nice To Have`），禁止用 `priority` 数字 | 数字优先级跨项目语义不一致 |
| R-04 | 工时 API 的 `entity_type` 必须用 `story`（单数）；增删改查工单的 `entity_type` 必须用 `stories`（复数） | 搞反必报 422 |
| R-05 | TAPD API **不强制流转矩阵**，AI 必须自行遵守本文档的流转规则 | API 调用成功但违反业务约束 |
| R-06 | 待确认项（Item）创建时必须传 `parent_id`，TAPD 配置强制要求 | 创建失败 |
| R-07 | 写入工单后必须用 `get_stories_or_tasks` 回读校验关键字段 | 数据漂移无感知 |

---

## 2. 实体类型与 entity_type 速查

| 操作 | API | entity_type 值 |
|------|-----|----------------|
| 创建/更新/查询工单（含 Story / Subtask / Item / Bug / Epic / 长期任务） | `create_story_or_task` / `update_story_or_task` / `get_stories_or_tasks` | `stories` |
| 新增工时 | `add_timesheets` | `story`（**单数**） |
| 查询工时 | `get_timesheets` | （无需传） |
| 更新工时 | `update_timesheets` | （无需传，传 `id`） |
| 评论 | `get_comments` / `create_comments` | `entry_type`：`stories` / `tasks` / `bugs` |

> ⚠️ 评论 API 的 `entry_type` 与工单 API 的 `entity_type` 是不同维度的入参，前者按"目标实体的类目"取值。

---

## 3. workitem_type 名称（用于 `get_workitem_types.options.name`）

| Portal 显示名 | name 参数 | 用途 |
|---|---|---|
| 需求 | `需求` | 标准 Story |
| 子任务 | `子任务` | Dev/QA 个人任务拆分 |
| 待确认项 | `待确认项` | Q / CO Item |
| 长故事 | `长故事` | Epic |
| 长期任务 | `长期任务` | 长周期任务 |

> 同一对话首次创建某类型时调用一次 `get_workitem_types`，结果应在 skill 上下文内缓存复用。

---

## 4. 状态常量表（写入 `v_status` 时只能取这些中文值）

### 4.1 需求（Story）— 6 个状态

| `v_status` | 起 | 终 | 语义 |
|-----------|----|----|------|
| `规划中` | ✅ |  | PM 创建，需求规划/评审 |
| `To do` |  |  | 已确认，待 Dev 排期 |
| `实现中` |  |  | Dev 开发中 |
| `任务/测试完成` |  |  | 开发完成 + QA 通过 |
| `已实现/上线` |  | ✅ | 已部署 + PO 验收 |
| `关闭` |  | ✅ | 关闭（完结 / 废弃） |

**流转矩阵**（❌ 行 = AI 必须拒绝执行的转换）：

| 从 ＼ 到 | 规划中 | To do | 实现中 | 任务/测试完成 | 已实现/上线 | 关闭 |
|---------|-------|-------|-------|-------------|-----------|------|
| 规划中 | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| To do | ✅ | — | ✅ | ✅ | ✅ | ✅ |
| 实现中 | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| 任务/测试完成 | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| 已实现/上线 | ✅ | ✅ | ❌ | ❌ | — | ✅ |
| 关闭 | ✅ | ✅ | ❌ | ❌ | ❌ | — |

> **dev-flow 强约束**：本工作流**永不**调用 `update_story_or_task` 推进 Story 状态。Story 全部状态流转由 PM/PO 手工操作或外部自动化触发。

### 4.2 子任务（Subtask）— 4 个状态

| `v_status` | 起 | 终 | 语义 |
|-----------|----|----|------|
| `To do` | ✅ |  | 创建后待开始 |
| `实现中` |  |  | 正在执行 |
| `任务/测试完成` |  | ✅ | 任务完成（**必须填工时**） |
| `关闭` |  | ✅ | 关闭 |

**流转矩阵**：

| 从 ＼ 到 | To do | 实现中 | 任务/测试完成 | 关闭 |
|---------|-------|-------|-------------|------|
| To do | — | ✅ | ✅ | ✅ |
| 实现中 | ✅ | — | ✅ | ✅ |
| 任务/测试完成 | ✅ | ❌ | — | ✅ |
| 关闭 | ✅ | ❌ | ❌ | — |

> **工时铁律**：流转到 `任务/测试完成` 或 `关闭` 前必须有 timesheet，未填则阻止流转。
> emit 后 dev-flow 立即设为 `任务/测试完成` 并附 timesheet（场景：交付完成才回填工时）。

### 4.3 待确认项（Item / Q&CO）— 3 个状态

| `v_status` | 起 | 终 | 语义 |
|-----------|----|----|------|
| `To do` | ✅ |  | 已创建，待响应 |
| `进行中` |  |  | 处理人已开始处理 |
| `已完成` |  | ✅ | 达成结论，创建人 close |

**流转矩阵**（单向，不可回退）：

| 从 ＼ 到 | To do | 进行中 | 已完成 |
|---------|-------|-------|--------|
| To do | — | ✅ | ✅ |
| 进行中 | ❌ | — | ✅ |
| 已完成 | ❌ | ❌ | — |

> Item 一旦达成结论不可重开；如需重议应**新建 Item**。

---

## 5. 自定义字段常量表（跨项目一致，已验证）

| Portal 字段名 | API field name | 类型 | 枚举值 |
|---|---|---|---|
| 需求性质 | `custom_field_199` | 单选 | `新需求` / `需求变更` / `内部优化` / `手动调整数据` |
| 协作类型 | `custom_field_198` | 单选 | `FE + BE + QA` / `FE + QA` / `BE + QA` |
| 来源 | `custom_field_197` | 单选 | `项目初始范围` / `生产疑问` / `生产事故` / `开发期间客户反馈` / `UAT客户反馈` / `第三方团队` / `QA内部验收` / `PO内部验收` / `AM内部验收` / `UI内部验收` / `安全规范要求` / `性能规范要求` |
| 前端LOE(h) | `custom_field_196` | 数值 | — |
| 后端LOE(h) | `custom_field_195` | 数值 | — |
| QA LOE(h) | `custom_field_194` | 数值 | — |
| 关联业务线 | `custom_field_193` | 多选 | `定制项目` / `CLM` / `CLS` / `CLD` / `360` / `CLL` / `DC Connector` / `MC Connector` / `SXP` / `LANBAO` |
| 受影响客户 | `custom_field_192` | 多选 | 见 `.chatlabs/knowledge/team/TAPD_Ticket_操作规范.md §1.4` 完整 27 个枚举值 |
| 需求完整度评分 | `custom_field_200` | 数值 | — |

**标签字段（`label`，多选用 `|` 分隔）**：`阻塞` / `开发受阻` / `有风险` / `等待设计走查` / `方案已沟通` / `等待转测`

---

## 6. 子任务标题角色 prefix

emit 子任务时必须按 case 类型加角色 prefix：

| case kind / 来源 | 标题 prefix | 说明 |
|-----------------|------------|------|
| `backend` / `kind: feature` 后端 | `【BE】` | 后端开发 |
| `frontend` | `【FE】` | 前端开发 |
| `qa` / 测试 case | `【QA】` | QA 测试 |
| `pm` / 业务确认 | `【PM】` | PM 待办 |
| `ui` / 设计走查 | `【UI】` | UI 设计 |
| `infra` / `doc` 等 | `【INFRA】` / `【DOC】` | 其他（按 case.kind 推断） |

**格式**：`【{role}】{case_title}`，例如 `【BE】用户登录接口开发`。

---

## 7. 创建/更新 ticket 的最小调用模板

### 7.1 创建 Subtask（dev-flow 主要场景）

```yaml
# 第 1 步：查类型 ID（每对话每类型一次，缓存复用）
tapd:get_workitem_types
  workspace_id: "{workspace_id}"
  options:
    name: "子任务"
# 返回结果中取 id 字段

# 第 2 步：创建
tapd:create_story_or_task
  workspace_id: "{workspace_id}"
  name: "【{role}】{case_title}"
  options:
    entity_type: "stories"                  # ← 复数
    workitem_type_id: "{第1步返回的id}"      # ← 禁止 workitem_type_name
    owner: "{处理人中文名}"                 # ← 单人
    priority_label: "Middle"                # ← 中文显示名
    effort: "{预估工时}"                    # ← 单位：人时（h）
    iteration_name: "{父Story的迭代}"       # ← 必须与父一致
    parent_id: "{父Story的ticket_id}"
    description: "{case 描述}"
```

### 7.2 推进 Subtask 状态

```yaml
tapd:update_story_or_task
  workspace_id: "{workspace_id}"
  options:
    entity_type: "stories"                  # ← 复数（注意与工时不同）
    id: "{subtask_id}"
    v_status: "任务/测试完成"               # ← 中文显示名
```

### 7.3 回填工时（与状态推进配对）

```yaml
# 先查：避免同人同天同 ticket 重复
tapd:get_timesheets
  workspace_id: "{workspace_id}"
  options:
    entity_id: "{subtask_id}"
    owner: "{处理人中文名}"
    spentdate: "YYYY-MM-DD"

# 无记录 → 新增
tapd:add_timesheets
  workspace_id: "{workspace_id}"
  options:
    entity_type: "story"                    # ← 单数！
    entity_id: "{subtask_id}"
    owner: "{处理人中文名}"
    spentdate: "YYYY-MM-DD"
    timespent: "{工时小时数}"               # 精度 0.5
    memo: "{工作内容描述}"

# 有记录 → 更新（用 timesheet id）
tapd:update_timesheets
  workspace_id: "{workspace_id}"
  options:
    id: "{timesheet_id}"
    timespent: "{新工时}"
    memo: "{描述}"
```

### 7.4 创建待确认项（Item）

```yaml
# 第 1 步：查 workitem_type_id
tapd:get_workitem_types
  workspace_id: "{workspace_id}"
  options:
    name: "待确认项"

# 第 2 步：创建（必填 parent_id）
tapd:create_story_or_task
  workspace_id: "{workspace_id}"
  name: "[Q] {问题描述}"                    # 或 "[CO] {变更描述}"
  options:
    entity_type: "stories"
    workitem_type_id: "{第1步返回的id}"
    owner: "{处理人中文名}"
    priority_label: "Middle"
    parent_id: "{父Story的ticket_id}"       # ← R-06 强制
    iteration_name: "{与父需求一致的迭代}"
    description: "{详细描述}"
```

---

## 8. 跨项目验证记录摘要

| 类别 | 已验证项目 | 结果 |
|------|----------|------|
| `v_status` 中文常量 | Moto test (41664282) + Test Test (66400652) | 12/12 通过 |
| 9 个自定义字段 + 优先级 + 标签 | 同上 | 跨项目枚举完全一致 |
| 工时 `entity_type=story` | Test Test | ✅ |
| 工时 `entity_type=stories` | Test Test | ❌ 422 ParamError |
| 待确认项 `workitem_type_name` 参数 | Test Test | 失败，必须用 `workitem_type_id` |

详细数据见 `.chatlabs/knowledge/team/TAPD_Ticket_操作规范.md 附录 A`。
