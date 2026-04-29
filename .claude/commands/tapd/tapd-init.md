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

### 第三步：智能匹配推荐（关键词匹配）

```
对每个语义键（to_dev/to_review/to_test/done），遍历状态列表：
- 用正则匹配中文名或英文名中的关键词
- 返回置信度最高的匹配作为推荐值
- 多个候选时选择第一个
```

**匹配规则（来自 status-enum.ts）**：
| 语义键 | 优先匹配关键词 |
|--------|---------------|
| to_dev | dev, develop, 开发, 进行中 |
| to_review | review, 评审 |
| to_test | test, 测试, QA, 待测 |
| done | done, 完成, resolved, 已实现 |

### 第四步：一次性确认所有映射

```
展示格式（使用 ASCII box）：
┌─ TAPD 状态映射配置 ─────────────────────────────────┐
│ 项目：my-project (ID: 123456)                        │
├─────────────────────────────────────────────────────┤
│ [Story 状态]                                         │
│   to_dev    → IN_DEVELOPMENT    ✓ (推荐)            │
│   to_review → IN_REVIEW          ✓ (推荐)           │
│   to_test   → PENDING_TEST      ✓ (推荐)            │
│   done      → COMPLETED          ✓ (推荐)           │
├─────────────────────────────────────────────────────┤
│ [Task 状态]                                           │
│   to_dev    → IN_DEVELOPMENT    ✓ (推荐)            │
│   to_test   → PENDING_TEST      ✓ (推荐)            │
│   done      → DONE               ✓ (推荐)           │
├─────────────────────────────────────────────────────┤
│ 输入数字修改映射，或直接回车接受全部推荐               │
└─────────────────────────────────────────────────────┘
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
