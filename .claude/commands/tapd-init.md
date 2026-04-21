# /tapd-init

> 引导式初始化 TAPD 集成配置。**首次使用必须运行**，生成 `.claude/tapd-config.json`。
>
> **用法**：`/tapd-init [--workspace-id <id>]`

## 行为

### 第一步：发现项目
1. 调用 `mcp__chopard-tapd__get_user_participant_projects`（默认 nick 取自环境）
2. 过滤 `category == "organization"` 的条目
3. 若 `--workspace-id` 已传 → 直接用
4. 否则用 AskUserQuestion 让用户选

### 第二步：探测工作流状态映射
1. 对 stories：`mcp__chopard-tapd__get_workflows_status_map(system="story", workitem_type_id=...)`
   - 工作流类别先用 `mcp__chopard-tapd__get_workitem_types` 列出，让用户选默认类别
2. 对 tasks：同上 `system="task"`
3. 把英文 status 列出来，用 AskUserQuestion 让用户分别为 to_dev/to_review/to_test/done 指定映射
4. **不假设默认值**——每个 workspace 的工作流不同

### 第三步：探测自定义字段（可选）
1. `mcp__chopard-tapd__get_entity_custom_fields(entity_type="stories")`
2. 若有重要字段（owner/module/severity 等映射不上系统字段），让用户确认 custom_field_NN

### 第四步：写配置
1. 校验所有必填字段（含 schema 校验）
2. 写入 `.claude/tapd-config.json`
3. **同步追加到 `.gitignore`**：`.claude/tapd-config.json` + `.chatlabs/tapd/tickets/`
4. 输出确认信息

## 输入

| 参数 | 必填 | 说明 |
|------|------|------|
| `--workspace-id <id>` | 否 | 跳过项目选择 |

## 产出

- `.claude/tapd-config.json`（schema：`.claude/templates/schemas/tapd/tapd-config.schema.json`）
- `.gitignore` 追加（若已有则跳过）

## 失败处理

| 场景 | 行为 |
|------|------|
| MCP 工具未安装 | 输出安装指引，退出 |
| `get_user_participant_projects` 返回空 | 输出"账户无项目权限"，退出 |
| 状态映射用户拒绝选择 | 写 `TBD` 占位 + Blocker（信息-需求缺失） |
| 文件写入失败 | 输出错误 + 退出，不写 partial 配置 |

## 关联

- Skill: `.claude/skills/tapd-init/SKILL.md`
- Schema: `.claude/templates/schemas/tapd/tapd-config.schema.json`
- 后续命令依赖：所有 `tapd-*` 命令都要求 tapd-config.json 存在
