# 异常处理 & 错误码（项目契约）

`@RestControllerAdvice` / `ResponseEntity` / `ExceptionHandler` 的 API 写法 AI 已熟，本文档只列**项目错误码字典 + 团队陷阱**。

## 统一错误响应格式（契约）

```json
{
  "code": "TOKEN_EXPIRED",
  "message": "访问令牌已过期，请刷新令牌",
  "timestamp": "2026-05-15T10:01:16",
  "path": "/afs/estimate/pdf/test-id",
  "traceId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**字段语义**：

| 字段 | 用途 | 谁消费 |
|------|------|--------|
| `code` | 业务错误码（契约） | 前端、QA、客户端 SDK 分支判断 |
| `message` | 人类可读文案 | 用户提示、日志阅读 |
| `timestamp` | ISO-8601 | 与日志对齐 |
| `path` | 请求路径 | 复现路径 |
| `traceId` | 链路追踪 ID | 关联日志 / 链路系统 |

**铁律**：业务断言只依赖 `code`，永远**不要**让前端 / QA `if (error.message === '...')`。文案会改，code 是契约。

## 错误码字典（项目级）

| HTTP | code | 说明 |
|------|------|------|
| 401 | `UNAUTHENTICATED` | 未认证 |
| 401 | `TOKEN_EXPIRED` | Token 过期 |
| 401 | `TOKEN_INVALID` | Token 非法 |
| 403 | `FORBIDDEN` | 无权限 |
| 404 | `RESOURCE_NOT_FOUND` | 资源不存在（可细化如 `PDF_NOT_FOUND` / `USER_NOT_FOUND`） |
| 429 | `RATE_LIMITED` | 限流 |
| 502 | `THIRD_PARTY_ERROR` | 上游业务异常 |
| 503 | `SERVICE_UNAVAILABLE` | 上游不可用（重试耗尽走这个） |
| 500 | `INTERNAL_ERROR` | 兜底，必须告警 |

**业务码 vs HTTP 码**：HTTP 描述传输层，业务码描述业务语义。`USER_NOT_FOUND` 走 404，`ORDER_ALREADY_PAID` 可以走 409。不要把所有错都塞 500。

## 关键陷阱：HttpMessageNotWritableException（必看）

接口 `produces = "application/pdf"`，异常分支返回 JSON 错误体 → Spring 沿用 PDF 的 Content-Type → `LinkedHashMap` 找不到转换器。

**修法**（首选）：`@RestControllerAdvice` 里返回时**显式**设 Content-Type：

```java
return ResponseEntity.status(status)
        .contentType(MediaType.APPLICATION_JSON)   // ← 这一行是红线
        .body(errorResponse);
```

这是 SKILL.md 红线第 2 条的来源——曾经因为这个出过生产事故。

## 业务异常设计原则

每种语义错误一个异常类型，集中处理：

- 抽象基类 `BusinessException` 持有 `code` 字段
- 具体类型（`TokenExpiredException` 等）只承载 message
- 全局 handler 用 `@ExceptionHandler(BusinessException.class)` 从异常拿 code，不要 `instanceof` 一堆类型

## 日志原则（团队约定）

- 业务异常（401 / 404 / 429）：`log.warn`，**不要** `log.error`（不是 bug，别污染告警）
- 5xx（含兜底 Exception）：`log.error` + 堆栈 + traceId
- 4xx 客户端错误：通常不记（量大、噪音）

```java
log.error("PDF 生成失败 orderId={} traceId={}", orderId, MDC.get("traceId"), e);
//                                                                         ^ 堆栈作为最后一个参数（不是 e.getMessage()）
```

## 测试断言模板（异常路径必用）

```java
.andExpect(status().isXxx())
.andExpect(header().string("Content-Type", "application/json"))
.andExpect(jsonPath("$.code").value("XXX"))
.andExpect(jsonPath("$.message").exists())
.andExpect(jsonPath("$.timestamp").exists())
.andExpect(jsonPath("$.path").value("..."));
```

**绝不允许**只断言 status——会让"改文案 / 改错误码"的变更测试不挂，破坏契约。
