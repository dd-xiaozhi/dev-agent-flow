# 架构约束规则

## 分层约束

### .claude/ 目录（只读）

**规则**：所有 Flow 配置位于 `.claude/`，运行时**只读不写**。

```python
# ✅ 正确：只读取配置
settings = json.load(open(".claude/settings.json"))
manifest = read_manifest()

# ❌ 错误：不要写入 .claude/
with open(".claude/settings.json", "w") as f:
    json.dump(new_settings, f)
```

**例外**：以下文件可在执行过程中更新：
- `.claude/.current_task` - 当前任务（session-start hook 管理）

### .chatlabs/ 目录（读写）

**规则**：所有运行时产物写入 `.chatlabs/`。

```
.chatlabs/
├── stories/          # Story 产物（契约、Spec、Cases）
├── state/             # 状态文件（workflow-state.json）
├── tapd/             # TAPD 工单缓存
├── reports/          # 执行报告
├── knowledge/        # 知识库（只在 init-project 时写入）
├── flow-logs/        # 自审日志
└── insights/         # 洞察结果
```

## 命令层约束

### Commands vs Skills vs Agents

| 类型 | 位置 | 用途 |
|------|------|------|
| **Command** | `.claude/commands/` | 入口命令（slash command） |
| **Skill** | `.claude/skills/` | 可复用能力（被 Agent 调用） |
| **Agent** | `.claude/agents/` | AI 角色定义（doc-librarian/planner/generator/evaluator） |

### 职责分离

```
Command
    ↓ 解析参数
    ↓ 路由到
Agent
    ↓ 执行业务逻辑
    ↓ 调用
Skill
    ↓ 提供具体能力
MCP Tool / Hook
```

**约束**：
- Command 不直接调用 MCP Tool
- Agent 不直接操作文件系统
- Skill 保持无状态（可组合）

## API 规范

### REST API 设计

契约文档中的 API 规范遵循 OpenAPI 3.0：

```yaml
openapi: 3.0.3
info:
  title: ChatLabs API
  version: 1.0.0
paths:
  /api/v1/stories:
    get:
      summary: 列出 Story
      parameters:
        - name: phase
          in: query
          schema:
            type: string
            enum: [doc-librarian, planner, generator, done]
      responses:
        '200':
          description: 成功
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Story'
```

### 端点命名规范

| 类型 | 格式 | 示例 |
|------|------|------|
| 资源集合 | `GET /resources` | `GET /api/v1/stories` |
| 单个资源 | `GET /resources/{id}` | `GET /api/v1/stories/STORY-001` |
| 创建资源 | `POST /resources` | `POST /api/v1/stories` |
| 更新资源 | `PUT /resources/{id}` | `PUT /api/v1/stories/STORY-001` |
| 删除资源 | `DELETE /resources/{id}` | `DELETE /api/v1/stories/STORY-001` |

## 数据约束

### Story ID 规则

```
TAPD 工单：直接使用 ticket_id（如 1140062001234567）
本地 Story：使用 STORY-<三位序号>（如 STORY-001）
```

### Case ID 规则

```
格式：CASE-<两位序号>
示例：CASE-01, CASE-02, ..., CASE-99
```

### 版本号规则

```
格式：<major>.<minor>.<patch>
示例：1.0.0, 1.1.0, 2.0.0
```

## TAPD 集成约束

### 工单同步

```python
# ✅ 正确：先检查配置是否存在
if project_config.get("tapd", {}).get("workspace_id"):
    tapd_client = TAPDClient(workspace_id)
else:
    raise FlowError("TAPD 未配置，运行 /tapd-init")

# ✅ 正确：使用 MCP Tool 进行操作
story = mcp__chopard_tapd__get_stories_or_tasks(...)
```

### 状态映射

| Flow Phase | TAPD Status |
|------------|-------------|
| doc-librarian | open / designing |
| waiting-consensus | testing |
| planner | open / planning |
| generator | in progress |
| done | done / closed |

## Fitness 检查约束

### 强制检查点

| 阶段 | 检查项 |
|------|--------|
| doc-librarian | openapi.yaml lint |
| planner | spec.md 完整性 |
| generator | fitness-run（每次修改后） |

### 检查失败处理

```
fitness-run FAIL
    ↓
Generator 修复问题
    ↓
重新运行 fitness-run
    ↓
通过后继续
```

## 错误处理约束

### 异常分类

```python
class FlowError(Exception):
    """Flow 执行异常基类"""

class StateError(FlowError):
    """状态管理异常"""

class ConfigError(FlowError):
    """配置缺失/无效"""

class TAPDSyncError(FlowError):
    """TAPD 同步异常"""

class ContractError(FlowError):
    """契约文档异常"""
```

### 错误恢复策略

```
可恢复错误：重试 3 次，每次间隔 2^n 秒
不可恢复错误：记录 blocker，跳过该任务
```