---
name: coding-convention
description: 代码注释与风格规范。禁止在代码中混入流程管理元数据（ CASE 编号、作者、日期、TODO 等），只保留业务决策说明。
---

# 代码注释与风格规范

> **核心原则**：代码自解释，注释只补充"why"，不重复"what"。流程管理信息（ CASE 编号、任务状态、作者、日期）一律写入文档，不混入代码。
>
> **强制执行**：所有 Generator / Evaluator 产出必须符合本规范。Fitness hook `post-tool-linter-feedback.py` 会检测违规注释。

---

## 一、注释分界线

```
注释说的是什么？
    │
    ├── "代码正在做什么"（what）  →  不写，代码本身应自解释
    │
    ├── "这段代码属于哪个流程步骤"  →  不写，流程信息在 case.md / contract.md
    │
    └── "为什么要这样实现"（why）  →  ✅ 写，解释业务决策或非常规选择
```

**写注释前自问**：这段注释描述的是代码动作还是业务决策？前者不写，后者写。

---

## 二、禁止出现的注释

### 2.1 流程管理类（绝对禁止）

| 违规模式 | 示例 | 正确做法 |
|---------|------|---------|
| CASE / 任务编号 | `// CASE-02: 脚本执行引擎` | 删除，case 信息在 `cases/CASE-02.md` |
| 端点列表（机械重复） | `// POST /api/v1/groovy-scripts/{id}/execute → 202` | 删除，OpenAPI spec 已有 |
| 人工标记 | `// TODO: 后续优化`、`// FIXME`、`// HACK` | 写入 `docs/tech-debt-backlog.md` |
| 流程步骤 | `// Step 1: 获取配置`、`// 阶段二：执行脚本` | 删除，case.md 已描述 |
| 功能模块标注 | `// CASE-03: 执行历史查询` | 删除 |

### 2.2 项目管理类（绝对禁止）

| 违规模式 | 示例 | 正确做法 |
|---------|------|---------|
| 作者署名 | `@author jeff chen` | 删除，git blame 已记录 |
| 创建日期 | `@since 2026/04/19` | 删除，git log 已记录 |
| 最后修改人 | `@last-modified 2026-04-20` | 删除 |
| 版权声明（标准模板除外） | `// Copyright 2026 xxx` | 仅标准 license header 保留 |

### 2.3 过度自述类（禁止，代码应自解释）

| 违规模式 | 示例 | 正确做法 |
|---------|------|---------|
| 解释显而易见的事 | `// 循环处理每个用户` | 删除，循环本身即说明 |
| 重复方法名已说的 | `// 获取用户列表`（在 `getUsers()` 方法里） | 删除，方法名已说明 |
| 描述而非解释 | `// 保存配置到文件` | 删除，改为解释例外情况 |

---

## 三、允许出现的注释

### 3.1 业务规则说明

```java
// 幂等：重复提交返回 409，而非报错
if (resourceExists()) {
    return Response.status(409).build();
}

// 折扣上限：单次优惠不超过订单金额的 20%（财务合规要求）
double cappedDiscount = Math.min(discount, subtotal * 0.20);
```

### 3.2 技术决策说明（非常规实现需要解释）

```java
// 使用 WeakHashMap 而非普通 Map：允许 GC 自动回收已完成的执行记录
private final Map<String, ExecutionContext> contexts = new WeakHashMap<>();

// 双重检查锁：防止在并发初始化时创建多个连接池实例
if (instance == null) {
    synchronized (this) {
        if (instance == null) {
            instance = new ConnectionPool();
        }
    }
}
```

### 3.3 外部契约引用

```java
// 对应 contract.md §3.2 AC-005：执行超时后状态流转
// 对应 openapi.yaml /groovy-script-executions/{id} 响应 schema
```

### 3.4 安全/合规边界

```java
// 鉴权：仅允许脚本创建者或 admin 角色执行（RBAC-02）
authorize(user, "groovy-script:execute");

// 日志脱敏：手机号中间四位打码（隐私合规 PIPL-2023 §9）
String maskedPhone = phone.replaceAll("(\\d{3})\\d{4}(\\d{4})", "$1****$2");
```

---

## 四、Java 注解使用规范

### 4.1 业务语义注解（推荐）

```java
@Valid                         // 表单校验，约束来自 AC-012
@NotNull                       // 非空约束，契约字段不可缺
@JsonIgnore                    // 不暴露给客户端，安全边界
```

### 4.2 过度使用（避免）

```java
// 不好：每个字段都加 @Description
// 理由：契约已在 openapi.yaml 中定义，此处重复无意义

// 好：只在关键字段上加有业务语义的 javadoc
// @param executionId 执行记录 ID（对应 AC-007~AC-010）
```

---

## 五、执行机制

| 阶段 | 检查点 |
|------|--------|
| 编码中 | 写注释前对照"禁止列表"自检 |
| Fitness hook | `post-tool-linter-feedback.py` 检测 `CASE-` / `@author` / `@since` 模式 |
| Sprint review | 注释规范作为评审维度之一，违规 → 写入 tech-debt-backlog |
| PR 门禁 | Fitness `code-style.sh` 检查注释密度（行数占比 ≤5% 为警告） |

---

## 六、违规处置

| 场景 | 处置 |
|------|------|
| 单次发现 | 直接修复，不通知 |
| 批量发现（3+ 处同类违规） | 修复 + 追加 tech-debt-backlog 条目 |
| 同一 agent 同类违规 ×2 | 评估是约束缺失还是理解偏差，更新 generator.md 约束 |

---

## 关联

- 源头规则：generator.md §代码注释纪律
- 技术债存储：docs/tech-debt-backlog.md
- Fitness 检查：hooks/post-tool-linter-feedback.py
