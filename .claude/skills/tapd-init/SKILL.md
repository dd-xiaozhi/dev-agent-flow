---
name: tapd-init
description: 引导式初始化 TAPD 集成配置。探测项目、工作流状态映射、自定义字段，写 .chatlabs/project-config.json。仅在 /tapd-init 命令调用时触发，不要在其他场景被动加载。触发关键词：tapd 初始化、tapd init、配置 tapd、绑定项目。
model: sonnet
---

# TAPD Init Skill

> 由 `/tapd-init` 命令唯一调用。**禁止在其他场景被动触发**（避免误改配置）。

## 输入

| 参数 | 类型 | 说明 |
|------|------|------|
| `workspace_id` | int? | 用户已知则跳过项目选择 |
| `interactive` | bool | 默认 true，false 时使用环境默认值且无人工确认（CI 用） |

## 输出

| 路径 | 内容 |
|------|------|
| `.chatlabs/project-config.json` | 完整配置 |
| stdout | 配置摘要 |

## 流程

```
1. 探测：mcp__chopard-tapd__get_user_participant_projects
2. 选择 workspace（AskUserQuestion 或 --workspace-id）
3. 列出 workitem_types：mcp__chopard-tapd__get_workitem_types
4. 让用户选默认 workitem_type_id（story 用）
5. 探测状态：mcp__chopard-tapd__get_workflows_status_map(system="story")
   ↓ 对每个语义键（to_dev / to_review / to_test / done）按关键词智能匹配
   （**关键词集见下表，双扫"中文名 + 英文 key"**）：

   | 语义键      | 关键词                                              |
   |-------------|-----------------------------------------------------|
   | to_dev      | dev / develop / 开发 / 实现 / 进行                  |
   | to_review   | review / 评审                                       |
   | to_test     | test / 测试 / QA / 待测                             |
   | done        | done / 完成 / resolved / 已实现                     |

   裁决规则（按优先级降序）：
   - 唯一命中（中文名命中优先于英文 key 命中）→ 直接采用，**不询问用户**
   - 多命中 → 取"匹配位置最靠前 + 关键词最长"；若仍并列 → AskUserQuestion 仅就该语义键单点询问
   - 零命中 → AskUserQuestion 仅就该语义键单点询问，候选为全部 status

6. 同步探测 task：mcp__chopard-tapd__get_workflows_status_map(system="task")
   ↓ 复用同一套关键词集 + 裁决规则（task 仅匹配 to_dev / to_test / done 三键）
   ↓ task 原生通常只有 open / progressing / done；自定义"待测试"若失配则按规则单点询问

7. 全部语义键解决后，**一次性展示最终映射摘要**（不要求用户再次回车确认）
8. 探测自定义字段：mcp__chopard-tapd__get_entity_custom_fields(entity_type="stories")
   ↓ 列出，让用户标注哪些字段对应本地语义
9. 组装 config 对象，做 schema 校验
10. 写文件，原子操作（先写 tmp，校验通过后 mv）
11. 追加 .gitignore（若未含）
```

## 关键约束

- 不假设默认值。每个字段必须从 MCP 返回中实测取得或智能匹配命中（关键词集见流程第 5 步）
- workspace_id 一旦写入不可改（更换需删除整个 .claude/tapd/ 重新 init）
- 状态映射默认按关键词智能匹配；仅在某个语义键失配（多命中并列 / 零命中）时单点询问该键
- 全部映射确定后一次性展示最终结果，不再做"整表确认"

## 失败处理

| 场景 | 行为 |
|------|------|
| MCP 工具不可用 | 输出"未检测到 mcp__chopard-tapd__*，请先安装 TAPD MCP"，退出 |
| 用户选项 timeout | 不写部分配置，退出 |
| schema 校验失败 | 输出 jsonschema 错误，让用户修正后重试 |
| .gitignore 写入失败 | 警告，但不阻塞配置写入（用户可手工补） |

## 依赖 MCP 工具清单

- `mcp__chopard-tapd__get_user_participant_projects`
- `mcp__chopard-tapd__get_workspace_info`
- `mcp__chopard-tapd__get_workitem_types`
- `mcp__chopard-tapd__get_workflows_status_map`
- `mcp__chopard-tapd__get_entity_custom_fields`

## 关联

- Command: `.claude/commands/tapd/tapd-init.md`
- 配置：`.chatlabs/project-config.json`
