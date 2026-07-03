# 命名规范 — naming-conventions

> **定位**:业务字段 / API 路径 / 数据库表的**默认命名约定**。`doc-librarian` 写 contract、`planner` 写 spec 时必读,`arbiter` 据此判定冲突。
>
> **覆盖规则**:接入项目可在 `docs/knowledge/tech/backend/naming-conventions.md` 覆盖本文件;**未覆盖即按本文件执行**。

---

## 1. API 字段命名

### 1.1 通用规则

| 维度 | 规则 | 示例 |
|------|------|------|
| 大小写 | **驼峰**(camelCase) | `userId` / `createdAt` / `wechatOpenId` |
| 禁止缩写 | 除非业界共识,禁止自创缩写 | ✅ `userId` ❌ `uid` `usrId` |
| 布尔 | `is` / `has` / `can` 前缀 | `isActive` `hasPermission` `canEdit` |
| 时间 | 后缀 `At`(时刻) / `Date`(日期) | `createdAt` `expiresAt` `birthDate` |
| ID | 后缀 `Id`(单个) / `Ids`(列表) | `userId` `roleIds` |
| 金额 | 后缀单位 `Cents` / `Yuan` | `amountCents` `priceYuan` |

### 1.2 业界共识缩写白名单

允许的缩写(仅这些):`url` / `uri` / `id` / `ip` / `os` / `db` / `api` / `sdk` / `cdn` / `ui` / `ux` / `qr`。

新缩写需走 ADR,不允许 agent 自行创造。

---

## 2. API 路径命名

### 2.1 通用规则

| 维度 | 规则 | 示例 |
|------|------|------|
| 大小写 | **kebab-case**(短横线) | `/api/v1/user-profiles` |
| 资源名 | **复数** | `/users` 而非 `/user` |
| 版本 | `/api/v{N}/` 前缀 | `/api/v1/` |
| 动作 | RESTful 优先,非 CRUD 用动词后缀 | `POST /users/{id}/lock` |
| 嵌套层级 | 最多 2 层 | `/users/{id}/orders` ✅ `/users/{id}/orders/{oid}/items` ❌ |

### 2.2 标准动词映射

| HTTP | 用途 | 路径示例 |
|------|------|---------|
| GET | 查询单/列表 | `GET /users` / `GET /users/{id}` |
| POST | 创建 | `POST /users` |
| PUT | 全量更新 | `PUT /users/{id}` |
| PATCH | 部分更新 | `PATCH /users/{id}` |
| DELETE | 删除 | `DELETE /users/{id}` |

非 CRUD 动作: `POST /users/{id}/<verb>`(如 `lock` / `unlock` / `reset-password`)。

---

## 3. 数据库命名

### 3.1 通用规则

| 维度 | 规则 | 示例 |
|------|------|------|
| 表名 | **复数 snake_case** | `users` `wechat_login_records` |
| 字段名 | **snake_case** | `user_id` `created_at` `wechat_open_id` |
| 主键 | `id`(BIGINT AUTO_INCREMENT) | `id` |
| 外键 | `<referenced_table_singular>_id` | `user_id` 引用 users.id |
| 时间字段 | `created_at` / `updated_at` / `deleted_at` | 必含前两个 |
| 软删除 | `deleted_at`(NULL = 未删) | 而非 `is_deleted` boolean |
| 布尔字段 | `is_<x>` / `has_<x>` | `is_active` `has_subscription` |

### 3.2 索引命名

| 类型 | 格式 | 示例 |
|------|------|------|
| 主键 | `PRIMARY` | — |
| 唯一 | `uniq_<scope>_<cols>` | `uniq_tenant_email` |
| 普通 | `idx_<cols>` | `idx_user_status` |
| 外键 | `fk_<table>_<ref_table>` | `fk_orders_users` |

---

## 4. 错误码命名

| 维度 | 规则 | 示例 |
|------|------|------|
| 格式 | `<MODULE>_<REASON>` 大写蛇形 | `USER_NOT_FOUND` `WECHAT_LOGIN_EXPIRED` |
| HTTP 映射 | 业务码与 HTTP 状态码分离 | 业务 `USER_NOT_FOUND` ↔ HTTP 404 |

---

## 5. 跨任务一致性(本规范的核心价值)

接 `arbiter` agent 的执行约束:

1. **同一业务概念全栈一致**——API 层 `userId` ↔ DB 层 `user_id`(各自符合自己层规范,但**语义指向同一实体**)
2. **新字段必经 registry 注册**——`doc-librarian` 写完 contract 后必须追加到 `docs/registry/schema.jsonl`,arbiter 据此检测冲突
3. **新 API 必经 registry 注册**——`planner` 写完 spec 后必须追加到 `docs/registry/api.jsonl`
4. **重名同义合并**——发现 `userId` 和 `uid` 指向同一概念时,arbiter 强制改名为 `userId`(本规范)

---

## 6. 项目覆盖

如本项目有特殊约定,在 `docs/knowledge/tech/backend/naming-conventions.md` 创建同名文件覆盖。优先级:

```
tech/backend/naming-conventions.md  >  team/naming-conventions.md
```

覆盖必须**整文件覆盖**(避免片段覆盖导致歧义),并在文件头声明覆盖原因。
