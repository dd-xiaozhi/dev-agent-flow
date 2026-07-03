# Registry — 跨任务注册表

> **定位**:跨 story / 跨任务的"全局事实表",解决并行多任务时字段命名冲突 / API 路径重复 / 重复造轮子问题。
>
> **不是文档**:这里的 jsonl 是机器产物,由 agent 自动追加,由 arbiter / spec-lint 消费。人工不直接编辑。

---

## 文件

| 文件 | 写入方 | 消费方 | 内容 |
|------|-------|-------|------|
| `api.jsonl` | planner | arbiter / spec-lint / 后续 planner | 全局 API 端点注册 |
| `schema.jsonl` | doc-librarian | arbiter / spec-lint / 后续 doc-librarian | 全局数据模型字段注册 |
| `decisions.jsonl` | planner / doc-librarian | arbiter / 后续 agent | 关键设计决策日志 |

**格式**:每行一条 JSON 对象(append-only,不修改历史行)。

---

## Schema 约定

### api.jsonl

```json
{"story_id":"05-27-wechat-login","method":"POST","path":"/api/v1/auth/wechat/login","request_schema":{"code":"string"},"response_schema":{"token":"string","expires_in":"int"},"owner_task":"05-27-wechat-login","status":"active","ts":"2026-05-28T22:00:00+08:00"}
```

**唯一性约束**:`method + path` 在 `status=active` 行中必须唯一。冲突时 arbiter 拒绝合入。

### schema.jsonl

```json
{"story_id":"05-27-wechat-login","entity":"User","field":"userId","type":"BIGINT","semantics":"用户唯一标识","source_task":"05-27-wechat-login","ts":"2026-05-28T22:00:00+08:00"}
```

**唯一性约束**:同一 `entity.field` 在不同 story 中类型必须一致,语义不可矛盾。

### decisions.jsonl

```json
{"task_id":"05-27-wechat-login","decision":"User 表新增 wechat_open_id 字段","rationale":"微信登录需要持久化映射","impact_scope":["User 表","所有读 User 的 service"],"ts":"2026-05-28T22:00:00+08:00"}
```

**用途**:不约束唯一性,仅供后续 agent 检索"其他任务做了什么决定影响我"。

---

## 生命周期

- **append**: doc-librarian 写完 contract.md / planner 写完 spec.md 时自动追加
- **standstill**: 任务进入 `done` 后,对应行的 `status` 由 arbiter 标记为 `frozen`(在 api.jsonl)
- **retire**: 任务被 finalize/废弃时,对应行 `status` 标 `deprecated`,新任务可复用相同 path/field

---

## 反模式

- ❌ 人工编辑历史行——append-only,改用新行 + 标 `status=superseded` 指向新行
- ❌ 跳过 arbiter 直接 commit 冲突——必走 arbiter 验证
- ❌ 在 jsonl 之外另起注册表——单一事实源,所有 agent 必读这 3 个
