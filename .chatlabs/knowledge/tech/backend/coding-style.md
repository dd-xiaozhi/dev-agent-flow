---
name: backend-coding-style
description: 后端编码风格、注释纪律、命名约定。所有后端 agent 产出的代码必须遵循。
---

# 后端编码风格

> 技术栈：Java 17 + Spring Boot 3.x
>
> **核心原则**：代码自解释，注释只补充 why，不重复 what。流程管理信息一律进文档，不混入代码。

---

## 一、注释纪律

### 禁止出现的注释

| 类别         | 示例                                    | 正确做法                          |
|-------------|----------------------------------------|----------------------------------|
| 流程管理类   | `// CASE-02: xxx` / `// Step 1: xxx`    | 删除，流程信息在 `cases/*.md`     |
| 人工标记     | `// TODO` / `// FIXME` / `// HACK`      | 写入 `docs/tech-debt-backlog.md` |
| 项目管理类   | `@author` / `@since` / `@last-modified` | 删除，git log / blame 已记录      |
| 过度自述     | `// 循环处理每个用户`                     | 删除，代码本身即说明              |

### 允许出现的注释

只解释 **why**，不解释 what：

- **业务规则**：`// 折扣上限 20%，财务合规要求`
- **非常规选型**：`// 用 WeakHashMap 允许 GC 回收已完成记录`
- **契约引用**：`// 对应 contract.md §3.2 AC-005`
- **安全/合规**：`// 日志脱敏，PIPL §9`

---

## 二、命名约定

| 元素         | 风格                  | 示例                        |
|------------|---------------------|---------------------------|
| 类 / 接口   | PascalCase           | `UserService`, `OrderController` |
| 方法 / 变量  | camelCase            | `getUserById`, `orderList` |
| 常量        | UPPER_SNAKE_CASE    | `MAX_RETRY_COUNT`, `DEFAULT_PAGE_SIZE` |
| 包          | lowercase（单数）     | `com.example.service`     |
| 测试类      | `XxxTest`（单元）/`XxxIT`（集成） | `UserServiceTest` |
| 资源类（Controller）| PascalCase + Controller suffix | `ScriptController` |

---

## 三、包结构

Spring Boot 标准分层：

```
com.example.<module>
├── controller/          # REST 入口，参数校验
├── service/             # 业务逻辑，事务边界
├── repository/          # 数据访问（JPA/MyBatis）
├── domain/              # 实体、值对象、领域事件
├── dto/                 # 数据传输对象（Request/Response）
├── config/              # 配置类
└── exception/           # 异常定义（业务异常 vs 系统异常）
```

**禁止**：`controller/` 直接调 `repository/`（绕过 service 层）。

---

## 四、错误处理

| 类型           | 使用场景                                    |
|---------------|-------------------------------------------|
| 业务异常        | 业务规则违反，抛 `BusinessException`（平台定义） |
| 系统异常        | NPE、SQLException，抛通用 500              |
| 参数校验        | `@Valid` + `BindingResult`，统一 400        |

**HTTP 状态码**：
- 2xx：成功
- 400：参数校验失败
- 404：资源不存在
- 409：幂等冲突（如重复提交）
- 500：系统错误

---

## 五、契约一致性

- OpenAPI 端点路径 vs 代码 `@RequestMapping` 必须 100% 一致
- Request/Response DTO 必须与 `openapi.yaml` schema 对齐
- 修改 endpoint 必须同步更新 `openapi.yaml`

---

## 六、执行机制

| 阶段           | 检查点                                         |
|---------------|-----------------------------------------------|
| 编码中         | 写注释前对照"禁止列表"自检                     |
| Fitness hook  | `post-tool-linter-feedback.py` 检测违规模式    |
| Sprint review | 违规入 `docs/tech-debt-backlog.md`             |
| 契约漂移       | `contract-drift-check.py --changed`           |

---

## 关联

- 架构检查：`backend/fitness-rules.md`
- 技术债：`docs/tech-debt-backlog.md`
- 契约：`docs/contract-template.md`