---
name: backend-api-conventions
description: 后端 API 响应格式、分页规则、错误码约定。doc-librarian 起草 openapi.yaml 时必须参照，generator 实现 endpoint 时必须遵循。
---

# 后端 API 规范约定

> 补充 `docs/contract-template.md` 的"接口层面"规范。
> 本文件定义 API 的响应格式、分页、错误码等实现约束。

---

## 一、响应格式

### 成功响应

```json
{
  "code": 0,
  "data": { ... },
  "message": "操作成功"
}
```

| 字段   | 类型     | 说明                                  |
|--------|---------|--------------------------------------|
| `code` | int     | 0 = 成功，非 0 = 业务错误              |
| `data` | object  | 业务数据（可能为 null）               |
| `message` | string | 人类可读描述（前端展示给用户）           |

### 错误响应

```json
{
  "code": 40001,
  "message": "用户名已存在",
  "data": null
}
```

`code` 格式：`XYZZZZ`
- X = 业务错误大类（如 4=客户端错误，5=服务端错误）
- Y = 模块号（由 team 自定义）
- ZZZZ = 具体错误序号

---

## 二、分页规范

### 请求参数

| 参数    | 类型    | 默认值 | 说明                        |
|--------|--------|-------|---------------------------|
| `page` | int    | 1     | 页码（从 1 开始）           |
| `pageSize` | int | 20  | 每页条数，最大 100           |

### 响应格式

```json
{
  "code": 0,
  "data": {
    "list": [ ... ],
    "pagination": {
      "page": 1,
      "pageSize": 20,
      "total": 156,
      "totalPages": 8
    }
  },
  "message": "操作成功"
}
```

**禁止**：返回"负载均衡分页"（如 cursor base，只在有大量数据迁移场景才考虑）。

---

## 三、字段命名

- **请求**：`camelCase`（与 Java 保持一致）
- **响应 JSON**：`camelCase`（前端友好）
- **OpenAPI schema**：`camelCase`
- **禁止**：混用 `snake_case`（除非外部 API 强制要求）

---

## 四、日期时间格式

- **统一 ISO-8601**：`yyyy-MM-dd'T'HH:mm:ss.SSSZ`
- 示例：`2026-04-21T10:30:00.000+0800`
- **禁止**：Unix timestamp 透传（前端需转换）

---

## 五、幂等性

| 操作类型      | 幂等策略                            |
|-------------|----------------------------------|
| 创建资源      | 返回 409（若已存在）+ 已有资源 ID      |
| 更新资源      | PUT 全量更新（幂等）                  |
| 删除资源      | 软删除（标记 deleted）或返回 204       |
| 执行动作      | 业务幂等键 + 防重表                   |

---

## 六、TBD

- [ ] TBD: 确认业务错误码的模块号分配规则（哪个模块占哪个号段）
- [ ] TBD: 确认是否有自定义错误码文档（目前只描述了通用结构）

---

## 关联

- 契约模板：`docs/contract-template.md`
- 编码风格：`backend/coding-style.md`