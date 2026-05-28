# 六铁律详解


## ① Skill 是文件夹，不是文件

**核心**：Skill 应是一个完整的文件夹，包含脚本、模板、配置和引用文档。利用渐进式披露策略：只在主文件说明有哪些资源，让 Claude 在需要时按需读取。

### 反模式
```
.claude/skills/foo/
└── SKILL.md   ← 500+ 行,塞满所有细节
```
每次激活都吞掉大量 context。

### 正模式
```
.claude/skills/foo/
├── SKILL.md          ← ~100 行索引 + 速查
├── scripts/
│   └── helper.py     ← 复用胶水代码
└── references/
    ├── advanced.md   ← 高阶用法（按需读）
    └── examples.md   ← 详细示例（按需读）
```

### 本项目正例
- `tapd/`（scripts + references）
- `python-design/`（主文件 51 行 + 8 个 references）
- `git/`（scripts 完整）

---

## ② Description 是触发器

**核心**：description 字段用于 Claude 索引。应写"什么时候用"（USE WHEN），而非"能做什么"。

### 反模式
```yaml
description: 工作流编排引擎,推进流程步骤并维护事件流
```
Claude 不知道"什么时候"需要它。

### 正模式
```yaml
description: "USE WHEN: 主 Claude 需推进 task.json.flow / 用户问'当前到哪步了' / agent 完成后 emit 事件。OUTPUT: 状态机推进结果 + 下一步指令。DO NOT USE: 单纯查任务清单(读 task.json 即可) / 修业务代码。"
```

### 公式
```
USE WHEN: <触发场景 1> / <触发场景 2> / ...
OUTPUT: <交付物路径或形式>
DO NOT USE: <易混场景 1> / <易混场景 2> / ...
```

---

## ③ 给代码，不给死指令

**核心**：在 Skill 里放 helper 脚本和函数库。让 Claude 专注于组合与决策，而不是每次都从头写样板代码。

### 反模式
SKILL.md 里写：
```bash
sshpass -p "$SSH_DEV_PASSWORD" ssh -o StrictHostKeyChecking=no user@host \
  "grep -n 'abc123' /path/to/logs/*.log" | sed 's|.*/log_debug_.*\.log:||' | ...
```
每次都让 Claude 重新拼这串命令，容易漏单引号、错 sed 模式。

### 正模式
SKILL.md 引导调用脚本：
```bash
python scripts/fetch.py grep <env> --keyword <kw> --output <path>
```
脚本内部封装 sshpass / 清洗 / 落盘，Claude 只负责传参。

### 何时不必下沉
- 操作真的是单行命令（如 `git status`）
- 操作需要主 Claude 调 MCP（脚本调不到，仍要文字指令）—— 此时把"配置解析+文本生成+状态写回"下沉，把 MCP 调用留给主 Claude（参考 `jenkins-deploy/scripts/deploy.py`）

---

## ④ Gotchas 是灵魂

**核心**：不要重复通用知识。专门记录 Claude 实际踩过的坑（如特定边界情况），并持续更新。

### 标准格式
```markdown
## Gotchas

1. <最常踩的坑> —— 直接说后果 + 怎么避免
2. <第二常踩的坑> —— ...
...
```

### 反模式（"AI 可能" 级别猜测，不要写）
> 1. 注意 Python 版本兼容性
> 2. 处理异常时要小心

太泛，无操作价值。

### 正模式（具体到行为）
> 1. `v_status` 用中文名(R-01)，不要用 `status` 英文枚举 —— TAPD 中英文双轨，英文各项目不一致
> 2. 创建必须两步法 `get_workitem_types → workitem_type_id`(R-02)，禁传 `workitem_type_name`（API 不识别）

### 来源
- ✅ 用户实测踩过的坑（最高质量）
- ✅ 既有代码注释里的 "注意 / 警告 / TODO" 提取
- ❌ AI 凭空猜的"理论坑"（不要）

---

## ⑤ Skill 可以有"记忆"

**核心**：利用文件存储历史数据，实现跨会话的状态保持。

### 本项目实现
- `gc` skill → `.chatlabs/reports/gc/<date>.json` 记录清理历史
- `context-reset` skill → `.chatlabs/reports/handoffs.jsonl` 累积 handoff 指标
- `flow-engine` → `task.json.events[]` append-only 事件流

### 设计要点
1. 状态文件路径由各脚本在顶部硬编码（`PROJECT_DIR / ".chatlabs" / ...`），不依赖中央常量
2. 写文件用原子操作（`tmp` → rename），防并发污染
3. append-only 优于 overwrite（保留历史链）

---

## ⑥ 指令留白

**核心**：Skill 复用率高，指令应描述目标而非具体步骤，给 Claude 留出适应具体情境的灵活度。

### 反模式
```markdown
## 步骤
1. 先 git status
2. 然后 git add .
3. 然后 git commit
4. 然后 git push
```
Claude 在不同上下文（worktree / 部分 stage / pre-commit 失败）会卡住。

### 正模式
```markdown
## 步骤
1. **确认变更范围** — 区分本 task 改动 vs 预先存在的脏文件
2. **精确 stage** — 只 add 本 task 文件，不用 -A
3. **commit-push** — 按 Conventional Commits 中文规范
```
Claude 自己决定怎么实现这些目标。

### 例外
**绝对的红线**（如 `禁止 push 到 master`）要硬指令，不留白。
留白只针对"如何达成目标"的过程。

---

## 6 铁律相互关系

```
Description(触发器)
    ↓ 决定何时进入
Skill 文件夹结构
    ├─ scripts/        ← 代码下沉(铁律 3)
    ├─ references/     ← 渐进披露(铁律 1)
    └─ SKILL.md
        ├─ Gotchas     ← 踩坑记录(铁律 4)
        ├─ 指令留白    ← 目标导向(铁律 6)
        └─ 状态读写    ← 跨 session 记忆(铁律 5)
```

六条铁律不是独立检查项，是同一设计哲学的不同侧面。
