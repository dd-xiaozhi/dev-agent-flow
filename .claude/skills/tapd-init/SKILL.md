---
name: tapd-init
description: 引导式初始化 TAPD 集成配置。探测项目、工作流状态映射、自定义字段，写 .claude/tapd-config.json。仅在 /tapd-init 命令调用时触发，不要在其他场景被动加载。触发关键词：tapd 初始化、tapd init、配置 tapd、绑定项目。
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
| `.claude/tapd-config.json` | 完整配置（schema：`.claude/templates/schemas/tapd/tapd-config.schema.json`） |
| stdout | 配置摘要 |

## 流程

```
1. 探测：mcp__chopard-tapd__get_user_participant_projects
2. 选择 workspace（AskUserQuestion 或 --workspace-id）
3. 列出 workitem_types：mcp__chopard-tapd__get_workitem_types
4. 让用户选默认 workitem_type_id（story 用）
5. 探测状态：mcp__chopard-tapd__get_workflows_status_map(system="story")
   ↓ 列出英文 status，让用户分别为 to_dev/to_review/to_test/done 指定
6. 同步探测 task：mcp__chopard-tapd__get_workflows_status_map(system="task")
   ↓ 注意：task 原生只有 open/progressing/done。若有自定义"待测试"，提示用户填写
7. 探测自定义字段：mcp__chopard-tapd__get_entity_custom_fields(entity_type="stories")
   ↓ 列出，让用户标注哪些字段对应本地语义
8. 组装 config 对象，做 schema 校验
9. 写文件，原子操作（先写 tmp，校验通过后 mv）
10. 追加 .gitignore（若未含）
```

## 关键约束

- 不假设默认值。每个字段必须从 MCP 返回中实测取得或用户明确指定
- workspace_id 一旦写入不可改（更换需删除整个 .claude/tapd/ 重新 init）
- 状态映射写入前必须人工确认（屏幕展示英文名 + 让用户挑选）

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
- Schema: `.claude/templates/schemas/tapd/tapd-config.schema.json`
