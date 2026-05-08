---
name: tapd-init
description: '[Internal] 引导式初始化 TAPD 集成配置——发现项目、探测工作流状态映射与自定义字段，写 .chatlabs/project-config.json。由 start-dev-flow 按需自动调用，首次使用必须运行。'
model: sonnet
---

# /tapd-init

> **[Internal]** 由 start-dev-flow 按需自动调用，用户通常不需要直接使用。

> 引导式初始化 TAPD 集成配置。**首次使用必须运行**，生成 `.chatlabs/project-config.json`。
>
> **用法**：`/tapd-init [--workspace-id <id>] [--migrate]`

## 行为

### 第一步：发现项目
1. 调用 `mcp__chopard-tapd__get_user_participant_projects`（默认 nick 取自环境）
2. 过滤 `category == "organization"` 的条目
3. 若 `--workspace-id` 已传 → 直接用
4. 否则用 AskUserQuestion 让用户选择

### 第二步：探测工作流状态（自动）

```
1. 对 stories：`mcp__chopard-tapd__get_workflows_status_map(system="story", workitem_type_id=...)`
2. 对 tasks：同上 `system="task"`
3. 获取所有可用状态列表 + 流转规则
```

### 第三步：智能匹配（关键词命中即采用）

对每个语义键执行**双扫**（中文名 + 英文 key 同时匹配）：

| 语义键 | 关键词集 |
|--------|---------|
| to_dev | dev / develop / 开发 / 实现 / 进行 |
| to_review | review / 评审 |
| to_test | test / 测试 / QA / 待测 |
| done | done / 完成 / resolved / 已实现 |

**裁决规则（按优先级降序）**：

1. 中文名命中 + 唯一 → 直接采用，不询问用户
2. 英文 key 命中 + 唯一 → 直接采用
3. 多命中 → 取"匹配位置最靠前 + 关键词最长"的项；仍并列 → 触发第四步单点确认
4. 零命中 → 触发第四步单点确认

> 设计原则：尽量做到零额外问题通过常见配置；只有真冲突才打扰用户。

### 第四步：失配项单点确认 + 最终展示

**仅对**第三步裁决出"并列 / 零命中"的语义键，逐项使用 `AskUserQuestion` 询问：

- 并列 → 候选为并列的几个 status
- 零命中 → 候选为该 system（story/task）的全部 status

**全部解决后一次性展示最终映射**（不再要求用户回车确认）：

```
┌─ TAPD 状态映射（已自动确定）──────────────────┐
│ 项目：my-project (ID: 123456)                  │
├───────────────────────────────────────────────┤
│ [Story]                                        │
│   to_dev    → developing       (匹配: 实现)   │
│   to_review → status_10        (用户选择)     │
│   to_test   → status_9         (匹配: 测试)   │
│   done      → resolved         (匹配: 已实现) │
├───────────────────────────────────────────────┤
│ [Task]                                         │
│   to_dev    → progressing      (匹配: 进行)   │
│   to_test   → status_test      (用户选择)     │
│   done      → done             (匹配: done)   │
└───────────────────────────────────────────────┘
```

### 第五步：生成配置

```python
def generate_config(workspace_id, workspace_name, status_list, recommendations):
    # 1. 构建 status_enum（所有可用状态）
    status_enum = {
        "story": status_list["story"],
        "task": status_list["task"]
    }

    # 2. 构建 status_map（推荐值）
    status_map = {
        "story": {
            "to_dev": recommendations["story"]["to_dev"],
            "to_review": recommendations["story"]["to_review"],
            "to_test": recommendations["story"]["to_test"],
            "done": recommendations["story"]["done"]
        },
        "task": {
            "to_dev": recommendations["task"]["to_dev"],
            "to_test": recommendations["task"]["to_test"],
            "done": recommendations["task"]["done"]
        }
    }

    # 3. 生成 transitions（从 API 获取）
    transitions = {
        "story": generate_transition_map(status_list["story"], api_data),
        "task": generate_transition_map(status_list["task"], api_data)
    }

    # 4. 生成 v_status_aliases
    v_status_aliases = generate_aliases(status_enum)

    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "status_enum": status_enum,
        "v_status_aliases": v_status_aliases,
        "status_map": status_map,
        "transitions": transitions,
        "comment_markers": {...},
        "init_at": datetime.now().isoformat(),
        "schema_version": "2.0"
    }
```

### 第六步：写入配置

1. 校验所有必填字段（含 schema 校验）
2. 写入 `.chatlabs/project-config.json`
3. **追加到 `.gitignore`**：`.chatlabs/project-config.json` + `.chatlabs/tapd/tickets/`
4. 输出确认信息

---

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `--workspace-id <id>` | 否 | 跳过项目选择 |

---

## 产出

- `.chatlabs/project-config.json`
- `.gitignore` 追加（若已有则跳过）

---

## 失败处理

| 场景 | 行为 |
|------|------|
| MCP 工具未安装 | 输出安装指引，退出 |
| `get_user_participant_projects` 返回空 | 输出"账户无项目权限"，退出 |
| 所有推荐值置信度 < 0.5 | 标记为待确认，用户需手动选择 |
| 文件写入失败 | 输出错误 + 退出，不写 partial 配置 |

---

## 关联

- Skill: `.claude/skills/tapd-init/SKILL.md`
- 后续命令依赖：所有 `tapd-*` 命令都要求 project-config.json 存在
